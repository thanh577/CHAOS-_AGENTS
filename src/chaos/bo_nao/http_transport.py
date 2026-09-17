"""HTTP transport for the Cloud Brain (stdlib only, no SDK).

Sync core over :mod:`http.client` plus a thin async wrapper via
:func:`asyncio.to_thread` — no aiohttp/httpx, so M1 adds zero
dependencies. Timeouts are socket-level (no thread leaks from
abandoned awaits); retries are bounded with exponential backoff.

Retry policy (deterministic, tested):
- 429 → honor ``Retry-After`` seconds (capped), else backoff;
- 5xx / connection errors / socket timeouts → backoff, then fail;
- other 4xx → fail immediately, never retried;
- attempts total = 1 + ``max_retries``.

Error mapping: rate-limit exhaustion and provider HTTP failures →
``ProviderError``; timeouts → ``OperationTimeoutError``; bad URLs →
``ConfigurationError``. Messages carry status codes only — bodies and
headers are never embedded or logged here.
"""

import asyncio
import http.client
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from chaos.ha_tang.contracts.errors import (
    ConfigurationError,
    OperationTimeoutError,
    ProviderError,
)

MAX_BODY_BYTES = 10 * 1024 * 1024
RETRY_AFTER_CAP_SECONDS = 60.0
BACKOFF_CAP_SECONDS = 30.0

_UNREACHABLE = "cannot reach provider"


@dataclass(frozen=True)
class HttpResponse:
    """One completed HTTP exchange. Body kept as bytes; decoding is the
    adapter's job (it knows the content type)."""

    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""


def _split_url(url: str) -> tuple[str, str, int, str]:
    """Return (scheme, host, port, path). Only http/https allowed."""
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise ConfigurationError(f"invalid provider URL: {url!r}") from exc
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ConfigurationError(f"invalid provider URL: {url!r}")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    path = parts.path or "/"
    if parts.query:
        path += f"?{parts.query}"
    return parts.scheme, parts.hostname, port, path


def post(url: str, body: bytes, headers: Mapping[str, str], timeout_seconds: float) -> HttpResponse:
    """Single POST attempt, no retry. Raises mapped CHAOS errors."""
    scheme, host, port, path = _split_url(url)
    connection_class = (
        http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
    )
    try:
        connection = connection_class(host, port, timeout=timeout_seconds)
    except OSError as exc:
        raise ProviderError(_UNREACHABLE) from exc
    try:
        connection.request("POST", path, body=body, headers=dict(headers))
        response = connection.getresponse()
        raw = response.read(MAX_BODY_BYTES + 1)
    except TimeoutError as exc:  # socket.timeout aliases the builtin since 3.10
        raise OperationTimeoutError("provider request timed out") from exc
    except (OSError, http.client.HTTPException) as exc:
        raise ProviderError(_UNREACHABLE) from exc
    finally:
        connection.close()
    if len(raw) > MAX_BODY_BYTES:
        raise ProviderError("provider response exceeds size limit")
    response_headers = {key.lower(): value for key, value in response.getheaders()}
    return HttpResponse(status=response.status, headers=response_headers, body=raw)


def _retry_after_seconds(headers: Mapping[str, str]) -> float | None:
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        delay = float(raw.strip())
    except ValueError:
        return None
    if delay < 0:
        return None
    return min(delay, RETRY_AFTER_CAP_SECONDS)


def post_with_retry(
    url: str,
    body: bytes,
    headers: Mapping[str, str],
    *,
    timeout_seconds: float,
    max_retries: int,
    backoff_base_seconds: float,
) -> HttpResponse:
    """POST with bounded retries per the module policy."""
    attempt = 0
    while True:
        try:
            response = post(url, body, headers, timeout_seconds)
        except OperationTimeoutError:
            if attempt >= max_retries:
                raise
            time.sleep(min(backoff_base_seconds * (2**attempt), BACKOFF_CAP_SECONDS))
            attempt += 1
            continue
        except ProviderError as exc:
            if str(exc) != _UNREACHABLE or attempt >= max_retries:
                raise
            time.sleep(min(backoff_base_seconds * (2**attempt), BACKOFF_CAP_SECONDS))
            attempt += 1
            continue
        if response.status == 429 and attempt < max_retries:
            delay = _retry_after_seconds(response.headers)
            if delay is None:
                delay = min(backoff_base_seconds * (2**attempt), BACKOFF_CAP_SECONDS)
            time.sleep(delay)
            attempt += 1
            continue
        if 500 <= response.status <= 599 and attempt < max_retries:
            time.sleep(min(backoff_base_seconds * (2**attempt), BACKOFF_CAP_SECONDS))
            attempt += 1
            continue
        if response.status == 429:
            raise ProviderError("provider rate limit exceeded")
        if response.status >= 400:
            raise ProviderError(f"provider request failed with status {response.status}")
        return response


async def apost_with_retry(
    url: str,
    body: bytes,
    headers: Mapping[str, str],
    *,
    timeout_seconds: float,
    max_retries: int,
    backoff_base_seconds: float,
) -> HttpResponse:
    """Async wrapper (thread-based; see module docstring)."""
    return await asyncio.to_thread(
        post_with_retry,
        url,
        body,
        headers,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        backoff_base_seconds=backoff_base_seconds,
    )


__all__ = [
    "BACKOFF_CAP_SECONDS",
    "MAX_BODY_BYTES",
    "RETRY_AFTER_CAP_SECONDS",
    "HttpResponse",
    "apost_with_retry",
    "post",
    "post_with_retry",
]
