from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, Path, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.auth import create_api_client, require_proxy_api_key, update_api_client
from app.batch import BatchService
from app.config import get_settings
from app.secrets import resolve_provider_api_key
from app.control_plane import build_control_plane
from app.model_aliases import list_aliases
from app.pricing import pricing_for_model
from app.providers.anthropic import AnthropicProvider
from app.providers.cohere import CohereProvider
from app.providers.openai import OpenAIProvider
from app.runtime_config import RuntimeConfigStore
from app.schemas import (
    AnthropicMessagesPassthroughRequest,
    ApiClientCreateRequest,
    ApiClientUpdateRequest,
    BatchCreateRequest,
    ChatCompletionRequest,
    ChatMessage,
    ChatToolCall,
    EmbeddingsRequest,
    ModelBulkToggleRequest,
    ModelMetadata,
    ModelRecord,
    Policy,
    ProviderConfig,
    RerankRequest,
    ResponsesFunctionCallOutput,
    ResponsesMessageContent,
    ResponsesOutputMessage,
    ResponsesRequest,
    ResponsesResponse,
    SearchRequest,
)
from app.search import SearchService
from app.tags import merge_tags, parse_header_tags
from app.webui import ASSETS_DIR, render_webui

settings = get_settings()
runtime_config = RuntimeConfigStore(settings)
control_plane = build_control_plane(settings, runtime_config)
_openai_provider = OpenAIProvider(settings)
_anthropic_provider = AnthropicProvider(settings)
_cohere_provider = CohereProvider(settings)
_search_service = SearchService(settings)
_batch_service = BatchService(control_plane)

app = FastAPI(title="LLM Control Plane", version="0.4.0")

# Static assets for the web UI (design bundle: CSS + JSX modules).
app.mount("/ui/assets", StaticFiles(directory=str(ASSETS_DIR)), name="ui-assets")


@app.middleware("http")
async def add_portal_iframe_headers(request: Request, call_next):
    """Allow embedding under the Tech-Sphere portal iframe."""
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "frame-ancestors https://www.tech-sphere.pro 'self'"
    )
    # Strip any X-Frame-Options that would block framing
    if "x-frame-options" in {k.lower() for k in response.headers.keys()}:
        del response.headers["X-Frame-Options"]
    return response


def _require_proxy_api_key(authorization: str | None = Header(default=None)):
    return require_proxy_api_key(runtime_config, authorization)


def _default_chat_model(request: ChatCompletionRequest) -> ChatCompletionRequest:
    if request.model:
        return request
    default_model = "tools:auto" if request.tools else "openai:auto"
    return request.model_copy(update={"model": default_model})


def _default_responses_model(request: ResponsesRequest) -> ResponsesRequest:
    if request.model:
        return request
    default_model = "tools:auto" if request.tools else "openai:auto"
    return request.model_copy(update={"model": default_model})


def _inject_tags(
    request: ChatCompletionRequest,
    x_tags: str | None,
    x_litelm_tags: str | None,
) -> ChatCompletionRequest:
    header_tags = parse_header_tags(x_tags) + parse_header_tags(x_litelm_tags)
    if not header_tags and not request.tags:
        return request
    merged = merge_tags(header_tags, request.tags)
    return request.model_copy(update={"tags": merged})


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/ui", status_code=302)


@app.get("/ui", response_class=HTMLResponse)
def webui() -> str:
    return render_webui()


@app.get("/healthz")
def healthcheck() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "environment": settings.environment,
        "clickhouse_enabled": settings.clickhouse_enabled,
        "redis_enabled": settings.redis_enabled,
    }


@app.post("/v1/chat/completions")
def create_chat_completion(
    request: ChatCompletionRequest,
    x_tags: str | None = Header(default=None, alias="X-Tags"),
    x_litelm_tags: str | None = Header(default=None, alias="X-LiteLLM-Tags"),
    x_provider_name: str | None = Header(default=None, alias="X-Provider-Name"),
):
    request = _inject_tags(request, x_tags, x_litelm_tags)
    return control_plane.handle_chat_completion(_default_chat_model(request), provider_name_override=x_provider_name)


@app.post("/openai/v1/chat/completions")
def create_openai_compatible_chat_completion(
    request: ChatCompletionRequest,
    _: object = Depends(_require_proxy_api_key),
    x_tags: str | None = Header(default=None, alias="X-Tags"),
    x_litelm_tags: str | None = Header(default=None, alias="X-LiteLLM-Tags"),
    x_provider_name: str | None = Header(default=None, alias="X-Provider-Name"),
):
    request = _inject_tags(request, x_tags, x_litelm_tags)
    return control_plane.handle_chat_completion(_default_chat_model(request), provider_name_override=x_provider_name)


@app.post("/v1/responses")
def create_response(
    request: ResponsesRequest,
    x_tags: str | None = Header(default=None, alias="X-Tags"),
    x_litelm_tags: str | None = Header(default=None, alias="X-LiteLLM-Tags"),
    x_provider_name: str | None = Header(default=None, alias="X-Provider-Name"),
) -> ResponsesResponse:
    request = _default_responses_model(request)
    chat_request = ChatCompletionRequest(
        model=request.model,
        messages=_coerce_response_input(request.input),
        temperature=request.temperature,
        max_tokens=request.max_output_tokens,
        tools=request.tools,
        tool_choice=request.tool_choice,
        parallel_tool_calls=request.parallel_tool_calls,
        metadata=request.metadata,
    )
    chat_request = _inject_tags(chat_request, x_tags, x_litelm_tags)
    chat_response = control_plane.handle_chat_completion(chat_request, provider_name_override=x_provider_name)
    message = chat_response.choices[0].message
    output: list[dict[str, Any]] = []
    if message.content:
        output.append(
            ResponsesOutputMessage(
                id=f"msg_{uuid4().hex}",
                content=[ResponsesMessageContent(text=message.content)],
            ).model_dump()
        )
    for tool_call in message.tool_calls:
        output.append(_tool_call_output(tool_call))
    if not output:
        output.append(
            ResponsesOutputMessage(
                id=f"msg_{uuid4().hex}",
                content=[],
            ).model_dump()
        )

    return ResponsesResponse(
        id=f"resp_{uuid4().hex}",
        model=chat_response.model,
        output=output,
        usage={
            "input_tokens": chat_response.usage.prompt_tokens,
            "output_tokens": chat_response.usage.completion_tokens,
            "total_tokens": chat_response.usage.total_tokens,
        },
        metadata=chat_response.control_plane,
    )


@app.post("/openai/v1/responses")
def create_openai_compatible_response(
    request: ResponsesRequest,
    _: object = Depends(_require_proxy_api_key),
    x_tags: str | None = Header(default=None, alias="X-Tags"),
    x_litelm_tags: str | None = Header(default=None, alias="X-LiteLLM-Tags"),
    x_provider_name: str | None = Header(default=None, alias="X-Provider-Name"),
) -> ResponsesResponse:
    return create_response(request, x_tags=x_tags, x_litelm_tags=x_litelm_tags, x_provider_name=x_provider_name)


@app.get("/v1/models")
def list_openai_models() -> dict[str, Any]:
    models = [
        {
            "id": model.model,
            "object": "model",
            "owned_by": model.provider,
        }
        for model in runtime_config.list_models()
        if model.enabled
    ]
    aliases = [
        {
            "id": alias.alias_id,
            "object": "model",
            "owned_by": alias.owned_by,
        }
        for alias in list_aliases()
    ]
    return {"object": "list", "data": aliases + models}


@app.get("/openai/v1/models")
def list_openai_compatible_models(
    _: object = Depends(_require_proxy_api_key),
) -> dict[str, Any]:
    return list_openai_models()


@app.post("/v1/embeddings")
def create_embeddings(request: EmbeddingsRequest) -> Any:
    return _handle_embeddings(request)


@app.post("/openai/v1/embeddings")
def create_openai_embeddings(
    request: EmbeddingsRequest,
    _: object = Depends(_require_proxy_api_key),
) -> Any:
    return _handle_embeddings(request)


def _handle_embeddings(request: EmbeddingsRequest) -> Any:
    provider_config = _resolve_embeddings_provider(request.model)
    return _openai_provider.embed(request.model, request, provider_config=provider_config)


def _resolve_embeddings_provider(model: str) -> ProviderConfig | None:
    for provider in runtime_config.list_provider_responses():
        if provider.provider_type in {"openai", "kimi"} and provider.enabled:
            full = runtime_config.get_provider(provider.provider_id)
            if full and resolve_provider_api_key(full.provider_type, full.api_key, settings):
                return full
    return None


@app.post("/rerank")
@app.post("/v1/rerank")
@app.post("/v2/rerank")
def create_rerank(request: RerankRequest) -> Any:
    return _cohere_provider.rerank(request.model, request)


@app.post("/anthropic/v1/messages")
def create_anthropic_message(
    request: AnthropicMessagesPassthroughRequest,
    _: object = Depends(_require_proxy_api_key),
) -> Any:
    body = request.model_dump(exclude_none=True)
    result = _anthropic_provider.messages_passthrough(body)
    result.pop("_latency_ms", None)
    return result


@app.post("/anthropic/v1/messages/count_tokens")
def count_anthropic_tokens(
    request: AnthropicMessagesPassthroughRequest,
    _: object = Depends(_require_proxy_api_key),
) -> Any:
    body = request.model_dump(exclude_none=True)
    result = _anthropic_provider.count_tokens(body)
    result.pop("_latency_ms", None)
    return result


@app.post("/v1/messages/count_tokens")
def count_tokens(request: AnthropicMessagesPassthroughRequest) -> Any:
    body = request.model_dump(exclude_none=True)
    result = _anthropic_provider.count_tokens(body)
    result.pop("_latency_ms", None)
    return result


@app.post("/v1/search")
def web_search(request: SearchRequest) -> Any:
    return _search_service.search(request)


@app.post("/openai/v1/openai/deployments/{model}/chat/completions")
def azure_chat_completions(
    model: str = Path(...),
    request: ChatCompletionRequest = ...,
    _: object = Depends(_require_proxy_api_key),
    x_tags: str | None = Header(default=None, alias="X-Tags"),
    x_litelm_tags: str | None = Header(default=None, alias="X-LiteLLM-Tags"),
    x_provider_name: str | None = Header(default=None, alias="X-Provider-Name"),
) -> Any:
    request = _inject_tags(request.model_copy(update={"model": model}), x_tags, x_litelm_tags)
    return control_plane.handle_chat_completion(
        _default_chat_model(request),
        provider_name_override=x_provider_name or "azure-openai",
    )


@app.get("/v1/models/metadata")
def models_metadata(include_in_cli: bool | None = Query(default=None)) -> dict[str, Any]:
    models = runtime_config.list_models()
    results: list[ModelMetadata] = []
    for m in models:
        in_cli = "cli" in m.tags
        if include_in_cli is not None and in_cli != include_in_cli:
            continue
        results.append(ModelMetadata(
            id=m.model,
            provider=m.provider,
            mode=m.mode,
            cost_per_1k_input_tokens=m.cost_per_1k_input_tokens,
            cost_per_1k_output_tokens=m.cost_per_1k_output_tokens,
            avg_latency_ms=m.avg_latency_ms,
            quality_score=m.quality_score,
            supports_tools=m.supports_tools,
            supports_streaming=m.supports_streaming,
            enabled=m.enabled,
            tags=m.tags,
            include_in_cli=in_cli,
        ))
    return {"object": "list", "data": [r.model_dump() for r in results]}


@app.get("/v1/admin/providers")
def list_providers():
    return runtime_config.list_provider_responses()


@app.put("/v1/admin/providers/{provider_id}")
def upsert_provider(provider_id: str, provider: ProviderConfig):
    saved = runtime_config.upsert_provider(provider.model_copy(update={"provider_id": provider_id}))
    return runtime_config._mask_provider(saved)


def _infer_imported_model(provider_id: str, model_name: str) -> ModelRecord:
    lowered = model_name.lower()
    mode = "balanced"
    quality_score = 0.8
    avg_latency_ms = 1200
    supports_tools = False
    supports_streaming = True
    tags = [provider_id, "imported", "review-required", "text"]

    if provider_id == "openai":
        supports_tools = True
        tags.append("live")
        if (
            "gpt-4o" in lowered
            or "omni" in lowered
            or "vision" in lowered
            or "image" in lowered
            or lowered.startswith("o")
        ):
            tags.append("image")
        if "nano" in lowered:
            mode = "economy"
            quality_score = 0.72
            avg_latency_ms = 500
        elif "mini" in lowered:
            mode = "balanced"
            quality_score = 0.84
            avg_latency_ms = 800
        elif "pro" in lowered or "codex" in lowered or lowered.startswith("o") or "gpt-5" in lowered:
            mode = "premium"
            quality_score = 0.94
            avg_latency_ms = 1600
        elif "gpt-4.1" in lowered:
            mode = "premium"
            quality_score = 0.92
            avg_latency_ms = 1400
    elif provider_id == "anthropic":
        supports_tools = True
        tags.append("live")
        if "claude" in lowered:
            tags.append("image")
        if "haiku" in lowered:
            mode = "economy"
            quality_score = 0.82
            avg_latency_ms = 700
        elif "sonnet" in lowered:
            mode = "balanced"
            quality_score = 0.9
            avg_latency_ms = 1100
        elif "opus" in lowered:
            mode = "premium"
            quality_score = 0.96
            avg_latency_ms = 1800
    elif provider_id == "kimi":
        supports_tools = True
        tags.extend(["live", "kimi"])
        if "k2.5" in lowered or "thinking" in lowered:
            mode = "premium"
            quality_score = 0.93
            avg_latency_ms = 1600
            tags.append("image")
        elif "turbo" in lowered:
            mode = "balanced"
            quality_score = 0.87
            avg_latency_ms = 900
        else:
            mode = "balanced"
            quality_score = 0.89
            avg_latency_ms = 1100
    elif provider_id == "groq":
        supports_tools = True
        tags.append("live")
        if "70b" in lowered or "90b" in lowered:
            mode = "premium"
            quality_score = 0.88
            avg_latency_ms = 700
        elif "8b" in lowered or "7b" in lowered:
            mode = "balanced"
            quality_score = 0.80
            avg_latency_ms = 400
        else:
            mode = "balanced"
            quality_score = 0.82
            avg_latency_ms = 500
    elif provider_id == "mistral":
        supports_tools = True
        tags.append("live")
        if "large" in lowered:
            mode = "premium"
            quality_score = 0.91
            avg_latency_ms = 1200
        elif "small" in lowered or "7b" in lowered:
            mode = "economy"
            quality_score = 0.73
            avg_latency_ms = 700
        else:
            mode = "balanced"
            quality_score = 0.83
            avg_latency_ms = 900
    elif provider_id == "gemini":
        supports_tools = True
        tags.append("live")
        if "ultra" in lowered or "pro" in lowered:
            mode = "premium"
            quality_score = 0.93
            avg_latency_ms = 1400
        elif "flash" in lowered:
            mode = "balanced"
            quality_score = 0.87
            avg_latency_ms = 600
        else:
            mode = "balanced"
            quality_score = 0.85
            avg_latency_ms = 900
    elif provider_id in {"azure-openai", "azure_openai"}:
        supports_tools = True
        tags.append("live")
        if "gpt-4" in lowered or "o1" in lowered:
            mode = "premium"
            quality_score = 0.92
            avg_latency_ms = 1500
        elif "mini" in lowered:
            mode = "balanced"
            quality_score = 0.84
            avg_latency_ms = 800
        else:
            mode = "balanced"
            quality_score = 0.85
            avg_latency_ms = 1000

    if supports_tools:
        tags.append("tools")

    pricing = pricing_for_model(provider_id, model_name)

    return ModelRecord(
        model=model_name,
        provider=provider_id,
        mode=mode,
        cost_per_1k_input_tokens=pricing.input_per_1k if pricing else 0.0,
        cost_per_1k_output_tokens=pricing.output_per_1k if pricing else 0.0,
        avg_latency_ms=avg_latency_ms,
        quality_score=quality_score,
        error_rate=0.01,
        supports_tools=supports_tools,
        supports_streaming=supports_streaming,
        enabled=False,
        tags=tags,
    )


@app.post("/v1/admin/providers/{provider_id}/sync-models")
def sync_provider_models(provider_id: str):
    model_names = control_plane.provider_router.list_models_for_provider(provider_id)
    existing = {model.model: model for model in runtime_config.list_models()}
    records: list[ModelRecord] = []
    for model_name in model_names:
        inferred = _infer_imported_model(provider_id, model_name)
        if model_name in existing:
            current = existing[model_name]
            imported_record = "imported" in current.tags or "review-required" in current.tags
            update_payload: dict[str, Any] = {"provider": provider_id}
            if imported_record or (
                current.cost_per_1k_input_tokens == 0.0 and current.cost_per_1k_output_tokens == 0.0
            ):
                update_payload["cost_per_1k_input_tokens"] = inferred.cost_per_1k_input_tokens
                update_payload["cost_per_1k_output_tokens"] = inferred.cost_per_1k_output_tokens
                update_payload["avg_latency_ms"] = inferred.avg_latency_ms
                update_payload["quality_score"] = inferred.quality_score
                update_payload["mode"] = inferred.mode
            if imported_record:
                update_payload["supports_tools"] = inferred.supports_tools
                update_payload["supports_streaming"] = inferred.supports_streaming
                update_payload["tags"] = sorted(set(current.tags).union(inferred.tags))
            records.append(current.model_copy(update=update_payload))
        else:
            records.append(inferred)
    runtime_config.upsert_models(records)
    return {
        "provider_id": provider_id,
        "synced_models": len(records),
        "models": [record.model for record in records],
    }


@app.get("/v1/admin/models")
def list_models():
    return runtime_config.list_models()


@app.put("/v1/admin/models/{model_name}")
def upsert_model(model_name: str, model: ModelRecord):
    return runtime_config.upsert_model(model.model_copy(update={"model": model_name}))


@app.post("/v1/admin/models/bulk-toggle")
def bulk_toggle_models(request: ModelBulkToggleRequest):
    updated = runtime_config.bulk_toggle_models(request.models, request.enabled)
    return {"updated": len(updated), "models": [model.model for model in updated], "enabled": request.enabled}


@app.get("/v1/admin/policies")
def list_policies():
    return runtime_config.list_policies()


@app.put("/v1/admin/policies/{policy_id}")
def upsert_policy(policy_id: str, policy: Policy):
    return runtime_config.upsert_policy(policy.model_copy(update={"policy_id": policy_id}))


@app.get("/v1/admin/requests")
def list_recent_requests(
    limit: int = Query(default=100, ge=1, le=500),
    tag: str | None = Query(default=None),
):
    return control_plane.recent_logs(limit=limit, tag=tag)


@app.get("/v1/admin/overview")
def admin_overview():
    providers = runtime_config.list_provider_responses()
    models = runtime_config.list_models()
    requests = control_plane.recent_logs(limit=200)

    def _sample_models(provider_id: str) -> list[str]:
        provider_models = [model for model in models if model.provider == provider_id]
        enabled = [model.model for model in provider_models if model.enabled][:3]
        if enabled:
            return enabled
        return [model.model for model in provider_models[:3]]

    provider_cards: list[dict[str, Any]] = []
    for provider in providers:
        provider_models = [model for model in models if model.provider == provider.provider_id]
        enabled_models = [model for model in provider_models if model.enabled]
        request_count = sum(
            1 for item in requests if provider.provider_id.lower() in str(item.model_used or "").lower()
        )
        provider_cards.append(
            {
                "provider_id": provider.provider_id,
                "provider_type": provider.provider_type,
                "api_key_configured": provider.api_key_configured,
                "enabled": provider.enabled,
                "model_count": len(provider_models),
                "enabled_model_count": len(enabled_models),
                "sample_models": _sample_models(provider.provider_id),
                "request_count": request_count,
                "updated_at": getattr(provider, "updated_at", None),
            }
        )

    enabled_models = [model for model in models if model.enabled]
    model_options = {
        provider.provider_id: [model.model for model in enabled_models if model.provider == provider.provider_id]
        for provider in providers
    }

    return {
        "providers": providers,
        "provider_cards": provider_cards,
        "provider_model_options": model_options,
        "totals": {
            "providers": len(providers),
            "models": len(models),
            "enabled_models": len(enabled_models),
            "requests": len(requests),
        },
    }


@app.get("/v1/admin/api-keys")
def list_api_keys():
    return runtime_config.list_api_client_responses()


@app.post("/v1/admin/api-keys")
def create_api_key(request: ApiClientCreateRequest):
    return create_api_client(runtime_config, request)


@app.put("/v1/admin/api-keys/{key_id}")
def update_api_key(key_id: str, request: ApiClientUpdateRequest):
    updated = update_api_client(runtime_config, key_id, request)
    return runtime_config._mask_api_client(updated)


@app.delete("/v1/admin/api-keys/{key_id}")
def delete_api_key(key_id: str):
    deleted = runtime_config.delete_api_client(key_id)
    return {"deleted": deleted, "key_id": key_id}


# ── Files API ─────────────────────────────────────────────────────────────────

@app.post("/openai/v1/files")
async def upload_file(
    file: UploadFile = File(...),
    purpose: str = "batch",
    _: object = Depends(_require_proxy_api_key),
) -> Any:
    content = await file.read()
    return _batch_service.upload_file(file.filename or "upload", purpose, content)


@app.get("/openai/v1/files")
def list_files(
    purpose: str | None = Query(default=None),
    _: object = Depends(_require_proxy_api_key),
) -> Any:
    return {"object": "list", "data": [f.model_dump() for f in _batch_service.list_files(purpose=purpose)]}


@app.get("/openai/v1/files/{file_id}")
def get_file(file_id: str, _: object = Depends(_require_proxy_api_key)) -> Any:
    return _batch_service.get_file(file_id)


@app.delete("/openai/v1/files/{file_id}")
def delete_file(file_id: str, _: object = Depends(_require_proxy_api_key)) -> Any:
    return _batch_service.delete_file(file_id)


@app.get("/openai/v1/files/{file_id}/content")
def get_file_content(file_id: str, _: object = Depends(_require_proxy_api_key)) -> Any:
    content = _batch_service.get_file_content(file_id)
    return Response(content=content, media_type="application/octet-stream")


# ── Batch API ─────────────────────────────────────────────────────────────────

@app.post("/openai/v1/batches")
def create_batch(
    request: BatchCreateRequest,
    _: object = Depends(_require_proxy_api_key),
) -> Any:
    return _batch_service.create_batch(request)


@app.get("/openai/v1/batches")
def list_batches(_: object = Depends(_require_proxy_api_key)) -> Any:
    return {"object": "list", "data": [b.model_dump() for b in _batch_service.list_batches()]}


@app.get("/openai/v1/batches/{batch_id}")
def get_batch(batch_id: str, _: object = Depends(_require_proxy_api_key)) -> Any:
    return _batch_service.get_batch(batch_id)


@app.post("/openai/v1/batches/{batch_id}/cancel")
def cancel_batch(batch_id: str, _: object = Depends(_require_proxy_api_key)) -> Any:
    return _batch_service.cancel_batch(batch_id)


def _coerce_response_input(value: str | list[Any]) -> list[ChatMessage]:
    if isinstance(value, str):
        return [ChatMessage(role="user", content=value)]

    messages: list[ChatMessage] = []
    for item in value:
        if isinstance(item, str):
            messages.append(ChatMessage(role="user", content=item))
            continue
        if not isinstance(item, dict):
            continue

        item_type = item.get("type")
        if item_type == "message":
            role = item.get("role", "user")
            content = _coerce_response_message_content(item.get("content"))
            messages.append(ChatMessage(role=role, content=content))
            continue
        if item_type == "function_call_output":
            messages.append(
                ChatMessage(
                    role="tool",
                    content=str(item.get("output", "")),
                    tool_call_id=item.get("call_id"),
                )
            )
            continue
        if item.get("content") or item.get("text"):
            messages.append(
                ChatMessage(
                    role=item.get("role", "user"),
                    content=str(item.get("content") or item.get("text") or ""),
                )
            )
    return messages or [ChatMessage(role="user", content="")]


def _coerce_response_message_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if isinstance(item, dict):
                if item.get("text"):
                    chunks.append(str(item["text"]))
                elif item.get("content"):
                    chunks.append(str(item["content"]))
        return "\n".join(chunks)
    return str(content)


def _tool_call_output(tool_call: ChatToolCall) -> dict[str, Any]:
    return ResponsesFunctionCallOutput(
        id=f"fc_{uuid4().hex}",
        call_id=tool_call.id,
        name=tool_call.function.name,
        arguments=tool_call.function.arguments,
    ).model_dump()
