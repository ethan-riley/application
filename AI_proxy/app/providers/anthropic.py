from __future__ import annotations

import json
from time import perf_counter
from urllib import error, request as urllib_request
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import Settings
from app.schemas import ChatCompletionRequest, ChatToolCall, ChatToolFunction, ProviderConfig, ProviderResponse
from app.secrets import resolve_provider_api_key


class AnthropicProvider:
    def __init__(self, settings: Settings):
        self._settings = settings

    def complete(
        self,
        model: str,
        request: ChatCompletionRequest,
        provider_config: ProviderConfig | None = None,
    ) -> ProviderResponse:
        api_key = resolve_provider_api_key(
            provider_type="anthropic",
            explicit_value=provider_config.api_key if provider_config else None,
            settings=self._settings,
        )
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Anthropic provider is enabled but no API key is configured",
            )

        system_prompt, messages = self._serialize_messages(request)
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens or 512,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.tools:
            payload["tools"] = [
                {
                    "name": tool.function.name,
                    "description": tool.function.description,
                    "input_schema": tool.function.parameters or {"type": "object", "properties": {}},
                }
                for tool in request.tools
            ]
        if request.tool_choice is not None:
            payload["tool_choice"] = self._serialize_tool_choice(request.tool_choice)

        raw_payload = self._request(
            method="POST",
            path="/messages",
            api_key=api_key,
            provider_config=provider_config,
            payload=payload,
        )

        text_chunks: list[str] = []
        tool_calls: list[ChatToolCall] = []
        for index, block in enumerate(raw_payload.get("content", [])):
            if block.get("type") == "text" and block.get("text"):
                text_chunks.append(str(block["text"]))
                continue
            if block.get("type") == "tool_use":
                arguments = block.get("input", {})
                if not isinstance(arguments, str):
                    arguments = json.dumps(arguments)
                tool_calls.append(
                    ChatToolCall(
                        id=block.get("id") or f"call_{uuid4().hex}",
                        index=index,
                        function=ChatToolFunction(
                            name=block.get("name", "unknown"),
                            arguments=arguments,
                        ),
                    )
                )

        usage = raw_payload.get("usage", {})
        return ProviderResponse(
            model=raw_payload.get("model", model),
            content="\n".join(text_chunks) if text_chunks else None,
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            latency_ms=raw_payload.get("_latency_ms", 0),
            finish_reason="tool_calls" if tool_calls else raw_payload.get("stop_reason", "stop"),
            tool_calls=tool_calls,
            raw=raw_payload,
        )

    def messages_passthrough(self, body: dict, provider_config: ProviderConfig | None = None) -> dict:
        api_key = resolve_provider_api_key(
            provider_type="anthropic",
            explicit_value=provider_config.api_key if provider_config else None,
            settings=self._settings,
        )
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Anthropic provider is enabled but no API key is configured",
            )
        return self._request("POST", "/messages", api_key=api_key, provider_config=provider_config, payload=body)

    def count_tokens(self, body: dict, provider_config: ProviderConfig | None = None) -> dict:
        api_key = resolve_provider_api_key(
            provider_type="anthropic",
            explicit_value=provider_config.api_key if provider_config else None,
            settings=self._settings,
        )
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Anthropic provider is enabled but no API key is configured",
            )
        return self._request("POST", "/messages/count_tokens", api_key=api_key, provider_config=provider_config, payload=body)

    def list_models(self, provider_config: ProviderConfig | None = None) -> list[str]:
        api_key = resolve_provider_api_key(
            provider_type="anthropic",
            explicit_value=provider_config.api_key if provider_config else None,
            settings=self._settings,
        )
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Anthropic provider is enabled but no API key is configured",
            )

        raw_payload = self._request(
            method="GET",
            path="/models",
            api_key=api_key,
            provider_config=provider_config,
        )
        return [item["id"] for item in raw_payload.get("data", []) if item.get("id")]

    def _serialize_messages(self, request: ChatCompletionRequest) -> tuple[str | None, list[dict]]:
        system_chunks: list[str] = []
        messages: list[dict] = []

        for message in request.messages:
            if message.role == "system":
                if message.content:
                    system_chunks.append(message.content)
                continue
            if message.role == "tool":
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message.tool_call_id,
                                "content": message.content or "",
                            }
                        ],
                    }
                )
                continue
            if message.role == "assistant" and message.tool_calls:
                content_blocks = []
                if message.content:
                    content_blocks.append({"type": "text", "text": message.content})
                for tool_call in message.tool_calls:
                    arguments = tool_call.function.arguments
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            arguments = {"raw_arguments": arguments}
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tool_call.id,
                            "name": tool_call.function.name,
                            "input": arguments,
                        }
                    )
                messages.append({"role": "assistant", "content": content_blocks or [{"type": "text", "text": ""}]})
                continue
            messages.append(
                {
                    "role": message.role,
                    "content": [{"type": "text", "text": message.content or ""}],
                }
            )

        return ("\n\n".join(system_chunks) if system_chunks else None, messages)

    def _serialize_tool_choice(self, tool_choice: str | dict) -> dict | None:
        if isinstance(tool_choice, dict):
            if tool_choice.get("type") == "function":
                function = tool_choice.get("function", {})
                if function.get("name"):
                    return {"type": "tool", "name": function["name"]}
            return tool_choice
        if tool_choice == "required":
            return {"type": "any"}
        if tool_choice == "auto":
            return {"type": "auto"}
        return None

    def _request(
        self,
        method: str,
        path: str,
        api_key: str,
        provider_config: ProviderConfig | None = None,
        payload: dict | None = None,
    ) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": self._settings.anthropic_version,
        }
        base_url = provider_config.base_url if provider_config and provider_config.base_url else self._settings.anthropic_base_url
        timeout_seconds = (
            provider_config.timeout_seconds
            if provider_config and provider_config.timeout_seconds is not None
            else self._settings.anthropic_timeout_seconds
        )
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        endpoint = base_url.rstrip("/") + path
        http_request = urllib_request.Request(endpoint, data=body, headers=headers, method=method)
        started = perf_counter()
        try:
            with urllib_request.urlopen(http_request, timeout=timeout_seconds) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(
                status_code=exc.code,
                detail=f"Anthropic API error: {detail}",
            ) from exc
        except error.URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Anthropic API unreachable: {exc.reason}",
            ) from exc

        raw_payload["_latency_ms"] = int((perf_counter() - started) * 1000)
        return raw_payload
