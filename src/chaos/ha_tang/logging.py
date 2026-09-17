"""Deterministic stdlib logging for CHAOS (Milestone 0).

Rules enforced here and by tests:
- never log settings objects wholesale (they may hold secrets);
- never log the process environment;
- only :func:`safe_summary` output is safe to log at startup;
- event payloads go through redaction inside :func:`log_event`;
- raw prompts, model responses and raw tool arguments are never
  logged by this layer — only safe metadata.
"""

import logging
from collections.abc import Mapping
from typing import Any

from chaos.cau_hinh.settings import ChaosSettings
from chaos.ha_tang.context import get_context
from chaos.ha_tang.contracts.errors import ConfigurationError
from chaos.ha_tang.redaction import redact_mapping

_CONFIGURED = False

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

#: Structured-logging convention. Every entry carries ``event``;
#: correlation ids are attached when a TraceContext is installed.
STRUCTURED_FIELDS = ("event", "correlation_id", "session_id", "task_id", "tool_run_id")


def configure_logging(level: str) -> logging.Logger:
    """Configure the ``chaos`` logger once, deterministically.

    Safe to call repeatedly — the first call wins so imports and tests
    cannot reconfigure the format mid-run.
    """
    global _CONFIGURED
    logger = logging.getLogger("chaos")
    if not _CONFIGURED:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.propagate = False
        _CONFIGURED = True
    logger.setLevel(level)
    return logger


def resolve_level(level: str | int) -> int:
    """Map a level name (``DEBUG``…``CRITICAL``, case-insensitive) or a
    numeric level to its number. Unknown names fail with
    ``ConfigurationError``, never silently."""
    if isinstance(level, int) and not isinstance(level, bool):
        if level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL):
            return level
        raise ConfigurationError(f"invalid log level number: {level!r}")
    if isinstance(level, str):
        normalized = level.strip().upper()
        mapped = logging.getLevelName(normalized)
        if isinstance(mapped, int):
            return mapped
    raise ConfigurationError(f"invalid log level: {level!r}")


def log_event(
    logger: logging.Logger,
    level: str | int,
    event: str,
    payload: Mapping[str, Any] | None = None,
) -> None:
    """Emit one structured log entry.

    The payload is redacted before logging and the installed
    :class:`TraceContext` ids (if any) are attached under the
    :data:`STRUCTURED_FIELDS` names. Message shape is fixed so a
    future backend can replace the formatter without touching callers.
    """
    number = resolve_level(level)
    context = get_context()
    fields: dict[str, Any] = {"event": event}
    if context is not None:
        fields["correlation_id"] = context.correlation_id
        fields["session_id"] = context.session_id
        fields["task_id"] = context.task_id
        fields["tool_run_id"] = context.tool_run_id
    if payload:
        fields["payload"] = redact_mapping(dict(payload))
    logger.log(number, "%s", fields)


def safe_summary(settings: ChaosSettings) -> dict[str, Any]:
    """Startup-safe configuration summary with secrets excluded.

    Presence of credentials is reported as booleans only — values,
    especially ``api_key``, never appear here.
    """
    return {
        "environment": settings.app.environment,
        "debug": settings.app.debug,
        "log_level": settings.logging.level,
        "request_timeout_seconds": settings.runtime.request_timeout_seconds,
        "data_dir": settings.storage.data_dir,
        "ai_provider_configured": settings.ai.provider_name is not None,
        "ai_model_configured": settings.ai.model is not None,
        "ai_api_key_present": settings.ai.api_key is not None,
        "mask_secrets_in_logs": settings.security.mask_secrets_in_logs,
    }


__all__ = [
    "LOG_FORMAT",
    "STRUCTURED_FIELDS",
    "configure_logging",
    "log_event",
    "resolve_level",
    "safe_summary",
]
