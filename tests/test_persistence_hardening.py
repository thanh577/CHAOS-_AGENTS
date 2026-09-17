"""Persistence contract hardening tests (T0.8).

Pins semantics the contract now guarantees explicitly:
timestamps on update, corrupt-row mapping, transaction ownership,
migration ordering, settings/audit semantics, backend-type boundary.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from chaos.ha_tang.contracts.errors import ValidationError
from chaos.ha_tang.persistence.models import Memory, Session, Setting, Task
from chaos.ha_tang.persistence.sqlite_store import (
    Migration,
    SqliteDatabase,
    migrate,
    repositories,
)


@pytest.fixture()
def database(tmp_path):
    db = SqliteDatabase(tmp_path / "hard.db")
    db.initialize()
    yield db
    db.close()


@pytest.fixture()
def repos(database):
    return repositories(database)


def _at(year: int) -> datetime:
    return datetime(year, 6, 1, tzinfo=UTC)


def test_update_preserves_created_at_and_refreshes_updated_at(repos):
    sessions = repos["sessions"]
    created = sessions.create(
        Session(id="s", title="v1", created_at=_at(2024), updated_at=_at(2024))
    )
    assert (created.created_at, created.updated_at) == (_at(2024), _at(2024))
    tampered = Session(id="s", title="v2", created_at=_at(2026), updated_at=_at(2024))
    stored = sessions.update(tampered)
    assert stored.created_at == _at(2024)  # immutable: stored value wins
    assert stored.updated_at >= _at(2024)
    assert stored.updated_at.tzinfo is not None
    assert stored.title == "v2"
    assert stored is not tampered  # frozen entities: update returns a new copy
    assert sessions.get("s") == stored


def test_update_returns_stored_copy_matching_readback(repos):
    tasks = repos["tasks"]
    tasks.create(Task(id="t", title="a"))
    first = tasks.update(Task(id="t", title="b", status="doing"))
    second = tasks.update(Task(id="t", title="c", status="doing"))
    assert first.updated_at <= second.updated_at
    assert tasks.get("t") == second


def test_corrupt_json_payload_maps_to_validation_error(database, repos):
    with database.transaction() as connection:
        connection.execute(
            text(
                "INSERT INTO memories (id, scope, content, metadata, created_at, updated_at) "
                "VALUES ('bad', 's', 'c', '[broken', '2026-01-01T00:00:00+00:00', "
                "'2026-01-01T00:00:00+00:00')"
            )
        )
    with pytest.raises(ValidationError, match="invalid memories row"):
        repos["memories"].get("bad")
    with pytest.raises(ValidationError, match="invalid memories row"):
        repos["memories"].list()


def test_multi_repository_atomic_composition(database, repos):
    sessions = repos["sessions"]
    tasks = repos["tasks"]
    with pytest.raises(ValidationError), database.transaction():
        sessions.create(Session(id="comp"))
        tasks.create(Task(id="comp"))
        sessions.create(Session(id="comp"))  # duplicate -> everything rolls back
    assert sessions.get("comp") is None
    assert tasks.get("comp") is None


def test_outer_commit_keeps_inner_work(database, repos):
    with database.transaction():
        repos["sessions"].create(Session(id="k1"))
        with database.transaction():
            repos["tasks"].create(Task(id="k2"))
    assert repos["sessions"].get("k1") is not None
    assert repos["tasks"].get("k2") is not None


def test_each_method_owns_its_transaction_without_caller(repos):
    repos["sessions"].create(Session(id="solo"))
    assert repos["sessions"].get("solo") is not None  # committed without outer tx


def test_migration_input_order_does_not_matter(tmp_path):
    # v3 depends on v2's table: applying input order would fail, so success
    # proves version sorting. (v1 already applied by initialize, version=1.)
    db = SqliteDatabase(tmp_path / "order.db")
    db.initialize()
    try:
        with db.transaction() as connection:
            version = migrate(
                connection,
                (
                    Migration(3, "seed", ("INSERT INTO t2 (id) VALUES ('x')",)),
                    Migration(2, "make", ("CREATE TABLE t2 (id TEXT)",)),
                ),
            )
        assert version == 3
        assert db.schema_version() == 3
        assert "t2" in db.table_names()
    finally:
        db.close()


def test_settings_create_duplicate_key_fails(repos):
    settings = repos["settings"]
    settings.create(Setting(id="a", key="theme", value="dark"))
    with pytest.raises(ValidationError):
        settings.create(Setting(id="b", key="theme", value="light"))


def test_settings_value_update_keeps_key(repos):
    settings = repos["settings"]
    settings.create(Setting(id="a", key="theme", value="dark"))
    updated = settings.update(Setting(id="a", key="theme", value="light"))
    assert updated.value == "light"
    assert settings.get("a").value == "light"


def test_list_empty_table_returns_empty_list(repos):
    assert repos["tasks"].list() == []
    assert repos["audit_events"].list(limit=10, offset=5) == []


def test_repository_returns_domain_models_only(repos):
    sessions = repos["sessions"]
    created = sessions.create(Session(id="s", title="t"))
    assert type(created).__module__ == "chaos.ha_tang.persistence.models"
    fetched = sessions.get("s")
    assert type(fetched) is Session
    listed = sessions.list()
    assert all(type(item) is Session for item in listed)
    for item in (created, fetched, *listed):
        assert type(item).__module__.split(".")[0] == "chaos"


def test_memory_metadata_survives_json_round_trip_through_backend(repos):
    memories = repos["memories"]
    created = memories.create(Memory(id="m", content="c", metadata={"n": {"x": [1, 2]}}))
    assert memories.get("m") == created
