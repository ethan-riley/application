from __future__ import annotations

import json
from time import perf_counter
from urllib import error, request as urllib_request
from uuid import uuid4

from fastapi import HTTPException, status

from app.providers.openai import OpenAIProvider
from app.schemas import ChatCompletionRequest, ProviderConfig, ProviderResponse
from app.secrets import resolve_provider_api_key


class AzureOpenAIProvider(OpenAIProvider):
    def complete(
        self,
        model: str,
        request: ChatCompletionRequest,
        provider_config: ProviderConfig | None = None,
    ) -> ProviderResponse:
        api_key = resolve_provider_api_key(
            provider_type="azure_openai",
            explicit_value=provider_config.api_key if provider_config else None,
            settings=self._settings,
        )
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Azure OpenAI provider is enabled but no API key is configured",
            )

        base_url = (
            provider_config.base_url
            if provider_config and provider_config.base_url
            else self._settings.azure_openai_base_url
        )
        if not base_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Azure OpenAI provider requires a base URL (set LLM_CP_AZURE_OPENAI_BASE_URL)",
            )
        api_version = (
            (provider_config.labels or {}).get("api_version")
            if provider_config
            else None
        ) or self._settings.azure_openai_api_version
        timeout_seconds = (
            provider_config.timeout_seconds
            if provider_config and provider_config.timeout_seconds is not None
            else self._settings.azure_openai_timeout_seconds
        )

        payload = {
            "messages": [self._serialize_message(m) for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }
        if request.tools:
            payload["tools"] = [tool.model_dump() for tool in request.tools]
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice
        if request.parallel_tool_calls is not None:
            payload["parallel_tool_calls"] = request.parallel_tool_calls

        endpoint = (
            f"{base_url.rstrip('/')}/openai/deployments/{model}"
            f"/chat/completions?api-version={api_version}"
        )
        headers = {
            "Content-Type": "application/json",
            "api-key": api_key,
        }

        body = json.dumps(payload).encode("utf-8")
        http_request = urllib_request.Request(endpoint, data=body, headers=headers, method="POST")
        started = perf_counter()

        try:
            with urllib_request.urlopen(http_request, timeout=timeout_seconds) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(status_code=exc.code, detail=f"Azure OpenAI API error: {detail}") from exc
        except error.URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Azure OpenAI API unreachable: {exc.reason}",
            ) from exc

        latency_ms = int((perf_counter() - started) * 1000)
        choice = (raw_payload.get("choices") or [{}])[0]
        message = choice.get("message", {})
        usage = raw_payload.get("usage", {})
        tool_calls = self._parse_tool_calls(message.get("tool_calls", []))

        return ProviderResponse(
            model=raw_payload.get("model", model),
            content=self._coerce_content(message.get("content")),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
            finish_reason=choice.get("finish_reason", "tool_calls" if tool_calls else "stop"),
            tool_calls=tool_calls,
            raw=raw_payload,
        )
