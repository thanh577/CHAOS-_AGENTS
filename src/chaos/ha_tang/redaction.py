"""Conservative secret redaction for logs, errors and event payloads.

Deterministic, stdlib-only, dependency-free by design: this module
imports nothing from ``chaos`` so the shared kernel (``contracts``)
can use it without import cycles. Secret holders such as
``chaos.cau_hinh.secrets.Secret`` are recognized by duck typing
(a callable ``expose`` attribute), never by import.
"""

import re
from collections.abc import Iterable, Mapping
from typing import Any

REDACTED = "***"

_SENSITIVE_STEMS = (
    "apikey",
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "authtoken",
    "clientsecret",
    "password",
    "passwd",
    "secret",
    "secrets",
    "token",
    "tokens",
    "authorization",
    "bearer",
    "credential",
    "credentials",
    "sessionkey",
    "privatekey",
)

_BEARER_RE = re.compile(r"(?i)\b(Bearer|Basic|Token)\s+[A-Za-z0-9\-._~+/=]+")
_KEY_VALUE_RE = re.compile(
    r"(?i)\b(api[_-]?key|password|passwd|secret|access[_-]?token|auth[_-]?token)\s*"
    r"([:=]\s*['\"]?)[^'\"\s,}]+"
)


def _is_sensitive_key(key: str) -> bool:
    """Match a normalized key exactly or by suffix.

    Suffix (not substring) matching redacts ``x-api-key`` and
    ``my_token`` while sparing ``ai_api_key_present``, ``token_count``
    and ``secretary`` — conservative about secrets, precise about
    non-secrets. Bare ``auth`` is deliberately *not* a stem so
    structured ``auth`` blocks recurse instead of being nuked.
    """
    normalized = key.lower().replace("_", "").replace("-", "")
    return any(normalized == stem or normalized.endswith(stem) for stem in _SENSITIVE_STEMS)


def _is_secret_holder(value: Any) -> bool:
    return callable(getattr(value, "expose", None)) and not isinstance(value, str)


def redact_text(text: str) -> str:
    """Redact credential patterns inside free text.

    Covers ``Authorization: Bearer <token>``-style headers and
    ``key=value``/``key: value`` pairs. Conservative: unknown shapes
    pass through, so structured redaction (:func:`redact`) is still
    required for mappings — and :func:`scrub_known_secrets` for values
    the caller already knows are secret.
    """
    redacted = _BEARER_RE.sub(lambda match: f"{match.group(1)} {REDACTED}", text)
    return _KEY_VALUE_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", redacted)


def scrub_known_secrets(text: str, secrets: Iterable[str]) -> str:
    """Replace exact known-secret values with ``***``.

    Last line of defense for error strings: pattern redaction cannot
    recognize an arbitrary credential, but the holder (e.g. settings)
    knows its own secrets. Longest first, empties skipped,
    deterministic. Values stay in memory only — never logged.
    """
    redacted = text
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        redacted = redacted.replace(secret, REDACTED)
    return redacted


def redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with sensitive values replaced, recursing into
    nested mappings, lists and tuples."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        result[key] = REDACTED if _is_sensitive_key(str(key)) else redact(value)
    return result


def redact(value: Any) -> Any:
    """Redact ``value`` conservatively. Strings are pattern-scanned,
    mappings/lists/tuples are recursed, secret holders become ``***``,
    everything else passes through untouched."""
    if _is_secret_holder(value):
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value


def format_error(exc: BaseException) -> str:
    """One-line, log-safe rendering of an exception.

    CHAOS errors carry their stable code; anything else is tagged
    ``unknown``. The message is pattern-redacted — never log ``exc``
    raw if it may hold credentials.
    """
    code = getattr(exc, "code", None)
    label = code.value if code is not None else "unknown"
    return f"[{label}] {redact_text(str(exc))}"


def error_details(exc: BaseException) -> dict[str, Any]:
    """Redacted copy of a CHAOS error's structured details (``{}`` for
    non-CHAOS exceptions)."""
    details = getattr(exc, "details", None)
    if not isinstance(details, Mapping):
        return {}
    return redact_mapping(details)


__all__ = [
    "REDACTED",
    "error_details",
    "format_error",
    "redact",
    "redact_mapping",
    "redact_text",
    "scrub_known_secrets",
]
