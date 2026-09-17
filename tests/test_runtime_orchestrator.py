"""Runtime orchestration tests: hooks, idempotency, no-restart, failures."""

import logging
from dataclasses import FrozenInstanceError

import pytest

from chaos.cau_hinh.settings import ChaosSettings
from chaos.ha_tang.application import ApplicationContext, create_application
from chaos.ha_tang.contracts.errors import ExecutionError, ValidationError
from chaos.ha_tang.runtime import Runtime, RuntimeState, Service


class RecordingService(Service):
    """Test double with scripted failures — lives in tests, never in src."""

    def __init__(self, name: str, *, fail_on: str = "") -> None:
        self._name = name
        self._fail_on = fail_on
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    def startup(self) -> None:
        self.calls.append(f"{self._name}.startup")
        if self._fail_on == "startup":
            raise ExecutionError(f"{self._name} failed to start")

    def shutdown(self) -> None:
        self.calls.append(f"{self._name}.shutdown")
        if self._fail_on == "shutdown":
            raise ExecutionError(f"{self._name} failed to stop")


def test_service_is_abstract_without_name():
    with pytest.raises(TypeError):
        Service()  # type: ignore[abstract]


def test_default_runtime_has_no_services():
    assert Runtime().services == ()


def test_hook_order_startup_then_reverse_shutdown():
    first, second = RecordingService("a"), RecordingService("b")
    runtime = Runtime(services=(first, second))
    runtime.initialize()
    runtime.start()
    runtime.stop()
    assert first.calls == ["a.startup", "a.shutdown"]
    assert second.calls == ["b.startup", "b.shutdown"]
    assert runtime.history == (
        RuntimeState.CREATED,
        RuntimeState.INITIALIZED,
        RuntimeState.RUNNING,
        RuntimeState.STOPPING,
        RuntimeState.STOPPED,
    )


def test_failing_startup_hook_leaves_state_and_classification():
    runtime = Runtime(services=(RecordingService("bad", fail_on="startup"),))
    with pytest.raises(ExecutionError, match="bad failed to start"):
        runtime.initialize()
    assert runtime.state is RuntimeState.CREATED
    assert runtime.history == (RuntimeState.CREATED,)


def test_failing_shutdown_hook_leaves_running_and_propagates():
    runtime = Runtime(services=(RecordingService("bad", fail_on="shutdown"),))
    runtime.initialize()
    runtime.start()
    with pytest.raises(ExecutionError, match="bad failed to stop"):
        runtime.stop()
    assert runtime.state is RuntimeState.RUNNING  # well-defined, retryable


def test_stop_idempotent_from_stopped():
    runtime = Runtime()
    runtime.initialize()
    runtime.start()
    runtime.stop()
    before = runtime.history
    runtime.stop()
    runtime.stop()
    assert runtime.history == before
    assert runtime.state is RuntimeState.STOPPED


@pytest.mark.parametrize(
    ("setup", "expected_history"),
    [
        (
            ("initialize", "start", "shutdown"),
            ("created", "initialized", "running", "stopping", "stopped"),
        ),
        (
            ("initialize", "shutdown"),  # never claims RUNNING without start
            ("created", "initialized", "stopping", "stopped"),
        ),
        (
            ("initialize", "start", "stop", "shutdown"),  # shutdown idempotent
            ("created", "initialized", "running", "stopping", "stopped"),
        ),
    ],
)
def test_shutdown_paths(setup, expected_history):
    runtime = Runtime()
    for step in setup:
        getattr(runtime, step)()
    assert runtime.state is RuntimeState.STOPPED
    assert tuple(state.value for state in runtime.history) == expected_history


def test_no_restart_from_stopped():
    runtime = Runtime()
    runtime.initialize()
    runtime.start()
    runtime.stop()
    for step in ("initialize", "start"):
        with pytest.raises(ValidationError):
            getattr(runtime, step)()


@pytest.mark.parametrize(
    "steps",
    [
        ("start",),
        ("stop",),
        ("shutdown",),
        ("initialize", "stop"),
        ("initialize", "start", "start"),
        ("initialize", "start", "initialize"),
    ],
)
def test_invalid_transitions_fail(steps):
    runtime = Runtime()
    with pytest.raises(ValidationError):
        for step in steps:
            getattr(runtime, step)()


def test_context_is_frozen_and_explicit():
    app = create_application(ChaosSettings.defaults())
    context = app.context
    assert isinstance(context, ApplicationContext)
    assert isinstance(context.logger, logging.Logger)
    assert context.settings is not None and context.runtime is not None
    with pytest.raises(FrozenInstanceError):
        context.settings = ChaosSettings.defaults()  # type: ignore[misc]


def test_run_walks_full_sequence_to_exit_zero():
    app = create_application(ChaosSettings.defaults())
    assert app.run() == 0
    assert app.context.runtime.state is RuntimeState.STOPPED
    assert app.context.runtime.history == (
        RuntimeState.CREATED,
        RuntimeState.INITIALIZED,
        RuntimeState.RUNNING,
        RuntimeState.STOPPING,
        RuntimeState.STOPPED,
    )


def test_run_failure_never_fakes_running_and_keeps_classification():
    from chaos.ha_tang.application import Application, ApplicationContext
    from chaos.ha_tang.logging import configure_logging

    secret = "s3cr3t-startup-value"
    settings = ChaosSettings.from_env({"CHAOS_AI_API_KEY": secret})
    logger = configure_logging(settings.logging.level)
    app = Application(
        ApplicationContext(
            settings=settings,
            runtime=Runtime(services=(RecordingService("bad", fail_on="startup"),)),
            logger=logger,
        )
    )

    records: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger.addHandler(collector := _Collector())
    try:
        with pytest.raises(ExecutionError, match="bad failed to start"):
            app.run()
    finally:
        logger.handlers.remove(collector)
    assert app.context.runtime.state is RuntimeState.CREATED
    rendered = " ".join(record.getMessage() for record in records)
    assert "[execution]" in rendered
    assert secret not in rendered
