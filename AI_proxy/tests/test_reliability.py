from fastapi import HTTPException

from app.reliability import ReliabilityLayer
from app.schemas import ChatCompletionRequest, ChatMessage, ProviderResponse
from app.storage.memory import InMemoryCircuitBreakerStore


class FlakyProvider:
    def __init__(self):
        self.calls: list[str] = []

    def complete(self, model: str, request: ChatCompletionRequest) -> ProviderResponse:
        self.calls.append(model)
        if model == "primary":
            return ProviderResponse(
                model=model,
                content="slow",
                prompt_tokens=10,
                completion_tokens=5,
                latency_ms=3000,
            )
        return ProviderResponse(
            model=model,
            content="ok",
            prompt_tokens=10,
            completion_tokens=5,
            latency_ms=100,
        )



def test_reliability_falls_back_after_timeout():
    provider = FlakyProvider()
    layer = ReliabilityLayer(provider, circuit_breaker=InMemoryCircuitBreakerStore())
    request = ChatCompletionRequest(messages=[ChatMessage(role="user", content="hello")])

    response, attempts = layer.execute(request, primary_model="primary", fallback_chain=["secondary"], timeout_ms=500)

    assert response.model == "secondary"
    assert attempts == ["primary", "secondary"]



def test_reliability_skips_open_circuit():
    provider = FlakyProvider()
    breaker = InMemoryCircuitBreakerStore(failure_threshold=1)
    breaker.record_failure("primary")
    layer = ReliabilityLayer(provider, circuit_breaker=breaker)
    request = ChatCompletionRequest(messages=[ChatMessage(role="user", content="hello")])

    response, attempts = layer.execute(request, primary_model="primary", fallback_chain=["secondary"], timeout_ms=500)

    assert response.model == "secondary"
    assert attempts == ["secondary"]



def test_reliability_raises_when_all_models_fail():
    provider = FlakyProvider()
    layer = ReliabilityLayer(provider, circuit_breaker=InMemoryCircuitBreakerStore())
    request = ChatCompletionRequest(messages=[ChatMessage(role="user", content="hello")])

    try:
        layer.execute(request, primary_model="primary", fallback_chain=[], timeout_ms=500)
    except HTTPException as exc:
        assert exc.status_code == 504
    else:
        raise AssertionError("Expected reliability layer to fail")
