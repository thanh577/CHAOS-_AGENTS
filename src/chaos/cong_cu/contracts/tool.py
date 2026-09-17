"""Tool contract — the executable boundary of CHAOS.

A Tool declares *what* it is (name, schemas, permission class,
timeout) and exposes ``validate``/``execute`` as abstract operations.
It deliberately holds **no reference to PermissionEngine**: the
runtime must check ``permission`` via the engine *before* calling
``execute``. There is no path in this module that can bypass that
check — enforced by the boundary test in ``tests/``.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from chaos.ha_tang.contracts.common import PermissionClass, ToolCall
from chaos.ha_tang.contracts.errors import ChaosError


@dataclass(frozen=True)
class ToolResult:
    """Standardized, machine-readable tool outcome.

    Invariant: ``ok=True`` carries data and no error;
    ``ok=False`` must carry the error.
    """

    ok: bool
    tool: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)
    error: ChaosError | None = None
    call_id: str | None = None

    def __post_init__(self) -> None:
        if self.ok and self.error is not None:
            raise ValueError("ToolResult(ok=True) must not carry an error")
        if not self.ok and self.error is None:
            raise ValueError("ToolResult(ok=False) must carry an error")


class Tool(ABC):
    """Interface every tool must implement (Milestone 3+).

    Schemas are plain JSON-schema-shaped mappings to keep the
    contract dependency-free.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name referenced by ``ToolCall.name``."""
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable summary shown to planners/operators."""
        raise NotImplementedError

    @property
    @abstractmethod
    def input_schema(self) -> Mapping[str, Any]:
        """JSON-schema-shaped mapping describing valid input."""
        raise NotImplementedError

    @property
    @abstractmethod
    def output_schema(self) -> Mapping[str, Any]:
        """JSON-schema-shaped mapping describing ``ToolResult.data``."""
        raise NotImplementedError

    @property
    @abstractmethod
    def permission(self) -> PermissionClass:
        """Risk class the runtime's PermissionEngine must enforce."""
        raise NotImplementedError

    @property
    @abstractmethod
    def timeout_seconds(self) -> float:
        """Maximum execution time the runtime must enforce."""
        raise NotImplementedError

    @abstractmethod
    async def validate(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Validate/normalize raw input.

        Returns a normalized copy or raises ``ValidationError``.
        """
        raise NotImplementedError

    @abstractmethod
    async def execute(self, call: ToolCall) -> ToolResult:
        """Run the validated call. Only the runtime may invoke this,
        and only after a permission decision allows it.
        """
        raise NotImplementedError


__all__ = ["Tool", "ToolResult"]
