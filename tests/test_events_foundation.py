"""Event-foundation tests: envelope invariants, UTC, identity, safety."""

from datetime import UTC

from chaos.ha_tang.contracts.events import Event, is_conventional_name


def test_required_fields_and_utc_timestamp():
    event = Event(event_type="tool.execution.started", source="cong_cu")
    assert event.event_type == "tool.execution.started"
    assert event.source == "cong_cu"
    assert event.payload == {}
    assert event.correlation_id is None
    assert event.occurred_at.tzinfo is not None
    assert event.occurred_at.utcoffset() == UTC.utcoffset(None)


def test_event_identity_unique():
    first = Event(event_type="a.b", source="s")
    second = Event(event_type="a.b", source="s")
    assert first.event_id != second.event_id


def test_naming_convention():
    assert is_conventional_name("tool.execution.started")
    assert is_conventional_name("tool.execution.failed")
    assert is_conventional_name("tool.execution.completed")
    assert not is_conventional_name("ToolExecutionStarted")
    assert not is_conventional_name("single")
    assert not is_conventional_name("")


def test_safe_payload_redacts_secrets():
    event = Event(
        event_type="tool.execution.completed",
        source="cong_cu",
        payload={"tool": "echo", "api_key": "hidden", "nested": {"token": "hidden"}},
        correlation_id="corr-1",
    )
    assert event.payload["api_key"] == "hidden"  # raw envelope untouched
    safe = event.safe_payload()
    assert safe == {"tool": "echo", "api_key": "***", "nested": {"token": "***"}}
    assert "hidden" not in repr(safe)
    assert event.correlation_id == "corr-1"
