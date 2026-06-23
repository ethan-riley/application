from __future__ import annotations

import json
from urllib import error, request as urllib_request

from fastapi import HTTPException, status

from app.config import Settings
from app.schemas import RerankRequest


class CohereProvider:
    def __init__(self, settings: Settings):
        self._settings = settings

    def rerank(self, model: str, request: RerankRequest) -> dict:
        api_key = self._settings.cohere_api_key
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cohere provider has no API key configured",
            )

        payload: dict = {
            "model": model,
            "query": request.query,
            "documents": request.documents,
        }
        if request.top_n is not None:
            payload["top_n"] = request.top_n
        if request.return_documents is not None:
            payload["return_documents"] = request.return_documents

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        endpoint = self._settings.cohere_base_url.rstrip("/") + "/v1/rerank"
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib_request.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with urllib_request.urlopen(http_request, timeout=self._settings.cohere_timeout_seconds) as resp:
                try:
                    return json.loads(resp.read().decode("utf-8"))
                except json.JSONDecodeError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Cohere API returned non-JSON response",
                    ) from exc
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(status_code=exc.code, detail=f"Cohere API error: {detail}") from exc
        except error.URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cohere API unreachable: {exc.reason}",
            ) from exc
