from fastapi import HTTPException

from app.config import Settings
from app.control_plane import ControlPlane
from app.observability import ObservabilityService
from app.prompt_intel import PromptIntelligence
from app.providers.router import ProviderRouter
from app.reliability import ReliabilityLayer
from app.routing import IntelligentRouter
from app.runtime_config import RuntimeConfigStore
from app.schemas import (
    ChatCompletionRequest,
    ChatMessage,
    ChatToolCall,
    ChatToolDefinition,
    ChatToolDefinitionFunction,
    ChatToolFunction,
    Policy,
    PolicyRuleSet,
)
from app.storage.memory import InMemoryQuotaStore, InMemoryRequestLogStore


class DummyProvider:
    def complete(self, model: str, request: ChatCompletionRequest):
        from app.schemas import ProviderResponse

        return ProviderResponse(
            model=model,
            content="ok",
            prompt_tokens=10,
            completion_tokens=5,
            latency_ms=10,
            raw={"provider": "mock"},
        )


class ToolCallingDummyProvider:
    def complete(self, model: str, request: ChatCompletionRequest):
        from app.schemas import ProviderResponse

        return ProviderResponse(
            model=model,
            content=None,
            prompt_tokens=20,
            completion_tokens=8,
            latency_ms=12,
            finish_reason="tool_calls",
            tool_calls=[
                ChatToolCall(
                    id="call_123",
                    function=ChatToolFunction(name="lookup_weather", arguments='{"city":"Santiago"}'),
                )
            ],
            raw={"provider": "mock"},
        )


def build_control_plane_for_test(tmp_path, settings: Settings, provider=None) -> tuple[ControlPlane, RuntimeConfigStore]:
    runtime_settings = settings.model_copy(update={"runtime_config_path": str(tmp_path / 'runtime.json')})
    runtime_config = RuntimeConfigStore(runtime_settings)
    control_plane = ControlPlane(
        settings=runtime_settings,
        prompt_intelligence=PromptIntelligence(),
        router=IntelligentRouter(),
        reliability_layer=ReliabilityLayer(provider or DummyProvider()),
        observability=ObservabilityService(InMemoryRequestLogStore()),
        quota_store=InMemoryQuotaStore(default_team_daily_cost_limit_usd=settings.default_team_daily_cost_limit_usd),
        provider_router=ProviderRouter(runtime_settings, runtime_config),
        runtime_config=runtime_config,
    )
    return control_plane, runtime_config


def test_control_plane_errors_when_policy_removes_all_models(tmp_path):
    settings = Settings(allow_mock_fallback=False, runtime_config_path=str(tmp_path / 'runtime.json'))
    control_plane, runtime_config = build_control_plane_for_test(tmp_path, settings)
    runtime_config.upsert_policy(
        Policy(
            policy_id="empty-team",
            scope="team",
            scope_id="blocked-team",
            rules=PolicyRuleSet(allowed_models=["non-existent-model"]),
        )
    )
    request = ChatCompletionRequest(
        messages=[ChatMessage(role="user", content="hello")],
        metadata={"team_id": "blocked-team"},
    )

    try:
        control_plane.handle_chat_completion(request)
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "No live models available" in exc.detail
    else:
        raise AssertionError("Expected control plane to reject empty model set")


def test_control_plane_rejects_quota_exceeded(tmp_path):
    settings = Settings(
        default_team_daily_cost_limit_usd=0.00001,
        allow_mock_fallback=True,
        openai_api_key="test-key",
        runtime_config_path=str(tmp_path / 'runtime.json'),
    )
    control_plane, _ = build_control_plane_for_test(tmp_path, settings)
    request = ChatCompletionRequest(
        model="gpt-4.1",
        messages=[ChatMessage(role="user", content="hello world")],
    )

    try:
        control_plane.handle_chat_completion(request)
    except HTTPException as exc:
        assert exc.status_code == 429
        assert "quota exceeded" in exc.detail or "daily team cost quota exceeded" in exc.detail
    else:
        raise AssertionError("Expected quota enforcement to fail")


def test_control_plane_prices_versioned_openai_model_names(tmp_path):
    settings = Settings(allow_mock_fallback=False, runtime_config_path=str(tmp_path / 'runtime.json'))
    control_plane, _ = build_control_plane_for_test(tmp_path, settings)

    cost = control_plane._calculate_actual_cost(
        model_name="gpt-4o-mini-2024-07-18",
        prompt_tokens=1000,
        completion_tokens=1000,
    )

    expected = next(model for model in control_plane.model_registry if model.model == "gpt-4o-mini")
    assert cost == expected.cost_per_1k_input_tokens + expected.cost_per_1k_output_tokens


def test_control_plane_uses_virtual_alias_for_smart_routing(tmp_path):
    settings = Settings(openai_api_key="test-key", allow_mock_fallback=True, runtime_config_path=str(tmp_path / 'runtime.json'))
    control_plane, _ = build_control_plane_for_test(tmp_path, settings)
    response = control_plane.handle_chat_completion(
        ChatCompletionRequest(
            model="openai:auto",
            messages=[ChatMessage(role="user", content="Reply with exactly: hi")],
            tools=[
                ChatToolDefinition(
                    function=ChatToolDefinitionFunction(
                        name="noop",
                        parameters={"type": "object", "properties": {}},
                    )
                )
            ],
        )
    )
    assert response.model == "gpt-4o-mini"
    assert response.control_plane["resolved_alias"] == "openai:auto"


def test_control_plane_returns_tool_calls_in_chat_shape(tmp_path):
    settings = Settings(allow_mock_fallback=True, runtime_config_path=str(tmp_path / 'runtime.json'))
    control_plane, _ = build_control_plane_for_test(tmp_path, settings, provider=ToolCallingDummyProvider())
    response = control_plane.handle_chat_completion(
        ChatCompletionRequest(
            model="tools:auto",
            messages=[ChatMessage(role="user", content="check the weather")],
            tools=[
                ChatToolDefinition(
                    function=ChatToolDefinitionFunction(
                        name="lookup_weather",
                        parameters={"type": "object", "properties": {"city": {"type": "string"}}},
                    )
                )
            ],
        )
    )
    assert response.choices[0].finish_reason == "tool_calls"
    assert response.choices[0].message.tool_calls[0].function.name == "lookup_weather"
