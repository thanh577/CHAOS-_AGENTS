"""Minimal event contract for the future Event Bus (ARCHITECTURE layer 9).

Only the envelope shape is defined here. Bus implementation,
subscription, persistence and replay belong to later milestones.

Event-type convention: dotted lowercase segments such as
``tool.execution.started``. Payloads must be redacted via
``safe_payload`` (or ``chaos.ha_tang.redaction``) before logging —
raw prompts, model responses and tool arguments never ride along.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

EVENT_NAME_RE = re.compile(r"^[a-z0-9]+(\.[a-z0-9_]+)+$")


@dataclass(frozen=True)
class Event:
    """Machine-readable envelope emitted by runtime layers."""

    event_type: str
    source: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid4().hex)
    correlation_id: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def safe_payload(self) -> dict[str, Any]:
        """Redacted copy of the payload, safe to log or transport."""
        from chaos.ha_tang.redaction import redact_mapping

        return redact_mapping(dict(self.payload))


def is_conventional_name(event_type: str) -> bool:
    """Check the dotted-lowercase event-type convention."""
    return EVENT_NAME_RE.match(event_type) is not None


__all__ = ["EVENT_NAME_RE", "Event", "is_conventional_name"]
