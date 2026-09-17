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
from chaos.ha_tang.contracts.events import EVENT_NAME_RE, Event, is_conventional_name

__all__ = [
    "EVENT_NAME_RE",
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
    "is_conventional_name",
]
