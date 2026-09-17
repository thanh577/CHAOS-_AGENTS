"""Bootstrap tests: wiring, lifecycle, CI-safe entrypoint."""

import os

import pytest

from chaos.cau_hinh.settings import ChaosSettings
from chaos.ha_tang.application import Application, ApplicationContext, create_application
from chaos.ha_tang.contracts.errors import ValidationError
from chaos.ha_tang.runtime import Runtime, RuntimeState
from chaos.main import main


def _clean_env(monkeypatch):
    for key in [k for k in os.environ if k.startswith("CHAOS_")]:
        monkeypatch.delenv(key, raising=False)


def test_lifecycle_full_walk():
    runtime = Runtime()
    assert runtime.state is RuntimeState.CREATED
    runtime.initialize()
    runtime.start()
    runtime.stop()
    assert runtime.state is RuntimeState.STOPPED
    assert runtime.history == (
        RuntimeState.CREATED,
        RuntimeState.INITIALIZED,
        RuntimeState.RUNNING,
        RuntimeState.STOPPING,
        RuntimeState.STOPPED,
    )


@pytest.mark.parametrize(
    "steps",
    [
        ("start",),
        ("stop",),
        ("initialize", "initialize"),
        ("initialize", "stop"),
        ("initialize", "start", "start"),
    ],
)
def test_invalid_transitions_fail(steps):
    runtime = Runtime()
    with pytest.raises(ValidationError):
        for step in steps:
            getattr(runtime, step)()


def test_application_wiring_uses_explicit_context():
    settings = ChaosSettings.defaults()
    app = create_application(settings)
    assert isinstance(app, Application)
    assert isinstance(app.context, ApplicationContext)
    assert app.context.settings is settings
    assert isinstance(app.context.runtime, Runtime)
    assert app.run() == 0
    assert app.context.runtime.state is RuntimeState.STOPPED


def test_no_global_singleton_context():
    first = create_application(ChaosSettings.defaults())
    second = create_application(ChaosSettings.defaults())
    assert first.context is not second.context
    assert first.context.runtime is not second.context.runtime


def test_main_runs_ci_safe_without_api_key(monkeypatch, capsys):
    _clean_env(monkeypatch)
    assert main() == 0
    out = capsys.readouterr().out
    assert "CHAOS" in out
    assert "Milestone 0" in out


def test_main_reports_configuration_error_without_leaking(monkeypatch, capsys):
    _clean_env(monkeypatch)
    monkeypatch.setenv("CHAOS_ENV", "banana")
    assert main() == 2
    captured = capsys.readouterr()
    assert "configuration error" in captured.err.lower()
    assert "banana" in captured.err  # the invalid value is not a secret
    assert captured.out == ""
