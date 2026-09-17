"""SQLite persistence backend (stdlib ``sqlite3`` only).

Ownership: :class:`SqliteDatabase` owns one explicit path, one
connection, schema initialization and transactions. Nothing connects
on import — the database opens only via :meth:`SqliteDatabase.initialize`
and closes via :meth:`SqliteDatabase.close`. ``AuditEvent`` support is
create/read/list only at the repository level (no update/delete).

Schema: ``CREATE TABLE IF NOT EXISTS`` per DATA_MODEL table plus a
``schema_version`` row (currently 1) as the minimal version marker —
no migration framework in M0. Foreign keys are enforced
(``PRAGMA foreign_keys = ON``).

Errors: constraint violations (duplicate identity, bad references,
invalid data reaching the backend) surface as ``ValidationError``;
driver/connection failures surface as ``ExecutionError`` — always
``raise ... from`` to keep the original context, and messages never
embed row values.
"""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chaos.ha_tang.contracts.errors import ExecutionError, ValidationError
from chaos.ha_tang.persistence import models
from chaos.ha_tang.persistence.repository import Repository

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class _Table[T]:
    """Explicit row mapping for one entity — plain metadata, not an ORM."""

    name: str
    columns: tuple[str, ...]
    ddl: str
    to_row: Callable[[T], tuple[Any, ...]]
    from_row: Callable[[sqlite3.Row], T]


def _row_to_session(row: sqlite3.Row) -> models.Session:
    return models.Session.from_dict(dict(row))


def _row_to_message(row: sqlite3.Row) -> models.Message:
    return models.Message.from_dict(dict(row))


def _row_to_memory(row: sqlite3.Row) -> models.Memory:
    return models.Memory.from_dict(dict(row))


def _row_to_task(row: sqlite3.Row) -> models.Task:
    return models.Task.from_dict(dict(row))


def _row_to_task_step(row: sqlite3.Row) -> models.TaskStep:
    return models.TaskStep.from_dict(dict(row))


def _row_to_tool_run(row: sqlite3.Row) -> models.ToolRun:
    return models.ToolRun.from_dict(dict(row))


def _row_to_permission(row: sqlite3.Row) -> models.Permission:
    return models.Permission.from_dict(dict(row))


def _row_to_audit_event(row: sqlite3.Row) -> models.AuditEvent:
    return models.AuditEvent.from_dict(dict(row))


def _row_to_setting(row: sqlite3.Row) -> models.Setting:
    return models.Setting.from_dict(dict(row))


TABLES: dict[str, _Table[Any]] = {
    "sessions": _Table(
        name="sessions",
        columns=("id", "title", "created_at", "updated_at"),
        ddl="""CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        to_row=lambda e: (e.id, e.title, e.created_at.isoformat(), e.updated_at.isoformat()),
        from_row=_row_to_session,
    ),
    "messages": _Table(
        name="messages",
        columns=("id", "session_id", "role", "content", "created_at", "updated_at"),
        ddl="""CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            role TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        to_row=lambda e: (
            e.id,
            e.session_id,
            e.role,
            e.content,
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_row_to_message,
    ),
    "memories": _Table(
        name="memories",
        columns=("id", "scope", "content", "metadata", "created_at", "updated_at"),
        ddl="""CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            scope TEXT NOT NULL DEFAULT 'default',
            content TEXT NOT NULL DEFAULT '',
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        to_row=lambda e: (
            e.id,
            e.scope,
            e.content,
            models._dump_payload(e.metadata),
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_row_to_memory,
    ),
    "tasks": _Table(
        name="tasks",
        columns=("id", "title", "status", "created_at", "updated_at"),
        ddl="""CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        to_row=lambda e: (
            e.id,
            e.title,
            e.status,
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_row_to_task,
    ),
    "task_steps": _Table(
        name="task_steps",
        columns=("id", "task_id", "label", "status", "created_at", "updated_at"),
        ddl="""CREATE TABLE IF NOT EXISTS task_steps (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL REFERENCES tasks(id),
            label TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        to_row=lambda e: (
            e.id,
            e.task_id,
            e.label,
            e.status,
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_row_to_task_step,
    ),
    "tool_runs": _Table(
        name="tool_runs",
        columns=("id", "tool_name", "status", "task_id", "payload", "created_at", "updated_at"),
        ddl="""CREATE TABLE IF NOT EXISTS tool_runs (
            id TEXT PRIMARY KEY,
            tool_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            task_id TEXT NULL REFERENCES tasks(id),
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        to_row=lambda e: (
            e.id,
            e.tool_name,
            e.status,
            e.task_id,
            models._dump_payload(e.payload),
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_row_to_tool_run,
    ),
    "permissions": _Table(
        name="permissions",
        columns=("id", "tool_name", "verdict", "reason", "created_at", "updated_at"),
        ddl="""CREATE TABLE IF NOT EXISTS permissions (
            id TEXT PRIMARY KEY,
            tool_name TEXT NOT NULL,
            verdict TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        to_row=lambda e: (
            e.id,
            e.tool_name,
            e.verdict,
            e.reason,
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_row_to_permission,
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
        ddl="""CREATE TABLE IF NOT EXISTS audit_events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            source TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            correlation_id TEXT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        to_row=lambda e: (
            e.id,
            e.event_type,
            e.source,
            models._dump_payload(e.payload),
            e.correlation_id,
            e.created_at.isoformat(),
            e.updated_at.isoformat(),
        ),
        from_row=_row_to_audit_event,
    ),
    "settings": _Table(
        name="settings",
        columns=("id", "key", "value", "created_at", "updated_at"),
        ddl="""CREATE TABLE IF NOT EXISTS settings (
            id TEXT PRIMARY KEY,
            key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        to_row=lambda e: (e.id, e.key, e.value, e.created_at.isoformat(), e.updated_at.isoformat()),
        from_row=_row_to_setting,
    ),
}


class SqliteDatabase:
    """Owns one database file, its connection and its schema.

    Not integrated into ``ApplicationContext`` in M0 (explicit,
    independent lifecycle — see T0.6 report). A future milestone may
    attach it as a ``Service`` without changing this class.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._connection: sqlite3.Connection | None = None
        self._tx_depth = 0

    @property
    def path(self) -> Path:
        """Configured database path (the only filesystem location used)."""
        return self._path

    @property
    def is_open(self) -> bool:
        """Whether a connection is currently owned."""
        return self._connection is not None

    def initialize(self) -> None:
        """Open the connection and create the schema (idempotent)."""
        if self._connection is not None:
            self._ensure_schema(self._connection)
            return
        try:
            connection = sqlite3.connect(str(self._path), isolation_level=None)
        except sqlite3.Error as exc:
            raise ExecutionError("cannot open database") from exc
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            self._ensure_schema(connection)
            connection.commit()
        except sqlite3.Error as exc:
            connection.close()
            raise ExecutionError("cannot initialize database schema") from exc
        self._connection = connection

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL
            )"""
        )
        for table in TABLES.values():
            connection.execute(table.ddl)
        connection.execute(
            "INSERT INTO schema_version (id, version) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET version = excluded.version",
            (SCHEMA_VERSION,),
        )

    def _connection_or_raise(self) -> sqlite3.Connection:
        if self._connection is None:
            raise ExecutionError("database is not initialized (call initialize() first)")
        return self._connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Yield the connection in a transaction: commit on success,
        rollback on error. Nesting is supported via SAVEPOINTs, so
        repository calls compose inside an outer transaction —
        a failure anywhere rolls back to the outermost boundary.
        Single-threaded use only in M0."""
        connection = self._connection_or_raise()
        depth = self._tx_depth
        if depth == 0:
            connection.execute("BEGIN")
        else:
            connection.execute(f"SAVEPOINT chaos_{depth}")
        self._tx_depth = depth + 1
        try:
            yield connection
        except Exception:
            self._tx_depth = depth
            if depth == 0:
                connection.execute("ROLLBACK")
            else:
                connection.execute(f"ROLLBACK TO chaos_{depth}")
                connection.execute(f"RELEASE chaos_{depth}")
            raise
        self._tx_depth = depth
        if depth == 0:
            connection.execute("COMMIT")
        else:
            connection.execute(f"RELEASE chaos_{depth}")

    def close(self) -> None:
        """Release the owned connection (idempotent)."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def table_names(self) -> list[str]:
        """User tables present in the database (introspection helper)."""
        connection = self._connection_or_raise()
        try:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall()
        except sqlite3.Error as exc:
            raise ExecutionError("cannot inspect database schema") from exc
        return [row["name"] for row in rows]

    def schema_version(self) -> int:
        """Version marker written by initialization."""
        connection = self._connection_or_raise()
        try:
            row = connection.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
        except sqlite3.Error as exc:
            raise ExecutionError("cannot read schema version") from exc
        if row is None:
            raise ExecutionError("schema version marker is missing")
        return int(row["version"])


class SqliteRepository[T](Repository[T]):
    """Generic ``Repository`` over one table. All statements are
    parameterized — user input never touches SQL text."""

    def __init__(self, database: SqliteDatabase, table: _Table[T]) -> None:
        self._database = database
        self._table = table

    def create(self, entity: T) -> T:
        placeholders = ", ".join("?" for _ in self._table.columns)
        sql = f"INSERT INTO {self._table.name} ({', '.join(self._table.columns)}) VALUES ({placeholders})"
        try:
            with self._database.transaction() as connection:
                connection.execute(sql, self._table.to_row(entity))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(f"cannot create {self._table.name} row") from exc
        except sqlite3.Error as exc:
            raise ExecutionError(f"cannot create {self._table.name} row") from exc
        return entity

    def get(self, entity_id: str) -> T | None:
        sql = f"SELECT * FROM {self._table.name} WHERE id = ?"
        try:
            connection = self._database._connection_or_raise()
            row = connection.execute(sql, (entity_id,)).fetchone()
        except sqlite3.Error as exc:
            raise ExecutionError(f"cannot read {self._table.name} row") from exc
        if row is None:
            return None
        return self._table.from_row(row)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[T]:
        if limit < 0 or offset < 0:
            raise ValidationError("list limit/offset must not be negative")
        sql = f"SELECT * FROM {self._table.name} ORDER BY created_at, id LIMIT ? OFFSET ?"
        try:
            connection = self._database._connection_or_raise()
            rows = connection.execute(sql, (limit, offset)).fetchall()
        except sqlite3.Error as exc:
            raise ExecutionError(f"cannot list {self._table.name} rows") from exc
        return [self._table.from_row(row) for row in rows]

    def update(self, entity: T) -> T:
        assignments = ", ".join(f"{column} = ?" for column in self._table.columns if column != "id")
        sql = f"UPDATE {self._table.name} SET {assignments} WHERE id = ?"
        values = [
            value
            for column, value in zip(self._table.columns, self._table.to_row(entity))
            if column != "id"
        ]
        entity_id = self._table.to_row(entity)[0]
        try:
            with self._database.transaction() as connection:
                cursor = connection.execute(sql, (*values, entity_id))
                if cursor.rowcount == 0:
                    raise ValidationError(f"{self._table.name} row does not exist")
        except ValidationError:
            raise
        except sqlite3.IntegrityError as exc:
            raise ValidationError(f"cannot update {self._table.name} row") from exc
        except sqlite3.Error as exc:
            raise ExecutionError(f"cannot update {self._table.name} row") from exc
        return entity

    def delete(self, entity_id: str) -> bool:
        sql = f"DELETE FROM {self._table.name} WHERE id = ?"
        try:
            with self._database.transaction() as connection:
                cursor = connection.execute(sql, (entity_id,))
                return cursor.rowcount > 0
        except sqlite3.Error as exc:
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
    "SCHEMA_VERSION",
    "TABLES",
    "ReadOnlyRepository",
    "SqliteDatabase",
    "SqliteRepository",
    "repositories",
]
