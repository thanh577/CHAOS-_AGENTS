"""Verifier contract — the reality-check boundary.

After execution, the runtime asks a Verifier whether the claimed
outcome actually holds. Three states: the claim checked out
(VERIFIED), it demonstrably failed (FAILED), or the evidence was
insufficient to tell (UNCERTAIN — the runtime must then retry,
replan or escalate, never silently accept). Real checkers belong
to Milestone 5+; only the shapes here.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from chaos.cong_cu.contracts.tool import ToolResult


@dataclass(frozen=True)
class VerificationExpectation:
    """What the planner expected: named postconditions to check."""

    conditions: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)


class VerificationVerdict(Enum):
    """The three outcomes a verification can produce."""

    VERIFIED = "verified"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class VerificationResult:
    """The checker's answer: verdict plus what was checked,
    the evidence observed, and the reason in plain words.
    """

    verdict: VerificationVerdict
    checked: tuple[str, ...] = ()
    evidence: Mapping[str, Any] = field(default_factory=dict)
    reason: str = ""


class Verifier(ABC):
    """Interface every postcondition checker implements (Milestone 5+)."""

    @abstractmethod
    async def verify(
        self,
        result: ToolResult,
        expectation: VerificationExpectation,
    ) -> VerificationResult:
        """Check the tool outcome against the expectation."""
        raise NotImplementedError


__all__ = [
    "VerificationExpectation",
    "VerificationResult",
    "VerificationVerdict",
    "Verifier",
]
