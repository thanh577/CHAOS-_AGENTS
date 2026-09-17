"""Configuration tests: defaults, overrides, validation, secret redaction."""

import pytest

from chaos.cau_hinh.secrets import Secret
from chaos.cau_hinh.settings import (
    AISettings,
    AppSettings,
    ChaosSettings,
    LoggingSettings,
    RuntimeSettings,
    StorageSettings,
)
from chaos.ha_tang.contracts.errors import ConfigurationError
from chaos.ha_tang.logging import safe_summary

SECRET_VALUE = "s3cr3t-api-key-value"


def test_defaults_are_ci_safe():
    settings = ChaosSettings.defaults()
    assert settings.app.environment == "development"
    assert settings.app.debug is False
    assert settings.logging.level == "INFO"
    assert settings.runtime.request_timeout_seconds == 60.0
    assert settings.storage.data_dir == "./data"
    assert settings.ai.provider_name is None
    assert settings.ai.api_key is None
    assert settings.security.mask_secrets_in_logs is True


def test_environment_override():
    settings = ChaosSettings.from_env(
        {
            "CHAOS_ENV": "testing",
            "CHAOS_DEBUG": "true",
            "CHAOS_LOG_LEVEL": "debug",
            "CHAOS_DATA_DIR": "/tmp/chaos-data",
            "CHAOS_REQUEST_TIMEOUT": "5",
            "CHAOS_MASK_SECRETS": "false",
            "CHAOS_AI_PROVIDER": "stub",
            "CHAOS_AI_MODEL": "stub-model",
            "CHAOS_AI_API_KEY": SECRET_VALUE,
            "CHAOS_AI_ENDPOINT": "https://example.invalid",
        }
    )
    assert settings.app.environment == "testing"
    assert settings.app.debug is True
    assert settings.logging.level == "DEBUG"
    assert settings.storage.data_dir == "/tmp/chaos-data"
    assert settings.runtime.request_timeout_seconds == 5.0
    assert settings.security.mask_secrets_in_logs is False
    assert settings.ai.provider_name == "stub"
    assert isinstance(settings.ai.api_key, Secret)
    assert settings.ai.api_key.expose() == SECRET_VALUE


def test_blank_values_fall_back_to_defaults():
    settings = ChaosSettings.from_env({"CHAOS_ENV": "  ", "CHAOS_AI_API_KEY": "  "})
    assert settings.app.environment == "development"
    assert settings.ai.api_key is None


@pytest.mark.parametrize(
    "env",
    [
        {"CHAOS_ENV": "banana"},
        {"CHAOS_LOG_LEVEL": "VERBOSE"},
        {"CHAOS_DEBUG": "maybe"},
        {"CHAOS_REQUEST_TIMEOUT": "soon"},
        {"CHAOS_REQUEST_TIMEOUT": "0"},
        {"CHAOS_REQUEST_TIMEOUT": "-1"},
        {"CHAOS_REQUEST_TIMEOUT": "601"},
        {"CHAOS_ENV": "production", "CHAOS_DEBUG": "true"},
    ],
)
def test_invalid_configuration_fails_clearly(env):
    with pytest.raises(ConfigurationError, match=".+"):
        ChaosSettings.from_env(env)


def test_blank_data_dir_falls_back_to_default():
    # Blank means "unset" for every variable (see test_blank_values_fall_back_to_defaults);
    # empty locations are still rejected on direct construction (test_direct_group_validation).
    assert ChaosSettings.from_env({"CHAOS_DATA_DIR": "   "}).storage.data_dir == "./data"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"environment": "nope"},
        {"environment": "production", "debug": True},
    ],
)
def test_app_settings_validate_directly(kwargs):
    with pytest.raises(ConfigurationError):
        AppSettings(**kwargs)


def test_direct_group_validation():
    with pytest.raises(ConfigurationError):
        LoggingSettings(level="TRACE")
    with pytest.raises(ConfigurationError):
        RuntimeSettings(request_timeout_seconds=0)
    with pytest.raises(ConfigurationError):
        StorageSettings(data_dir="")
    assert AISettings().api_key is None  # optional outside production


def test_production_requires_ai_credentials_by_name_only():
    with pytest.raises(ConfigurationError) as exc_info:
        ChaosSettings.from_env({"CHAOS_ENV": "production"})
    message = str(exc_info.value)
    assert "CHAOS_AI_PROVIDER" in message
    assert "CHAOS_AI_MODEL" in message
    assert "CHAOS_AI_API_KEY" in message

    with pytest.raises(ConfigurationError):
        ChaosSettings.from_env(
            {"CHAOS_ENV": "production", "CHAOS_AI_PROVIDER": "stub"}  # still missing rest
        )

    full = ChaosSettings.from_env(
        {
            "CHAOS_ENV": "production",
            "CHAOS_AI_PROVIDER": "stub",
            "CHAOS_AI_MODEL": "stub-model",
            "CHAOS_AI_API_KEY": SECRET_VALUE,
        }
    )
    assert full.app.environment == "production"


def test_secret_redaction():
    secret = Secret(SECRET_VALUE)
    assert repr(secret) == "Secret('***')"
    assert str(secret) == "***"
    assert SECRET_VALUE not in repr(secret)
    assert bool(secret) is True
    assert bool(Secret("")) is False

    settings = ChaosSettings.from_env({"CHAOS_AI_API_KEY": SECRET_VALUE})
    assert SECRET_VALUE not in repr(settings)
    assert SECRET_VALUE not in str(settings.ai.api_key)

    summary = safe_summary(settings)
    assert summary["ai_api_key_present"] is True
    assert SECRET_VALUE not in repr(summary)

    with pytest.raises(ConfigurationError) as exc_info:
        ChaosSettings.from_env({"CHAOS_ENV": "production", "CHAOS_AI_API_KEY": SECRET_VALUE})
    assert SECRET_VALUE not in str(exc_info.value)
