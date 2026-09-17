"""PermissionEngine contract tests: decisions carry verdict+reason+risk."""

import asyncio
import inspect

import pytest

from chaos.bao_mat.contracts.permission_engine import (
    PermissionDecision,
    PermissionEngine,
    PermissionRequest,
    PermissionVerdict,
)
from chaos.ha_tang.contracts.common import PermissionClass


class FixedEngine(PermissionEngine):
    """Test double with a canned decision — lives in tests, never in src."""

    def __init__(self, decision: PermissionDecision) -> None:
        self._decision = decision

    async def check(self, request: PermissionRequest) -> PermissionDecision:
        assert request.tool_name
        return self._decision


def test_engine_is_abstract():
    with pytest.raises(TypeError):
        PermissionEngine()  # type: ignore[abstract]
    assert inspect.iscoroutinefunction(PermissionEngine.check)


def test_verdicts_cover_allow_confirm_block():
    assert {v.value for v in PermissionVerdict} == {"allow", "confirm", "block"}


def test_allow_and_block_decisions():
    allow = PermissionDecision(verdict=PermissionVerdict.ALLOW, reason="safe tool")
    assert allow.confirmation_prompt is None
    block = PermissionDecision(
        verdict=PermissionVerdict.BLOCK,
        reason="destructive scope",
        risks=("deletes user data",),
    )
    out = asyncio.run(
        FixedEngine(block).check(
            PermissionRequest(tool_name="wipe", permission_class=PermissionClass.BLOCK)
        )
    )
    assert out.verdict is PermissionVerdict.BLOCK
    assert out.risks == ("deletes user data",)


def test_confirm_requires_prompt():
    with pytest.raises(ValueError):
        PermissionDecision(verdict=PermissionVerdict.CONFIRM, reason="needs human")
    confirm = PermissionDecision(
        verdict=PermissionVerdict.CONFIRM,
        reason="writes outside workspace",
        risks=("modifies /etc/hosts",),
        confirmation_prompt="Allow writing /etc/hosts?",
    )
    out = asyncio.run(
        FixedEngine(confirm).check(
            PermissionRequest(tool_name="write", permission_class=PermissionClass.CONFIRM)
        )
    )
    assert out.confirmation_prompt == "Allow writing /etc/hosts?"


def test_request_defaults():
    req = PermissionRequest(tool_name="t", permission_class=PermissionClass.SAFE)
    assert req.input_summary == {}
    assert req.context == ""
