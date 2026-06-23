from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import date

from app.schemas import QuotaDecision, RequestLog


class InMemoryRequestLogStore:
    def __init__(self, max_entries: int = 500):
        self._logs: deque[RequestLog] = deque(maxlen=max_entries)

    def append(self, log: RequestLog) -> None:
        self._logs.appendleft(log)

    def recent(self, limit: int = 100, tag: str | None = None) -> list[RequestLog]:
        logs = list(self._logs)
        if tag:
            logs = [l for l in logs if tag in l.tags]
        return logs[:limit]


class InMemoryQuotaStore:
    def __init__(self, default_team_daily_cost_limit_usd: float | None = None):
        self._limit = default_team_daily_cost_limit_usd
        self._usage: dict[str, tuple[str, float]] = {}

    def check_and_increment(self, team_id: str, cost_usd: float) -> QuotaDecision:
        scope_key = f"team:{team_id}:day:{date.today().isoformat()}"
        if self._limit is None:
            return QuotaDecision(allowed=True, scope_key=scope_key, limit_usd=None, current_usage_usd=None)

        bucket_day, current = self._usage.get(team_id, (date.today().isoformat(), 0.0))
        today = date.today().isoformat()
        if bucket_day != today:
            current = 0.0

        projected = current + cost_usd
        if projected > self._limit:
            return QuotaDecision(
                allowed=False,
                scope_key=scope_key,
                limit_usd=self._limit,
                current_usage_usd=round(current, 6),
                retry_after_seconds=86400,
                reason="daily team cost quota exceeded",
            )

        self._usage[team_id] = (today, projected)
        return QuotaDecision(
            allowed=True,
            scope_key=scope_key,
            limit_usd=self._limit,
            current_usage_usd=round(projected, 6),
        )


@dataclass
class _BreakerState:
    failures: int = 0
    open: bool = False


class InMemoryCircuitBreakerStore:
    def __init__(self, failure_threshold: int = 3):
        self._failure_threshold = failure_threshold
        self._state: dict[str, _BreakerState] = {}

    def is_open(self, model: str) -> bool:
        return self._state.get(model, _BreakerState()).open

    def record_success(self, model: str) -> None:
        self._state[model] = _BreakerState(failures=0, open=False)

    def record_failure(self, model: str) -> None:
        state = self._state.setdefault(model, _BreakerState())
        state.failures += 1
        if state.failures >= self._failure_threshold:
            state.open = True
