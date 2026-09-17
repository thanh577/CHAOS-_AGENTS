"""ToolRouter + PermissionEngine wiring tests (T4.3)."""

import asyncio

from chaos.bao_mat.contracts.permission_engine import (
    PermissionDecision,
    PermissionEngine,
    PermissionRequest,
)
from chaos.bao_mat.engine import StaticPermissionEngine
from chaos.cong_cu.contracts.tool import Tool, ToolResult
from chaos.cong_cu.router import ToolRouter
from chaos.ha_tang.contracts.common import PermissionClass, ToolCall
from chaos.ha_tang.contracts.errors import ExecutionError
from chaos.ha_tang.event_bus import WILDCARD, EventBus


class _BaseTool(Tool):
    permission_class = PermissionClass.SAFE

    @property
    def name(self) -> str:
        return "base"

    @property
    def description(self) -> str:
        return "test tool"

    @property
    def input_schema(self):
        return {"type": "object"}

    @property
    def output_schema(self):
        return {"type": "object"}

    @property
    def permission(self) -> PermissionClass:
        return self.permission_class

    @property
    def timeout_seconds(self) -> float:
        return 5.0

    async def validate(self, payload):
        return dict(payload)

    async def execute(self, call: ToolCall) -> ToolResult:
        return ToolResult(ok=True, tool=self.name, call_id=call.call_id)


class SafeTool(_BaseTool):
    @property
    def name(self) -> str:
        return "safe"


class ConfirmTool(_BaseTool):
    permission_class = PermissionClass.CONFIRM

    @property
    def name(self) -> str:
        return "risky"


class BlockTool(_BaseTool):
    permission_class = PermissionClass.BLOCK

    @property
    def name(self) -> str:
        return "forbidden"


class _RaisingEngine(PermissionEngine):
    def __init__(self, error: Exception) -> None:
        self._error = error

    async def check(self, request: PermissionRequest) -> PermissionDecision:
        raise self._error


def _collect(bus: EventBus) -> list:
    received: list = []
    bus.subscribe(WILDCARD, received.append)
    return received


def test_no_engine_falls_back_to_m3_safe_only_placeholder():
    router = ToolRouter({"safe": SafeTool(), "risky": ConfirmTool()})  # permission_engine omitted
    safe_result = asyncio.run(router.dispatch(ToolCall(name="safe", arguments={})))
    confirm_result = asyncio.run(router.dispatch(ToolCall(name="risky", arguments={})))
    assert safe_result.ok is True
    assert confirm_result.ok is False
    assert confirm_result.error.code.value == "permission"


def test_safe_tool_is_allowed_and_executes():
    router = ToolRouter({"safe": SafeTool()}, permission_engine=StaticPermissionEngine())
    result = asyncio.run(router.dispatch(ToolCall(name="safe", arguments={})))
    assert result.ok is True


def test_confirm_tool_is_refused_but_carries_the_engine_prompt():
    router = ToolRouter({"risky": ConfirmTool()}, permission_engine=StaticPermissionEngine())
    result = asyncio.run(router.dispatch(ToolCall(name="risky", arguments={})))
    assert result.ok is False
    assert result.error.code.value == "permission"
    assert "risky" in result.error.message


def test_block_tool_is_refused():
    router = ToolRouter({"forbidden": BlockTool()}, permission_engine=StaticPermissionEngine())
    result = asyncio.run(router.dispatch(ToolCall(name="forbidden", arguments={})))
    assert result.ok is False
    assert result.error.code.value == "permission"


def test_confirm_publishes_confirm_required_not_denied():
    bus = EventBus()
    received = _collect(bus)
    router = ToolRouter(
        {"risky": ConfirmTool()}, event_bus=bus, permission_engine=StaticPermissionEngine()
    )
    asyncio.run(router.dispatch(ToolCall(name="risky", arguments={}, call_id="k1")))
    assert [e.event_type for e in received] == ["tool.execution.confirm_required"]


def test_block_still_publishes_denied():
    bus = EventBus()
    received = _collect(bus)
    router = ToolRouter(
        {"forbidden": BlockTool()}, event_bus=bus, permission_engine=StaticPermissionEngine()
    )
    asyncio.run(router.dispatch(ToolCall(name="forbidden", arguments={}, call_id="k1")))
    assert [e.event_type for e in received] == ["tool.execution.denied"]


def test_safe_still_publishes_started_then_finished():
    bus = EventBus()
    received = _collect(bus)
    router = ToolRouter(
        {"safe": SafeTool()}, event_bus=bus, permission_engine=StaticPermissionEngine()
    )
    asyncio.run(router.dispatch(ToolCall(name="safe", arguments={}, call_id="k1")))
    assert [e.event_type for e in received] == ["tool.execution.started", "tool.execution.finished"]


def test_engine_raising_chaos_error_is_mapped_to_failed_not_denied():
    bus = EventBus()
    received = _collect(bus)
    router = ToolRouter(
        {"safe": SafeTool()},
        event_bus=bus,
        permission_engine=_RaisingEngine(ExecutionError("permission backend down")),
    )
    result = asyncio.run(router.dispatch(ToolCall(name="safe", arguments={})))
    assert result.ok is False
    assert result.error.code.value == "execution"
    assert [e.event_type for e in received] == ["tool.execution.failed"]


def test_engine_raising_unexpected_exception_does_not_crash_dispatch():
    router = ToolRouter(
        {"safe": SafeTool()}, permission_engine=_RaisingEngine(RuntimeError("boom"))
    )
    result = asyncio.run(router.dispatch(ToolCall(name="safe", arguments={})))
    assert result.ok is False
    assert result.error.code.value == "execution"
    assert "boom" in result.error.message


def test_call_id_preserved_across_permission_engine_outcomes():
    router = ToolRouter(
        {"risky": ConfirmTool(), "forbidden": BlockTool()},
        permission_engine=StaticPermissionEngine(),
    )
    confirm = asyncio.run(router.dispatch(ToolCall(name="risky", arguments={}, call_id="c1")))
    block = asyncio.run(router.dispatch(ToolCall(name="forbidden", arguments={}, call_id="c2")))
    assert (confirm.call_id, block.call_id) == ("c1", "c2")
