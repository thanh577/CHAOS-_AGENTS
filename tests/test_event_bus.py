"""EventBus tests (T2.1): pub/sub, ordering, isolation, naming, thread-safety."""

import logging
import threading

import pytest

from chaos.ha_tang.contracts.errors import ValidationError
from chaos.ha_tang.contracts.events import Event
from chaos.ha_tang.event_bus import WILDCARD, EventBus


@pytest.fixture()
def records():
    logger = logging.getLogger("chaos-test-event-bus")
    collected: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            collected.append(record)

    logger.addHandler(_Collector())
    logger.setLevel(logging.DEBUG)
    yield collected
    logger.handlers.clear()


@pytest.fixture()
def bus(records):
    return EventBus(logger=logging.getLogger("chaos-test-event-bus"))


def _event(event_type: str = "tool.execution.started", source: str = "test", **kwargs) -> Event:
    return Event(event_type=event_type, source=source, **kwargs)


def test_publish_delivers_to_exact_subscriber(bus):
    received: list[Event] = []
    bus.subscribe("tool.execution.started", received.append)
    event = _event()
    bus.publish(event)
    assert received == [event]


def test_publish_ignores_non_matching_subscribers(bus):
    received: list[Event] = []
    bus.subscribe("tool.execution.finished", received.append)
    bus.publish(_event("tool.execution.started"))
    assert received == []


def test_multiple_subscribers_called_in_registration_order(bus):
    order: list[str] = []
    bus.subscribe("tool.execution.started", lambda e: order.append("first"))
    bus.subscribe("tool.execution.started", lambda e: order.append("second"))
    bus.subscribe("tool.execution.started", lambda e: order.append("third"))
    bus.publish(_event())
    assert order == ["first", "second", "third"]


def test_wildcard_subscriber_receives_every_event_type(bus):
    received: list[Event] = []
    bus.subscribe(WILDCARD, received.append)
    a = _event("tool.execution.started")
    b = _event("tool.execution.finished")
    bus.publish(a)
    bus.publish(b)
    assert received == [a, b]


def test_wildcard_and_exact_both_fire_exact_first(bus):
    order: list[str] = []
    bus.subscribe("tool.execution.started", lambda e: order.append("exact"))
    bus.subscribe(WILDCARD, lambda e: order.append("wildcard"))
    bus.publish(_event())
    assert order == ["exact", "wildcard"]


def test_unsubscribe_stops_delivery(bus):
    received: list[Event] = []
    subscription = bus.subscribe("tool.execution.started", received.append)
    bus.publish(_event())
    bus.unsubscribe(subscription)
    bus.publish(_event())
    assert len(received) == 1


def test_unsubscribe_is_idempotent(bus):
    subscription = bus.subscribe("tool.execution.started", lambda e: None)
    bus.unsubscribe(subscription)
    bus.unsubscribe(subscription)  # second call: no-op, does not raise


def test_unsubscribe_unknown_subscription_is_noop(bus):
    other_bus = EventBus()
    foreign = other_bus.subscribe("tool.execution.started", lambda e: None)
    bus.unsubscribe(foreign)  # never registered on `bus`: still a no-op


def test_subscribe_rejects_malformed_target(bus):
    with pytest.raises(ValidationError, match="invalid subscription target"):
        bus.subscribe("ToolStarted", lambda e: None)
    with pytest.raises(ValidationError, match="invalid subscription target"):
        bus.subscribe("no_dots_here", lambda e: None)


def test_subscribe_allows_wildcard(bus):
    bus.subscribe(WILDCARD, lambda e: None)  # does not raise


def test_publish_rejects_malformed_event_type(bus):
    bad = Event(event_type="NotConventional", source="test")
    with pytest.raises(ValidationError, match="invalid event_type"):
        bus.publish(bad)


def test_failing_subscriber_does_not_block_others_or_raise(bus):
    received: list[str] = []

    def boom(event: Event) -> None:
        raise RuntimeError("subscriber exploded")

    bus.subscribe("tool.execution.started", boom)
    bus.subscribe("tool.execution.started", lambda e: received.append("ok"))
    bus.publish(_event())  # must not raise
    assert received == ["ok"]


def test_failing_subscriber_is_logged_with_metadata_only(bus, records):
    def boom(event: Event) -> None:
        raise RuntimeError("subscriber exploded with s3cr3t-value")

    bus.subscribe("tool.execution.started", boom)
    bus.publish(_event(source="cong_cu"))
    assert len(records) == 1
    payload = records[0].args["payload"]
    assert payload["event_type"] == "tool.execution.started"
    assert payload["source"] == "cong_cu"
    assert "subscriber exploded" in payload["error"]


def test_subscriber_count(bus):
    assert bus.subscriber_count("tool.execution.started") == 0
    bus.subscribe("tool.execution.started", lambda e: None)
    bus.subscribe("tool.execution.started", lambda e: None)
    assert bus.subscriber_count("tool.execution.started") == 2


def test_subscriber_unsubscribing_itself_during_publish_is_safe(bus):
    calls: list[int] = []
    subscription_holder: list = []

    def self_removing(event: Event) -> None:
        calls.append(1)
        bus.unsubscribe(subscription_holder[0])

    subscription_holder.append(bus.subscribe("tool.execution.started", self_removing))
    bus.publish(_event())
    bus.publish(_event())
    assert calls == [1]  # delivered once; second publish used the post-removal registry


def test_concurrent_subscribe_and_publish_does_not_crash(bus):
    errors: list[Exception] = []

    def subscriber_worker():
        try:
            for _ in range(50):
                sub = bus.subscribe("tool.execution.started", lambda e: None)
                bus.unsubscribe(sub)
        except Exception as exc:  # noqa: BLE001 — smoke test collects any thread failure
            errors.append(exc)

    def publisher_worker():
        try:
            for _ in range(50):
                bus.publish(_event())
        except Exception as exc:  # noqa: BLE001 — smoke test collects any thread failure
            errors.append(exc)

    threads = [threading.Thread(target=subscriber_worker) for _ in range(3)]
    threads += [threading.Thread(target=publisher_worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert errors == []
