"""Event → audit-trail persistence sink (Milestone 2, T2.2).

Bridges the in-process Event Bus (``event_bus.py``) to the append-only
``audit_events`` repository already defined in T0.6 — nothing new at
the persistence layer, this is purely a subscriber adapter. Not wired
into ``ApplicationContext`` here (see CHAOS_STATE.md Milestone 2 Plan):
a caller builds one from ``repositories(database)["audit_events"]``
and attaches it to a bus explicitly when it needs an audit trail.
"""

from chaos.ha_tang.contracts.events import Event
from chaos.ha_tang.persistence.models import AuditEvent, new_id
from chaos.ha_tang.persistence.repository import Repository


class AuditEventSink:
    """Callable subscriber: persists each :class:`Event` as an
    :class:`AuditEvent` row.

    The payload is redacted via :meth:`Event.safe_payload` before it
    ever reaches the database — the audit trail must never hold a raw
    secret, matching AGENTS.md section 11. Directly usable as an
    ``EventBus`` subscriber::

        sink = AuditEventSink(repositories(database)["audit_events"])
        bus.subscribe(WILDCARD, sink)

    Persistence failures (e.g. a closed database) raise from the
    repository as usual — this class adds no error handling of its
    own. When used through :class:`~chaos.ha_tang.event_bus.EventBus`,
    the bus already isolates subscriber failures from the publisher
    and from other subscribers; a caller invoking the sink directly
    gets the repository's real exception.
    """

    def __init__(self, repository: Repository[AuditEvent]) -> None:
        self._repository = repository

    def __call__(self, event: Event) -> None:
        self._repository.create(
            AuditEvent(
                id=new_id(),
                event_type=event.event_type,
                source=event.source,
                payload=event.safe_payload(),
                correlation_id=event.correlation_id,
                created_at=event.occurred_at,
                updated_at=event.occurred_at,
            )
        )


__all__ = ["AuditEventSink"]
