"""Deterministic stdlib logging for CHAOS (Milestone 0).

Rules enforced here and by tests:
- never log settings objects wholesale (they may hold secrets);
- never log the process environment;
- only :func:`safe_summary` output is safe to log at startup.
"""

import logging
from typing import Any

from chaos.cau_hinh.settings import ChaosSettings

_CONFIGURED = False


def configure_logging(level: str) -> logging.Logger:
    """Configure the ``chaos`` logger once, deterministically.

    Safe to call repeatedly — the first call wins so imports and tests
    cannot reconfigure the format mid-run.
    """
    global _CONFIGURED
    logger = logging.getLogger("chaos")
    if not _CONFIGURED:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
        _CONFIGURED = True
    logger.setLevel(level)
    return logger


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


__all__ = ["configure_logging", "safe_summary"]
