"""RecordingPermissionEngine (Milestone 4, T4.2) — decision audit trail.

Wraps another :class:`PermissionEngine` (Decorator pattern, not a
subclass override) and persists every decision it produces as a real
``Permission`` row via the ``permissions`` repository already defined
in T0.6 (``repositories(database)["permissions"]``). This is a
separate concern from the policy itself (``bao_mat/engine.py``) —
same split as ``ha_tang/event_bus.py`` (transport) vs
``ha_tang/event_sinks.py`` (persistence adapter) in Milestone 2.

Persists via a direct, explicit ``Repository[Permission]`` dependency
rather than the Event Bus: a permission check is a synchronous
request/response call whose result must be recorded reliably
regardless of whether any ``EventBus`` is attached — it is not a
"thing that already happened" fire-and-forget notification, so it
does not belong on that transport. This also keeps ``bao_mat``
decoupled from ``ha_tang.event_bus`` (Permission Engine, ARCHITECTURE
layer 6, has no need to know about the Event Bus, layer 9).

Not wired into ``ApplicationContext`` here (see CHAOS_STATE.md
Milestone 4 Plan) — a caller composes
``RecordingPermissionEngine(StaticPermissionEngine(), repositories(db)["permissions"])``
explicitly when it needs the audit trail, same DI style as
``AuditEventSink``.
"""

from chaos.bao_mat.contracts.permission_engine import (
    PermissionDecision,
    PermissionEngine,
    PermissionRequest,
)
from chaos.ha_tang.persistence.models import Permission
from chaos.ha_tang.persistence.repository import Repository


class RecordingPermissionEngine(PermissionEngine):
    """Delegates to ``engine`` then persists the resulting decision.

    Persistence failures (e.g. a closed database) raise from the
    repository as usual — this class adds no error handling of its
    own; a caller that wants failures isolated wraps this engine's
    use accordingly (mirrors ``AuditEventSink``'s direct-call
    behaviour from T2.2).
    """

    def __init__(self, engine: PermissionEngine, repository: Repository[Permission]) -> None:
        self._engine = engine
        self._repository = repository

    async def check(self, request: PermissionRequest) -> PermissionDecision:
        decision = await self._engine.check(request)
        self._repository.create(
            Permission(
                tool_name=request.tool_name,
                verdict=decision.verdict.value,
                reason=decision.reason,
            )
        )
        return decision


__all__ = ["RecordingPermissionEngine"]
