from app.routing import IntelligentRouter
from app.schemas import ModelRecord, PromptAnalysis, RequestMetadata


def test_router_prefers_low_cost_for_classification():
    router = IntelligentRouter()
    models = [
        ModelRecord(
            model="cheap-fast",
            provider="x",
            mode="economy",
            cost_per_1k_input_tokens=0.0001,
            cost_per_1k_output_tokens=0.0001,
            avg_latency_ms=400,
            quality_score=0.70,
            error_rate=0.02,
        ),
        ModelRecord(
            model="expensive-smart",
            provider="y",
            mode="premium",
            cost_per_1k_input_tokens=0.003,
            cost_per_1k_output_tokens=0.009,
            avg_latency_ms=1200,
            quality_score=0.95,
            error_rate=0.01,
        ),
    ]
    analysis = PromptAnalysis(
        task_type="classification",
        complexity="low",
        estimated_prompt_tokens=100,
        recommended_tier="economy",
    )
    metadata = RequestMetadata(latency_slo_ms=1000)

    decision = router.choose_model(models, analysis, metadata)
    assert decision.selected_model == "cheap-fast"


def test_router_honors_explicit_model_request():
    router = IntelligentRouter()
    models = [
        ModelRecord(
            model="gpt-4o-mini",
            provider="openai",
            mode="balanced",
            cost_per_1k_input_tokens=0.0001,
            cost_per_1k_output_tokens=0.0004,
            avg_latency_ms=800,
            quality_score=0.82,
            error_rate=0.01,
        ),
        ModelRecord(
            model="gpt-4.1",
            provider="openai",
            mode="premium",
            cost_per_1k_input_tokens=0.002,
            cost_per_1k_output_tokens=0.008,
            avg_latency_ms=1500,
            quality_score=0.93,
            error_rate=0.01,
        ),
    ]
    analysis = PromptAnalysis(
        task_type="general_chat",
        complexity="medium",
        estimated_prompt_tokens=500,
        recommended_tier="balanced",
    )
    metadata = RequestMetadata()

    decision = router.choose_model(models, analysis, metadata, requested_model="gpt-4.1")
    assert decision.selected_model == "gpt-4.1"
    assert decision.reason == "explicit model requested by client"


def test_router_prefers_cheapest_suitable_model_for_general_chat():
    router = IntelligentRouter()
    models = [
        ModelRecord(
            model="tiny-but-weak",
            provider="ollama",
            mode="economy",
            cost_per_1k_input_tokens=0.0,
            cost_per_1k_output_tokens=0.0,
            avg_latency_ms=300,
            quality_score=0.55,
            error_rate=0.02,
        ),
        ModelRecord(
            model="small-good-enough",
            provider="ollama",
            mode="economy",
            cost_per_1k_input_tokens=0.0,
            cost_per_1k_output_tokens=0.0,
            avg_latency_ms=700,
            quality_score=0.71,
            error_rate=0.02,
        ),
        ModelRecord(
            model="bigger-better",
            provider="openai",
            mode="balanced",
            cost_per_1k_input_tokens=0.00015,
            cost_per_1k_output_tokens=0.0006,
            avg_latency_ms=800,
            quality_score=0.83,
            error_rate=0.01,
        ),
    ]
    analysis = PromptAnalysis(
        task_type="general_chat",
        complexity="low",
        estimated_prompt_tokens=20,
        recommended_tier="balanced",
    )
    metadata = RequestMetadata(latency_slo_ms=2000)

    decision = router.choose_model(models, analysis, metadata)
    assert decision.selected_model == "small-good-enough"
