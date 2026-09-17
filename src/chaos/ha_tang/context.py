"""Async-safe correlation context (stdlib ``contextvars``).

Carries ``correlation_id``/``session_id``/``task_id``/``tool_run_id``
across layers without singletons or hidden global mutable state:
code reads the current context explicitly and installs a new one
with :func:`use_context`, which always resets on exit. Missing
context is ``None`` — never an exception.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class TraceContext:
    """Immutable correlation snapshot shared by logs and events."""

    correlation_id: str
    session_id: str | None = None
    task_id: str | None = None
    tool_run_id: str | None = None

    @classmethod
    def new(
        cls,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        tool_run_id: str | None = None,
    ) -> "TraceContext":
        """Create a context with a fresh random correlation id."""
        return cls(
            correlation_id=uuid4().hex,
            session_id=session_id,
            task_id=task_id,
            tool_run_id=tool_run_id,
        )


_current: ContextVar[TraceContext | None] = ContextVar("chaos_trace_context", default=None)


def get_context() -> TraceContext | None:
    """Return the current context, or ``None`` when unset."""
    return _current.get()


@contextmanager
def use_context(context: TraceContext) -> Iterator[TraceContext]:
    """Install ``context`` for the enclosed block, restoring the
    previous one afterwards (nesting-safe, task-local under asyncio)."""
    token = _current.set(context)
    try:
        yield context
    finally:
        _current.reset(token)


def clear_context() -> None:
    """Remove any installed context (test isolation helper)."""
    _current.set(None)


__all__ = ["TraceContext", "clear_context", "get_context", "use_context"]
