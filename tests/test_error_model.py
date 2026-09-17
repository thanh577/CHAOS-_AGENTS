"""Error-model tests: stable codes, inheritance, safe representation."""

import pytest

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
from chaos.ha_tang.redaction import error_details, format_error


def test_codes_are_stable_strings():
    assert [(c.name, c.value) for c in ErrorCode] == [
        ("VALIDATION", "validation"),
        ("PERMISSION", "permission"),
        ("EXECUTION", "execution"),
        ("PROVIDER", "provider"),
        ("TIMEOUT", "timeout"),
        ("VERIFICATION", "verification"),
        ("CONFIGURATION", "configuration"),
        ("UNKNOWN", "unknown"),
    ]


@pytest.mark.parametrize(
    ("error_cls", "code"),
    [
        (ValidationError, ErrorCode.VALIDATION),
        (ConfigurationError, ErrorCode.CONFIGURATION),
        (PermissionDeniedError, ErrorCode.PERMISSION),
        (ExecutionError, ErrorCode.EXECUTION),
        (ProviderError, ErrorCode.PROVIDER),
        (OperationTimeoutError, ErrorCode.TIMEOUT),
        (VerificationError, ErrorCode.VERIFICATION),
    ],
)
def test_classification(error_cls, code):
    err = error_cls("message", details={"field": "name"})
    assert isinstance(err, ChaosError)
    assert isinstance(err, Exception)
    assert err.code is code
    assert err.message == "message"
    assert err.details == {"field": "name"}


def test_details_copied_not_aliased():
    details = {"a": 1}
    err = ExecutionError("x", details=details)
    assert err.details == details and err.details is not details
    assert ExecutionError("y").details == {}


def test_to_dict_shape():
    as_dict = ProviderError("provider down", details={"retry": True}).to_dict()
    assert as_dict == {"code": "provider", "message": "provider down", "details": {"retry": True}}
    assert ChaosError("base").to_dict()["code"] == "unknown"


def test_safe_representation_redacts_secrets():
    secret = "s3cr3t-bearer-token-value"
    err = ProviderError(
        f"call failed with Authorization: Bearer {secret}",
        details={"api_key": secret, "nested": {"password": secret}, "ok": "fine"},
    )
    rendered = format_error(err)
    assert secret not in rendered
    assert "[provider]" in rendered
    redacted = error_details(err)
    assert redacted == {"api_key": "***", "nested": {"password": "***"}, "ok": "fine"}
    assert secret not in repr(redacted)


def test_plain_exceptions_format_safely():
    rendered = format_error(ValueError("plain boom"))
    assert rendered == "[unknown] plain boom"
    assert error_details(ValueError("x")) == {}
