"""ToolRouter tests (T3.1): validate -> permission placeholder -> timeout-bounded execute."""

import asyncio

from chaos.cong_cu.contracts.tool import Tool, ToolResult
from chaos.cong_cu.router import ToolRouter
from chaos.ha_tang.contracts.common import PermissionClass, ToolCall
from chaos.ha_tang.contracts.errors import ValidationError


class _BaseTool(Tool):
    permission_class = PermissionClass.SAFE
    timeout = 5.0

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
        return self.timeout

    async def validate(self, payload):
        return dict(payload)

    async def execute(self, call: ToolCall) -> ToolResult:
        return ToolResult(ok=True, tool=self.name, data=dict(call.arguments), call_id=call.call_id)


class SafeEchoTool(_BaseTool):
    @property
    def name(self) -> str:
        return "echo"

    async def validate(self, payload):
        if "text" not in payload:
            raise ValidationError("missing 'text'")
        return {"text": str(payload["text"])}


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


class SlowTool(_BaseTool):
    timeout = 0.05

    @property
    def name(self) -> str:
        return "slow"

    async def execute(self, call: ToolCall) -> ToolResult:
        await asyncio.sleep(10)
        return ToolResult(ok=True, tool=self.name)  # pragma: no cover - never reached


class BrokenValidateTool(_BaseTool):
    @property
    def name(self) -> str:
        return "broken-validate"

    async def validate(self, payload):
        raise RuntimeError("validate exploded")


class BrokenExecuteTool(_BaseTool):
    @property
    def name(self) -> str:
        return "broken-execute"

    async def execute(self, call: ToolCall) -> ToolResult:
        raise RuntimeError("execute exploded")


class BadReturnTool(_BaseTool):
    @property
    def name(self) -> str:
        return "bad-return"

    async def execute(self, call: ToolCall) -> ToolResult:
        return {"not": "a ToolResult"}  # type: ignore[return-value]


def _router(*tools: Tool) -> ToolRouter:
    return ToolRouter({tool.name: tool for tool in tools})


def test_safe_tool_executes_and_returns_normalized_data():
    router = _router(SafeEchoTool())
    result = asyncio.run(router.dispatch(ToolCall(name="echo", arguments={"text": 42})))
    assert result.ok is True
    assert result.data == {"text": "42"}  # coerced by validate()


def test_unknown_tool_name_is_a_validation_error():
    router = _router(SafeEchoTool())
    result = asyncio.run(router.dispatch(ToolCall(name="does-not-exist", arguments={})))
    assert result.ok is False
    assert isinstance(result.error, ValidationError)
    assert "unknown tool" in result.error.message


def test_validate_failure_is_returned_not_raised():
    router = _router(SafeEchoTool())
    result = asyncio.run(router.dispatch(ToolCall(name="echo", arguments={})))
    assert result.ok is False
    assert isinstance(result.error, ValidationError)


def test_confirm_tool_is_denied_without_permission_engine():
    router = _router(ConfirmTool())
    result = asyncio.run(router.dispatch(ToolCall(name="risky", arguments={})))
    assert result.ok is False
    assert result.error.code.value == "permission"


def test_block_tool_is_denied():
    router = _router(BlockTool())
    result = asyncio.run(router.dispatch(ToolCall(name="forbidden", arguments={})))
    assert result.ok is False
    assert result.error.code.value == "permission"


def test_execution_timeout_is_mapped_to_operation_timeout_error():
    router = _router(SlowTool())
    result = asyncio.run(router.dispatch(ToolCall(name="slow", arguments={})))
    assert result.ok is False
    assert result.error.code.value == "timeout"


def test_unexpected_validate_exception_does_not_crash_dispatch():
    router = _router(BrokenValidateTool())
    result = asyncio.run(router.dispatch(ToolCall(name="broken-validate", arguments={})))
    assert result.ok is False
    assert isinstance(result.error, ValidationError)
    assert "validate exploded" in result.error.message


def test_unexpected_execute_exception_does_not_crash_dispatch():
    router = _router(BrokenExecuteTool())
    result = asyncio.run(router.dispatch(ToolCall(name="broken-execute", arguments={})))
    assert result.ok is False
    assert result.error.code.value == "execution"
    assert "execute exploded" in result.error.message


def test_tool_returning_wrong_type_is_caught():
    router = _router(BadReturnTool())
    result = asyncio.run(router.dispatch(ToolCall(name="bad-return", arguments={})))
    assert result.ok is False
    assert result.error.code.value == "execution"
    assert "expected ToolResult" in result.error.message


def test_call_id_is_preserved_across_every_failure_path():
    router = _router(SafeEchoTool(), ConfirmTool(), SlowTool())
    unknown = asyncio.run(router.dispatch(ToolCall(name="nope", arguments={}, call_id="k1")))
    invalid = asyncio.run(router.dispatch(ToolCall(name="echo", arguments={}, call_id="k2")))
    denied = asyncio.run(router.dispatch(ToolCall(name="risky", arguments={}, call_id="k3")))
    timed_out = asyncio.run(router.dispatch(ToolCall(name="slow", arguments={}, call_id="k4")))
    assert [r.call_id for r in (unknown, invalid, denied, timed_out)] == ["k1", "k2", "k3", "k4"]


def test_tool_names_lists_registered_tools_sorted():
    router = _router(SafeEchoTool(), ConfirmTool())
    assert router.tool_names == ("echo", "risky")
