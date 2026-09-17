"""AuditEventSink tests (T2.2): Event Bus -> audit_events persistence."""

import pytest

from chaos.ha_tang.contracts.errors import ExecutionError
from chaos.ha_tang.contracts.events import Event
from chaos.ha_tang.event_bus import WILDCARD, EventBus
from chaos.ha_tang.event_sinks import AuditEventSink
from chaos.ha_tang.persistence.sqlite_store import SqliteDatabase, repositories


@pytest.fixture()
def database(tmp_path):
    db = SqliteDatabase(tmp_path / "test.db")
    db.initialize()
    yield db
    db.close()


@pytest.fixture()
def audit_repo(database):
    return repositories(database)["audit_events"]


def _event(**kwargs) -> Event:
    defaults = {"event_type": "tool.execution.started", "source": "cong_cu"}
    defaults.update(kwargs)
    return Event(**defaults)


def test_sink_persists_event_as_audit_row(audit_repo):
    sink = AuditEventSink(audit_repo)
    event = _event(correlation_id="corr-1", payload={"tool": "search"})
    sink(event)
    rows = audit_repo.list()
    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == "tool.execution.started"
    assert row.source == "cong_cu"
    assert row.correlation_id == "corr-1"
    assert row.payload == {"tool": "search"}


def test_sink_preserves_occurred_at_as_timestamps(audit_repo):
    sink = AuditEventSink(audit_repo)
    event = _event()
    sink(event)
    row = audit_repo.list()[0]
    assert row.created_at == event.occurred_at
    assert row.updated_at == event.occurred_at


def test_sink_redacts_secret_before_persisting(audit_repo):
    sink = AuditEventSink(audit_repo)
    event = _event(payload={"api_key": "s3cr3t-real-value", "tool": "search"})
    sink(event)
    row = audit_repo.list()[0]
    assert row.payload["api_key"] == "***"
    assert row.payload["tool"] == "search"
    assert "s3cr3t-real-value" not in repr(row.payload)


def test_sink_gives_each_event_a_distinct_id(audit_repo):
    sink = AuditEventSink(audit_repo)
    sink(_event())
    sink(_event())
    rows = audit_repo.list()
    assert len({row.id for row in rows}) == 2


def test_sink_wired_to_event_bus_via_wildcard(audit_repo):
    bus = EventBus()
    bus.subscribe(WILDCARD, AuditEventSink(audit_repo))
    bus.publish(_event(event_type="tool.execution.started"))
    bus.publish(_event(event_type="tool.execution.finished"))
    rows = audit_repo.list()
    assert [row.event_type for row in rows] == [
        "tool.execution.started",
        "tool.execution.finished",
    ]


def test_sink_failure_is_isolated_by_the_bus(audit_repo, database):
    bus = EventBus()
    bus.subscribe(WILDCARD, AuditEventSink(audit_repo))
    received: list[str] = []
    bus.subscribe(WILDCARD, lambda e: received.append(e.event_type))
    database.close()  # sink's repository.create() will now fail
    bus.publish(_event())  # must not raise — EventBus isolates subscriber failures
    assert received == ["tool.execution.started"]


def test_sink_direct_call_propagates_real_repository_errors(audit_repo, database):
    sink = AuditEventSink(audit_repo)
    database.close()
    with pytest.raises(ExecutionError):
        sink(_event())
