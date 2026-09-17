"""MemoryStore contract — persistence boundary for long-term memory.

Only the four operations (store/retrieve/update/delete) and the
record/query shapes. Storage engines (SQLite, …) arrive in later
milestones; no database code here.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MemoryRecord:
    """One stored memory. ``scope`` namespaces memories
    (e.g. per-user or per-project); ``metadata`` is free-form."""

    id: str
    content: str
    scope: str = "default"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class MemoryQuery:
    """A retrieval request: scored/filtered by the future engine."""

    query: str
    scope: str | None = None
    limit: int = 10


class MemoryStore(ABC):
    """Interface every memory backend must implement (Milestone 8+)."""

    @abstractmethod
    async def store(self, record: MemoryRecord) -> MemoryRecord:
        """Persist a new record, returning the stored copy."""
        raise NotImplementedError

    @abstractmethod
    async def retrieve(self, query: MemoryQuery) -> tuple[MemoryRecord, ...]:
        """Return up to ``query.limit`` matching records."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, record: MemoryRecord) -> MemoryRecord:
        """Replace the record with the same id, returning the new copy."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, record_id: str) -> bool:
        """Remove a record; ``True`` if one existed."""
        raise NotImplementedError


__all__ = ["MemoryQuery", "MemoryRecord", "MemoryStore"]
