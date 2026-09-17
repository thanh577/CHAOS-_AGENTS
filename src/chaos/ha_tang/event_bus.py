"""In-process Event Bus (ARCHITECTURE layer 9, Milestone 2).

Implements exactly what ``ha_tang/contracts/events.py`` deferred:
publish/subscribe over the existing :class:`~chaos.ha_tang.contracts.events.Event`
envelope. Out of scope here (see CHAOS_STATE.md Milestone 2 Plan):
cross-process transport, async subscribers, wildcard *prefix*
subscription (only exact event-type match and the global ``"*"`` are
supported), and persistence/replay beyond whatever a subscriber does
with the event it receives (the audit sink in ``event_sinks.py`` is
one such subscriber).

Delivery model: synchronous, in registration order, one subscriber at
a time. A subscriber that raises is caught, logged (never silently
swallowed — see AGENTS.md section 16) and skipped; the remaining
subscribers still run and :meth:`EventBus.publish` never raises on
their behalf. A lock protects the subscriber registry so a subscriber
that (un)subscribes while being called cannot corrupt the in-flight
delivery list — this guards against exactly one race (mutate during
iterate); it is not a claim of full concurrent-publish ordering
guarantees across threads.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import uuid4

from chaos.ha_tang.contracts.errors import ValidationError
from chaos.ha_tang.contracts.events import Event, is_conventional_name
from chaos.ha_tang.logging import log_event
from chaos.ha_tang.redaction import format_error

#: Subscribes to every event regardless of type.
WILDCARD = "*"

Subscriber = Callable[[Event], None]


@dataclass(frozen=True)
class Subscription:
    """Opaque handle returned by :meth:`EventBus.subscribe`.

    Callers only need it to unsubscribe later — the fields are not a
    public contract to introspect.
    """

    event_type: str
    _token: str = field(default_factory=lambda: uuid4().hex)


def _validate_target(event_type: str) -> None:
    if event_type == WILDCARD:
        return
    if not is_conventional_name(event_type):
        raise ValidationError(
            f"invalid subscription target: {event_type!r} "
            f"(expected dotted lowercase like 'tool.execution.started', or '*')"
        )


class EventBus:
    """Minimal synchronous publish/subscribe bus.

    One bus instance is independent state — there is no process-wide
    singleton. Callers that want a shared bus construct one and pass
    it around explicitly (matches the explicit-DI style used by
    :class:`~chaos.ha_tang.application.ApplicationContext`).
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger if logger is not None else logging.getLogger("chaos")
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[tuple[Subscription, Subscriber]]] = {}

    def subscribe(self, event_type: str, subscriber: Subscriber) -> Subscription:
        """Register ``subscriber`` for ``event_type`` (or ``"*"`` for all events).

        Raises ``ValidationError`` immediately for a malformed target —
        a typo in the subscription target should never fail silently
        by matching nothing.
        """
        _validate_target(event_type)
        subscription = Subscription(event_type=event_type)
        with self._lock:
            self._subscribers.setdefault(event_type, []).append((subscription, subscriber))
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        """Remove a subscription. Idempotent: unsubscribing twice, or a
        subscription this bus never held (or already removed), is a
        no-op rather than an error — callers cleaning up during
        shutdown should never have to guard this call."""
        with self._lock:
            bucket = self._subscribers.get(subscription.event_type)
            if not bucket:
                return
            self._subscribers[subscription.event_type] = [
                entry for entry in bucket if entry[0] is not subscription
            ]

    def subscriber_count(self, event_type: str) -> int:
        """Number of subscribers currently registered for ``event_type``
        (exact match only — does not fold in ``"*"``). Test/introspection
        helper, not used by delivery."""
        with self._lock:
            return len(self._subscribers.get(event_type, ()))

    def publish(self, event: Event) -> None:
        """Deliver ``event`` to every matching subscriber.

        Validates ``event.event_type`` against the naming convention
        first — a malformed event is a caller bug and fails fast
        rather than being silently delivered to nobody. Subscriber
        failures are isolated: caught, logged via ``log_event``
        (metadata only — the payload is never re-logged raw here,
        callers already redact via ``Event.safe_payload``), and never
        propagated to the publisher or to other subscribers.
        """
        if not is_conventional_name(event.event_type):
            raise ValidationError(
                f"invalid event_type: {event.event_type!r} "
                f"(expected dotted lowercase like 'tool.execution.started')"
            )
        with self._lock:
            snapshot = list(self._subscribers.get(event.event_type, ())) + list(
                self._subscribers.get(WILDCARD, ())
            )
        for subscription, subscriber in snapshot:
            try:
                subscriber(event)
            except Exception as exc:  # noqa: BLE001 — isolation boundary, logged below, never swallowed
                log_event(
                    self._logger,
                    "ERROR",
                    "event_bus.subscriber.failed",
                    {
                        "event_type": event.event_type,
                        "source": event.source,
                        "subscription_target": subscription.event_type,
                        "error": format_error(exc),
                    },
                )


__all__ = ["WILDCARD", "EventBus", "Subscriber", "Subscription"]
