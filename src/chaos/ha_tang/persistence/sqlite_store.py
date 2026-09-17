"""SQLite persistence backend over SQLAlchemy Core (no ORM).

AGENTS.md section 17 mandates SQLAlchemy with a migration strategy;
this module is that backend. Architecture boundary holds:

```text
Domain Model (models.py, frozen dataclasses)
    ↓
Repository ABC (repository.py, backend-agnostic)
    ↓
This backend (SQLAlchemy Core only — no ORM Session/Engine leaks upward)
```

Ownership: :class:`SqliteDatabase` owns one explicit path, the engine,
schema migration and transactions. Nothing connects on import — the
engine opens only via :meth:`SqliteDatabase.initialize` and is disposed
via :meth:`SqliteDatabase.close`. ``AuditEvent`` support is
create/read/list only at the repository level (no update/delete).

Migrations: an ordered :data:`MIGRATIONS` registry (version, description,
statements). :func:`migrate` applies pending migrations in order, one
transaction per call from :meth:`initialize`; a failed migration raises
with the version marker untouched. No Alembic in M0.

Errors: constraint violations (duplicate identity, bad references)
surface as ``ValidationError``; driver/connection/migration failures
surface as ``ExecutionError`` — always ``raise ... from`` to keep the
original context, and messages never embed row values.
"""

import sqlite3
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Column,
    Connection,
    ForeignKey,
    MetaData,
    String,
    Table,
    create_engine,
    event,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CreateTable

from chaos.ha_tang.contracts.errors import ExecutionError, ValidationError
from chaos.ha_tang.persistence import models
from chaos.ha_tang.persistence.repository import Repository

SCHEMA_VERSION = 1

_METADATA = MetaData()

_SA_TABLES: dict[str, Table] = {
    "sessions": Table(
        "sessions",
        _METADATA,
        Column("id", String, primary_key=True),
        Column("title", String, nullable=False),
        Column("created_at", String, nullable=False),
        Column("updated_at", String, nullable=False),
    ),
    "messages": Table(
        "messages",
        _METADATA,
        Column("id", String, primary_key=True),
        Column("session_id", ForeignKey("sessions.id"), nullable=False),
        Column("role", String, nullable=False),
        Column("content", String, nullable=False),
        Column("created_at", String, nullable=False),
        Column("updated_at", String, nullable=False),
    ),
    "memories": Table(
        "memories",
        _METADATA,
        Column("id", String, primary_key=True),
        Column("scope", String, nullable=False),
        Column("content", String, nullable=False),
        Column("metadata", String, nullable=False),
        Column("created_at", String, nullable=False),
        Column("updated_at", String, nullable=False),
    ),
    "tasks": Table(
        "tasks",
        _METADATA,
        Column("id", String, primary_key=True),
        Column("title", String, nullable=False),
        Column("status", String, nullable=False),
        Column("created_at", String, nullable=False),
        Column("updated_at", String, nullable=False),
    ),
    "task_steps": Table(
        "task_steps",
        _METADATA,
        Column("id", String, primary_key=True),
        Column("task_id", ForeignKey("tasks.id"), nullable=False),
        Column("label", String, nullable=False),
        Column("status", String, nullable=False),
        Column("created_at", String, nullable=False),
        Column("updated_at", String, nullable=False),
    ),
    "tool_runs": Table(
        "tool_runs",
        _METADATA,
        Column("id", String, primary_key=True),
        Column("tool_name", String, nullable=False),
        Column("status", String, nullable=False),
        Column("task_id", ForeignKey("tasks.id"), nullable=True),
        Column("payload", String, nullable=False),
        Column("created_at", String, nullable=False),
        Column("updated_at", String, nullable=False),
    ),
    "permissions": Table(
        "permissions",
        _METADATA,
        Column("id", String, primary_key=True),
        Column("tool_name", String, nullable=False),
        Column("verdict", String, nullable=False),
        Column("reason", String, nullable=False),
        Column("created_at", String, nullable=False),
        Column("updated_at", String, nullable=False),
    ),
    "audit_events": Table(
        "audit_events",
        _METADATA,
        Column("id", String, primary_key=True),
        Column("event_type", String, nullable=False),
        Column("source", String, nullable=False),
        Column("payload", String, nullable=False),
        Column("correlation_id", String, nullable=True),
        Column("created_at", String, nullable=False),
        Column("updated_at", String, nullable=False),
    ),
    "settings": Table(
        "settings",
        _METADATA,
        Column("id", String, primary_key=True),
        Column("key", String, nullable=False, unique=True),
        Column("value", String, nullable=False),
        Column("created_at", String, nullable=False),
        Column("updated_at", String, nullable=False),
    ),
}

# DDL order follows ownership (parents before children); kept explicit
# so future migrations append without reordering history.
_DDL_ORDER = (
    "sessions",
    "messages",
    "memories",
    "tasks",
    "task_steps",
    "tool_runs",
    "permissions",
    "audit_events",
    "settings",
)


@dataclass(frozen=True)
class _Table[T]:
    """Explicit row mapping for one entity — plain metadata, not an ORM."""

    name: str
    columns: tuple[str, ...]
    to_row: Callable[[T], tuple[Any, ...]]
    from_row: Callable[[Mapping[str, Any]], T]


def _mapping_to_session(data: Mapping[str, Any]) -> models.Session:
    return models.Session.from_dict(data)


def _mapping_to_message(data: Mapping[str, Any]) -> models.Message:
    return models.Message.from_dict(data)


def _mapping_to_memory(data: Mapping[str, Any]) -> models.Memory:
    return models.Memory.from_dict(data)


def _mapping_to_task(data: Mapping[str, Any]) -> models.Task:
    return models.Task.from_dict(data)


def _mapping_to_task_step(data: Mapping[str, Any]) -> models.TaskStep:
    return models.TaskStep.from_dict(data)


def _mapping_to_tool_run(data: Mapping[str, Any]) -> models.ToolRun:
    return models.ToolRun.from_dict(data)


def _mapping_to_permission(data: Mapping[str, Any]) -> models.Permission:
    return models.Permission.from_dict(data)


def _mapping_to_audit_event(data: Mapping[str, Any]) -> models.AuditEvent:
    return models.AuditEvent.from_dict(data)


def _mapping_to_setting(data: Mapping[str, Any]) -> models.Setting:
    return models.Setting.from_dict(data)


TABLES: dict[str, _Table[Any]] = {
    "sessions": _Table(
        name="sessions",
        columns=("id", "title", "created_at", "updated_at"),
        to_row=lambda e: (e.id, e.title, e.created_at.isoformat(), e.updated_at.isoformat()),
        from_row=_mapping_to_session,
    ),
    "messages": _Table(
        name="messages",
        columns=("id", "session_id", "role", "content", "created_at", "updated_at"),
        to_row=lambda e: (
            e.id,
            e.session_id,
            e.role,
            e.content,
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_mapping_to_message,
    ),
    "memories": _Table(
        name="memories",
        columns=("id", "scope", "content", "metadata", "created_at", "updated_at"),
        to_row=lambda e: (
            e.id,
            e.scope,
            e.content,
            models._dump_payload(e.metadata),
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_mapping_to_memory,
    ),
    "tasks": _Table(
        name="tasks",
        columns=("id", "title", "status", "created_at", "updated_at"),
        to_row=lambda e: (
            e.id,
            e.title,
            e.status,
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_mapping_to_task,
    ),
    "task_steps": _Table(
        name="task_steps",
        columns=("id", "task_id", "label", "status", "created_at", "updated_at"),
        to_row=lambda e: (
            e.id,
            e.task_id,
            e.label,
            e.status,
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_mapping_to_task_step,
    ),
    "tool_runs": _Table(
        name="tool_runs",
        columns=("id", "tool_name", "status", "task_id", "payload", "created_at", "updated_at"),
        to_row=lambda e: (
            e.id,
            e.tool_name,
            e.status,
            e.task_id,
            models._dump_payload(e.payload),
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_mapping_to_tool_run,
    ),
    "permissions": _Table(
        name="permissions",
        columns=("id", "tool_name", "verdict", "reason", "created_at", "updated_at"),
        to_row=lambda e: (
            e.id,
            e.tool_name,
            e.verdict,
            e.reason,
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_mapping_to_permission,
    ),
    "audit_events": _Table(
        name="audit_events",
        columns=(
            "id",
            "event_type",
            "source",
            "payload",
            "correlation_id",
            "created_at",
            "updated_at",
        ),
        to_row=lambda e: (
            e.id,
            e.event_type,
            e.source,
            models._dump_payload(e.payload),
            e.correlation_id,
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_mapping_to_audit_event,
    ),
    "settings": _Table(
        name="settings",
        columns=("id", "key", "value", "created_at", "updated_at"),
        to_row=lambda e: (
            e.id,
            e.key,
            e.value,
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_mapping_to_setting,
    ),
}


@dataclass(frozen=True)
class Migration:
    """One ordered schema step: identity, description, statements."""

    version: int
    description: str
    statements: tuple[str, ...]


def _create_table_statements() -> tuple[str, ...]:
    return tuple(str(CreateTable(_SA_TABLES[name], if_not_exists=True)) for name in _DDL_ORDER)


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        description="initial DATA_MODEL schema (9 tables)",
        statements=_create_table_statements(),
    ),
)


def _read_version(connection: Connection) -> int:
    names = {
        row[0]
        for row in connection.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'table'")
        ).fetchall()
    }
    if "schema_version" not in names:
        return 0
    row = connection.execute(text("SELECT version FROM schema_version WHERE id = 1")).fetchone()
    return int(row[0]) if row is not None else 0


def _write_version(connection: Connection, version: int) -> None:
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            "id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO schema_version (id, version) VALUES (1, :version) "
            "ON CONFLICT(id) DO UPDATE SET version = excluded.version"
        ),
        {"version": version},
    )


def migrate(connection: Connection, migrations: Sequence[Migration] = MIGRATIONS) -> int:
    """Apply pending migrations in version order, returning the version.

    Each call runs inside the caller's transaction: a failed migration
    aborts with the version marker untouched.
    """
    ordered = sorted(migrations, key=lambda migration: migration.version)
    versions = [migration.version for migration in ordered]
    if len(set(versions)) != len(versions):
        raise ValidationError("duplicate migration versions")
    current = _read_version(connection)
    for migration in ordered:
        if migration.version <= current:
            continue
        try:
            for statement in migration.statements:
                connection.execute(text(statement))
            _write_version(connection, migration.version)
        except SQLAlchemyError as exc:
            raise ExecutionError(f"migration v{migration.version} failed") from exc
        current = migration.version
    return current


def _enable_foreign_keys(dbapi_connection: sqlite3.Connection, _: Any) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys = ON")


class SqliteDatabase:
    """Owns one database file, its engine and its schema.

    Not integrated into ``ApplicationContext`` in M0 (explicit,
    independent lifecycle). A future milestone may attach it as a
    ``Service`` without changing this class.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._engine: Engine | None = None
        self._connection: Connection | None = None
        self._tx_depth = 0

    @property
    def path(self) -> Path:
        """Configured database path (the only filesystem location used)."""
        return self._path

    @property
    def is_open(self) -> bool:
        """Whether the engine is currently owned."""
        return self._engine is not None

    def initialize(self) -> None:
        """Create the engine and migrate the schema (idempotent).

        The engine is only assigned after a successful migration, so a
        failed initialize leaves ``is_open`` False and nothing to clean up.
        """
        if self._engine is not None:
            try:
                with self._engine.begin() as connection:
                    migrate(connection)
            except SQLAlchemyError as exc:
                raise ExecutionError("cannot initialize database schema") from exc
            return
        try:
            engine = create_engine(f"sqlite:///{self._path}")
        except SQLAlchemyError as exc:
            raise ExecutionError("cannot open database") from exc
        event.listen(engine, "connect", _enable_foreign_keys)
        try:
            with engine.begin() as connection:
                migrate(connection)
        except SQLAlchemyError as exc:
            engine.dispose()
            raise ExecutionError("cannot initialize database schema") from exc
        except Exception:
            engine.dispose()
            raise
        self._engine = engine

    def _require_engine(self) -> Engine:
        if self._engine is None:
            raise ExecutionError("database is not initialized (call initialize() first)")
        return self._engine

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        """Yield a transactional connection: commit on success, rollback
        on error. Nesting uses SAVEPOINTs, so repository calls compose
        inside an outer transaction. Single-threaded use only in M0.

        The outer boundary always emits an explicit ``BEGIN``: the
        pysqlite driver only begins implicitly before DML, so a
        SAVEPOINT-first transaction would otherwise self-commit on
        ``RELEASE``. Explicit BEGIN keeps DEFERRED semantics.
        """
        engine = self._require_engine()
        if self._tx_depth > 0 and self._connection is not None:
            connection = self._connection
            savepoint = connection.begin_nested()
            self._tx_depth += 1
            try:
                yield connection
            except Exception:
                savepoint.rollback()
                raise
            else:
                savepoint.commit()
            finally:
                self._tx_depth -= 1
            return
        with engine.begin() as connection:
            connection.execute(text("BEGIN"))
            self._connection = connection
            self._tx_depth = 1
            try:
                yield connection
            finally:
                self._connection = None
                self._tx_depth = 0

    def close(self) -> None:
        """Dispose the owned engine (idempotent)."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._connection = None
            self._tx_depth = 0

    def table_names(self) -> list[str]:
        """User tables present in the database (introspection helper)."""
        engine = self._require_engine()
        try:
            with engine.connect() as connection:
                rows = connection.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type = 'table' "
                        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                    )
                ).fetchall()
        except SQLAlchemyError as exc:
            raise ExecutionError("cannot inspect database schema") from exc
        return [row[0] for row in rows]

    def schema_version(self) -> int:
        """Version marker written by migration."""
        engine = self._require_engine()
        try:
            with engine.connect() as connection:
                return _read_version(connection)
        except SQLAlchemyError as exc:
            raise ExecutionError("cannot read schema version") from exc


class SqliteRepository[T](Repository[T]):
    """Generic ``Repository`` over one table. All statements use
    SQLAlchemy Core constructs — user input never touches SQL text."""

    def __init__(self, database: SqliteDatabase, table: _Table[T]) -> None:
        self._database = database
        self._table = table

    def _values(self, entity: T) -> dict[str, Any]:
        return dict(zip(self._table.columns, self._table.to_row(entity)))

    def _sa_table(self) -> Table:
        return _SA_TABLES[self._table.name]

    def create(self, entity: T) -> T:
        table = self._sa_table()
        try:
            with self._database.transaction() as connection:
                connection.execute(table.insert().values(**self._values(entity)))
        except SAIntegrityError as exc:
            raise ValidationError(f"cannot create {self._table.name} row") from exc
        except SQLAlchemyError as exc:
            raise ExecutionError(f"cannot create {self._table.name} row") from exc
        return entity

    def get(self, entity_id: str) -> T | None:
        table = self._sa_table()
        try:
            with self._database.transaction() as connection:
                row = (
                    connection.execute(table.select().where(table.c.id == entity_id))
                    .mappings()
                    .fetchone()
                )
        except SQLAlchemyError as exc:
            raise ExecutionError(f"cannot read {self._table.name} row") from exc
        if row is None:
            return None
        return self._convert_row(dict(row))

    def _convert_row(self, data: dict[str, Any]) -> T:
        """Map one row to its domain model. Corrupt stored data (bad
        JSON, missing columns, naive timestamps) surfaces as
        ``ValidationError`` — never a raw mapping/codec exception."""
        try:
            return self._table.from_row(data)
        except ValidationError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"invalid {self._table.name} row") from exc

    def list(self, *, limit: int = 100, offset: int = 0) -> list[T]:
        if limit < 0 or offset < 0:
            raise ValidationError("list limit/offset must not be negative")
        table = self._sa_table()
        try:
            with self._database.transaction() as connection:
                rows = (
                    connection.execute(
                        table.select()
                        .order_by(table.c.created_at, table.c.id)
                        .limit(limit)
                        .offset(offset)
                    )
                    .mappings()
                    .fetchall()
                )
        except SQLAlchemyError as exc:
            raise ExecutionError(f"cannot list {self._table.name} rows") from exc
        return [self._convert_row(dict(row)) for row in rows]

    def update(self, entity: T) -> T:
        """Replace a stored entity, returning the stored copy.

        ``created_at`` is immutable: the stored value always wins, even
        when the caller passes a different one. ``updated_at`` is
        refreshed to now by the repository — callers never stamp it.
        Entities are frozen, so the returned copy is a new object.
        """
        table = self._sa_table()
        current = self.get(self._values(entity)["id"])
        if current is None:
            raise ValidationError(f"{self._table.name} row does not exist")
        stamped = replace(entity, created_at=current.created_at, updated_at=models.utcnow())
        values = self._values(stamped)
        entity_id = values.pop("id")
        try:
            with self._database.transaction() as connection:
                result = connection.execute(
                    table.update().where(table.c.id == entity_id).values(**values)
                )
                if result.rowcount == 0:
                    raise ValidationError(f"{self._table.name} row does not exist")
        except ValidationError:
            raise
        except SAIntegrityError as exc:
            raise ValidationError(f"cannot update {self._table.name} row") from exc
        except SQLAlchemyError as exc:
            raise ExecutionError(f"cannot update {self._table.name} row") from exc
        return stamped

    def delete(self, entity_id: str) -> bool:
        table = self._sa_table()
        try:
            with self._database.transaction() as connection:
                result = connection.execute(table.delete().where(table.c.id == entity_id))
                return (result.rowcount or 0) > 0
        except SQLAlchemyError as exc:
            raise ExecutionError(f"cannot delete {self._table.name} row") from exc


class ReadOnlyRepository[T](SqliteRepository[T]):
    """Create/read/list-only view — used for append-only entities such
    as audit events, where update/delete have no meaning."""

    def update(self, entity: T) -> T:
        raise ValidationError(f"{self._table.name} rows are append-only")

    def delete(self, entity_id: str) -> bool:
        raise ValidationError(f"{self._table.name} rows are append-only")


def repositories(database: SqliteDatabase) -> dict[str, Repository[Any]]:
    """Build one repository per DATA_MODEL table. Audit events are
    append-only; everything else is full CRUD."""
    repos: dict[str, Repository[Any]] = {}
    for name, table in TABLES.items():
        if name == "audit_events":
            repos[name] = ReadOnlyRepository(database, table)
        else:
            repos[name] = SqliteRepository(database, table)
    return repos


__all__ = [
    "MIGRATIONS",
    "SCHEMA_VERSION",
    "TABLES",
    "Migration",
    "ReadOnlyRepository",
    "SqliteDatabase",
    "SqliteRepository",
    "migrate",
    "repositories",
]
