from __future__ import annotations

from fastapi import HTTPException, status

from app.config import Settings
from app.providers.anthropic import AnthropicProvider
from app.providers.azure import AzureOpenAIProvider
from app.providers.mock import MockProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider
from app.runtime_config import RuntimeConfigStore
from app.secrets import resolve_provider_api_key
from app.schemas import ChatCompletionRequest, ModelRecord, ProviderConfig, ProviderResponse

_OPENAI_COMPATIBLE = {"openai", "kimi", "groq", "mistral", "gemini"}


class ProviderRouter:
    def __init__(self, settings: Settings, runtime_config: RuntimeConfigStore):
        self._settings = settings
        self._runtime_config = runtime_config
        self._mock = MockProvider()
        self._openai = OpenAIProvider(settings)
        self._anthropic = AnthropicProvider(settings)
        self._ollama = OllamaProvider(settings)
        self._azure = AzureOpenAIProvider(settings)

    def complete(self, model: str, request: ChatCompletionRequest) -> ProviderResponse:
        model_record = self._get_model(model)
        if not model_record:
            return self._mock_or_raise(model, request, "unknown model")

        provider_config = self._get_provider(model_record.provider)
        if not provider_config or not provider_config.enabled:
            return self._mock_or_raise(model, request, f"provider {model_record.provider} is disabled")

        if provider_config.provider_type in _OPENAI_COMPATIBLE and self.supports_model(model):
            return self._openai.complete(model, request, provider_config=provider_config)
        if provider_config.provider_type == "azure_openai" and self.supports_model(model):
            return self._azure.complete(model, request, provider_config=provider_config)
        if provider_config.provider_type == "anthropic" and self.supports_model(model):
            return self._anthropic.complete(model, request, provider_config=provider_config)
        if provider_config.provider_type == "ollama" and self.supports_model(model):
            return self._ollama.complete(model, request, provider_config=provider_config)

        return self._mock_or_raise(model, request, f"provider {provider_config.provider_type} is not live-configured")

    def supports_model(self, model: str) -> bool:
        model_record = self._get_model(model)
        if not model_record or not model_record.enabled:
            return self._settings.allow_mock_fallback

        provider_config = self._get_provider(model_record.provider)
        if not provider_config or not provider_config.enabled:
            return self._settings.allow_mock_fallback

        if provider_config.provider_type in _OPENAI_COMPATIBLE:
            return bool(resolve_provider_api_key(provider_config.provider_type, provider_config.api_key, self._settings))
        if provider_config.provider_type == "azure_openai":
            return bool(
                resolve_provider_api_key("azure_openai", provider_config.api_key, self._settings)
                and (provider_config.base_url or self._settings.azure_openai_base_url)
            )
        if provider_config.provider_type == "anthropic":
            return bool(resolve_provider_api_key("anthropic", provider_config.api_key, self._settings))
        if provider_config.provider_type == "ollama":
            return bool(provider_config.base_url)
        return self._settings.allow_mock_fallback

    def list_models_for_provider(self, provider_id: str) -> list[str]:
        provider_config = self._get_provider(provider_id)
        if not provider_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider {provider_id} is not configured",
            )

        if provider_config.provider_type in {*_OPENAI_COMPATIBLE, "anthropic"}:
            if not resolve_provider_api_key(provider_config.provider_type, provider_config.api_key, self._settings):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Provider {provider_id} has no API key configured",
                )
        elif provider_config.provider_type == "ollama" and not provider_config.base_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Provider {provider_id} has no base URL configured",
            )

        if provider_config.provider_type in _OPENAI_COMPATIBLE:
            return self._openai.list_models(provider_config=provider_config)
        if provider_config.provider_type == "anthropic":
            return self._anthropic.list_models(provider_config=provider_config)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider {provider_id} does not support model catalog sync",
        )

    def executable_models(self, models: list[ModelRecord]) -> list[ModelRecord]:
        executable = [model for model in models if model.enabled and self.supports_model(model.model)]
        if executable:
            return executable
        if self._settings.allow_mock_fallback:
            return [model for model in models if model.enabled]
        return []

    def _get_model(self, model_name: str) -> ModelRecord | None:
        return next((model for model in self._runtime_config.list_models() if model.model == model_name), None)

    def _get_provider(self, provider_id: str) -> ProviderConfig | None:
        return self._runtime_config.get_provider(provider_id)

    def _mock_or_raise(self, model: str, request: ChatCompletionRequest, reason: str) -> ProviderResponse:
        if self._settings.allow_mock_fallback:
            return self._mock.complete(model, request)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Model {model} is not executable: {reason}",
        )
