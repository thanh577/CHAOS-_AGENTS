"""Brain configuration tests (T1.1): retry/backoff/budget knobs."""

import pytest

from chaos.cau_hinh.settings import AISettings, ChaosSettings
from chaos.ha_tang.contracts.errors import ConfigurationError


def test_ai_defaults():
    settings = ChaosSettings.defaults().ai
    assert settings.max_retries == 3
    assert settings.retry_backoff_seconds == 1.0
    assert settings.max_context_tokens is None


def test_ai_env_override():
    settings = ChaosSettings.from_env(
        {
            "CHAOS_AI_MAX_RETRIES": "5",
            "CHAOS_AI_RETRY_BACKOFF": "0.5",
            "CHAOS_AI_MAX_CONTEXT_TOKENS": "8000",
        }
    ).ai
    assert settings.max_retries == 5
    assert settings.retry_backoff_seconds == 0.5
    assert settings.max_context_tokens == 8000


@pytest.mark.parametrize(
    "env",
    [
        {"CHAOS_AI_MAX_RETRIES": "-1"},
        {"CHAOS_AI_MAX_RETRIES": "11"},
        {"CHAOS_AI_MAX_RETRIES": "many"},
        {"CHAOS_AI_RETRY_BACKOFF": "0"},
        {"CHAOS_AI_RETRY_BACKOFF": "-2"},
        {"CHAOS_AI_RETRY_BACKOFF": "61"},
        {"CHAOS_AI_RETRY_BACKOFF": "soon"},
        {"CHAOS_AI_MAX_CONTEXT_TOKENS": "0"},
        {"CHAOS_AI_MAX_CONTEXT_TOKENS": "-100"},
        {"CHAOS_AI_MAX_CONTEXT_TOKENS": "lots"},
    ],
)
def test_invalid_ai_knobs_fail_clearly(env):
    with pytest.raises(ConfigurationError, match=".+"):
        ChaosSettings.from_env(env)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_retries": -1},
        {"max_retries": 11},
        {"max_retries": True},
        {"retry_backoff_seconds": 0},
        {"retry_backoff_seconds": 61},
        {"max_context_tokens": 0},
        {"max_context_tokens": -5},
    ],
)
def test_ai_settings_validate_directly(kwargs):
    with pytest.raises(ConfigurationError):
        AISettings(**kwargs)


def test_boundary_values_accepted():
    assert AISettings(max_retries=0).max_retries == 0
    assert AISettings(max_retries=10).max_retries == 10
    assert AISettings(retry_backoff_seconds=60).retry_backoff_seconds == 60
    assert AISettings(max_context_tokens=1).max_context_tokens == 1


def test_production_gate_unchanged_by_new_knobs():
    full = ChaosSettings.from_env(
        {
            "CHAOS_ENV": "production",
            "CHAOS_AI_PROVIDER": "stub",
            "CHAOS_AI_MODEL": "stub-model",
            "CHAOS_AI_API_KEY": "k",
        }
    )
    assert full.ai.max_retries == 3  # safe defaults, not required in production
    with pytest.raises(ConfigurationError, match="CHAOS_AI_PROVIDER"):
        ChaosSettings.from_env({"CHAOS_ENV": "production"})
