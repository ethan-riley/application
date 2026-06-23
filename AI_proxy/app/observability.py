from __future__ import annotations

from app.schemas import RequestLog
from app.storage.base import RequestLogStore
from app.storage.memory import InMemoryRequestLogStore


class ObservabilityService:
    def __init__(self, store: RequestLogStore | None = None):
        self._store = store or InMemoryRequestLogStore()

    def append(self, log: RequestLog) -> None:
        self._store.append(log)

    def recent(self, limit: int = 100, tag: str | None = None) -> list[RequestLog]:
        return self._store.recent(limit=limit, tag=tag)
