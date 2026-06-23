from __future__ import annotations

import json
from urllib import error, request as urllib_request

from fastapi import HTTPException, status

from app.config import Settings
from app.schemas import SearchRequest, SearchResponse, SearchSource


class SearchService:
    def __init__(self, settings: Settings):
        self._settings = settings

    def search(self, request: SearchRequest) -> SearchResponse:
        provider = self._settings.search_provider
        if provider == "exa" and self._settings.search_exa_api_key:
            return self._search_exa(request)
        if self._settings.search_tavily_api_key:
            return self._search_tavily(request)
        if self._settings.search_exa_api_key:
            return self._search_exa(request)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No search provider configured (set LLM_CP_SEARCH_TAVILY_API_KEY or LLM_CP_SEARCH_EXA_API_KEY)",
        )

    def _search_tavily(self, request: SearchRequest) -> SearchResponse:
        payload: dict = {
            "api_key": self._settings.search_tavily_api_key,
            "query": request.query,
            "max_results": request.limit,
            "search_depth": "advanced" if request.search_depth == "deep" else "basic",
        }
        if request.recency:
            payload["days"] = _recency_to_days(request.recency)

        raw = self._post(self._settings.search_tavily_endpoint, payload)
        sources: list[SearchSource] = []
        for item in raw.get("results", []):
            snippet = item.get("content", "") or ""
            if request.max_content_chars and len(snippet) > request.max_content_chars:
                snippet = snippet[: request.max_content_chars]
            sources.append(SearchSource(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=snippet or None,
            ))
        return SearchResponse(sources=sources)

    def _search_exa(self, request: SearchRequest) -> SearchResponse:
        payload: dict = {
            "query": request.query,
            "numResults": request.limit,
            "contents": {"text": {"maxCharacters": request.max_content_chars}},
        }
        if request.recency:
            days = _recency_to_days(request.recency)
            from datetime import datetime, timedelta, timezone
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
            payload["startPublishedDate"] = cutoff

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._settings.search_exa_api_key or "",
        }
        raw = self._post(self._settings.search_exa_endpoint, payload, headers=headers)
        sources: list[SearchSource] = []
        for item in raw.get("results", []):
            snippet = (item.get("text") or "")
            if request.max_content_chars and len(snippet) > request.max_content_chars:
                snippet = snippet[: request.max_content_chars]
            sources.append(SearchSource(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=snippet or None,
            ))
        return SearchResponse(sources=sources)

    def _post(self, endpoint: str, payload: dict, headers: dict | None = None) -> dict:
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)
        body = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(endpoint, data=body, headers=default_headers, method="POST")
        try:
            with urllib_request.urlopen(req, timeout=self._settings.search_timeout_seconds) as resp:
                try:
                    return json.loads(resp.read().decode("utf-8"))
                except json.JSONDecodeError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Search API returned non-JSON response",
                    ) from exc
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(status_code=exc.code, detail=f"Search API error: {detail}") from exc
        except error.URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Search API unreachable: {exc.reason}",
            ) from exc


def _recency_to_days(recency: str) -> int:
    return {"day": 1, "week": 7, "month": 30, "year": 365}.get(recency, 30)
