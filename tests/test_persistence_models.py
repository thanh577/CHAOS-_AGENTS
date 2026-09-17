"""Persistence model tests: construction, invariants, serialization."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from chaos.ha_tang.contracts.errors import ValidationError
from chaos.ha_tang.persistence import models
from chaos.ha_tang.persistence.models import (
    AuditEvent,
    Memory,
    Message,
    Permission,
    Session,
    Setting,
    Task,
    TaskStep,
    ToolRun,
    new_id,
    utcnow,
)


def test_ids_unique_and_timestamps_utc_aware():
    first = Session()
    second = Session()
    assert first.id != second.id
    assert new_id() != new_id()
    for moment in (first.created_at, first.updated_at, utcnow()):
        assert moment.tzinfo is not None
        assert moment.utcoffset() == UTC.utcoffset(None)


def test_models_are_frozen():
    with pytest.raises(FrozenInstanceError):
        Session().title = "mutated"  # type: ignore[misc]


@pytest.mark.parametrize(
    "make",
    [
        lambda **kw: Session(**kw),
        lambda **kw: Message(session_id="s", role="user", **kw),
        lambda **kw: Memory(**kw),
        lambda **kw: Task(**kw),
        lambda **kw: TaskStep(task_id="t", **kw),
        lambda **kw: ToolRun(tool_name="echo", **kw),
        lambda **kw: Permission(tool_name="t", verdict="allow", **kw),
        lambda **kw: AuditEvent(event_type="e", source="s", **kw),
        lambda **kw: Setting(key="k", **kw),
    ],
)
def test_empty_id_rejected(make):
    with pytest.raises(ValidationError):
        make(id="  ")


def test_naive_timestamps_rejected():
    naive = datetime(2026, 1, 1)  # noqa: DTZ001 — naive input is the point of this test
    with pytest.raises(ValidationError):
        Session(created_at=naive, updated_at=naive)


def test_required_links_rejected():
    with pytest.raises(ValidationError):
        Message(session_id="", role="user")
    with pytest.raises(ValidationError):
        Message(session_id="s", role="")
    with pytest.raises(ValidationError):
        TaskStep(task_id="")
    with pytest.raises(ValidationError):
        ToolRun(tool_name="")
    with pytest.raises(ValidationError):
        Permission(tool_name="t", verdict="")
    with pytest.raises(ValidationError):
        AuditEvent(event_type="", source="s")
    with pytest.raises(ValidationError):
        Setting(key="")


def test_memory_mirrors_contract_record_shape():
    memory = Memory(scope="user", content="remember", metadata={"k": "v"})
    assert memory.to_dict()["metadata"] == {"k": "v"}
    assert Memory.from_dict(memory.to_dict()) == memory


@pytest.mark.parametrize(
    "entity",
    [
        Session(id="s", title="t"),
        Message(id="m", session_id="s", role="user", content="hi"),
        Memory(id="m", content="c"),
        Task(id="t", title="title"),
        TaskStep(id="ts", task_id="t", label="step"),
        ToolRun(id="tr", tool_name="echo", task_id="t", payload={"a": 1}),
        Permission(id="p", tool_name="t", verdict="allow"),
        AuditEvent(id="a", event_type="e", source="s", correlation_id="c"),
        Setting(id="s", key="k", value="v"),
    ],
)
def test_serialization_round_trip(entity):
    assert type(entity).from_dict(entity.to_dict()) == entity


def test_json_payload_deterministic():
    first = models._dump_payload({"b": 1, "a": [3, 2]})
    second = models._dump_payload({"a": [3, 2], "b": 1})
    assert first == second == '{"a":[3,2],"b":1}'


def test_from_dict_rejects_bad_payload():
    with pytest.raises(ValidationError):
        Memory.from_dict(
            {
                "id": "m",
                "scope": "s",
                "content": "c",
                "metadata": "[1,2]",
                "created_at": utcnow().isoformat(),
                "updated_at": utcnow().isoformat(),
            }
        )
    with pytest.raises(ValidationError):
        Session.from_dict(
            {"id": "s", "title": "", "created_at": "2026-01-01", "updated_at": "2026-01-01"}
        )
