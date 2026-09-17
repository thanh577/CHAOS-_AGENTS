"""SQLite backend tests: schema, CRUD, transactions, cleanup (isolated tmp DBs)."""

import pytest

from chaos.ha_tang.contracts.errors import ExecutionError, ValidationError
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
)
from chaos.ha_tang.persistence.sqlite_store import (
    SCHEMA_VERSION,
    TABLES,
    SqliteDatabase,
    SqliteRepository,
    repositories,
)


@pytest.fixture()
def database(tmp_path):
    db = SqliteDatabase(tmp_path / "test.db")
    assert db.is_open is False  # nothing connects on construction
    db.initialize()
    yield db
    db.close()
    assert db.is_open is False


@pytest.fixture()
def repos(database):
    return repositories(database)


def test_schema_covers_all_data_model_tables(database):
    assert sorted(database.table_names()) == [
        "audit_events",
        "memories",
        "messages",
        "permissions",
        "schema_version",
        "sessions",
        "settings",
        "task_steps",
        "tasks",
        "tool_runs",
    ]
    assert set(TABLES) == {
        "sessions",
        "messages",
        "memories",
        "tasks",
        "task_steps",
        "tool_runs",
        "permissions",
        "audit_events",
        "settings",
    }
    assert database.schema_version() == SCHEMA_VERSION == 1


def test_initialization_idempotent(tmp_path):
    db = SqliteDatabase(tmp_path / "idem.db")
    db.initialize()
    db.initialize()  # second run must not fail or duplicate
    assert db.schema_version() == 1
    assert db.table_names().count("sessions") == 1
    db.close()
    db.close()  # close idempotent too


def test_operations_require_initialize(tmp_path):
    db = SqliteDatabase(tmp_path / "lazy.db")
    with pytest.raises(ExecutionError, match="not initialized"):
        db.table_names()
    with pytest.raises(ExecutionError, match="not initialized"):
        SqliteRepository(db, TABLES["sessions"]).list()


def test_connection_failure_maps_to_execution_error(tmp_path):
    db = SqliteDatabase(tmp_path / "no-such-dir" / "test.db")
    with pytest.raises(ExecutionError):
        db.initialize()
    assert db.is_open is False


def test_session_crud(repos):
    sessions = repos["sessions"]
    created = sessions.create(Session(id="s1", title="hello"))
    assert sessions.get("s1") == created
    assert sessions.get("missing") is None
    updated = sessions.update(Session(id="s1", title="renamed"))
    assert sessions.get("s1").title == "renamed"
    assert updated.title == "renamed"
    assert sessions.delete("s1") is True
    assert sessions.delete("s1") is False
    assert sessions.get("s1") is None


def test_duplicate_identity_fails(repos):
    repos["sessions"].create(Session(id="dup"))
    with pytest.raises(ValidationError):
        repos["sessions"].create(Session(id="dup"))


def test_update_missing_fails(repos):
    with pytest.raises(ValidationError, match="does not exist"):
        repos["tasks"].update(Task(id="ghost", title="x"))


def test_update_conflicting_unique_key_fails(repos):
    settings = repos["settings"]
    settings.create(Setting(id="a", key="k1", value="v1"))
    settings.create(Setting(id="b", key="k2", value="v2"))
    with pytest.raises(ValidationError):
        settings.update(Setting(id="b", key="k1", value="v2"))


def test_message_requires_session(repos):
    with pytest.raises(ValidationError):
        repos["messages"].create(Message(id="m1", session_id="nope", role="user", content="hi"))
    repos["sessions"].create(Session(id="s1"))
    repos["messages"].create(Message(id="m1", session_id="s1", role="user", content="hi"))
    assert repos["messages"].get("m1").content == "hi"


def test_task_step_requires_task(repos):
    with pytest.raises(ValidationError):
        repos["task_steps"].create(TaskStep(id="ts", task_id="nope", label="x"))
    repos["tasks"].create(Task(id="t1", title="work"))
    repos["task_steps"].create(TaskStep(id="ts", task_id="t1", label="step one"))
    assert repos["task_steps"].get("ts").label == "step one"


def test_tool_run_optional_task_link(repos):
    repos["tool_runs"].create(ToolRun(id="r1", tool_name="echo", payload={"a": 1}))
    assert repos["tool_runs"].get("r1").task_id is None
    repos["tasks"].create(Task(id="t1"))
    repos["tool_runs"].create(ToolRun(id="r2", tool_name="echo", task_id="t1"))
    with pytest.raises(ValidationError):
        repos["tool_runs"].create(ToolRun(id="r3", tool_name="echo", task_id="ghost"))


def test_list_order_and_pagination(repos):
    memories = repos["memories"]
    for index in range(5):
        memories.create(Memory(id=f"m{index}", content=f"c{index}"))
    page = memories.list(limit=2, offset=1)
    assert [m.id for m in page] == ["m1", "m2"]
    assert len(memories.list()) == 5
    assert memories.list(limit=0) == []
    with pytest.raises(ValidationError):
        memories.list(limit=-1)


def test_transaction_rollback_on_failure(database, repos):
    sessions = repos["sessions"]
    with pytest.raises(ValidationError), database.transaction():
        sessions.create(Session(id="tx1"))
        sessions.create(Session(id="tx1"))  # duplicate -> rollback
    assert sessions.get("tx1") is None


def test_nested_transaction_inner_rollback_keeps_outer(database, repos):
    sessions = repos["sessions"]
    with database.transaction():
        sessions.create(Session(id="outer"))
        with pytest.raises(ValidationError), database.transaction():
            sessions.create(Session(id="inner"))
            sessions.create(Session(id="inner"))  # duplicate -> inner rollback only
        sessions.create(Session(id="outer2"))
    assert sessions.get("outer") is not None
    assert sessions.get("outer2") is not None
    assert sessions.get("inner") is None


def test_transaction_commits_across_repositories(database, repos):
    from sqlalchemy import text

    with database.transaction() as connection:
        connection.execute(
            text(
                "INSERT INTO sessions (id, title, created_at, updated_at) "
                "VALUES (:id, :title, :created, :updated)"
            ),
            {
                "id": "txs",
                "title": "t",
                "created": "2026-01-01T00:00:00+00:00",
                "updated": "2026-01-01T00:00:00+00:00",
            },
        )
        connection.execute(
            text(
                "INSERT INTO messages (id, session_id, role, content, created_at, updated_at) "
                "VALUES (:id, :session, :role, :content, :created, :updated)"
            ),
            {
                "id": "txm",
                "session": "txs",
                "role": "user",
                "content": "hi",
                "created": "2026-01-01T00:00:00+00:00",
                "updated": "2026-01-01T00:00:00+00:00",
            },
        )
    assert repos["messages"].get("txm").session_id == "txs"


def test_audit_events_append_only(repos):
    audit = repos["audit_events"]
    created = audit.create(
        AuditEvent(id="a1", event_type="tool.done", source="cong_cu", correlation_id="c")
    )
    assert audit.get("a1") == created
    assert [event.id for event in audit.list()] == ["a1"]
    with pytest.raises(ValidationError, match="append-only"):
        audit.update(created)
    with pytest.raises(ValidationError, match="append-only"):
        audit.delete("a1")


def test_permission_round_trip(repos):
    permissions = repos["permissions"]
    created = permissions.create(
        Permission(id="p1", tool_name="wipe", verdict="block", reason="destructive")
    )
    assert permissions.get("p1") == created


def test_close_breaks_operations(database, repos):
    database.close()
    with pytest.raises(ExecutionError, match="not initialized"):
        repos["sessions"].list()


def test_engine_connection_uses_mappings_and_foreign_keys(database):
    from sqlalchemy import text

    with database.transaction() as connection:
        assert connection.execute(text("SELECT 1")).fetchone()[0] == 1
        assert connection.execute(text("PRAGMA foreign_keys")).fetchone()[0] == 1
        empty = connection.execute(text("SELECT * FROM sessions")).mappings().fetchall()
        assert empty == []
