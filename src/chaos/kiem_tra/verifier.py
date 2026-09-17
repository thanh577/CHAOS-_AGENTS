"""ExecutionOutcomeVerifier (Milestone 5) — the first real
implementation of the ``kiem_tra/contracts/verifier.py`` contract
(T0.2).

Deliberately conservative, same reasoning as M4's
``StaticPermissionEngine``: no tool exists yet (the first concrete
tools arrive at M6 browser / M7 OS), so this verifier cannot know how
to check a *named* postcondition ("file-exists", "http-200", ...) —
inventing that logic now would be speculative. It only ever bases its
verdict on whether the caller declared any specific postconditions at
all:

- no declared conditions -> ``VERIFIED``: nothing specific was asked
  for, so the tool's own reported outcome stands.
- one or more declared conditions -> ``UNCERTAIN``: this engine has no
  domain knowledge to check them. Per the contract's own docstring,
  "the runtime must then retry, replan or escalate, never silently
  accept" — so it is not allowed to shrug and call it VERIFIED just
  because it does not know how to check.

No I/O — pure logic over the objects it is handed, exactly like
``bao_mat/engine.py``. Persisting a verification outcome is not a
separate concern here the way ``bao_mat/recording.py`` was for
permissions: DATA_MODEL.md defines no dedicated ``verifications``
table, so there is nothing to wrap — an audit trail rides on the
existing ``EventBus`` -> ``audit_events`` pipeline once
``cong_cu/router.py`` wires this in (T5.2).
"""

from chaos.cong_cu.contracts.tool import ToolResult
from chaos.kiem_tra.contracts.verifier import (
    VerificationExpectation,
    VerificationResult,
    VerificationVerdict,
    Verifier,
)


class ExecutionOutcomeVerifier(Verifier):
    """Trusts a tool's own outcome when nothing specific was asked
    for; otherwise reports honest uncertainty."""

    async def verify(
        self,
        result: ToolResult,
        expectation: VerificationExpectation,
    ) -> VerificationResult:
        if not expectation.conditions:
            return VerificationResult(
                verdict=VerificationVerdict.VERIFIED,
                reason=(
                    f"tool {result.tool!r} reported success and no specific "
                    "postconditions were declared"
                ),
            )

        return VerificationResult(
            verdict=VerificationVerdict.UNCERTAIN,
            checked=(),
            reason=(
                f"{len(expectation.conditions)} postcondition(s) declared "
                f"({', '.join(expectation.conditions)}) but no tool-specific checker "
                "is available yet (Milestone 5 baseline)"
            ),
        )


__all__ = ["ExecutionOutcomeVerifier"]
