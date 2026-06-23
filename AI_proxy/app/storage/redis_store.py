from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.config import Settings
from app.schemas import QuotaDecision


class RedisQuotaStore:
    def __init__(self, settings: Settings):
        try:
            from redis import Redis
        except ImportError as exc:
            raise RuntimeError("redis is required when Redis runtime state is enabled") from exc

        self._client = Redis.from_url(settings.redis_url, decode_responses=True)
        self._prefix = settings.redis_quota_prefix
        self._limit = settings.default_team_daily_cost_limit_usd

    def check_and_increment(self, team_id: str, cost_usd: float) -> QuotaDecision:
        scope_key = self._key(team_id)
        if self._limit is None:
            return QuotaDecision(allowed=True, scope_key=scope_key)

        current = float(self._client.get(scope_key) or 0.0)
        projected = current + cost_usd
        if projected > self._limit:
            ttl = self._seconds_until_utc_midnight()
            return QuotaDecision(
                allowed=False,
                scope_key=scope_key,
                limit_usd=self._limit,
                current_usage_usd=round(current, 6),
                retry_after_seconds=ttl,
                reason="daily team cost quota exceeded",
            )

        pipeline = self._client.pipeline()
        pipeline.incrbyfloat(scope_key, cost_usd)
        pipeline.expire(scope_key, self._seconds_until_utc_midnight())
        pipeline.execute()
        return QuotaDecision(
            allowed=True,
            scope_key=scope_key,
            limit_usd=self._limit,
            current_usage_usd=round(projected, 6),
        )

    def _key(self, team_id: str) -> str:
        return f"{self._prefix}:{team_id}:{date.today().isoformat()}"

    def _seconds_until_utc_midnight(self) -> int:
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).date()
        midnight = datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc)
        return max(1, int((midnight - now).total_seconds()))


class RedisCircuitBreakerStore:
    def __init__(self, settings: Settings):
        try:
            from redis import Redis
        except ImportError as exc:
            raise RuntimeError("redis is required when Redis runtime state is enabled") from exc

        self._client = Redis.from_url(settings.redis_url, decode_responses=True)
        self._prefix = settings.redis_circuit_prefix
        self._failure_threshold = settings.redis_circuit_failure_threshold
        self._open_seconds = settings.redis_circuit_open_seconds

    def is_open(self, model: str) -> bool:
        return bool(self._client.exists(self._open_key(model)))

    def record_success(self, model: str) -> None:
        pipeline = self._client.pipeline()
        pipeline.delete(self._failures_key(model))
        pipeline.delete(self._open_key(model))
        pipeline.execute()

    def record_failure(self, model: str) -> None:
        failures = self._client.incr(self._failures_key(model))
        self._client.expire(self._failures_key(model), self._open_seconds)
        if failures >= self._failure_threshold:
            self._client.set(self._open_key(model), "1", ex=self._open_seconds)

    def _failures_key(self, model: str) -> str:
        return f"{self._prefix}:{model}:failures"

    def _open_key(self, model: str) -> str:
        return f"{self._prefix}:{model}:open"
