from __future__ import annotations

from typing import Protocol

from app.schemas import QuotaDecision, RequestLog


class RequestLogStore(Protocol):
    def append(self, log: RequestLog) -> None:
        ...

    def recent(self, limit: int = 100, tag: str | None = None) -> list[RequestLog]:
        ...


class QuotaStore(Protocol):
    def check_and_increment(self, team_id: str, cost_usd: float) -> QuotaDecision:
        ...


class CircuitBreakerStore(Protocol):
    def is_open(self, model: str) -> bool:
        ...

    def record_success(self, model: str) -> None:
        ...

    def record_failure(self, model: str) -> None:
        ...
