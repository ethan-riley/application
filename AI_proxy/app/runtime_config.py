from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from app.config import Settings
from app.registry import build_default_runtime_config
from app.secrets import resolve_provider_api_key
from app.schemas import (
    ApiClientRecord,
    ApiClientResponse,
    ModelRecord,
    Policy,
    ProviderConfig,
    ProviderConfigResponse,
    RuntimeConfig,
)
from app.storage.clickhouse_runtime_config import ClickHouseRuntimeConfigBackend


class FileRuntimeConfigBackend:
    def __init__(self, path: Path):
        self._path = path

    def exists(self) -> bool:
        return self._path.exists()

    def read(self) -> RuntimeConfig:
        payload = json.loads(self._path.read_text())
        return RuntimeConfig.model_validate(payload)

    def write(self, config: RuntimeConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True))


class RuntimeConfigStore:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._path = Path(settings.runtime_config_path)
        self._lock = Lock()
        self._backend = self._select_backend()
        self._ensure_exists()

    def get_config(self) -> RuntimeConfig:
        with self._lock:
            return self._read()

    def list_models(self) -> list[ModelRecord]:
        return self.get_config().models

    def list_policies(self) -> list[Policy]:
        return self.get_config().policies

    def list_providers(self) -> list[ProviderConfig]:
        return self.get_config().providers

    def list_api_clients(self) -> list[ApiClientRecord]:
        return self.get_config().api_clients

    def list_api_client_responses(self) -> list[ApiClientResponse]:
        return [self._mask_api_client(client) for client in self.list_api_clients()]

    def get_api_client(self, key_id: str) -> ApiClientRecord | None:
        return next((client for client in self.list_api_clients() if client.key_id == key_id), None)

    def list_provider_responses(self) -> list[ProviderConfigResponse]:
        return [self._mask_provider(provider) for provider in self.list_providers()]

    def get_provider(self, provider_id: str) -> ProviderConfig | None:
        return next((provider for provider in self.list_providers() if provider.provider_id == provider_id), None)

    def upsert_provider(self, provider: ProviderConfig) -> ProviderConfig:
        with self._lock:
            config = self._read()
            providers = [item for item in config.providers if item.provider_id != provider.provider_id]
            providers.append(provider)
            config.providers = sorted(providers, key=lambda item: item.provider_id)
            self._write(config)
            return provider

    def upsert_model(self, model: ModelRecord) -> ModelRecord:
        with self._lock:
            config = self._read()
            models = [item for item in config.models if item.model != model.model]
            models.append(model)
            config.models = sorted(models, key=lambda item: item.model)
            self._write(config)
            return model

    def upsert_models(self, models_to_save: list[ModelRecord]) -> list[ModelRecord]:
        with self._lock:
            config = self._read()
            merged = {item.model: item for item in config.models}
            for model in models_to_save:
                merged[model.model] = model
            config.models = sorted(merged.values(), key=lambda item: item.model)
            self._write(config)
            return models_to_save

    def upsert_policy(self, policy: Policy) -> Policy:
        with self._lock:
            config = self._read()
            policies = [item for item in config.policies if item.policy_id != policy.policy_id]
            policies.append(policy)
            config.policies = sorted(policies, key=lambda item: item.policy_id)
            self._write(config)
            return policy

    def upsert_api_client(self, client: ApiClientRecord) -> ApiClientRecord:
        with self._lock:
            config = self._read()
            clients = [item for item in config.api_clients if item.key_id != client.key_id]
            clients.append(client)
            config.api_clients = sorted(clients, key=lambda item: item.name)
            self._write(config)
            return client

    def delete_api_client(self, key_id: str) -> bool:
        with self._lock:
            config = self._read()
            before = len(config.api_clients)
            config.api_clients = [item for item in config.api_clients if item.key_id != key_id]
            self._write(config)
            return len(config.api_clients) != before

    def bulk_toggle_models(self, model_names: list[str], enabled: bool) -> list[ModelRecord]:
        with self._lock:
            config = self._read()
            updated: list[ModelRecord] = []
            rewritten: list[ModelRecord] = []
            model_set = set(model_names)
            for model in config.models:
                if model.model in model_set:
                    model = model.model_copy(update={"enabled": enabled})
                    updated.append(model)
                rewritten.append(model)
            config.models = sorted(rewritten, key=lambda item: item.model)
            self._write(config)
            return updated

    def _ensure_exists(self) -> None:
        if self._backend.exists():
            self._ensure_defaults_present()
            return
        self._write(build_default_runtime_config(self._settings))

    def _ensure_defaults_present(self) -> None:
        config = self._read()
        defaults = build_default_runtime_config(self._settings)
        provider_ids = {provider.provider_id for provider in config.providers}
        missing_providers = [provider for provider in defaults.providers if provider.provider_id not in provider_ids]
        changed = False
        if missing_providers:
            config.providers = sorted([*config.providers, *missing_providers], key=lambda item: item.provider_id)
            changed = True

        reconciled_providers: list[ProviderConfig] = []
        for provider in config.providers:
            resolved_key = resolve_provider_api_key(provider.provider_type, provider.api_key, self._settings)
            if resolved_key and not provider.enabled and provider.provider_type in {"openai", "anthropic", "kimi"}:
                provider = provider.model_copy(update={"enabled": True})
                changed = True
            reconciled_providers.append(provider)

        if changed:
            config.providers = sorted(reconciled_providers, key=lambda item: item.provider_id)
            self._write(config)

    def _read(self) -> RuntimeConfig:
        return self._backend.read()

    def _write(self, config: RuntimeConfig) -> None:
        self._backend.write(config)

    def _select_backend(self):
        backend = self._settings.runtime_config_backend.lower()
        if backend not in {"auto", "file", "clickhouse"}:
            raise ValueError(f"Unsupported runtime config backend: {self._settings.runtime_config_backend}")
        if backend in {"auto", "clickhouse"} and self._settings.clickhouse_enabled:
            try:
                return ClickHouseRuntimeConfigBackend(self._settings)
            except Exception:
                if backend == "clickhouse":
                    raise
        return FileRuntimeConfigBackend(self._path)

    def _mask_provider(self, provider: ProviderConfig) -> ProviderConfigResponse:
        resolved_key = resolve_provider_api_key(provider.provider_type, provider.api_key, self._settings)
        return ProviderConfigResponse(
            provider_id=provider.provider_id,
            provider_type=provider.provider_type,
            enabled=provider.enabled,
            base_url=provider.base_url,
            organization=provider.organization,
            project=provider.project,
            timeout_seconds=provider.timeout_seconds,
            labels=provider.labels,
            api_key_configured=bool(resolved_key),
        )

    def _mask_api_client(self, client: ApiClientRecord) -> ApiClientResponse:
        return ApiClientResponse(
            key_id=client.key_id,
            name=client.name,
            enabled=client.enabled,
            key_prefix=client.key_prefix,
            created_at=client.created_at,
            last_used_at=client.last_used_at,
            labels=client.labels,
        )
