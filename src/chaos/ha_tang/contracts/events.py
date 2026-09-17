"""Minimal event contract for the future Event Bus (ARCHITECTURE layer 9).

Only the envelope shape is defined here. Bus implementation,
subscription, persistence and replay belong to later milestones.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class Event:
    """Machine-readable envelope emitted by runtime layers."""

    event_type: str
    source: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid4().hex)
    correlation_id: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


__all__ = ["Event"]
