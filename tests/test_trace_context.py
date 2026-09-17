"""Trace-context tests: set/get/reset, nesting, async isolation."""

import asyncio
from dataclasses import FrozenInstanceError

import pytest

from chaos.ha_tang.context import TraceContext, clear_context, get_context, use_context


@pytest.fixture(autouse=True)
def _isolated():
    clear_context()
    yield
    clear_context()


def test_missing_context_is_none():
    assert get_context() is None


def test_set_get_and_reset():
    context = TraceContext.new(session_id="s1")
    assert context.correlation_id
    assert context.session_id == "s1"
    assert context.task_id is None
    with use_context(context) as installed:
        assert installed is context
        assert get_context() is context
    assert get_context() is None


def test_nested_contexts_restore():
    outer = TraceContext.new(session_id="outer")
    inner = TraceContext.new(session_id="inner", task_id="t1")
    with use_context(outer):
        assert get_context() is outer
        with use_context(inner):
            assert get_context() is inner
        assert get_context() is outer
    assert get_context() is None


def test_context_is_immutable():
    context = TraceContext.new()
    with pytest.raises(FrozenInstanceError):
        context.session_id = "mutated"  # type: ignore[misc]


def test_async_tasks_do_not_leak_context():
    parent = TraceContext.new(session_id="parent")

    async def _child():
        assert get_context() is parent  # inherited at creation
        with use_context(TraceContext.new(session_id="child")):
            assert get_context().session_id == "child"
            await asyncio.sleep(0)
        assert get_context() is parent

    async def _main():
        with use_context(parent):
            await asyncio.gather(_child(), _child())
            assert get_context() is parent

    asyncio.run(_main())
    assert get_context() is None
