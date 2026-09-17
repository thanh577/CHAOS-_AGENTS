"""ToolRouter audit-event tests (T3.2): EventBus wiring, redaction, and
end-to-end persistence via the M2 AuditEventSink."""

import asyncio

from chaos.cong_cu.contracts.tool import Tool, ToolResult
from chaos.cong_cu.router import ToolRouter
from chaos.ha_tang.contracts.common import PermissionClass, ToolCall
from chaos.ha_tang.contracts.events import Event
from chaos.ha_tang.event_bus import WILDCARD, EventBus
from chaos.ha_tang.event_sinks import AuditEventSink
from chaos.ha_tang.persistence.sqlite_store import SqliteDatabase, repositories


class SafeEchoTool(Tool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "echoes input"

    @property
    def input_schema(self):
        return {"type": "object"}

    @property
    def output_schema(self):
        return {"type": "object"}

    @property
    def permission(self) -> PermissionClass:
        return PermissionClass.SAFE

    @property
    def timeout_seconds(self) -> float:
        return 5.0

    async def validate(self, payload):
        return dict(payload)

    async def execute(self, call: ToolCall) -> ToolResult:
        return ToolResult(
            ok=True, tool=self.name, data={"secret": "s3cr3t-arg"}, call_id=call.call_id
        )


class ConfirmTool(SafeEchoTool):
    @property
    def name(self) -> str:
        return "risky"

    @property
    def permission(self) -> PermissionClass:
        return PermissionClass.CONFIRM


def _collect(bus: EventBus) -> list[Event]:
    received: list[Event] = []
    bus.subscribe(WILDCARD, received.append)
    return received


def test_no_event_bus_means_no_publishing_and_still_works():
    router = ToolRouter({"echo": SafeEchoTool()})  # event_bus omitted
    result = asyncio.run(router.dispatch(ToolCall(name="echo", arguments={"x": 1}, call_id="k1")))
    assert result.ok is True


def test_successful_dispatch_publishes_started_then_finished():
    bus = EventBus()
    received = _collect(bus)
    router = ToolRouter({"echo": SafeEchoTool()}, event_bus=bus)
    asyncio.run(router.dispatch(ToolCall(name="echo", arguments={}, call_id="k1")))
    assert [e.event_type for e in received] == ["tool.execution.started", "tool.execution.finished"]
    assert all(e.source == "cong_cu" for e in received)
    assert all(e.correlation_id == "k1" for e in received)
    assert received[1].payload["ok"] is True


def test_unknown_tool_publishes_failed_only():
    bus = EventBus()
    received = _collect(bus)
    router = ToolRouter({}, event_bus=bus)
    asyncio.run(router.dispatch(ToolCall(name="nope", arguments={}, call_id="k1")))
    assert [e.event_type for e in received] == ["tool.execution.failed"]
    assert "unknown tool" in received[0].payload["error"]


def test_confirm_tool_publishes_denied_not_started():
    bus = EventBus()
    received = _collect(bus)
    router = ToolRouter({"risky": ConfirmTool()}, event_bus=bus)
    asyncio.run(router.dispatch(ToolCall(name="risky", arguments={}, call_id="k1")))
    assert [e.event_type for e in received] == ["tool.execution.denied"]
    assert received[0].payload["permission"] == "confirm"


def test_event_payload_never_carries_raw_arguments_or_data():
    bus = EventBus()
    received = _collect(bus)
    router = ToolRouter({"echo": SafeEchoTool()}, event_bus=bus)
    asyncio.run(
        router.dispatch(ToolCall(name="echo", arguments={"password": "hunter2"}, call_id="k1"))
    )
    for event in received:
        assert "hunter2" not in repr(event.payload)
        assert "secret" not in event.payload
        assert "s3cr3t-arg" not in repr(event.payload)


def test_router_events_flow_into_audit_trail_via_sink(tmp_path):
    database = SqliteDatabase(tmp_path / "test.db")
    database.initialize()
    try:
        audit_repo = repositories(database)["audit_events"]
        bus = EventBus()
        bus.subscribe(WILDCARD, AuditEventSink(audit_repo))
        router = ToolRouter({"echo": SafeEchoTool()}, event_bus=bus)
        asyncio.run(router.dispatch(ToolCall(name="echo", arguments={}, call_id="k1")))
        rows = audit_repo.list()
        assert [row.event_type for row in rows] == [
            "tool.execution.started",
            "tool.execution.finished",
        ]
        assert all(row.source == "cong_cu" for row in rows)
        assert all(row.correlation_id == "k1" for row in rows)
    finally:
        database.close()
