"""Tool contract tests: shape, result invariants, async surface, no bypass."""

import ast
import asyncio
import inspect
from pathlib import Path

import pytest

import chaos.cong_cu.contracts.tool as tool_module
from chaos.cong_cu.contracts.tool import Tool, ToolResult
from chaos.ha_tang.contracts.common import PermissionClass, ToolCall
from chaos.ha_tang.contracts.errors import ExecutionError, ValidationError


class EchoTool(Tool):
    """Minimal test double — lives in tests, never in src."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "echoes input"

    @property
    def input_schema(self):
        return {"type": "object", "properties": {"text": {"type": "string"}}}

    @property
    def output_schema(self):
        return {"type": "object", "properties": {"text": {"type": "string"}}}

    @property
    def permission(self) -> PermissionClass:
        return PermissionClass.SAFE

    @property
    def timeout_seconds(self) -> float:
        return 5.0

    async def validate(self, payload):
        if "text" not in payload:
            raise ValidationError("missing 'text'")
        return {"text": str(payload["text"])}

    async def execute(self, call: ToolCall) -> ToolResult:
        validated = await self.validate(dict(call.arguments))
        return ToolResult(ok=True, tool=self.name, data=validated, call_id=call.call_id)


def test_tool_is_abstract():
    with pytest.raises(TypeError):
        Tool()  # type: ignore[abstract]


def test_tool_async_surface():
    assert inspect.iscoroutinefunction(Tool.validate)
    assert inspect.iscoroutinefunction(Tool.execute)


def test_tool_result_ok_invariant():
    ok = ToolResult(ok=True, tool="echo", data={"text": "hi"})
    assert ok.error is None
    with pytest.raises(ValueError):
        ToolResult(ok=True, tool="echo", error=ExecutionError("x"))
    with pytest.raises(ValueError):
        ToolResult(ok=False, tool="echo")


def test_echo_tool_end_to_end_shape():
    tool = EchoTool()
    assert tool.permission is PermissionClass.SAFE
    call = ToolCall(name="echo", arguments={"text": "hi"}, call_id="k1")
    result = asyncio.run(tool.execute(call))
    assert result.ok and result.data == {"text": "hi"} and result.call_id == "k1"
    with pytest.raises(ValidationError):
        asyncio.run(tool.validate({}))


def test_tool_module_has_no_permission_bypass_path():
    """The Tool contract must not reach the PermissionEngine at all.

    AST-based (docstrings ignored): no import from ``bao_mat`` and no
    code-level reference to the ``PermissionEngine`` name.
    """
    tree = ast.parse(Path(tool_module.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "bao_mat" not in alias.name
                assert "PermissionEngine" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "bao_mat"
            for alias in node.names:
                assert alias.name != "PermissionEngine"
        elif isinstance(node, ast.Name):
            assert node.id != "PermissionEngine"
