"""ha_tang.contracts — shared kernel: errors, common types, events."""

from chaos.ha_tang.contracts.common import PermissionClass, ToolCall
from chaos.ha_tang.contracts.errors import (
    ChaosError,
    ConfigurationError,
    ErrorCode,
    ExecutionError,
    OperationTimeoutError,
    PermissionDeniedError,
    ProviderError,
    ValidationError,
    VerificationError,
)
from chaos.ha_tang.contracts.events import Event

__all__ = [
    "ChaosError",
    "ConfigurationError",
    "ErrorCode",
    "Event",
    "ExecutionError",
    "OperationTimeoutError",
    "PermissionClass",
    "PermissionDeniedError",
    "ProviderError",
    "ToolCall",
    "ValidationError",
    "VerificationError",
]
