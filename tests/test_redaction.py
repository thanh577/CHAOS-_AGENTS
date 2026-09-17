"""Redaction tests: keys, bearer text, nesting, holders, determinism."""

from chaos.cau_hinh.secrets import Secret
from chaos.ha_tang.redaction import (
    REDACTED,
    redact,
    redact_mapping,
    redact_text,
    scrub_known_secrets,
)


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


def test_key_matching_is_precise_not_substring():
    # Gap-audit regression: presence/counter/descriptive keys must survive;
    # real credential keys (even prefixed) must not.
    data = redact_mapping(
        {
            "ai_api_key_present": True,
            "token_count": 5,
            "secretary": "Ms Smith",
            "auth": {"mode": "none"},
            "x-api-key": "hidden",
            "my_token": "hidden",
        }
    )
    assert data["ai_api_key_present"] is True
    assert data["token_count"] == 5
    assert data["secretary"] == "Ms Smith"
    assert data["auth"] == {"mode": "none"}
    assert data["x-api-key"] == REDACTED
    assert data["my_token"] == REDACTED


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


def test_scrub_known_secrets_replaces_exact_values():
    assert scrub_known_secrets("backend down for hunter2-abc", ["hunter2-abc"]) == (
        "backend down for ***"
    )
    assert scrub_known_secrets("nothing here", ["hunter2-abc"]) == "nothing here"
    assert scrub_known_secrets("keep hunter2-abc twice hunter2-abc", ["hunter2-abc"]) == (
        "keep *** twice ***"
    )
    assert scrub_known_secrets("untouched", ["", "x"]) == "untouched"
