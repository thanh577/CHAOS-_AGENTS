"""Shared kernel types: permission classes and structured tool calls.

This module lives in ``ha_tang`` (infrastructure) on purpose: these
types are needed by ``cong_cu`` (Tool declares a permission class),
``bao_mat`` (PermissionEngine interprets it) and ``bo_nao``
(AIProvider emits tool calls). A shared kernel avoids coupling the
domain packages to each other. Reversible if a later ADR relocates it.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PermissionClass(Enum):
    """Risk class declared by a Tool. Interpreted by PermissionEngine."""

    SAFE = "safe"
    CONFIRM = "confirm"
    BLOCK = "block"


@dataclass(frozen=True)
class ToolCall:
    """A structured tool call: the only shape allowed to cross the
    LLM → runtime boundary. Raw shell/commands can never be a ToolCall.
    """

    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    call_id: str | None = None


__all__ = ["PermissionClass", "ToolCall"]
