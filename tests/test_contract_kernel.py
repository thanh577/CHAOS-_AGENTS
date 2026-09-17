"""Kernel contract tests: errors, permission classes, tool calls, events."""

import pytest

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


def test_error_codes_cover_required_categories():
    assert {c.value for c in ErrorCode} >= {
        "validation",
        "permission",
        "execution",
        "provider",
        "timeout",
        "verification",
        "configuration",
    }


@pytest.mark.parametrize(
    ("error_cls", "code"),
    [
        (ValidationError, ErrorCode.VALIDATION),
        (PermissionDeniedError, ErrorCode.PERMISSION),
        (ExecutionError, ErrorCode.EXECUTION),
        (ProviderError, ErrorCode.PROVIDER),
        (OperationTimeoutError, ErrorCode.TIMEOUT),
        (VerificationError, ErrorCode.VERIFICATION),
        (ConfigurationError, ErrorCode.CONFIGURATION),
    ],
)
def test_each_error_maps_to_its_code(error_cls, code):
    err = error_cls("boom", details={"k": "v"})
    assert isinstance(err, ChaosError)
    assert isinstance(err, Exception)
    assert err.code is code
    assert err.message == "boom"
    assert err.details == {"k": "v"}
    assert str(err) == "boom"


def test_error_details_default_empty_and_copied():
    details = {"a": 1}
    err = ExecutionError("x", details=details)
    assert err.details == {"a": 1}
    assert err.details is not details
    assert ExecutionError("y").details == {}


def test_permission_classes_exist():
    assert PermissionClass.SAFE.value == "safe"
    assert PermissionClass.CONFIRM.value == "confirm"
    assert PermissionClass.BLOCK.value == "block"


def test_tool_call_shape():
    call = ToolCall(name="read_file", arguments={"path": "/tmp/x"}, call_id="c1")
    assert call.name == "read_file"
    assert call.arguments["path"] == "/tmp/x"
    assert ToolCall(name="noop").arguments == {}
    assert ToolCall(name="noop").call_id is None


def test_event_defaults_and_uniqueness():
    first = Event(event_type="tool.done", source="cong_cu")
    second = Event(event_type="tool.done", source="cong_cu")
    assert first.event_id != second.event_id
    assert first.occurred_at.tzinfo is not None
    assert first.correlation_id is None
    assert first.payload == {}
    correlated = Event(event_type="t", source="s", correlation_id=first.event_id)
    assert correlated.correlation_id == first.event_id
