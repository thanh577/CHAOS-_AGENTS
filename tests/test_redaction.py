"""Redaction tests: keys, bearer text, nesting, holders, determinism."""

from chaos.cau_hinh.secrets import Secret
from chaos.ha_tang.redaction import REDACTED, redact, redact_mapping, redact_text


def test_sensitive_keys_redacted_case_insensitively():
    data = redact_mapping(
        {
            "api_key": "v1",
            "API_KEY": "v2",
            "api-key": "v3",
            "token": "v4",
            "access_token": "v5",
            "password": "v6",
            "passwd": "v7",
            "secret": "v8",
            "authorization": "v9",
            "client_secret": "v10",
            "public_name": "keep",
        }
    )
    assert data["public_name"] == "keep"
    assert all(value == REDACTED for key, value in data.items() if key != "public_name")


def test_bearer_and_basic_headers_redacted():
    secret = "s3cr3t-token"
    assert redact_text(f"Authorization: Bearer {secret}") == "Authorization: Bearer ***"
    assert secret not in redact_text(f"authorization: Basic {secret}")
    assert redact_text("nothing sensitive here") == "nothing sensitive here"


def test_key_value_pairs_redacted():
    assert redact_text("api_key=supersecret") == "api_key=***"
    assert "supersecret" not in redact_text("login failed for password: hunter2")


def test_nested_structures_recursed():
    # Bare string values carry no key context, so only explicit credential
    # patterns (e.g. Bearer tokens) are redacted inside them — conservative
    # by design; key-based redaction needs the mapping around the value.
    data = redact(
        {
            "user": "alice",
            "auth": {"token": "t", "scopes": ["read"]},
            "history": [{"password": "p"}, "plain"],
            "header": "Authorization: Bearer abc123",
        }
    )
    assert data == {
        "user": "alice",
        "auth": {"token": "***", "scopes": ["read"]},
        "history": [{"password": "***"}, "plain"],
        "header": "Authorization: Bearer ***",
    }


def test_secret_holders_and_passthrough():
    assert redact(Secret("hidden")) == REDACTED
    assert redact(42) == 42
    assert redact(None) is None
    assert redact(3.14) == 3.14


def test_deterministic_and_non_mutating():
    source = {"api_key": "v", "nested": {"token": "t"}}
    first, second = redact(source), redact(source)
    assert first == second == {"api_key": "***", "nested": {"token": "***"}}
    assert source == {"api_key": "v", "nested": {"token": "t"}}
