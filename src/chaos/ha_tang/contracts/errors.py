"""Shared error model for CHAOS (Milestone 0 — contracts only).

One hierarchy for the whole runtime so every layer reports failures
the same way. Concrete handling/retry policies belong to later
milestones; this module only defines the shape of errors.
"""

from collections.abc import Mapping
from enum import Enum
from typing import Any, ClassVar


class ErrorCode(Enum):
    """Machine-readable error categories shared by all contracts."""

    VALIDATION = "validation"
    PERMISSION = "permission"
    EXECUTION = "execution"
    PROVIDER = "provider"
    TIMEOUT = "timeout"
    VERIFICATION = "verification"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


class ChaosError(Exception):
    """Base class for all CHAOS runtime errors."""

    code: ClassVar[ErrorCode] = ErrorCode.UNKNOWN

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = dict(details) if details else {}

    def to_dict(self) -> dict[str, Any]:
        """Stable machine-readable shape. Callers must redact ``details``
        (see ``chaos.ha_tang.redaction``) before logging or transport."""
        return {"code": self.code.value, "message": self.message, "details": dict(self.details)}


class ValidationError(ChaosError):
    """Structured input/schema validation failed."""

    code: ClassVar[ErrorCode] = ErrorCode.VALIDATION


class PermissionDeniedError(ChaosError):
    """A permission check refused the requested action.

    Named to avoid shadowing the builtin ``PermissionError``.
    """

    code: ClassVar[ErrorCode] = ErrorCode.PERMISSION


class ExecutionError(ChaosError):
    """A tool/provider executor failed while running."""

    code: ClassVar[ErrorCode] = ErrorCode.EXECUTION


class ProviderError(ChaosError):
    """An external provider (AI, STT, TTS, …) reported a failure."""

    code: ClassVar[ErrorCode] = ErrorCode.PROVIDER


class OperationTimeoutError(ChaosError):
    """An operation exceeded its contract timeout.

    Named to avoid shadowing the builtin ``TimeoutError``.
    """

    code: ClassVar[ErrorCode] = ErrorCode.TIMEOUT


class VerificationError(ChaosError):
    """A postcondition check failed."""

    code: ClassVar[ErrorCode] = ErrorCode.VERIFICATION


class ConfigurationError(ChaosError):
    """Runtime configuration is missing or invalid."""

    code: ClassVar[ErrorCode] = ErrorCode.CONFIGURATION


__all__ = [
    "ChaosError",
    "ConfigurationError",
    "ErrorCode",
    "ExecutionError",
    "OperationTimeoutError",
    "PermissionDeniedError",
    "ProviderError",
    "ValidationError",
    "VerificationError",
]
