"""Tool Router (Milestone 3, extended Milestone 4 and Milestone 5) —
the runtime side of the ``Tool`` contract locked in T0.2.

``cong_cu/contracts/tool.py`` defines *what* a tool is and forbids
that module from ever reaching a ``PermissionEngine``. This module is
the implementation that actually walks the full AGENTS.md core loop
(``validation -> permission -> executor -> verifier``):

1. Look up the tool by name in a plain ``Mapping[str, Tool]`` registry
   (no registry *class* — same minimalism as ``BrainRuntime``'s
   provider mapping in Milestone 1).
2. ``tool.validate()`` the raw arguments; the normalized result is
   what actually reaches ``execute()``.
3. Permission: an optional ``PermissionEngine`` (Milestone 4,
   ``bao_mat.contracts.permission_engine``) decides ALLOW/CONFIRM/
   BLOCK. When no engine is attached (the default), the router falls
   back to the conservative Milestone 3 placeholder policy —
   **only ``PermissionClass.SAFE`` tools run**.
4. Execute with the tool's own ``timeout_seconds`` enforced via
   ``asyncio.wait_for``.
5. Verify: an optional ``Verifier`` (Milestone 5,
   ``kiem_tra.contracts.verifier``) double-checks a *successful*
   outcome against an optional per-call ``VerificationExpectation``
   (passed to :meth:`dispatch`, not the router — postconditions are
   per-call data, not a router-wide constant, and adding a field to
   the locked ``ToolCall`` kernel contract just for this optional
   feature would be a bigger change than warranted). When no verifier
   is attached, or the tool itself already reported failure, no
   verification runs — matches Milestone 3/4 behavior exactly.

``ToolRouter`` is *implementation*, not the ``Tool`` contract itself —
it is allowed to know about permission/verification (see
``cong_cu/contracts/tool.py``'s own boundary test, scoped to that
contract module only), but it only ever depends on the
**abstractions**: which concrete ``PermissionEngine``/``Verifier``
runs is chosen by whoever constructs the router (DI), never hardcoded
here. There is no bypass either way.

``dispatch`` never raises. Every outcome — unknown tool, a validation
failure, a permission refusal, a timeout, an unexpected exception from
the tool itself, or a failed/uncertain verification — is mapped to a
``ToolResult(ok=False, ...)``, matching CONTRACTS.md's "Tool result
should be standardized and machine-readable". This is a deliberate
difference from ``BrainRuntime``, which raises: Brain has no result
envelope of its own, while ``Tool`` already does.

T3.2 adds an audit trail: an optional ``EventBus`` (Milestone 2) is
the "real event producer" that bus was built for. Published event
types are ``tool.execution.started`` / ``.finished`` / ``.denied`` /
``.confirm_required`` (T4.3) / ``.failed`` / ``.verification.failed`` /
``.verification.uncertain`` (T5.2) — payloads carry only tool name,
call id and (for failures) a redacted one-line error via
``format_error``. Raw call arguments and raw tool output are never
published (AGENTS.md section 11: no raw tool arguments in logs/audit).

T4.3: a ``CONFIRM`` verdict is published as ``tool.execution.confirm_required``
(not ``.denied``) so a future consumer can tell "needs a human to
approve" apart from "blocked outright" — the decision's
``confirmation_prompt``/reason ends up in the returned
``PermissionDeniedError``'s message either way, since there is no
interactive channel yet to actually resolve a CONFIRM (Desktop UI is
Milestone 9). This router does not itself resolve CONFIRM; it only
reports it faithfully.

T5.2: same non-resolution stance for a ``Verifier`` verdict of
``UNCERTAIN`` — the contract's own docstring says the runtime "must
then retry, replan or escalate, never silently accept", but that loop
belongs to the Agent Loop (Milestone 15), which does not exist yet.
This router reports ``UNCERTAIN`` faithfully (as a failed
``ToolResult``, distinct event name from ``FAILED``) rather than
inventing a retry mechanism prematurely. A verified/failed/uncertain
verdict short-circuits ``dispatch()`` exactly like a permission
denial does — its own event is the terminal one, ``tool.execution.finished``
is not published on top of it.
"""

import asyncio
from collections.abc import Mapping
from typing import Any

from chaos.bao_mat.contracts.permission_engine import (
    PermissionEngine,
    PermissionRequest,
    PermissionVerdict,
)
from chaos.cong_cu.contracts.tool import Tool, ToolResult
from chaos.ha_tang.contracts.common import PermissionClass, ToolCall
from chaos.ha_tang.contracts.errors import (
    ChaosError,
    ExecutionError,
    OperationTimeoutError,
    PermissionDeniedError,
    ValidationError,
    VerificationError,
)
from chaos.ha_tang.contracts.events import Event
from chaos.ha_tang.event_bus import EventBus
from chaos.ha_tang.redaction import format_error
from chaos.kiem_tra.contracts.verifier import (
    VerificationExpectation,
    VerificationVerdict,
    Verifier,
)

SOURCE = "cong_cu"


class ToolRouter:
    """Dispatches structured ``ToolCall``s to registered ``Tool``s."""

    def __init__(
        self,
        tools: Mapping[str, Tool],
        event_bus: EventBus | None = None,
        permission_engine: PermissionEngine | None = None,
        verifier: Verifier | None = None,
    ) -> None:
        self._tools = dict(tools)
        self._event_bus = event_bus
        self._permission_engine = permission_engine
        self._verifier = verifier

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

    def _deny(self, call: ToolCall, tool: Tool, event_type: str, error: ChaosError) -> ToolResult:
        self._publish(event_type, call, permission=tool.permission.value, error=format_error(error))
        return ToolResult(ok=False, tool=tool.name, error=error, call_id=call.call_id)

    def _unverified(
        self, call: ToolCall, tool: Tool, event_type: str, error: ChaosError
    ) -> ToolResult:
        self._publish(event_type, call, error=format_error(error))
        return ToolResult(ok=False, tool=tool.name, error=error, call_id=call.call_id)

    async def _check_permission(self, tool: Tool, call: ToolCall) -> ToolResult | None:
        """``None`` means the call may proceed; otherwise the returned
        ``ToolResult`` is the final answer for this ``dispatch()``."""
        if self._permission_engine is None:
            # Milestone 3 placeholder, kept verbatim: SAFE-only, ignorant
            # of call content, no PermissionEngine attached.
            if tool.permission is PermissionClass.SAFE:
                return None
            return self._deny(
                call,
                tool,
                "tool.execution.denied",
                PermissionDeniedError(
                    f"tool {tool.name!r} requires permission class "
                    f"{tool.permission.value!r} — no PermissionEngine attached (Milestone 4)"
                ),
            )

        request = PermissionRequest(tool_name=tool.name, permission_class=tool.permission)
        try:
            decision = await self._permission_engine.check(request)
        except ChaosError as exc:
            return self._fail(call, tool.name, exc)
        except Exception as exc:  # noqa: BLE001 — a rogue engine must never crash the router
            return self._fail(call, tool.name, ExecutionError(f"permission engine raised: {exc}"))

        if decision.verdict is PermissionVerdict.ALLOW:
            return None

        error = PermissionDeniedError(
            decision.reason or f"tool {tool.name!r} was not allowed to run"
        )
        event_type = (
            "tool.execution.confirm_required"
            if decision.verdict is PermissionVerdict.CONFIRM
            else "tool.execution.denied"
        )
        return self._deny(call, tool, event_type, error)

    async def _check_verification(
        self,
        tool: Tool,
        call: ToolCall,
        result: ToolResult,
        expectation: VerificationExpectation | None,
    ) -> ToolResult | None:
        """``None`` means ``result`` stands unchanged; otherwise the
        returned ``ToolResult`` (already published) is the final
        answer for this ``dispatch()``. Only runs when a ``Verifier``
        is attached and the tool itself already reported success —
        verifying a claimed failure is not this milestone's job."""
        if self._verifier is None or not result.ok:
            return None

        try:
            decision = await self._verifier.verify(result, expectation or VerificationExpectation())
        except ChaosError as exc:
            return self._fail(call, tool.name, exc)
        except Exception as exc:  # noqa: BLE001 — a rogue verifier must never crash the router
            return self._fail(call, tool.name, ExecutionError(f"verifier raised: {exc}"))

        if decision.verdict is VerificationVerdict.VERIFIED:
            return None

        error = VerificationError(
            decision.reason or f"tool {tool.name!r} outcome could not be verified"
        )
        event_type = (
            "tool.verification.uncertain"
            if decision.verdict is VerificationVerdict.UNCERTAIN
            else "tool.verification.failed"
        )
        return self._unverified(call, tool, event_type, error)

    async def dispatch(
        self, call: ToolCall, expectation: VerificationExpectation | None = None
    ) -> ToolResult:
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

        denial = await self._check_permission(tool, call)
        if denial is not None:
            return denial

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

        override = await self._check_verification(tool, call, result, expectation)
        if override is not None:
            return override

        self._publish("tool.execution.finished", call, ok=result.ok)
        return result


__all__ = ["ToolRouter"]
