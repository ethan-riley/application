from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import Settings
from app.model_aliases import filter_models_for_alias, get_alias
from app.observability import ObservabilityService
from app.policy_engine import PolicyEngine
from app.prompt_intel import PromptIntelligence
from app.providers.router import ProviderRouter
from app.reliability import ReliabilityLayer
from app.routing import IntelligentRouter
from app.runtime_config import RuntimeConfigStore
from app.schemas import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    ChatMessage,
    ModelRecord,
    RequestLog,
)
from app.storage.base import QuotaStore
from app.storage.clickhouse import ClickHouseRequestLogStore
from app.storage.memory import InMemoryQuotaStore, InMemoryRequestLogStore
from app.storage.redis_store import RedisCircuitBreakerStore, RedisQuotaStore


class ControlPlane:
    def __init__(
        self,
        settings: Settings,
        prompt_intelligence: PromptIntelligence,
        router: IntelligentRouter,
        reliability_layer: ReliabilityLayer,
        observability: ObservabilityService,
        quota_store: QuotaStore,
        provider_router: ProviderRouter,
        runtime_config: RuntimeConfigStore,
    ):
        self._settings = settings
        self._prompt_intelligence = prompt_intelligence
        self._router = router
        self._reliability_layer = reliability_layer
        self._observability = observability
        self._quota_store = quota_store
        self._provider_router = provider_router
        self._runtime_config = runtime_config

    @property
    def model_registry(self) -> list[ModelRecord]:
        return self._runtime_config.list_models()

    @property
    def provider_router(self) -> ProviderRouter:
        return self._provider_router

    def handle_chat_completion(
        self,
        request: ChatCompletionRequest,
        provider_name_override: str | None = None,
    ) -> ChatCompletionResponse:
        analysis = self._prompt_intelligence.analyze(request)
        policies = self._runtime_config.list_policies()
        policy_engine = PolicyEngine(policies)
        effective_policy = policy_engine.resolve(
            org_id=request.metadata.org_id,
            team_id=request.metadata.team_id,
        )

        alias = get_alias(request.model)
        available_models = policy_engine.filter_models(effective_policy, self._runtime_config.list_models())
        if alias:
            available_models = filter_models_for_alias(available_models, alias)
        available_models = self._provider_router.executable_models(available_models)
        if provider_name_override:
            available_models = [m for m in available_models if m.provider == provider_name_override]
        if not available_models:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No live models available after policy and backend filtering",
            )

        requested_model = None if alias else request.model
        decision = self._router.choose_model(
            models=available_models,
            analysis=analysis,
            metadata=request.metadata,
            requested_model=requested_model,
            fallback_model=effective_policy.rules.fallback_model or self._settings.default_fallback_model,
        )

        estimated_cost_usd = self._estimate_request_cost(
            model_name=decision.selected_model,
            completion_tokens=request.max_tokens or 256,
            prompt_tokens=analysis.estimated_prompt_tokens,
        )
        request_for_policy = request if not alias else request.model_copy(update={"model": None})
        policy_engine.validate_request(request_for_policy, effective_policy, available_models, estimated_cost_usd)

        quota_decision = self._quota_store.check_and_increment(
            team_id=request.metadata.team_id,
            cost_usd=estimated_cost_usd,
        )
        if not quota_decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=quota_decision.reason or "quota exceeded",
                headers={"Retry-After": str(quota_decision.retry_after_seconds or 60)},
            )

        provider_response, attempts = self._reliability_layer.execute(
            request=request.model_copy(update={"model": decision.selected_model}),
            primary_model=decision.selected_model,
            fallback_chain=decision.fallback_chain,
            timeout_ms=request.metadata.latency_slo_ms or self._settings.default_timeout_ms,
        )

        cost_usd = self._calculate_actual_cost(
            model_name=provider_response.model,
            prompt_tokens=provider_response.prompt_tokens,
            completion_tokens=provider_response.completion_tokens,
        )
        request_id = str(uuid4())
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        self._observability.append(
            RequestLog(
                request_id=request_id,
                created_at=created_at,
                org_id=request.metadata.org_id,
                team_id=request.metadata.team_id,
                user_id=request.metadata.user_id,
                service=request.metadata.service,
                task_type=analysis.task_type,
                prompt_tokens=provider_response.prompt_tokens,
                completion_tokens=provider_response.completion_tokens,
                model_used=provider_response.model,
                latency_ms=provider_response.latency_ms,
                cost_usd=round(cost_usd, 6),
                status="success",
                policy_id=effective_policy.policy_id,
                route_reason=decision.reason,
                attempted_models=attempts,
                tags=request.tags,
            )
        )

        provider_mode = provider_response.raw.get("provider", "unknown")
        if provider_response.raw.get("id") and provider_mode == "unknown":
            provider_mode = "openai-live"
        if provider_response.raw.get("model") and provider_mode == "unknown":
            provider_mode = "ollama-live"

        message = ChatMessage(
            role="assistant",
            content=provider_response.content,
            tool_calls=provider_response.tool_calls,
        )
        finish_reason = provider_response.finish_reason or ("tool_calls" if provider_response.tool_calls else "stop")
        route_reason = decision.reason
        if alias:
            route_reason = f"virtual alias {alias.alias_id}: {route_reason}"

        return ChatCompletionResponse(
            id=request_id,
            model=provider_response.model,
            choices=[
                ChatCompletionChoice(
                    message=message,
                    finish_reason=finish_reason,
                )
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=provider_response.prompt_tokens,
                completion_tokens=provider_response.completion_tokens,
                total_tokens=provider_response.prompt_tokens + provider_response.completion_tokens,
            ),
            control_plane={
                "task_type": analysis.task_type,
                "complexity": analysis.complexity,
                "recommended_tier": analysis.recommended_tier,
                "routing": decision.model_dump(),
                "attempts": attempts,
                "policy_id": effective_policy.policy_id,
                "cost_usd": round(cost_usd, 6),
                "quota": quota_decision.model_dump(),
                "provider_mode": provider_mode,
                "requested_model": request.model,
                "resolved_alias": alias.alias_id if alias else None,
            },
        )

    def recent_logs(self, limit: int = 100, tag: str | None = None):
        return self._observability.recent(limit=limit, tag=tag)

    def _estimate_request_cost(self, model_name: str, completion_tokens: int, prompt_tokens: int) -> float:
        model = self._resolve_model_record(model_name)
        if model is None:
            return 0.0
        return (
            prompt_tokens / 1000 * model.cost_per_1k_input_tokens
            + completion_tokens / 1000 * model.cost_per_1k_output_tokens
        )

    def _calculate_actual_cost(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        model = self._resolve_model_record(model_name)
        if model is None:
            return 0.0
        return (
            prompt_tokens / 1000 * model.cost_per_1k_input_tokens
            + completion_tokens / 1000 * model.cost_per_1k_output_tokens
        )

    def _resolve_model_record(self, model_name: str) -> ModelRecord | None:
        for model in self._runtime_config.list_models():
            if model.model == model_name:
                return model

        for model in self._runtime_config.list_models():
            if model_name.startswith(f"{model.model}-"):
                return model

        return None


def build_control_plane(settings: Settings, runtime_config: RuntimeConfigStore) -> ControlPlane:
    request_log_store = InMemoryRequestLogStore()
    if settings.clickhouse_enabled:
        request_log_store = ClickHouseRequestLogStore(settings)

    quota_store: QuotaStore = InMemoryQuotaStore(
        default_team_daily_cost_limit_usd=settings.default_team_daily_cost_limit_usd,
    )
    circuit_breaker_store = None
    if settings.redis_enabled:
        quota_store = RedisQuotaStore(settings)
        circuit_breaker_store = RedisCircuitBreakerStore(settings)

    provider_router = ProviderRouter(settings=settings, runtime_config=runtime_config)

    return ControlPlane(
        settings=settings,
        prompt_intelligence=PromptIntelligence(),
        router=IntelligentRouter(),
        reliability_layer=ReliabilityLayer(provider_router, circuit_breaker=circuit_breaker_store),
        observability=ObservabilityService(request_log_store),
        quota_store=quota_store,
        provider_router=provider_router,
        runtime_config=runtime_config,
    )
