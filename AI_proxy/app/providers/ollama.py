from __future__ import annotations

import json
from time import perf_counter
from urllib import error, request as urllib_request
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import Settings
from app.schemas import ChatCompletionRequest, ChatToolCall, ChatToolFunction, ProviderConfig, ProviderResponse


class OllamaProvider:
    def __init__(self, settings: Settings):
        self._settings = settings

    def complete(
        self,
        model: str,
        request: ChatCompletionRequest,
        provider_config: ProviderConfig | None = None,
    ) -> ProviderResponse:
        payload = {
            "model": model,
            "messages": [self._serialize_message(message) for message in request.messages],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        if request.tools:
            payload["tools"] = [tool.model_dump() for tool in request.tools]

        base_url = provider_config.base_url if provider_config and provider_config.base_url else self._settings.ollama_base_url
        timeout_seconds = (
            provider_config.timeout_seconds
            if provider_config and provider_config.timeout_seconds is not None
            else self._settings.ollama_timeout_seconds
        )
        endpoint = base_url.rstrip("/") + "/api/chat"
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib_request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = perf_counter()

        try:
            with urllib_request.urlopen(http_request, timeout=timeout_seconds) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(
                status_code=exc.code,
                detail=f"Ollama API error: {detail}",
            ) from exc
        except error.URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Ollama API unreachable: {exc.reason}",
            ) from exc

        latency_ms = int((perf_counter() - started) * 1000)
        message = raw_payload.get("message", {})
        prompt_tokens = raw_payload.get("prompt_eval_count", 0)
        completion_tokens = raw_payload.get("eval_count", 0)
        tool_calls = self._parse_tool_calls(message.get("tool_calls", []))
        finish_reason = raw_payload.get("done_reason") or ("tool_calls" if tool_calls else "stop")

        return ProviderResponse(
            model=raw_payload.get("model", model),
            content=message.get("content"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            raw=raw_payload,
        )

    def _serialize_message(self, message):
        payload = {"role": message.role}
        if message.content is not None:
            payload["content"] = message.content
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            payload["tool_calls"] = [tool_call.model_dump(exclude_none=True) for tool_call in message.tool_calls]
        return payload

    def _parse_tool_calls(self, tool_calls):
        parsed: list[ChatToolCall] = []
        for index, tool_call in enumerate(tool_calls):
            function = tool_call.get("function", tool_call)
            arguments = function.get("arguments", {})
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments)
            parsed.append(
                ChatToolCall(
                    id=tool_call.get("id") or f"call_{uuid4().hex}",
                    index=index,
                    function=ChatToolFunction(
                        name=function.get("name", "unknown"),
                        arguments=arguments,
                    ),
                )
            )
        return parsed
