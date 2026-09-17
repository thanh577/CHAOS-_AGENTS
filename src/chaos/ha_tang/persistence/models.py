"""Persistence domain models — one frozen dataclass per DATA_MODEL table.

Source of truth for *table names* is ``docs/spec/DATA_MODEL.md``
(sessions, messages, memories, tasks, task_steps, tool_runs,
permissions, audit_events, settings). That spec defines no fields,
so the minimal column sets below are **agent-defined, reversible**:
identity + UTC timestamps on every entity, obvious ownership links,
and JSON payload/metadata where the domain is schemaless by nature.
No business logic, no I/O, no connections here.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from chaos.ha_tang.contracts.errors import ValidationError


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp (single format project-wide)."""
    return datetime.now(UTC)


def new_id() -> str:
    """Stable string identity for entities."""
    return uuid4().hex


def _require_id(value: str) -> None:
    if not value or not value.strip():
        raise ValidationError("entity id must not be empty")


def _require_aware(moment: datetime, *, field_name: str) -> None:
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        raise ValidationError(f"{field_name} must be a timezone-aware datetime")


def _dump_payload(data: Mapping[str, Any]) -> str:
    """Deterministic JSON encoding (sorted keys, no whitespace drift)."""
    return json.dumps(dict(data), sort_keys=True, separators=(",", ":"))


def _load_payload(raw: str) -> dict[str, Any]:
    decoded = json.loads(raw)
    if not isinstance(decoded, dict):
        raise ValidationError("payload column must hold a JSON object")
    return decoded


def _parse_time(raw: str) -> datetime:
    moment = datetime.fromisoformat(raw)
    if moment.tzinfo is None:
        raise ValidationError("stored timestamps must be timezone-aware")
    return moment


@dataclass(frozen=True)
class Session:
    """A conversation/session container."""

    id: str = field(default_factory=new_id)
    title: str = ""
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        _require_id(self.id)
        _require_aware(self.created_at, field_name="created_at")
        _require_aware(self.updated_at, field_name="updated_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Session":
        return cls(
            id=str(data["id"]),
            title=str(data.get("title", "")),
            created_at=_parse_time(str(data["created_at"])),
            updated_at=_parse_time(str(data["updated_at"])),
        )


@dataclass(frozen=True)
class Message:
    """One message inside a session."""

    id: str = field(default_factory=new_id)
    session_id: str = ""
    role: str = ""
    content: str = ""
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        _require_id(self.id)
        if not self.session_id.strip():
            raise ValidationError("message session_id must not be empty")
        if not self.role.strip():
            raise ValidationError("message role must not be empty")
        _require_aware(self.created_at, field_name="created_at")
        _require_aware(self.updated_at, field_name="updated_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Message":
        return cls(
            id=str(data["id"]),
            session_id=str(data["session_id"]),
            role=str(data["role"]),
            content=str(data.get("content", "")),
            created_at=_parse_time(str(data["created_at"])),
            updated_at=_parse_time(str(data["updated_at"])),
        )


@dataclass(frozen=True)
class Memory:
    """A stored memory. Shape mirrors the T0.2 ``MemoryRecord`` contract
    (id/scope/content/metadata/timestamps) so the future M8 backend can
    adopt this table without translation."""

    id: str = field(default_factory=new_id)
    scope: str = "default"
    content: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        _require_id(self.id)
        _require_aware(self.created_at, field_name="created_at")
        _require_aware(self.updated_at, field_name="updated_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scope": self.scope,
            "content": self.content,
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Memory":
        metadata = data.get("metadata", {})
        if isinstance(metadata, str):
            metadata = _load_payload(metadata)
        if not isinstance(metadata, Mapping):
            raise ValidationError("memory metadata must be a mapping")
        return cls(
            id=str(data["id"]),
            scope=str(data.get("scope", "default")),
            content=str(data.get("content", "")),
            metadata=dict(metadata),
            created_at=_parse_time(str(data["created_at"])),
            updated_at=_parse_time(str(data["updated_at"])),
        )


@dataclass(frozen=True)
class Task:
    """A unit of planned work. ``status`` stays a plain string — the
    spec defines no lifecycle values, so none are invented here."""

    id: str = field(default_factory=new_id)
    title: str = ""
    status: str = "pending"
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        _require_id(self.id)
        _require_aware(self.created_at, field_name="created_at")
        _require_aware(self.updated_at, field_name="updated_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Task":
        return cls(
            id=str(data["id"]),
            title=str(data.get("title", "")),
            status=str(data.get("status", "pending")),
            created_at=_parse_time(str(data["created_at"])),
            updated_at=_parse_time(str(data["updated_at"])),
        )


@dataclass(frozen=True)
class TaskStep:
    """One step inside a task."""

    id: str = field(default_factory=new_id)
    task_id: str = ""
    label: str = ""
    status: str = "pending"
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        _require_id(self.id)
        if not self.task_id.strip():
            raise ValidationError("task_step task_id must not be empty")
        _require_aware(self.created_at, field_name="created_at")
        _require_aware(self.updated_at, field_name="updated_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "label": self.label,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TaskStep":
        return cls(
            id=str(data["id"]),
            task_id=str(data["task_id"]),
            label=str(data.get("label", "")),
            status=str(data.get("status", "pending")),
            created_at=_parse_time(str(data["created_at"])),
            updated_at=_parse_time(str(data["updated_at"])),
        )


@dataclass(frozen=True)
class ToolRun:
    """Record of one tool execution. ``task_id`` is an optional,
    non-identifying link — the spec does not define step linkage,
    so none is asserted."""

    id: str = field(default_factory=new_id)
    tool_name: str = ""
    status: str = "pending"
    task_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        _require_id(self.id)
        if not self.tool_name.strip():
            raise ValidationError("tool_run tool_name must not be empty")
        _require_aware(self.created_at, field_name="created_at")
        _require_aware(self.updated_at, field_name="updated_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "status": self.status,
            "task_id": self.task_id,
            "payload": dict(self.payload),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ToolRun":
        payload = data.get("payload", {})
        if isinstance(payload, str):
            payload = _load_payload(payload)
        if not isinstance(payload, Mapping):
            raise ValidationError("tool_run payload must be a mapping")
        task_id = data.get("task_id")
        return cls(
            id=str(data["id"]),
            tool_name=str(data["tool_name"]),
            status=str(data.get("status", "pending")),
            task_id=str(task_id) if task_id is not None else None,
            payload=dict(payload),
            created_at=_parse_time(str(data["created_at"])),
            updated_at=_parse_time(str(data["updated_at"])),
        )


@dataclass(frozen=True)
class Permission:
    """Record of one permission decision (mirrors the T0.2
    ``PermissionDecision`` vocabulary without importing the engine)."""

    id: str = field(default_factory=new_id)
    tool_name: str = ""
    verdict: str = ""
    reason: str = ""
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        _require_id(self.id)
        if not self.tool_name.strip():
            raise ValidationError("permission tool_name must not be empty")
        if not self.verdict.strip():
            raise ValidationError("permission verdict must not be empty")
        _require_aware(self.created_at, field_name="created_at")
        _require_aware(self.updated_at, field_name="updated_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "verdict": self.verdict,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Permission":
        return cls(
            id=str(data["id"]),
            tool_name=str(data["tool_name"]),
            verdict=str(data["verdict"]),
            reason=str(data.get("reason", "")),
            created_at=_parse_time(str(data["created_at"])),
            updated_at=_parse_time(str(data["updated_at"])),
        )


@dataclass(frozen=True)
class AuditEvent:
    """Immutable audit trail entry. No update/delete semantics —
    the repository exposes create/read/list only (enforced by tests)."""

    id: str = field(default_factory=new_id)
    event_type: str = ""
    source: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        _require_id(self.id)
        if not self.event_type.strip():
            raise ValidationError("audit event_type must not be empty")
        if not self.source.strip():
            raise ValidationError("audit source must not be empty")
        _require_aware(self.created_at, field_name="created_at")
        _require_aware(self.updated_at, field_name="updated_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "source": self.source,
            "payload": dict(self.payload),
            "correlation_id": self.correlation_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AuditEvent":
        payload = data.get("payload", {})
        if isinstance(payload, str):
            payload = _load_payload(payload)
        if not isinstance(payload, Mapping):
            raise ValidationError("audit payload must be a mapping")
        correlation_id = data.get("correlation_id")
        return cls(
            id=str(data["id"]),
            event_type=str(data["event_type"]),
            source=str(data["source"]),
            payload=dict(payload),
            correlation_id=str(correlation_id) if correlation_id is not None else None,
            created_at=_parse_time(str(data["created_at"])),
            updated_at=_parse_time(str(data["updated_at"])),
        )


@dataclass(frozen=True)
class Setting:
    """Single configuration entry. ``key`` is unique; identity stays
    uniform with the other entities via ``id``."""

    id: str = field(default_factory=new_id)
    key: str = ""
    value: str = ""
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        _require_id(self.id)
        if not self.key.strip():
            raise ValidationError("setting key must not be empty")
        _require_aware(self.created_at, field_name="created_at")
        _require_aware(self.updated_at, field_name="updated_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Setting":
        return cls(
            id=str(data["id"]),
            key=str(data["key"]),
            value=str(data.get("value", "")),
            created_at=_parse_time(str(data["created_at"])),
            updated_at=_parse_time(str(data["updated_at"])),
        )


__all__ = [
    "AuditEvent",
    "Memory",
    "Message",
    "Permission",
    "Session",
    "Setting",
    "Task",
    "TaskStep",
    "ToolRun",
    "new_id",
    "utcnow",
]
