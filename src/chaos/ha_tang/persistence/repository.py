"""Repository contract — backend-agnostic persistence boundary.

One generic sync contract for all entities. Sync because the M0
foundation has no async DB boundary; a future async backend (or an
SQLAlchemy implementation) implements this same shape or supersedes
it with an async contract of its own. No SQLite types leak here —
backends translate to and from domain models only.

Transaction ownership: each method runs in its own transaction.
Callers compose multiple calls inside an outer
``Database.transaction()`` (SAVEPOINT nesting): an inner failure rolls
back inner work only; an outer rollback discards everything including
committed inner work; an outer commit keeps all inner work. Methods
never return backend types — only domain models and primitives.
"""

from abc import ABC, abstractmethod


class Repository[T](ABC):
    """CRUD boundary for a single entity type."""

    @abstractmethod
    def create(self, entity: T) -> T:
        """Persist a new entity. Duplicate identity fails."""
        raise NotImplementedError

    @abstractmethod
    def get(self, entity_id: str) -> T | None:
        """Return the entity, or ``None`` when absent."""
        raise NotImplementedError

    @abstractmethod
    def list(self, *, limit: int = 100, offset: int = 0) -> list[T]:
        """Return entities in stable order (creation, then id)."""
        raise NotImplementedError

    @abstractmethod
    def update(self, entity: T) -> T:
        """Replace a stored entity. Missing identity fails."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """Remove an entity. ``True`` when one existed."""
        raise NotImplementedError


__all__ = ["Repository"]
