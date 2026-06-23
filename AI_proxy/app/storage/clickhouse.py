from __future__ import annotations

from datetime import datetime, timezone

from app.config import Settings
from app.schemas import RequestLog


class ClickHouseRequestLogStore:
    def __init__(self, settings: Settings):
        try:
            import clickhouse_connect
        except ImportError as exc:
            raise RuntimeError(
                "clickhouse-connect is required when ClickHouse logging is enabled"
            ) from exc

        self._table = settings.clickhouse_request_log_table
        self._client = clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_username,
            password=settings.clickhouse_password,
            database=settings.clickhouse_database,
            secure=settings.clickhouse_secure,
        )
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._client.command(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table} (
                request_id String,
                created_at DateTime,
                org_id String,
                team_id String,
                user_id String,
                service String,
                task_type String,
                prompt_tokens UInt32,
                completion_tokens UInt32,
                model_used String,
                latency_ms UInt32,
                cost_usd Float64,
                status LowCardinality(String),
                policy_id Nullable(String),
                route_reason Nullable(String),
                attempted_models Array(String),
                tags Array(String)
            )
            ENGINE = MergeTree
            ORDER BY (team_id, created_at, request_id)
            """
        )
        try:
            self._client.command(
                f"ALTER TABLE {self._table} ADD COLUMN IF NOT EXISTS tags Array(String) DEFAULT []"
            )
        except Exception:
            pass

    def append(self, log: RequestLog) -> None:
        created_at = self._normalize_datetime(log.created_at)
        self._client.insert(
            self._table,
            [[
                log.request_id,
                created_at,
                log.org_id,
                log.team_id,
                log.user_id,
                log.service,
                log.task_type,
                log.prompt_tokens,
                log.completion_tokens,
                log.model_used,
                log.latency_ms,
                log.cost_usd,
                log.status,
                log.policy_id,
                log.route_reason,
                log.attempted_models,
                log.tags,
            ]],
            column_names=[
                "request_id",
                "created_at",
                "org_id",
                "team_id",
                "user_id",
                "service",
                "task_type",
                "prompt_tokens",
                "completion_tokens",
                "model_used",
                "latency_ms",
                "cost_usd",
                "status",
                "policy_id",
                "route_reason",
                "attempted_models",
                "tags",
            ],
        )

    def recent(self, limit: int = 100, tag: str | None = None) -> list[RequestLog]:
        where = "WHERE has(tags, %(tag)s)" if tag else ""
        params: dict = {"limit": limit}
        if tag:
            params["tag"] = tag
        result = self._client.query(
            f"""
            SELECT request_id, created_at, org_id, team_id, user_id, service, task_type,
                   prompt_tokens, completion_tokens, model_used, latency_ms, cost_usd,
                   status, policy_id, route_reason, attempted_models, tags
            FROM {self._table}
            {where}
            ORDER BY created_at DESC
            LIMIT %(limit)s
            """,
            parameters=params,
        )
        logs: list[RequestLog] = []
        for row in result.result_rows:
            logs.append(
                RequestLog(
                    request_id=row[0],
                    created_at=str(row[1]),
                    org_id=row[2],
                    team_id=row[3],
                    user_id=row[4],
                    service=row[5],
                    task_type=row[6],
                    prompt_tokens=row[7],
                    completion_tokens=row[8],
                    model_used=row[9],
                    latency_ms=row[10],
                    cost_usd=row[11],
                    status=row[12],
                    policy_id=row[13],
                    route_reason=row[14],
                    attempted_models=row[15] or [],
                    tags=list(row[16]) if row[16] else [],
                )
            )
        return logs

    def _normalize_datetime(self, value: str | datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value)
