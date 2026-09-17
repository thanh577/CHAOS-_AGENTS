"""Static PermissionEngine (Milestone 4) — pure classification policy.

The ``bao_mat/contracts/permission_engine.py`` contract (T0.2) already
locked the shape: ``check(request) -> PermissionDecision`` with three
verdicts (``ALLOW``/``CONFIRM``/``BLOCK``). This module is the first
real implementation of that contract.

``StaticPermissionEngine`` maps a tool's declared ``PermissionClass``
straight to a verdict — it is deliberately *ignorant* of
``request.input_summary``/``request.context`` (same reasoning as the
M3 ``ToolRouter`` placeholder it replaces: a policy that never reads
call content cannot be tuned, accidentally or otherwise, into a
content-based bypass). Content-aware scoping (e.g. path/URL rules for
a specific tool) is out of scope until a concrete tool exists to need
it (M6 browser / M7 OS) — inventing that now would be speculative.

This module has no I/O: no persistence, no event bus, no logging.
Recording decisions to the ``permissions`` table is a separate
concern (``bao_mat/recording.py``, T4.2) — same split as
``ha_tang/event_bus.py`` (transport) vs ``ha_tang/event_sinks.py``
(persistence adapter) in Milestone 2.
"""

from chaos.bao_mat.contracts.permission_engine import (
    PermissionDecision,
    PermissionEngine,
    PermissionRequest,
    PermissionVerdict,
)
from chaos.ha_tang.contracts.common import PermissionClass


class StaticPermissionEngine(PermissionEngine):
    """Classifies purely by the tool's declared ``PermissionClass``."""

    async def check(self, request: PermissionRequest) -> PermissionDecision:
        if request.permission_class is PermissionClass.SAFE:
            return PermissionDecision(
                verdict=PermissionVerdict.ALLOW,
                reason=f"tool {request.tool_name!r} declares SAFE permission class",
            )

        if request.permission_class is PermissionClass.CONFIRM:
            return PermissionDecision(
                verdict=PermissionVerdict.CONFIRM,
                reason=(
                    f"tool {request.tool_name!r} declares CONFIRM permission class — "
                    "requires explicit approval before running"
                ),
                risks=(f"running {request.tool_name!r} may have side effects",),
                confirmation_prompt=f"Allow running tool {request.tool_name!r}?",
            )

        # PermissionClass.BLOCK — the only case left, but matched explicitly
        # rather than an `else` so a future PermissionClass member fails loud.
        if request.permission_class is PermissionClass.BLOCK:
            return PermissionDecision(
                verdict=PermissionVerdict.BLOCK,
                reason=(
                    f"tool {request.tool_name!r} declares BLOCK permission class — "
                    "not permitted to run"
                ),
                risks=(f"tool {request.tool_name!r} is classified as high-risk",),
            )

        raise AssertionError(f"unhandled PermissionClass: {request.permission_class!r}")


__all__ = ["StaticPermissionEngine"]
