from __future__ import annotations

import json
from datetime import datetime, timezone

from app.config import Settings
from app.schemas import RuntimeConfig


class ClickHouseRuntimeConfigBackend:
    def __init__(self, settings: Settings):
        try:
            import clickhouse_connect
        except ImportError as exc:
            raise RuntimeError(
                "clickhouse-connect is required when ClickHouse runtime config is enabled"
            ) from exc

        self._table = settings.clickhouse_runtime_config_table
        self._config_key = settings.clickhouse_runtime_config_key
        self._client = clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_username,
            password=settings.clickhouse_password,
            database=settings.clickhouse_database,
            secure=settings.clickhouse_secure,
        )
        self._ensure_schema()

    def exists(self) -> bool:
        result = self._client.query(
            f"SELECT count() FROM {self._table} WHERE config_key = %(config_key)s",
            parameters={"config_key": self._config_key},
        )
        return bool(result.result_rows and result.result_rows[0][0] > 0)

    def read(self) -> RuntimeConfig:
        result = self._client.query(
            f"""
            SELECT payload
            FROM {self._table}
            WHERE config_key = %(config_key)s
            ORDER BY version DESC
            LIMIT 1
            """,
            parameters={"config_key": self._config_key},
        )
        if not result.result_rows:
            raise FileNotFoundError("No runtime config exists in ClickHouse")
        payload = json.loads(result.result_rows[0][0])
        return RuntimeConfig.model_validate(payload)

    def write(self, config: RuntimeConfig) -> None:
        payload = json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True)
        version = int(datetime.now(timezone.utc).timestamp() * 1_000_000)
        updated_at = datetime.now(timezone.utc)
        self._client.insert(
            self._table,
            [[self._config_key, version, updated_at, payload]],
            column_names=["config_key", "version", "updated_at", "payload"],
        )

    def _ensure_schema(self) -> None:
        self._client.command(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table} (
                config_key LowCardinality(String),
                version UInt64,
                updated_at DateTime64(3),
                payload String
            )
            ENGINE = MergeTree
            ORDER BY (config_key, version)
            """
        )
