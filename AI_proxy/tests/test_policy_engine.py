from fastapi import HTTPException

from app.policy_engine import PolicyEngine
from app.registry import load_model_registry, load_policies
from app.schemas import ChatCompletionRequest, ChatMessage



def build_request(content: str, model: str | None = None) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model=model,
        messages=[ChatMessage(role="user", content=content)],
    )



def test_team_policy_overrides_org_limits():
    engine = PolicyEngine(load_policies())
    effective = engine.resolve("techsphere", "platform")
    assert effective.policy_id == "team-platform"
    assert effective.rules.max_cost_per_request == 0.015
    assert "gpt-4o-mini" in effective.rules.allowed_models
    assert "pii" in effective.rules.blocked_terms



def test_policy_allows_live_openai_model_in_team_policy():
    engine = PolicyEngine(load_policies())
    effective = engine.resolve("techsphere", "platform")
    request = build_request("hello", model="gpt-4.1")
    engine.validate_request(request, effective, load_model_registry(), estimated_cost_usd=0.001)



def test_policy_blocks_sensitive_term():
    engine = PolicyEngine(load_policies())
    effective = engine.resolve("techsphere", "platform")
    request = build_request("Please process this PII payload.")

    try:
        engine.validate_request(request, effective, load_model_registry(), estimated_cost_usd=0.001)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "blocked by policy" in exc.detail
    else:
        raise AssertionError("Expected blocked term validation to fail")
