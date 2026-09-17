"""ToolRouter + Verifier wiring tests (T5.2)."""

import asyncio

from chaos.cong_cu.contracts.tool import Tool, ToolResult
from chaos.cong_cu.router import ToolRouter
from chaos.ha_tang.contracts.common import PermissionClass, ToolCall
from chaos.ha_tang.contracts.errors import ExecutionError
from chaos.ha_tang.event_bus import WILDCARD, EventBus
from chaos.kiem_tra.contracts.verifier import (
    VerificationExpectation,
    VerificationResult,
    VerificationVerdict,
    Verifier,
)
from chaos.kiem_tra.verifier import ExecutionOutcomeVerifier


class _BaseTool(Tool):
    outcome_ok = True

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
        return PermissionClass.SAFE

    @property
    def timeout_seconds(self) -> float:
        return 5.0

    async def validate(self, payload):
        return dict(payload)

    async def execute(self, call: ToolCall) -> ToolResult:
        if self.outcome_ok:
            return ToolResult(ok=True, tool=self.name, call_id=call.call_id)
        return ToolResult(
            ok=False,
            tool=self.name,
            error=ExecutionError("tool reported its own failure"),
            call_id=call.call_id,
        )


class SucceedingTool(_BaseTool):
    @property
    def name(self) -> str:
        return "succeeds"


class FailingTool(_BaseTool):
    outcome_ok = False

    @property
    def name(self) -> str:
        return "fails"


class _FixedVerifier(Verifier):
    def __init__(self, result: VerificationResult) -> None:
        self._result = result

    async def verify(self, result: ToolResult, expectation: VerificationExpectation):
        return self._result


class _RaisingVerifier(Verifier):
    def __init__(self, error: Exception) -> None:
        self._error = error

    async def verify(self, result: ToolResult, expectation: VerificationExpectation):
        raise self._error


def _collect(bus: EventBus) -> list:
    received: list = []
    bus.subscribe(WILDCARD, received.append)
    return received


def test_no_verifier_leaves_m3_m4_behavior_unchanged():
    router = ToolRouter({"succeeds": SucceedingTool()})  # verifier omitted
    result = asyncio.run(router.dispatch(ToolCall(name="succeeds", arguments={})))
    assert result.ok is True


def test_verified_verdict_leaves_result_unchanged():
    router = ToolRouter({"succeeds": SucceedingTool()}, verifier=ExecutionOutcomeVerifier())
    result = asyncio.run(router.dispatch(ToolCall(name="succeeds", arguments={})))
    assert result.ok is True


def test_uncertain_verdict_overrides_to_not_ok_with_named_event():
    bus = EventBus()
    received = _collect(bus)
    router = ToolRouter(
        {"succeeds": SucceedingTool()}, event_bus=bus, verifier=ExecutionOutcomeVerifier()
    )
    result = asyncio.run(
        router.dispatch(
            ToolCall(name="succeeds", arguments={}, call_id="k1"),
            expectation=VerificationExpectation(conditions=("file-exists",)),
        )
    )
    assert result.ok is False
    assert result.error.code.value == "verification"
    assert [e.event_type for e in received] == [
        "tool.execution.started",
        "tool.verification.uncertain",
    ]


def test_failed_verdict_overrides_to_not_ok_with_named_event():
    bus = EventBus()
    received = _collect(bus)
    failed = VerificationResult(verdict=VerificationVerdict.FAILED, reason="postcondition broke")
    router = ToolRouter(
        {"succeeds": SucceedingTool()}, event_bus=bus, verifier=_FixedVerifier(failed)
    )
    result = asyncio.run(router.dispatch(ToolCall(name="succeeds", arguments={}, call_id="k1")))
    assert result.ok is False
    assert result.error.code.value == "verification"
    assert "postcondition broke" in result.error.message
    assert [e.event_type for e in received] == [
        "tool.execution.started",
        "tool.verification.failed",
    ]


def test_verification_short_circuits_finished_event():
    """A FAILED/UNCERTAIN verdict is terminal — tool.execution.finished
    must not also fire on top of the verification event."""
    bus = EventBus()
    received = _collect(bus)
    uncertain = VerificationResult(verdict=VerificationVerdict.UNCERTAIN, reason="dunno")
    router = ToolRouter(
        {"succeeds": SucceedingTool()}, event_bus=bus, verifier=_FixedVerifier(uncertain)
    )
    asyncio.run(router.dispatch(ToolCall(name="succeeds", arguments={})))
    assert "tool.execution.finished" not in [e.event_type for e in received]


def test_verifier_is_never_consulted_when_tool_reports_its_own_failure():
    bus = EventBus()
    received = _collect(bus)
    router = ToolRouter(
        {"fails": FailingTool()},
        event_bus=bus,
        verifier=_RaisingVerifier(RuntimeError("should never be called")),
    )
    result = asyncio.run(router.dispatch(ToolCall(name="fails", arguments={})))
    assert result.ok is False
    assert "tool reported its own failure" in result.error.message
    assert [e.event_type for e in received] == ["tool.execution.started", "tool.execution.finished"]


def test_verifier_raising_chaos_error_is_mapped_to_failed():
    bus = EventBus()
    received = _collect(bus)
    router = ToolRouter(
        {"succeeds": SucceedingTool()},
        event_bus=bus,
        verifier=_RaisingVerifier(ExecutionError("verifier backend down")),
    )
    result = asyncio.run(router.dispatch(ToolCall(name="succeeds", arguments={})))
    assert result.ok is False
    assert result.error.code.value == "execution"
    assert [e.event_type for e in received] == ["tool.execution.started", "tool.execution.failed"]


def test_verifier_raising_unexpected_exception_does_not_crash_dispatch():
    router = ToolRouter(
        {"succeeds": SucceedingTool()}, verifier=_RaisingVerifier(RuntimeError("boom"))
    )
    result = asyncio.run(router.dispatch(ToolCall(name="succeeds", arguments={})))
    assert result.ok is False
    assert result.error.code.value == "execution"
    assert "boom" in result.error.message


def test_call_id_preserved_across_verification_outcomes():
    uncertain = VerificationResult(verdict=VerificationVerdict.UNCERTAIN, reason="dunno")
    router = ToolRouter({"succeeds": SucceedingTool()}, verifier=_FixedVerifier(uncertain))
    result = asyncio.run(router.dispatch(ToolCall(name="succeeds", arguments={}, call_id="c1")))
    assert result.call_id == "c1"
