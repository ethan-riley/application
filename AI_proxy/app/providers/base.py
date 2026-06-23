from __future__ import annotations

from typing import Protocol

from app.schemas import ChatCompletionRequest, ModelRecord, ProviderResponse


class Provider(Protocol):
    def complete(self, model: str, request: ChatCompletionRequest) -> ProviderResponse:
        ...

    def supports_model(self, model: str) -> bool:
        ...
