"""ExecutionOutcomeVerifier tests (T5.1): declared-conditions -> verdict policy."""

import asyncio

from chaos.cong_cu.contracts.tool import ToolResult
from chaos.kiem_tra.contracts.verifier import (
    VerificationExpectation,
    VerificationVerdict,
    Verifier,
)
from chaos.kiem_tra.verifier import ExecutionOutcomeVerifier


def _verify(conditions: tuple[str, ...] = (), **kwargs) -> object:
    result = ToolResult(ok=True, tool="thetool")
    expectation = VerificationExpectation(conditions=conditions, **kwargs)
    return asyncio.run(ExecutionOutcomeVerifier().verify(result, expectation))


def test_is_a_real_verifier():
    assert isinstance(ExecutionOutcomeVerifier(), Verifier)


def test_no_declared_conditions_is_verified():
    out = _verify()
    assert out.verdict is VerificationVerdict.VERIFIED
    assert "thetool" in out.reason


def test_declared_conditions_are_uncertain_not_silently_accepted():
    out = _verify(conditions=("file-exists",))
    assert out.verdict is VerificationVerdict.UNCERTAIN
    assert "file-exists" in out.reason


def test_multiple_declared_conditions_are_all_named_in_the_reason():
    out = _verify(conditions=("file-exists", "http-200"))
    assert out.verdict is VerificationVerdict.UNCERTAIN
    assert "file-exists" in out.reason
    assert "http-200" in out.reason


def test_details_do_not_change_the_verdict():
    """Ignorant of expectation.details, same reasoning as
    StaticPermissionEngine ignoring input_summary/context."""
    plain = _verify()
    with_details = _verify(details={"path": "/etc/passwd"})
    assert plain.verdict == with_details.verdict


def test_never_returns_failed_on_its_own():
    """This baseline never fabricates a FAILED verdict — it has no
    domain knowledge to prove a claim false, only to admit it cannot
    confirm one."""
    for conditions in ((), ("x",), ("x", "y")):
        out = _verify(conditions=conditions)
        assert out.verdict is not VerificationVerdict.FAILED
