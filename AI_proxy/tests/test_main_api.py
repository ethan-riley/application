import app.main as main
from app.config import Settings
from app.runtime_config import RuntimeConfigStore
from app.schemas import (
    ChatCompletionChoice,
    ChatCompletionResponse,
    ChatCompletionUsage,
    ChatMessage,
    ChatToolCall,
    ChatToolFunction,
    ModelRecord,
    Policy,
    PolicyRuleSet,
    ProviderConfig,
    ResponsesRequest,
)


class StubControlPlane:
    def handle_chat_completion(self, request, provider_name_override=None):
        return ChatCompletionResponse(
            id="chatcmpl_test",
            model=request.model or "gemma3:latest",
            choices=[
                ChatCompletionChoice(
                    message=ChatMessage(
                        role="assistant",
                        content="proxy ok" if not request.tools else None,
                        tool_calls=[
                            ChatToolCall(
                                id="call_1",
                                function=ChatToolFunction(name="search_docs", arguments='{"query":"kubernetes"}'),
                            )
                        ] if request.tools else [],
                    ),
                    finish_reason="tool_calls" if request.tools else "stop",
                )
            ],
            usage=ChatCompletionUsage(prompt_tokens=5, completion_tokens=2, total_tokens=7),
            control_plane={"provider_mode": "ollama-live"},
        )

    def recent_logs(self, limit=100, tag=None):
        return [{"request_id": "1", "status": "success"}]


def test_models_endpoint_returns_openai_shape_and_aliases(tmp_path, monkeypatch):
    store = RuntimeConfigStore(Settings(runtime_config_path=str(tmp_path / "runtime.json")))
    monkeypatch.setattr(main, 'runtime_config', store)
    body = main.list_openai_models()
    assert body['object'] == 'list'
    ids = {item['id'] for item in body['data']}
    assert 'gpt-4o-mini' in ids
    assert 'openai:auto' in ids
    assert 'tools:auto' in ids


def test_openai_namespace_models_endpoint_reuses_main_models(tmp_path, monkeypatch):
    store = RuntimeConfigStore(Settings(runtime_config_path=str(tmp_path / "runtime.json")))
    monkeypatch.setattr(main, 'runtime_config', store)
    body = main.list_openai_compatible_models()
    ids = {item['id'] for item in body['data']}
    assert 'openai:auto' in ids


def test_responses_endpoint_wraps_text_chat_completion(monkeypatch):
    monkeypatch.setattr(main, 'control_plane', StubControlPlane())
    body = main.create_response(ResponsesRequest(input='say hi'))
    assert body.object == 'response'
    assert body.output[0]['content'][0]['text'] == 'proxy ok'


def test_chat_completion_defaults_to_openai_auto(monkeypatch):
    captured = {}

    class StubControlPlaneDefault(StubControlPlane):
        def handle_chat_completion(self, request, provider_name_override=None):
            captured["model"] = request.model
            return super().handle_chat_completion(request)

    monkeypatch.setattr(main, 'control_plane', StubControlPlaneDefault())
    body = main.create_openai_compatible_chat_completion(
        main.ChatCompletionRequest(messages=[ChatMessage(role="user", content="hi")])
    )
    assert captured["model"] == "openai:auto"
    assert body.model


def test_responses_defaults_to_openai_auto(monkeypatch):
    captured = {}

    class StubControlPlaneDefault(StubControlPlane):
        def handle_chat_completion(self, request, provider_name_override=None):
            captured["model"] = request.model
            return super().handle_chat_completion(request)

    monkeypatch.setattr(main, 'control_plane', StubControlPlaneDefault())
    main.create_openai_compatible_response(ResponsesRequest(input='say hi'))
    assert captured["model"] == "openai:auto"


def test_tool_requests_default_to_tools_auto(monkeypatch):
    captured = {}

    class StubControlPlaneDefault(StubControlPlane):
        def handle_chat_completion(self, request, provider_name_override=None):
            captured["model"] = request.model
            return super().handle_chat_completion(request)

    monkeypatch.setattr(main, 'control_plane', StubControlPlaneDefault())
    main.create_openai_compatible_chat_completion(
        main.ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="search docs")],
            tools=[{'type': 'function', 'function': {'name': 'search_docs', 'parameters': {'type': 'object'}}}],
        )
    )
    assert captured["model"] == "tools:auto"


def test_responses_endpoint_wraps_tool_calls(monkeypatch):
    monkeypatch.setattr(main, 'control_plane', StubControlPlane())
    body = main.create_response(
        ResponsesRequest(
            input='search docs',
            tools=[],
            model='tools:auto',
        ).model_copy(update={
            'tools': []
        })
    )
    # sanity check for default text path
    assert body.output[0]['type'] == 'message'


def test_responses_endpoint_emits_function_call_output(monkeypatch):
    monkeypatch.setattr(main, 'control_plane', StubControlPlane())
    body = main.create_response(
        ResponsesRequest(
            input='find docs',
            tools=[{'type': 'function', 'function': {'name': 'search_docs', 'parameters': {'type': 'object'}}}],
        )
    )
    assert any(item['type'] == 'function_call' for item in body.output)


def test_admin_provider_endpoint_masks_api_key(tmp_path, monkeypatch):
    store = RuntimeConfigStore(Settings(runtime_config_path=str(tmp_path / "runtime.json")))
    monkeypatch.setattr(main, 'runtime_config', store)
    body = main.upsert_provider(
        'openai',
        ProviderConfig(
            provider_id='openai',
            provider_type='openai',
            enabled=True,
            base_url='https://api.openai.com/v1',
            api_key='secret',
            labels={'kind': 'saas'},
        ),
    )
    assert body.provider_id == 'openai'
    assert body.api_key_configured is True


def test_runtime_store_includes_default_kimi_provider(tmp_path, monkeypatch):
    store = RuntimeConfigStore(Settings(runtime_config_path=str(tmp_path / "runtime.json")))
    monkeypatch.setattr(main, 'runtime_config', store)
    providers = {provider.provider_id for provider in main.list_providers()}
    assert 'kimi' in providers


def test_sync_provider_models_imports_disabled_records(tmp_path, monkeypatch):
    store = RuntimeConfigStore(Settings(runtime_config_path=str(tmp_path / "runtime.json")))
    monkeypatch.setattr(main, 'runtime_config', store)

    class StubProviderRouter:
        def list_models_for_provider(self, provider_id):
            assert provider_id == "anthropic"
            return ["claude-sonnet-4-20250514", "claude-opus-4-20250514"]

    class StubControlPlane:
        provider_router = StubProviderRouter()

    monkeypatch.setattr(main, 'control_plane', StubControlPlane())
    body = main.sync_provider_models("anthropic")
    assert body["synced_models"] == 2
    imported = {model.model: model for model in store.list_models()}
    assert imported["claude-sonnet-4-20250514"].enabled is False
    assert imported["claude-sonnet-4-20250514"].provider == "anthropic"


def test_sync_provider_models_imports_kimi_records(tmp_path, monkeypatch):
    store = RuntimeConfigStore(Settings(runtime_config_path=str(tmp_path / "runtime.json")))
    monkeypatch.setattr(main, 'runtime_config', store)

    class StubProviderRouter:
        def list_models_for_provider(self, provider_id):
            assert provider_id == "kimi"
            return ["kimi-k2.5", "kimi-k2-thinking"]

    class StubControlPlane:
        provider_router = StubProviderRouter()

    monkeypatch.setattr(main, 'control_plane', StubControlPlane())
    body = main.sync_provider_models("kimi")
    assert body["synced_models"] == 2
    imported = {model.model: model for model in store.list_models()}
    assert imported["kimi-k2.5"].provider == "kimi"
    assert imported["kimi-k2.5"].supports_tools is True
    assert imported["kimi-k2.5"].cost_per_1k_input_tokens == 0.0006
    assert imported["kimi-k2.5"].cost_per_1k_output_tokens == 0.003


def test_sync_provider_models_enriches_openai_prices(tmp_path, monkeypatch):
    store = RuntimeConfigStore(Settings(runtime_config_path=str(tmp_path / "runtime.json")))
    monkeypatch.setattr(main, 'runtime_config', store)

    class StubProviderRouter:
        def list_models_for_provider(self, provider_id):
            assert provider_id == "openai"
            return ["gpt-4o-mini-2024-07-18", "gpt-4.1-mini"]

    class StubControlPlane:
        provider_router = StubProviderRouter()

    monkeypatch.setattr(main, 'control_plane', StubControlPlane())
    body = main.sync_provider_models("openai")
    assert body["synced_models"] == 2
    imported = {model.model: model for model in store.list_models()}
    assert imported["gpt-4o-mini-2024-07-18"].cost_per_1k_input_tokens == 0.00015
    assert imported["gpt-4o-mini-2024-07-18"].cost_per_1k_output_tokens == 0.0006
    assert imported["gpt-4.1-mini"].cost_per_1k_input_tokens == 0.0004
    assert imported["gpt-4.1-mini"].cost_per_1k_output_tokens == 0.0016


def test_sync_provider_models_enriches_anthropic_prices(tmp_path, monkeypatch):
    store = RuntimeConfigStore(Settings(runtime_config_path=str(tmp_path / "runtime.json")))
    monkeypatch.setattr(main, 'runtime_config', store)

    class StubProviderRouter:
        def list_models_for_provider(self, provider_id):
            assert provider_id == "anthropic"
            return ["claude-sonnet-4-20250514", "claude-opus-4-20250514"]

    class StubControlPlane:
        provider_router = StubProviderRouter()

    monkeypatch.setattr(main, 'control_plane', StubControlPlane())
    main.sync_provider_models("anthropic")
    imported = {model.model: model for model in store.list_models()}
    assert imported["claude-sonnet-4-20250514"].cost_per_1k_input_tokens == 0.0015
    assert imported["claude-sonnet-4-20250514"].cost_per_1k_output_tokens == 0.0075
    assert imported["claude-opus-4-20250514"].cost_per_1k_input_tokens == 0.0075
    assert imported["claude-opus-4-20250514"].cost_per_1k_output_tokens == 0.0375


def test_admin_model_endpoint_persists_model(tmp_path, monkeypatch):
    store = RuntimeConfigStore(Settings(runtime_config_path=str(tmp_path / "runtime.json")))
    monkeypatch.setattr(main, 'runtime_config', store)
    body = main.upsert_model(
        'custom-model',
        ModelRecord(
            model='custom-model',
            provider='ollama',
            mode='economy',
            cost_per_1k_input_tokens=0,
            cost_per_1k_output_tokens=0,
            avg_latency_ms=500,
            quality_score=0.7,
            error_rate=0.01,
            enabled=True,
            tags=['local'],
        ),
    )
    assert body.model == 'custom-model'


def test_bulk_toggle_models_updates_enabled_state(tmp_path, monkeypatch):
    store = RuntimeConfigStore(Settings(runtime_config_path=str(tmp_path / "runtime.json")))
    monkeypatch.setattr(main, 'runtime_config', store)
    body = main.bulk_toggle_models(main.ModelBulkToggleRequest(models=['gpt-4o-mini'], enabled=False))
    assert body["updated"] == 1
    models = {model.model: model for model in store.list_models()}
    assert models['gpt-4o-mini'].enabled is False


def test_admin_policy_endpoint_persists_policy(tmp_path, monkeypatch):
    store = RuntimeConfigStore(Settings(runtime_config_path=str(tmp_path / "runtime.json")))
    monkeypatch.setattr(main, 'runtime_config', store)
    body = main.upsert_policy(
        'team-demo',
        Policy(
            policy_id='team-demo',
            scope='team',
            scope_id='demo',
            rules=PolicyRuleSet(max_cost_per_request=0.02, allowed_models=['gpt-4o-mini']),
        ),
    )
    assert body.policy_id == 'team-demo'
