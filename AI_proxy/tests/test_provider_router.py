from pathlib import Path

from app.config import Settings
from app.providers.router import ProviderRouter
from app.runtime_config import RuntimeConfigStore
from app.schemas import ChatCompletionRequest, ChatMessage, ModelRecord


class StubOpenAIProvider:
    def complete(self, model, request, provider_config=None):
        from app.schemas import ProviderResponse

        return ProviderResponse(
            model=model,
            content="live-openai",
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=1,
            raw={"id": "cmpl-test", "provider": "openai-live"},
        )

    def list_models(self, provider_config=None):
        provider_type = provider_config.provider_type if provider_config else "openai"
        if provider_type == "kimi":
            return ["kimi-k2.5", "kimi-k2-thinking"]
        return ["gpt-4o-mini", "gpt-4.1"]


class StubOllamaProvider:
    def complete(self, model, request, provider_config=None):
        from app.schemas import ProviderResponse

        return ProviderResponse(
            model=model,
            content="live-ollama",
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=1,
            raw={"model": model, "provider": "ollama-live"},
        )


class StubAnthropicProvider:
    def complete(self, model, request, provider_config=None):
        from app.schemas import ProviderResponse

        return ProviderResponse(
            model=model,
            content="live-anthropic",
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=1,
            raw={"id": "msg-test", "provider": "anthropic-live"},
        )

    def list_models(self, provider_config=None):
        return ["claude-sonnet-4-20250514", "claude-opus-4-20250514"]


def build_runtime_store(tmp_path: Path, **settings_overrides):
    settings = Settings(runtime_config_path=str(tmp_path / "runtime_config.json"), **settings_overrides)
    return settings, RuntimeConfigStore(settings)


def test_provider_router_uses_openai_when_key_present(tmp_path):
    settings, runtime_config = build_runtime_store(tmp_path, openai_api_key="test-key", allow_mock_fallback=False)
    router = ProviderRouter(settings, runtime_config)
    router._openai = StubOpenAIProvider()
    router._anthropic = StubAnthropicProvider()
    router._ollama = StubOllamaProvider()
    response = router.complete(
        "gpt-4o-mini",
        ChatCompletionRequest(messages=[ChatMessage(role="user", content="hello")]),
    )
    assert response.content == "live-openai"


def test_provider_router_uses_ollama_for_ollama_models(tmp_path):
    settings, runtime_config = build_runtime_store(tmp_path, openai_api_key=None, allow_mock_fallback=False)
    router = ProviderRouter(settings, runtime_config)
    router._openai = StubOpenAIProvider()
    router._anthropic = StubAnthropicProvider()
    router._ollama = StubOllamaProvider()
    response = router.complete(
        "qwen3.5:4b",
        ChatCompletionRequest(messages=[ChatMessage(role="user", content="hello")]),
    )
    assert response.content == "live-ollama"


def test_provider_router_excludes_non_live_models_when_mock_disabled(tmp_path):
    settings, runtime_config = build_runtime_store(tmp_path, openai_api_key="test-key", allow_mock_fallback=False)
    router = ProviderRouter(settings, runtime_config)
    executable = router.executable_models(runtime_config.list_models())
    executable_names = {model.model for model in executable}
    assert "claude-3-5-haiku" not in executable_names
    assert "mistral-small" not in executable_names
    assert "gpt-4o-mini" in executable_names
    assert "qwen3.5:4b" in executable_names


def test_provider_router_uses_anthropic_when_key_present(tmp_path):
    settings, runtime_config = build_runtime_store(tmp_path, anthropic_api_key="test-key", allow_mock_fallback=False)
    router = ProviderRouter(settings, runtime_config)
    router._openai = StubOpenAIProvider()
    router._anthropic = StubAnthropicProvider()
    router._ollama = StubOllamaProvider()
    response = router.complete(
        "claude-3-5-haiku",
        ChatCompletionRequest(messages=[ChatMessage(role="user", content="hello")]),
    )
    assert response.content == "live-anthropic"


def test_provider_router_lists_live_models_for_anthropic(tmp_path):
    settings, runtime_config = build_runtime_store(tmp_path, anthropic_api_key="test-key", allow_mock_fallback=False)
    router = ProviderRouter(settings, runtime_config)
    router._anthropic = StubAnthropicProvider()
    assert router.list_models_for_provider("anthropic") == [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
    ]


def test_provider_router_uses_kimi_when_key_present(tmp_path):
    settings, runtime_config = build_runtime_store(tmp_path, kimi_api_key="test-key", kimi_enabled=True, allow_mock_fallback=False)
    runtime_config.upsert_model(
        ModelRecord(
            model="kimi-k2.5",
            provider="kimi",
            mode="premium",
            cost_per_1k_input_tokens=0.0006,
            cost_per_1k_output_tokens=0.003,
            avg_latency_ms=1500,
            quality_score=0.92,
            error_rate=0.01,
            supports_tools=True,
            supports_streaming=True,
            enabled=True,
            tags=["kimi", "live", "image", "tools"],
        )
    )
    router = ProviderRouter(settings, runtime_config)
    router._openai = StubOpenAIProvider()
    router._anthropic = StubAnthropicProvider()
    router._ollama = StubOllamaProvider()
    response = router.complete(
        "kimi-k2.5",
        ChatCompletionRequest(messages=[ChatMessage(role="user", content="hello")]),
    )
    assert response.content == "live-openai"


def test_provider_router_lists_live_models_for_kimi(tmp_path):
    settings, runtime_config = build_runtime_store(tmp_path, kimi_api_key="test-key", kimi_enabled=True, allow_mock_fallback=False)
    router = ProviderRouter(settings, runtime_config)
    router._openai = StubOpenAIProvider()
    assert router.list_models_for_provider("kimi") == ["kimi-k2.5", "kimi-k2-thinking"]


def test_provider_router_lists_kimi_models_when_key_exists_even_if_provider_disabled(tmp_path):
    settings, runtime_config = build_runtime_store(tmp_path, kimi_api_key="test-key", kimi_enabled=False, allow_mock_fallback=False)
    router = ProviderRouter(settings, runtime_config)
    router._openai = StubOpenAIProvider()
    assert router.list_models_for_provider("kimi") == ["kimi-k2.5", "kimi-k2-thinking"]
