from __future__ import annotations

import json
from time import perf_counter
from urllib import error, request as urllib_request
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import Settings
from app.schemas import ChatCompletionRequest, ChatToolCall, ChatToolFunction, EmbeddingsRequest, ProviderConfig, ProviderResponse
from app.secrets import resolve_provider_api_key


class OpenAIProvider:
    def __init__(self, settings: Settings):
        self._settings = settings

    def complete(
        self,
        model: str,
        request: ChatCompletionRequest,
        provider_config: ProviderConfig | None = None,
    ) -> ProviderResponse:
        provider_type = provider_config.provider_type if provider_config else "openai"
        api_key = resolve_provider_api_key(
            provider_type=provider_type,
            explicit_value=provider_config.api_key if provider_config else None,
            settings=self._settings,
        )
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{provider_type.capitalize()} provider is enabled but no API key is configured",
            )

        payload = {
            "model": model,
            "messages": [self._serialize_message(message) for message in request.messages],
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

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        if provider_type == "openai":
            organization = provider_config.organization if provider_config and provider_config.organization else self._settings.openai_organization
            project = provider_config.project if provider_config and provider_config.project else self._settings.openai_project
            if organization:
                headers["OpenAI-Organization"] = organization
            if project:
                headers["OpenAI-Project"] = project

        default_base_url = self._settings.kimi_base_url if provider_type == "kimi" else self._settings.openai_base_url
        default_timeout = self._settings.kimi_timeout_seconds if provider_type == "kimi" else self._settings.openai_timeout_seconds
        base_url = provider_config.base_url if provider_config and provider_config.base_url else default_base_url
        timeout_seconds = (
            provider_config.timeout_seconds
            if provider_config and provider_config.timeout_seconds is not None
            else default_timeout
        )
        endpoint = base_url.rstrip("/") + "/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib_request.Request(endpoint, data=body, headers=headers, method="POST")
        started = perf_counter()

        try:
            with urllib_request.urlopen(http_request, timeout=timeout_seconds) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(
                status_code=exc.code,
                detail=f"OpenAI API error: {detail}",
            ) from exc
        except error.URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"OpenAI API unreachable: {exc.reason}",
            ) from exc

        latency_ms = int((perf_counter() - started) * 1000)
        choice = raw_payload.get("choices", [{}])[0]
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

    def embed(self, model: str, request: EmbeddingsRequest, provider_config: ProviderConfig | None = None) -> dict:
        provider_type = provider_config.provider_type if provider_config else "openai"
        api_key = resolve_provider_api_key(
            provider_type=provider_type,
            explicit_value=provider_config.api_key if provider_config else None,
            settings=self._settings,
        )
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{provider_type.capitalize()} provider has no API key configured",
            )

        payload: dict = {"model": model, "input": request.input}
        if request.user:
            payload["user"] = request.user
        if request.encoding_format:
            payload["encoding_format"] = request.encoding_format
        if request.dimensions:
            payload["dimensions"] = request.dimensions

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        if provider_type == "openai":
            org = provider_config.organization if provider_config and provider_config.organization else self._settings.openai_organization
            proj = provider_config.project if provider_config and provider_config.project else self._settings.openai_project
            if org:
                headers["OpenAI-Organization"] = org
            if proj:
                headers["OpenAI-Project"] = proj

        default_base = self._settings.kimi_base_url if provider_type == "kimi" else self._settings.openai_base_url
        default_timeout = self._settings.kimi_timeout_seconds if provider_type == "kimi" else self._settings.openai_timeout_seconds
        base_url = provider_config.base_url if provider_config and provider_config.base_url else default_base
        timeout = provider_config.timeout_seconds if provider_config and provider_config.timeout_seconds is not None else default_timeout

        endpoint = base_url.rstrip("/") + "/embeddings"
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib_request.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with urllib_request.urlopen(http_request, timeout=timeout) as response:
                try:
                    return json.loads(response.read().decode("utf-8"))
                except json.JSONDecodeError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="OpenAI API returned non-JSON response",
                    ) from exc
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(status_code=exc.code, detail=f"OpenAI API error: {detail}") from exc
        except error.URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"OpenAI API unreachable: {exc.reason}",
            ) from exc

    def list_models(self, provider_config: ProviderConfig | None = None) -> list[str]:
        provider_type = provider_config.provider_type if provider_config else "openai"
        api_key = resolve_provider_api_key(
            provider_type=provider_type,
            explicit_value=provider_config.api_key if provider_config else None,
            settings=self._settings,
        )
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{provider_type.capitalize()} provider is enabled but no API key is configured",
            )

        headers = {"Authorization": f"Bearer {api_key}"}
        if provider_type == "openai":
            organization = provider_config.organization if provider_config and provider_config.organization else self._settings.openai_organization
            project = provider_config.project if provider_config and provider_config.project else self._settings.openai_project
            if organization:
                headers["OpenAI-Organization"] = organization
            if project:
                headers["OpenAI-Project"] = project

        default_base_url = self._settings.kimi_base_url if provider_type == "kimi" else self._settings.openai_base_url
        default_timeout = self._settings.kimi_timeout_seconds if provider_type == "kimi" else self._settings.openai_timeout_seconds
        base_url = provider_config.base_url if provider_config and provider_config.base_url else default_base_url
        timeout_seconds = (
            provider_config.timeout_seconds
            if provider_config and provider_config.timeout_seconds is not None
            else default_timeout
        )
        endpoint = base_url.rstrip("/") + "/models"
        http_request = urllib_request.Request(endpoint, headers=headers, method="GET")
        try:
            with urllib_request.urlopen(http_request, timeout=timeout_seconds) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(
                status_code=exc.code,
                detail=f"OpenAI API error: {detail}",
            ) from exc
        except error.URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"OpenAI API unreachable: {exc.reason}",
            ) from exc

        return [item["id"] for item in raw_payload.get("data", []) if item.get("id")]

    def _serialize_message(self, message):
        payload = {"role": message.role}
        if message.content is not None:
            payload["content"] = message.content
        if message.name:
            payload["name"] = message.name
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            payload["tool_calls"] = [tool_call.model_dump(exclude_none=True) for tool_call in message.tool_calls]
        return payload

    def _coerce_content(self, content) -> str | None:
        if content is None:
            return None
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("text"):
                    chunks.append(str(item["text"]))
            return "\n".join(chunks) if chunks else None
        return str(content)

    def _parse_tool_calls(self, tool_calls):
        parsed: list[ChatToolCall] = []
        for index, tool_call in enumerate(tool_calls):
            function = tool_call.get("function", {})
            parsed.append(
                ChatToolCall(
                    id=tool_call.get("id") or f"call_{uuid4().hex}",
                    index=tool_call.get("index", index),
                    function=ChatToolFunction(
                        name=function.get("name", "unknown"),
                        arguments=function.get("arguments", "{}"),
                    ),
                )
            )
        return parsed
