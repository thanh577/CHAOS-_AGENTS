"""OpenAI-compatible chat adapter — the M1 reference AI provider.

Speaks the open chat-completions wire protocol (JSON over HTTP, SSE
for streaming) so it works against any compatible endpoint, not just
one vendor: no vendor SDK, no vendor lock-in. Other adapters implement
the same :class:`AIProvider` contract and register by name.

Streaming note: the transport delivers the full SSE body; this adapter
parses it and yields deltas incrementally per the contract. True
incremental network delivery is deferred (documented, reversible).
"""

import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlsplit

from chaos.bo_nao.contracts.ai_provider import (
    AIMessage,
    AIProvider,
    AIRequest,
    AIResponse,
    AIStreamChunk,
    Role,
    ToolSpec,
)
from chaos.bo_nao.http_transport import apost_with_retry
from chaos.cau_hinh.secrets import Secret
from chaos.ha_tang.contracts.common import ToolCall
from chaos.ha_tang.contracts.errors import (
    ConfigurationError,
    ProviderError,
    ValidationError,
)

_COMPLETIONS_PATH = "/chat/completions"


def _role_to_wire(role: Role) -> str:
    return role.value


def _message_to_wire(message: AIMessage) -> dict[str, Any]:
    wire: dict[str, Any] = {"role": _role_to_wire(message.role), "content": message.content}
    if message.tool_calls:
        wire["tool_calls"] = [
            {
                "id": call.call_id or "",
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(dict(call.arguments))},
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        wire["tool_call_id"] = message.tool_call_id
    return wire


def _tools_to_wire(tools: tuple[ToolSpec, ...]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": dict(tool.input_schema) or {"type": "object"},
            },
        }
        for tool in tools
    ]


def _parse_tool_calls(raw_calls: Any) -> tuple[ToolCall, ...]:
    if not raw_calls:
        return ()
    if not isinstance(raw_calls, list):
        raise ValidationError("provider tool_calls must be a list")
    parsed: list[ToolCall] = []
    for call in raw_calls:
        if not isinstance(call, dict):
            raise ValidationError("provider tool call must be an object")
        function = call.get("function", {})
        if not isinstance(function, dict) or not function.get("name"):
            raise ValidationError("provider tool call lacks a function name")
        raw_arguments = function.get("arguments") or "{}"
        try:
            arguments = (
                json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            )
        except ValueError as exc:
            raise ValidationError("provider tool arguments are not valid JSON") from exc
        if not isinstance(arguments, dict):
            raise ValidationError("provider tool arguments must be a JSON object")
        call_id = call.get("id")
        parsed.append(
            ToolCall(
                name=str(function["name"]),
                arguments=arguments,
                call_id=str(call_id) if call_id is not None else None,
            )
        )
    return tuple(parsed)


def _parse_response(body: bytes) -> AIResponse:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProviderError("malformed provider response") from exc
    if not isinstance(payload, dict):
        raise ProviderError("malformed provider response")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderError("malformed provider response")
    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        raise ProviderError("malformed provider response")
    content = message.get("content") or ""
    usage = payload.get("usage")
    model = payload.get("model")
    return AIResponse(
        content=str(content),
        tool_calls=_parse_tool_calls(message.get("tool_calls")),
        model=str(model) if model is not None else None,
        usage=dict(usage) if isinstance(usage, dict) else {},
    )


def _parse_sse(body: bytes) -> tuple[list[AIStreamChunk], tuple[ToolCall, ...]]:
    """Parse an SSE body into content chunks plus assembled tool calls."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProviderError("malformed provider stream") from exc
    chunks: list[AIStreamChunk] = []
    fragments: dict[int, dict[str, str]] = {}
    done = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(":"):
            continue
        if not stripped.startswith("data:"):
            continue
        data = stripped[len("data:") :].strip()
        if data == "[DONE]":
            done = True
            break
        try:
            event = json.loads(data)
        except ValueError as exc:
            raise ProviderError("malformed provider stream") from exc
        if not isinstance(event, dict):
            raise ProviderError("malformed provider stream")
        choices = event.get("choices", [])
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            continue
        delta = choices[0].get("delta", {})
        if not isinstance(delta, dict):
            continue
        content = delta.get("content")
        if content:
            chunks.append(AIStreamChunk(delta=str(content)))
        for raw_call in delta.get("tool_calls") or []:
            if not isinstance(raw_call, dict):
                raise ProviderError("malformed provider stream")
            index = raw_call.get("index", 0)
            fragment = fragments.setdefault(index, {"id": "", "name": "", "arguments": ""})
            function = raw_call.get("function", {})
            if not isinstance(function, dict):
                raise ProviderError("malformed provider stream")
            if raw_call.get("id"):
                fragment["id"] = str(raw_call["id"])
            if function.get("name"):
                fragment["name"] = str(function["name"])
            arguments = function.get("arguments")
            if arguments:
                fragment["arguments"] += str(arguments)
    if not done:
        raise ProviderError("provider stream ended without completion")
    tool_calls: list[ToolCall] = []
    for index in sorted(fragments):
        fragment = fragments[index]
        if not fragment["name"]:
            raise ProviderError("provider stream tool call lacks a name")
        try:
            arguments = json.loads(fragment["arguments"] or "{}")
        except ValueError as exc:
            raise ProviderError("provider stream tool arguments are not valid JSON") from exc
        if not isinstance(arguments, dict):
            raise ProviderError("provider stream tool arguments must be a JSON object")
        tool_calls.append(
            ToolCall(
                name=fragment["name"],
                arguments=arguments,
                call_id=fragment["id"] or None,
            )
        )
    return chunks, tuple(tool_calls)


class OpenAICompatAdapter(AIProvider):
    """Reference adapter for OpenAI-compatible chat endpoints."""

    def __init__(
        self,
        *,
        name: str,
        endpoint: str,
        model: str,
        api_key: Secret | None = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        backoff_base_seconds: float = 1.0,
    ) -> None:
        try:
            parts = urlsplit(endpoint)
        except ValueError as exc:
            raise ConfigurationError(f"invalid provider endpoint: {endpoint!r}") from exc
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ConfigurationError(f"invalid provider endpoint: {endpoint!r}")
        if not model.strip():
            raise ConfigurationError("provider model must not be empty")
        self._name = name
        self._endpoint = endpoint.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds

    def __repr__(self) -> str:
        return f"OpenAICompatAdapter(name={self._name!r}, model={self._model!r})"

    @property
    def name(self) -> str:
        return self._name

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key.expose()}"
        return headers

    def _payload(self, request: AIRequest, *, stream: bool) -> bytes:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [_message_to_wire(message) for message in request.messages],
            "stream": stream,
        }
        if request.tools:
            body["tools"] = _tools_to_wire(request.tools)
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            body["temperature"] = request.temperature
        return json.dumps(body).encode("utf-8")

    def _transport_kwargs(self, request: AIRequest) -> dict[str, Any]:
        return {
            "timeout_seconds": request.timeout_seconds,
            "max_retries": self._max_retries,
            "backoff_base_seconds": self._backoff_base_seconds,
        }

    async def complete(self, request: AIRequest) -> AIResponse:
        """Run one non-streaming turn."""
        response = await apost_with_retry(
            self._endpoint + _COMPLETIONS_PATH,
            self._payload(request, stream=False),
            self._headers(),
            **self._transport_kwargs(request),
        )
        return _parse_response(response.body)

    async def stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        """Run one streaming turn, yielding deltas until ``done``."""
        response = await apost_with_retry(
            self._endpoint + _COMPLETIONS_PATH,
            self._payload(request, stream=True),
            self._headers(),
            **self._transport_kwargs(request),
        )
        chunks, tool_calls = _parse_sse(response.body)
        for chunk in chunks:
            yield chunk
        yield AIStreamChunk(tool_calls=tool_calls, done=True)


__all__ = ["OpenAICompatAdapter"]
