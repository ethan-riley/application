from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from app.schemas import ChatCompletionRequest, ModelRecord, Policy, PolicyRuleSet


@dataclass
class EffectivePolicy:
    policy_id: str | None
    rules: PolicyRuleSet


class PolicyEngine:
    def __init__(self, policies: list[Policy]):
        self._policies = policies

    def resolve(self, org_id: str, team_id: str) -> EffectivePolicy:
        org_policy = next(
            (policy for policy in self._policies if policy.scope == "org" and policy.scope_id == org_id),
            None,
        )
        team_policy = next(
            (policy for policy in self._policies if policy.scope == "team" and policy.scope_id == team_id),
            None,
        )

        merged = PolicyRuleSet()
        policy_id = None

        if org_policy:
            merged = org_policy.rules.model_copy(deep=True)
            policy_id = org_policy.policy_id

        if team_policy:
            if team_policy.rules.max_cost_per_request is not None:
                merged.max_cost_per_request = team_policy.rules.max_cost_per_request
            if team_policy.rules.allowed_models:
                merged.allowed_models = team_policy.rules.allowed_models
            if team_policy.rules.blocked_terms:
                merged.blocked_terms = sorted(
                    set(merged.blocked_terms).union(team_policy.rules.blocked_terms)
                )
            if team_policy.rules.fallback_model:
                merged.fallback_model = team_policy.rules.fallback_model
            policy_id = team_policy.policy_id

        return EffectivePolicy(policy_id=policy_id, rules=merged)

    def validate_request(
        self,
        request: ChatCompletionRequest,
        effective_policy: EffectivePolicy,
        available_models: list[ModelRecord],
        estimated_cost_usd: float,
    ) -> None:
        text = " ".join(message.content for message in request.messages).lower()

        for blocked_term in effective_policy.rules.blocked_terms:
            if blocked_term.lower() in text:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Request blocked by policy term match: {blocked_term}",
                )

        max_cost = request.metadata.max_cost_usd or effective_policy.rules.max_cost_per_request
        if max_cost is not None and estimated_cost_usd > max_cost:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estimated request cost {estimated_cost_usd:.4f} exceeds limit {max_cost:.4f}",
            )

        explicit_model = request.model
        if explicit_model and effective_policy.rules.allowed_models:
            if explicit_model not in effective_policy.rules.allowed_models:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Model {explicit_model} is not allowed for this tenant",
                )

        known_models = {model.model for model in available_models}
        if explicit_model and explicit_model not in known_models:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown model: {explicit_model}",
            )

    def filter_models(
        self,
        effective_policy: EffectivePolicy,
        models: list[ModelRecord],
    ) -> list[ModelRecord]:
        if not effective_policy.rules.allowed_models:
            return models
        allowed = set(effective_policy.rules.allowed_models)
        return [model for model in models if model.model in allowed]
