"""HTTP transport tests (T1.2): scripted fake server, no outside network."""

import http.server
import threading
import time
from typing import ClassVar

import pytest

from chaos.bo_nao import http_transport
from chaos.bo_nao.http_transport import apost_with_retry, post, post_with_retry
from chaos.ha_tang.contracts.errors import (
    ConfigurationError,
    OperationTimeoutError,
    ProviderError,
)


class ScriptedHandler(http.server.BaseHTTPRequestHandler):
    """Serves queued (status, headers, body) scripts; records requests."""

    script: ClassVar[list] = []
    requests: ClassVar[list] = []
    protocol_version = "HTTP/1.1"

    def _handle(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        type(self).requests.append((self.path, dict(self.headers), body))
        if type(self).script:
            status, headers, payload = type(self).script.pop(0)
        else:
            status, headers, payload = (200, {}, b"{}")
        if isinstance(payload, tuple):  # ("sleep", seconds) for timeout tests
            time.sleep(payload[1])
            payload = b"{}"
        encoded = payload if isinstance(payload, bytes) else payload.encode()
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
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


def _call(url, **kwargs):
    params = {"timeout_seconds": 5.0, "max_retries": 3, "backoff_base_seconds": 0}
    params.update(kwargs)
    return post_with_retry(url, b'{"a":1}', {"Content-Type": "application/json"}, **params)


def test_success_passthrough(server):
    ScriptedHandler.script = [(200, {"X-Test": "yes"}, b'{"ok":true}')]
    response = _call(server + "/v1/chat")
    assert response.status == 200
    assert response.body == b'{"ok":true}'
    path, _headers, body = ScriptedHandler.requests[0]
    assert path == "/v1/chat"
    assert body == b'{"a":1}'


def test_retry_after_honored_then_success(server):
    ScriptedHandler.script = [(429, {"Retry-After": "0"}, b"slow"), (200, {}, b"fine")]
    assert _call(server).body == b"fine"
    assert len(ScriptedHandler.requests) == 2


def test_500_retries_then_success(server):
    ScriptedHandler.script = [(500, {}, b"e"), (503, {}, b"e"), (200, {}, b"ok")]
    assert _call(server).body == b"ok"
    assert len(ScriptedHandler.requests) == 3


def test_persistent_500_fails_after_bounded_attempts(server):
    ScriptedHandler.script = [(500, {}, b"e")] * 10
    with pytest.raises(ProviderError):
        _call(server, max_retries=2)
    assert len(ScriptedHandler.requests) == 3  # 1 + 2 retries, then stop


def test_persistent_429_exhaustion(server):
    ScriptedHandler.script = [(429, {}, b"busy")] * 10
    with pytest.raises(ProviderError, match="rate limit"):
        _call(server, max_retries=1)
    assert len(ScriptedHandler.requests) == 2


def test_client_errors_never_retried(server):
    for status in (400, 401, 403, 404, 422):
        ScriptedHandler.script = [(status, {}, b"nope")] * 5
        ScriptedHandler.requests = []
        with pytest.raises(ProviderError, match=f"status {status}"):
            _call(server)
        assert len(ScriptedHandler.requests) == 1


def test_timeout_maps_and_retries_bounded(server):
    ScriptedHandler.script = [(200, {}, ("sleep", 3))] * 5
    with pytest.raises(OperationTimeoutError):
        _call(server, timeout_seconds=0.2, max_retries=1, backoff_base_seconds=0)
    assert len(ScriptedHandler.requests) == 2


def test_connection_refused_maps_to_provider_error():
    with pytest.raises(ProviderError, match="cannot reach"):
        post_with_retry(
            "http://127.0.0.1:1/unreachable",
            b"{}",
            {},
            timeout_seconds=1.0,
            max_retries=0,
            backoff_base_seconds=0,
        )


@pytest.mark.parametrize("url", ["ftp://x/y", "file:///etc/passwd", "not-a-url", "http://"])
def test_bad_urls_rejected_without_connecting(url):
    with pytest.raises(ConfigurationError):
        post(url, b"{}", {}, 1.0)


def test_backoff_schedule_is_exponential(monkeypatch, server):
    ScriptedHandler.script = [(500, {}, b"e")] * 10
    sleeps: list[float] = []
    monkeypatch.setattr(http_transport.time, "sleep", sleeps.append)
    with pytest.raises(ProviderError):
        _call(server, max_retries=3, backoff_base_seconds=0.5)
    assert sleeps == [0.5, 1.0, 2.0]


def test_body_size_limit_enforced(monkeypatch, server):
    monkeypatch.setattr(http_transport, "MAX_BODY_BYTES", 4)
    ScriptedHandler.script = [(200, {}, b"too-long-body")]
    with pytest.raises(ProviderError, match="size limit"):
        _call(server, max_retries=0)


def test_async_wrapper(server):
    import asyncio

    ScriptedHandler.script = [(200, {}, b"async-ok")]

    async def _run():
        return await apost_with_retry(
            server,
            b"{}",
            {},
            timeout_seconds=5.0,
            max_retries=0,
            backoff_base_seconds=0,
        )

    assert asyncio.run(_run()).body == b"async-ok"


def test_single_post_returns_status_without_policy(server):
    ScriptedHandler.script = [(500, {}, b"e")] * 3
    ScriptedHandler.requests = []
    response = post(server, b"{}", {}, 5.0)
    assert response.status == 500  # post() never retries; policy lives in post_with_retry
    assert len(ScriptedHandler.requests) == 1
