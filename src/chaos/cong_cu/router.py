"""Tool Router (Milestone 3) — the runtime side of the ``Tool``
contract locked in T0.2.

``cong_cu/contracts/tool.py`` defines *what* a tool is and forbids
that module from ever reaching a ``PermissionEngine``. This module is
the implementation that actually walks the reduced AGENTS.md core
loop (``validation -> permission -> executor``; ``verifier`` is
Milestone 5 and out of scope here):

1. Look up the tool by name in a plain ``Mapping[str, Tool]`` registry
   (no registry *class* — same minimalism as ``BrainRuntime``'s
   provider mapping in Milestone 1).
2. ``tool.validate()`` the raw arguments; the normalized result is
   what actually reaches ``execute()``.
3. Permission: ``PermissionEngine`` does not exist yet (Milestone 4).
   Until it does, this router applies one conservative, documented
   placeholder policy — **only ``PermissionClass.SAFE`` tools run**;
   ``CONFIRM`` and ``BLOCK`` are refused outright with
   ``PermissionDeniedError``. There is no bypass: a later milestone
   replaces this policy without changing :meth:`ToolRouter.dispatch`'s
   signature.
4. Execute with the tool's own ``timeout_seconds`` enforced via
   ``asyncio.wait_for``.

``dispatch`` never raises. Every outcome — unknown tool, a validation
failure, a permission refusal, a timeout, or an unexpected exception
from the tool itself — is mapped to a ``ToolResult(ok=False, ...)``,
matching CONTRACTS.md's "Tool result should be standardized and
machine-readable". This is a deliberate difference from
``BrainRuntime``, which raises: Brain has no result envelope of its
own, while ``Tool`` already does.

T3.2 adds an audit trail: an optional ``EventBus`` (Milestone 2) is
the "real event producer" that bus was built for. Published event
types are ``tool.execution.started`` / ``.finished`` / ``.denied`` /
``.failed`` — payloads carry only tool name, call id and (for
failures) a redacted one-line error via ``format_error``. Raw call
arguments and raw tool output are never published (AGENTS.md section
11: no raw tool arguments in logs/audit).
"""

import asyncio
from collections.abc import Mapping
from typing import Any

from chaos.cong_cu.contracts.tool import Tool, ToolResult
from chaos.ha_tang.contracts.common import PermissionClass, ToolCall
from chaos.ha_tang.contracts.errors import (
    ChaosError,
    ExecutionError,
    OperationTimeoutError,
    PermissionDeniedError,
    ValidationError,
)
from chaos.ha_tang.contracts.events import Event
from chaos.ha_tang.event_bus import EventBus
from chaos.ha_tang.redaction import format_error

SOURCE = "cong_cu"


def _is_permitted(tool: Tool, call: ToolCall) -> bool:
    """Placeholder permission policy (Milestone 3): SAFE-only.

    Deliberately ignorant of ``call`` — a real ``PermissionEngine``
    (Milestone 4) will consider the call, prior confirmations and
    user policy; this stand-in only ever looks at the tool's declared
    class, and always the same way, so it cannot be tuned into an
    accidental bypass.
    """
    return tool.permission is PermissionClass.SAFE


class ToolRouter:
    """Dispatches structured ``ToolCall``s to registered ``Tool``s."""

    def __init__(self, tools: Mapping[str, Tool], event_bus: EventBus | None = None) -> None:
        self._tools = dict(tools)
        self._event_bus = event_bus

    @property
    def tool_names(self) -> tuple[str, ...]:
        """Registered tool names, sorted for deterministic reporting."""
        return tuple(sorted(self._tools))

    def _publish(self, event_type: str, call: ToolCall, **payload: Any) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(
            Event(
                event_type=event_type,
                source=SOURCE,
                payload={"tool": call.name, **payload},
                correlation_id=call.call_id,
            )
        )

    def _fail(self, call: ToolCall, tool_name: str, error: ChaosError) -> ToolResult:
        self._publish("tool.execution.failed", call, error=format_error(error))
        return ToolResult(ok=False, tool=tool_name, error=error, call_id=call.call_id)

    async def dispatch(self, call: ToolCall) -> ToolResult:
        """Run the reduced core loop for one call. Never raises."""
        tool = self._tools.get(call.name)
        if tool is None:
            return self._fail(
                call,
                call.name,
                ValidationError(
                    f"unknown tool: {call.name!r} (available: {', '.join(self.tool_names)})"
                ),
            )

        try:
            validated_arguments: dict[str, Any] = await tool.validate(dict(call.arguments))
        except ChaosError as exc:
            return self._fail(call, tool.name, exc)
        except Exception as exc:  # noqa: BLE001 — a tool's validate() must never crash the router
            return self._fail(call, tool.name, ValidationError(f"tool validate() raised: {exc}"))

        if not _is_permitted(tool, call):
            error = PermissionDeniedError(
                f"tool {tool.name!r} requires permission class "
                f"{tool.permission.value!r} — no PermissionEngine attached (Milestone 4)"
            )
            self._publish(
                "tool.execution.denied",
                call,
                permission=tool.permission.value,
                error=format_error(error),
            )
            return ToolResult(ok=False, tool=tool.name, error=error, call_id=call.call_id)

        normalized_call = ToolCall(
            name=call.name, arguments=validated_arguments, call_id=call.call_id
        )
        self._publish("tool.execution.started", call)
        try:
            result = await asyncio.wait_for(
                tool.execute(normalized_call), timeout=tool.timeout_seconds
            )
        except TimeoutError:
            return self._fail(
                call,
                tool.name,
                OperationTimeoutError(
                    f"tool {tool.name!r} exceeded {tool.timeout_seconds}s timeout"
                ),
            )
        except ChaosError as exc:
            return self._fail(call, tool.name, exc)
        except Exception as exc:  # noqa: BLE001 — a rogue tool must never crash the router
            return self._fail(call, tool.name, ExecutionError(f"tool execute() raised: {exc}"))

        if not isinstance(result, ToolResult):
            return self._fail(
                call,
                tool.name,
                ExecutionError(
                    f"tool {tool.name!r} returned {type(result).__name__}, expected ToolResult"
                ),
            )
        self._publish("tool.execution.finished", call, ok=result.ok)
        return result


__all__ = ["ToolRouter"]
