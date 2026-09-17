"""StaticPermissionEngine tests (T4.1): pure PermissionClass -> verdict policy."""

import asyncio

from chaos.bao_mat.contracts.permission_engine import (
    PermissionEngine,
    PermissionRequest,
    PermissionVerdict,
)
from chaos.bao_mat.engine import StaticPermissionEngine
from chaos.ha_tang.contracts.common import PermissionClass


def _check(permission_class: PermissionClass, **kwargs) -> object:
    request = PermissionRequest(tool_name="thetool", permission_class=permission_class, **kwargs)
    return asyncio.run(StaticPermissionEngine().check(request))


def test_is_a_real_permission_engine():
    assert isinstance(StaticPermissionEngine(), PermissionEngine)


def test_safe_is_allowed():
    decision = _check(PermissionClass.SAFE)
    assert decision.verdict is PermissionVerdict.ALLOW
    assert decision.reason
    assert decision.confirmation_prompt is None
    assert decision.risks == ()


def test_confirm_carries_a_prompt_and_a_risk():
    decision = _check(PermissionClass.CONFIRM)
    assert decision.verdict is PermissionVerdict.CONFIRM
    assert decision.confirmation_prompt is not None
    assert "thetool" in decision.confirmation_prompt
    assert decision.risks != ()
    assert decision.reason


def test_block_is_denied_with_reason_and_risk():
    decision = _check(PermissionClass.BLOCK)
    assert decision.verdict is PermissionVerdict.BLOCK
    assert decision.confirmation_prompt is None
    assert decision.risks != ()
    assert decision.reason


def test_decision_is_deterministic_and_ignores_input_summary_and_context():
    """Same tool + class must always decide the same way regardless of
    call content — a content-aware policy is explicitly out of scope
    (see Milestone 4 Plan): this engine must never become an
    accidental bypass tunable by what the caller passes in."""
    plain = _check(PermissionClass.CONFIRM)
    with_content = _check(
        PermissionClass.CONFIRM,
        input_summary={"path": "/etc/passwd", "danger": True},
        context="a very suspicious context string",
    )
    assert plain == with_content


def test_different_tool_names_produce_different_prompts():
    a = _check(PermissionClass.CONFIRM)
    other = asyncio.run(
        StaticPermissionEngine().check(
            PermissionRequest(tool_name="othertool", permission_class=PermissionClass.CONFIRM)
        )
    )
    assert a.confirmation_prompt != other.confirmation_prompt
