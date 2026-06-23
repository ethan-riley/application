from __future__ import annotations

from app.schemas import ChatCompletionRequest, ProviderResponse


class MockProvider:
    def complete(self, model: str, request: ChatCompletionRequest) -> ProviderResponse:
        prompt = request.messages[-1].content
        prompt_tokens = max(1, len(" ".join(m.content for m in request.messages).split()) * 2)
        completion_tokens = min(request.max_tokens or 256, 120)
        latency_ms = 450 + min(prompt_tokens, 1_500) // 4
        content = (
            f"[mock:{model}] Routed response for task. "
            f"Last user message: {prompt[:160]}"
        )
        return ProviderResponse(
            model=model,
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            raw={"provider": "mock"},
        )
