"""PermissionEngine contract — the safety boundary decision point.

The engine answers one question: ``check(request) → decision``.
The decision tells the runtime whether the action is allowed,
needs explicit confirmation, or is blocked — plus the reason and
the risks/consequences to show the operator. Policy tables and
enforcement mechanics belong to Milestone 4+; only the shapes here.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from chaos.ha_tang.contracts.common import PermissionClass


class PermissionVerdict(Enum):
    """The three outcomes a permission check can produce."""

    ALLOW = "allow"
    CONFIRM = "confirm"
    BLOCK = "block"


@dataclass(frozen=True)
class PermissionRequest:
    """What the runtime asks about before executing a tool call."""

    tool_name: str
    permission_class: PermissionClass
    input_summary: Mapping[str, Any] = field(default_factory=dict)
    context: str = ""


@dataclass(frozen=True)
class PermissionDecision:
    """The engine's answer. ``CONFIRM`` must name what the operator
    is asked to approve via ``confirmation_prompt``; ``risks`` lists
    consequences to disclose for CONFIRM/BLOCK alike.
    """

    verdict: PermissionVerdict
    reason: str = ""
    risks: tuple[str, ...] = ()
    confirmation_prompt: str | None = None

    def __post_init__(self) -> None:
        if self.verdict is PermissionVerdict.CONFIRM and not self.confirmation_prompt:
            raise ValueError("CONFIRM decisions must carry a confirmation_prompt")


class PermissionEngine(ABC):
    """Interface the permission system must implement (Milestone 4+)."""

    @abstractmethod
    async def check(self, request: PermissionRequest) -> PermissionDecision:
        """Decide whether the requested action may proceed."""
        raise NotImplementedError


__all__ = [
    "PermissionDecision",
    "PermissionEngine",
    "PermissionRequest",
    "PermissionVerdict",
]
