"""Migration tests: ordering, repeatability, legacy upgrade, failure."""

import sqlite3

import pytest

from chaos.ha_tang.contracts.errors import ExecutionError
from chaos.ha_tang.persistence.models import Session
from chaos.ha_tang.persistence.sqlite_store import (
    MIGRATIONS,
    Migration,
    SqliteDatabase,
    migrate,
    repositories,
)


@pytest.fixture()
def database(tmp_path):
    db = SqliteDatabase(tmp_path / "mig.db")
    db.initialize()
    yield db
    db.close()


def test_registry_has_single_ordered_initial_migration():
    assert [(m.version, m.description) for m in MIGRATIONS] == [
        (1, "initial DATA_MODEL schema (9 tables)")
    ]
    assert all(m.statements for m in MIGRATIONS)


def test_migrate_repeatable(database):
    with database.transaction() as connection:
        assert migrate(connection) == 1
        assert migrate(connection) == 1
    assert database.schema_version() == 1


def test_upgrade_legacy_database_preserves_data(tmp_path):
    # Legacy layout: full sessions/messages tables but no version marker and
    # none of the other 7 tables. Column evolution (ALTER TABLE) belongs to
    # a future v2 migration, not this mechanism demo.
    path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(str(path))
    legacy.execute(
        "CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '', "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    legacy.execute(
        "CREATE TABLE messages (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, "
        "content TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    legacy.execute(
        "INSERT INTO sessions (id, title, created_at, updated_at) "
        "VALUES ('old', 'kept', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
    )
    legacy.commit()
    legacy.close()

    db = SqliteDatabase(path)
    db.initialize()
    try:
        assert db.schema_version() == 1
        assert "audit_events" in db.table_names()
        assert "settings" in db.table_names()
        repos = repositories(db)
        assert repos["sessions"].get("old").title == "kept"
        repos["sessions"].create(Session(id="new", title="fresh"))
        assert repos["sessions"].get("new") is not None
    finally:
        db.close()


def test_failed_migration_leaves_version_untouched(tmp_path):
    path = tmp_path / "bad.db"
    db = SqliteDatabase(path)
    db.initialize()
    bad = (
        Migration(version=1, description="ok", statements=MIGRATIONS[0].statements),
        Migration(version=2, description="broken", statements=("CREATE TABLE broken (",)),
    )
    try:
        with (
            db.transaction() as connection,
            pytest.raises(ExecutionError, match="migration v2 failed"),
        ):
            migrate(connection, bad)
        assert db.schema_version() == 1
        assert "broken" not in db.table_names()
    finally:
        db.close()


def test_duplicate_migration_versions_rejected(database):
    from chaos.ha_tang.contracts.errors import ValidationError

    with (
        database.transaction() as connection,
        pytest.raises(ValidationError, match="duplicate migration versions"),
    ):
        migrate(
            connection,
            (
                Migration(version=1, description="a", statements=()),
                Migration(version=1, description="b", statements=()),
            ),
        )
