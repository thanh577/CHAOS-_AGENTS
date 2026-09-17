"""Persistence/application lifecycle integration tests (T0.7).

Ownership under test: Application creates/initializes/owns/shuts-down
both Runtime and Persistence as siblings. All databases are isolated
tmp files — never ./data, never production.
"""

import logging
from pathlib import Path

import pytest

from chaos.cau_hinh.settings import ChaosSettings
from chaos.ha_tang.application import (
    DATABASE_FILENAME,
    Application,
    ApplicationContext,
    create_application,
)
from chaos.ha_tang.contracts.errors import (
    ConfigurationError,
    ExecutionError,
    OperationTimeoutError,
    ValidationError,
)
from chaos.ha_tang.persistence.sqlite_store import SqliteDatabase
from chaos.ha_tang.runtime import Runtime, RuntimeState, Service


def _settings(tmp_path, extra: dict | None = None):
    env = {"CHAOS_DATA_DIR": str(tmp_path / "data")}
    env.update(extra or {})
    return ChaosSettings.from_env(env)


def _events(records: list[logging.LogRecord]):
    return [record.args for record in records]


@pytest.fixture()
def logged_app(tmp_path):
    settings = _settings(tmp_path)
    app = create_application(settings)
    records: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    collector = _Collector()
    app.context.logger.addHandler(collector)
    yield app, records
    app.context.logger.handlers.remove(collector)


def test_create_wires_but_does_not_open(tmp_path):
    app = create_application(_settings(tmp_path))
    db_path = tmp_path / "data" / DATABASE_FILENAME
    assert (tmp_path / "data").is_dir()  # storage dir prepared, nothing more
    assert not db_path.exists()  # no database file before run
    assert app.context.persistence.is_open is False
    assert app.context.persistence.path == db_path


def test_create_fails_clearly_when_storage_unpreparable(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    settings = _settings(tmp_path, {"CHAOS_DATA_DIR": str(blocker / "data")})
    with pytest.raises(ConfigurationError, match="storage location"):
        create_application(settings)


def test_startup_order_persistence_before_runtime(tmp_path):
    observed: dict[str, object] = {}
    wired = create_application(_settings(tmp_path))
    persistence = wired.context.persistence

    class _Probe(Service):
        @property
        def name(self) -> str:
            return "probe"

        def startup(self) -> None:
            observed["open"] = persistence.is_open
            observed["version"] = persistence.schema_version()

    app = Application(
        ApplicationContext(
            settings=wired.context.settings,
            runtime=Runtime(services=(_Probe(),)),
            logger=wired.context.logger,
            persistence=persistence,
        )
    )
    assert app.run() == 0
    assert observed == {"open": True, "version": 1}
    assert app.context.runtime.state is RuntimeState.STOPPED


def test_repeated_startup_keeps_schema_intact(tmp_path):
    settings = _settings(tmp_path)
    assert create_application(settings).run() == 0
    second = create_application(settings)
    assert second.run() == 0
    # run() closes the backend; re-open idempotently to verify the schema.
    second.context.persistence.initialize()
    try:
        assert second.context.persistence.schema_version() == 1
        assert "sessions" in second.context.persistence.table_names()
    finally:
        second.context.persistence.close()


def test_shutdown_order_and_repeat_safety(tmp_path):
    app = create_application(_settings(tmp_path))
    assert app.run() == 0
    assert app.context.runtime.state is RuntimeState.STOPPED
    assert app.context.persistence.is_open is False
    app.shutdown()  # second shutdown: runtime no-op + close idempotent
    app.shutdown()
    assert app.context.persistence.is_open is False


def test_shutdown_closes_persistence_even_when_runtime_halt_fails(tmp_path):
    app = create_application(_settings(tmp_path))
    app.context.persistence.initialize()
    with pytest.raises(ValidationError):  # CREATED -> shutdown refused...
        app.shutdown()
    assert app.context.persistence.is_open is False  # ...but persistence still closed


def test_persistence_init_failure_never_runs_runtime(tmp_path, monkeypatch):
    app = create_application(_settings(tmp_path))

    def _broken(self):
        raise ExecutionError("disk gone")

    monkeypatch.setattr(SqliteDatabase, "initialize", _broken)
    with pytest.raises(ExecutionError, match="disk gone"):
        app.run()
    assert app.context.runtime.state is RuntimeState.CREATED
    assert app.context.runtime.history == (RuntimeState.CREATED,)


def test_runtime_start_failure_cleans_up_persistence(tmp_path):
    class _NoStart(Runtime):
        def start(self) -> None:
            raise OperationTimeoutError("nope")

    wired = create_application(_settings(tmp_path))
    app = Application(
        ApplicationContext(
            settings=wired.context.settings,
            runtime=_NoStart(),
            logger=wired.context.logger,
            persistence=wired.context.persistence,
        )
    )
    with pytest.raises(OperationTimeoutError, match="nope"):
        app.run()
    assert app.context.runtime.state is RuntimeState.INITIALIZED
    assert app.context.persistence.is_open is False  # unwound


def test_stop_failure_keeps_persistence_open(tmp_path):
    class _NoStop(Runtime):
        def stop(self) -> None:
            raise ExecutionError("cannot stop")

    wired = create_application(_settings(tmp_path))
    app = Application(
        ApplicationContext(
            settings=wired.context.settings,
            runtime=_NoStop(),
            logger=wired.context.logger,
            persistence=wired.context.persistence,
        )
    )
    with pytest.raises(ExecutionError, match="cannot stop"):
        app.run()
    # Runtime still alive -> persistence must NOT be closed underneath it.
    assert app.context.runtime.state is RuntimeState.RUNNING
    assert app.context.persistence.is_open is True
    app.context.persistence.close()


def test_persistence_shutdown_failure_propagates_with_deterministic_state(tmp_path, monkeypatch):
    app = create_application(_settings(tmp_path))
    assert app.run() == 0

    def _broken(self):
        raise ExecutionError("close failed")

    monkeypatch.setattr(SqliteDatabase, "close", _broken)
    with pytest.raises(ExecutionError, match="close failed"):
        app.shutdown()
    assert app.context.runtime.state is RuntimeState.STOPPED
    monkeypatch.undo()
    app.shutdown()  # real close now succeeds, idempotent
    assert app.context.persistence.is_open is False


def test_lifecycle_events_cover_persistence(logged_app):
    app, records = logged_app
    assert app.run() == 0
    events = _events(records)
    by_name = {fields["event"]: fields for fields in events}
    assert set(by_name) >= {
        "application.started",
        "persistence.initialized",
        "application.stopped",
        "persistence.shutdown",
    }
    assert by_name["persistence.initialized"]["payload"] == {"schema_version": 1}
    correlation_ids = {fields["correlation_id"] for fields in events}
    assert len(correlation_ids) == 1 and next(iter(correlation_ids))


def test_persistence_init_failure_event_carries_no_secret(tmp_path, monkeypatch):
    secret = "s3cr3t-integration-value"
    settings = _settings(tmp_path, {"CHAOS_AI_API_KEY": secret})
    app = create_application(settings)
    records: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    def _broken(self):
        raise ExecutionError(f"backend down for {secret}")

    monkeypatch.setattr(SqliteDatabase, "initialize", _broken)
    collector = _Collector()
    app.context.logger.addHandler(collector)
    try:
        with pytest.raises(ExecutionError):
            app.run()
    finally:
        app.context.logger.handlers.remove(collector)
    rendered = " ".join(str(getattr(record, "args", record.getMessage())) for record in records)
    assert "persistence.initialization.failed" in rendered
    assert secret not in rendered
    assert secret not in repr(app.context.settings)
    assert app.context.runtime.state is RuntimeState.CREATED


def test_no_global_database_across_applications(tmp_path):
    first = create_application(_settings(tmp_path, {"CHAOS_DATA_DIR": str(tmp_path / "a")}))
    second = create_application(_settings(tmp_path, {"CHAOS_DATA_DIR": str(tmp_path / "b")}))
    assert first.context.persistence is not second.context.persistence
    assert first.context.persistence.path != second.context.persistence.path


def test_no_database_before_explicit_initialize(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = ChaosSettings.from_env({})  # default ./data, untouched by from_env
    assert settings.storage.data_dir == "./data"
    db = SqliteDatabase(Path("./data") / DATABASE_FILENAME)
    assert list(tmp_path.glob("**/*.db")) == []  # constructing opens nothing
    assert db.is_open is False
