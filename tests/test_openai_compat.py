"""Adapter tests (T1.3): OpenAI-compatible wire protocol vs fake server."""

import asyncio
import http.server
import json
import threading
from typing import ClassVar

import pytest

from chaos.bo_nao.contracts.ai_provider import AIMessage, AIRequest, Role, ToolSpec
from chaos.bo_nao.openai_compat import OpenAICompatAdapter
from chaos.cau_hinh.secrets import Secret
from chaos.ha_tang.contracts.errors import (
    ConfigurationError,
    ProviderError,
    ValidationError,
)


class ScriptedHandler(http.server.BaseHTTPRequestHandler):
    script: ClassVar[list] = []
    requests: ClassVar[list] = []
    protocol_version = "HTTP/1.1"

    def _handle(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        type(self).requests.append((self.path, dict(self.headers), json.loads(body or b"{}")))
        status, payload = type(self).script.pop(0) if type(self).script else (200, {})
        encoded = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    do_POST = _handle

    def log_message(self, *args):
        pass


@pytest.fixture()
def server():
    ScriptedHandler.script = []
    ScriptedHandler.requests = []
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ScriptedHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    thread.join()
    httpd.server_close()


def _adapter(server, **kwargs):
    params = {"name": "test", "endpoint": server, "model": "stub-model"}
    params.update(kwargs)
    return OpenAICompatAdapter(**params)


def _request(**kwargs):
    params = {"messages": (AIMessage(role=Role.USER, content="hi"),)}
    params.update(kwargs)
    return AIRequest(**params)


def _run(coro):
    return asyncio.run(coro)


def test_complete_text(server):
    ScriptedHandler.script = [
        (
            200,
            {
                "model": "stub-model",
                "choices": [{"message": {"role": "assistant", "content": "hello"}}],
                "usage": {"prompt_tokens": 3},
            },
        )
    ]
    response = _run(_adapter(server).complete(_request()))
    assert response.content == "hello"
    assert response.model == "stub-model"
    assert response.usage == {"prompt_tokens": 3}
    assert response.tool_calls == ()
    path, _headers, sent = ScriptedHandler.requests[0]
    assert path == "/chat/completions"
    assert sent["model"] == "stub-model"
    assert sent["stream"] is False
    assert "tools" not in sent


def test_complete_tool_calls(server):
    ScriptedHandler.script = [
        (
            200,
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {"name": "echo", "arguments": '{"text":"hi"}'},
                                },
                                {
                                    "id": "c2",
                                    "type": "function",
                                    "function": {"name": "noop", "arguments": "{}"},
                                },
                            ],
                        }
                    }
                ]
            },
        )
    ]
    tools = (ToolSpec(name="echo", description="e", input_schema={"type": "object"}),)
    response = _run(_adapter(server).complete(_request(tools=tools)))
    assert [c.name for c in response.tool_calls] == ["echo", "noop"]
    assert response.tool_calls[0].arguments == {"text": "hi"}
    assert response.tool_calls[0].call_id == "c1"
    _path, _headers, sent = ScriptedHandler.requests[0]
    assert sent["tools"][0]["function"]["name"] == "echo"


def test_malformed_tool_arguments_rejected(server):
    ScriptedHandler.script = [
        (
            200,
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {"id": "c", "function": {"name": "echo", "arguments": "{oops"}}
                            ],
                        }
                    }
                ]
            },
        )
    ]
    with pytest.raises(ValidationError, match="arguments"):
        _run(_adapter(server).complete(_request()))


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        {"choices": []},
        {"choices": [{"message": "oops"}]},
        {"no-choices": True},
    ],
)
def test_malformed_responses_rejected(server, payload):
    ScriptedHandler.script = [(200, payload)]
    with pytest.raises(ProviderError, match="malformed"):
        _run(_adapter(server).complete(_request()))


def test_auth_header_only_with_key(server):
    ScriptedHandler.script = [(200, {"choices": [{"message": {"content": "x"}}]})] * 2
    ScriptedHandler.requests = []
    _run(_adapter(server, api_key=Secret("k1")).complete(_request()))
    _path, headers, _sent = ScriptedHandler.requests[0]
    assert headers["Authorization"] == "Bearer k1"
    ScriptedHandler.requests = []
    _run(_adapter(server).complete(_request()))
    _path, headers, _sent = ScriptedHandler.requests[0]
    assert "Authorization" not in headers


def test_transport_errors_surface(server):
    ScriptedHandler.script = [(500, {"error": "down"})] * 10
    with pytest.raises(ProviderError):
        _run(_adapter(server, max_retries=0).complete(_request()))


def test_endpoint_and_model_validated():
    with pytest.raises(ConfigurationError):
        OpenAICompatAdapter(name="x", endpoint="ftp://h", model="m")
    with pytest.raises(ConfigurationError):
        OpenAICompatAdapter(name="x", endpoint="http://h", model="  ")
    assert "Secret" not in repr(_adapter("http://localhost:9"))


SSE_BODY = (
    b'data: {"choices": [{"delta": {"content": "he"}}]}\n'
    b'data: {"choices": [{"delta": {"content": "llo"}}]}\n'
    b'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", '
    b'"function": {"name": "echo", "arguments": "{\\"text\\""}}]}}]} \n'
    b'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, '
    b'"function": {"arguments": ":\\"hi\\"}"}}]}}]} \n'
    b"data: [DONE]\n"
)


def test_stream_deltas_then_done_with_tool_calls(server):
    ScriptedHandler.script = [(200, SSE_BODY)]

    async def _collect():
        return [chunk async for chunk in _adapter(server).stream(_request())]

    chunks = _run(_collect())
    assert [c.delta for c in chunks[:-1]] == ["he", "llo"]
    assert chunks[-1].done is True
    assert len(chunks[-1].tool_calls) == 1
    call = chunks[-1].tool_calls[0]
    assert (call.name, call.arguments, call.call_id) == ("echo", {"text": "hi"}, "c1")
    _path, _headers, sent = ScriptedHandler.requests[0]
    assert sent["stream"] is True


def test_stream_without_done_rejected(server):
    ScriptedHandler.script = [(200, b'data: {"choices": [{"delta": {"content": "x"}}]}\n')]

    async def _collect():
        return [chunk async for chunk in _adapter(server).stream(_request())]

    with pytest.raises(ProviderError, match="without completion"):
        _run(_collect())


def test_stream_malformed_line_rejected(server):
    ScriptedHandler.script = [(200, b"data: {broken\n")]

    async def _collect():
        return [chunk async for chunk in _adapter(server).stream(_request())]

    with pytest.raises(ProviderError, match="malformed"):
        _run(_collect())
