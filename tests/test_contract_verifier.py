"""Verifier contract tests: three states with evidence and reasons."""

import asyncio
import inspect

import pytest

from chaos.cong_cu.contracts.tool import ToolResult
from chaos.kiem_tra.contracts.verifier import (
    VerificationExpectation,
    VerificationResult,
    VerificationVerdict,
    Verifier,
)


class FixedVerifier(Verifier):
    """Test double with a canned result — lives in tests, never in src."""

    def __init__(self, result: VerificationResult) -> None:
        self._result = result

    async def verify(self, result: ToolResult, expectation: VerificationExpectation):
        assert isinstance(result, ToolResult)
        assert isinstance(expectation, VerificationExpectation)
        return self._result


def test_verifier_is_abstract():
    with pytest.raises(TypeError):
        Verifier()  # type: ignore[abstract]
    assert inspect.iscoroutinefunction(Verifier.verify)


def test_verdicts_cover_verified_failed_uncertain():
    assert {v.value for v in VerificationVerdict} == {"verified", "failed", "uncertain"}


@pytest.mark.parametrize(
    "verdict",
    [VerificationVerdict.VERIFIED, VerificationVerdict.FAILED, VerificationVerdict.UNCERTAIN],
)
def test_each_verdict_round_trips(verdict):
    result = ToolResult(ok=True, tool="t")
    expectation = VerificationExpectation(conditions=("file-exists",))
    canned = VerificationResult(
        verdict=verdict,
        checked=("file-exists",),
        evidence={"path": "/tmp/x"},
        reason="checked postcondition",
    )
    out = asyncio.run(FixedVerifier(canned).verify(result, expectation))
    assert out.verdict is verdict
    assert out.checked == ("file-exists",)
    assert out.evidence == {"path": "/tmp/x"}


def test_result_defaults():
    empty = VerificationResult(verdict=VerificationVerdict.UNCERTAIN)
    assert empty.checked == ()
    assert empty.evidence == {}
    assert empty.reason == ""
