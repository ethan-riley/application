from __future__ import annotations

from fastapi import HTTPException, status

from app.providers.base import Provider
from app.schemas import ChatCompletionRequest, ProviderResponse
from app.storage.base import CircuitBreakerStore
from app.storage.memory import InMemoryCircuitBreakerStore


class ReliabilityLayer:
    def __init__(self, provider: Provider, circuit_breaker: CircuitBreakerStore | None = None):
        self._provider = provider
        self._circuit_breaker = circuit_breaker or InMemoryCircuitBreakerStore()

    def execute(
        self,
        request: ChatCompletionRequest,
        primary_model: str,
        fallback_chain: list[str],
        timeout_ms: int,
    ) -> tuple[ProviderResponse, list[str]]:
        attempted: list[str] = []
        skipped_open: list[str] = []

        for model in [primary_model, *fallback_chain]:
            if self._circuit_breaker.is_open(model):
                skipped_open.append(model)
                continue

            attempted.append(model)
            try:
                response = self._provider.complete(model, request)
            except Exception:
                self._circuit_breaker.record_failure(model)
                continue

            if response.latency_ms <= timeout_ms:
                self._circuit_breaker.record_success(model)
                return response, attempted

            self._circuit_breaker.record_failure(model)

        detail = f"All models failed or exceeded timeout budget after attempts: {attempted}"
        if skipped_open:
            detail = f"{detail}; skipped open circuits: {skipped_open}"
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=detail,
        )
