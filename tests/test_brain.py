"""Brain runtime tests (T1.4): budget, selection, failure mapping, boundaries."""

import ast
import asyncio
import logging
from pathlib import Path

import pytest

import chaos.bo_nao.brain as brain_module
from chaos.bo_nao.brain import BrainRuntime, apply_budget, estimate_tokens
from chaos.bo_nao.contracts.ai_provider import (
    AIMessage,
    AIRequest,
    AIResponse,
    AIStreamChunk,
    Role,
)
from chaos.cau_hinh.settings import ChaosSettings
from chaos.ha_tang.contracts.common import ToolCall
from chaos.ha_tang.contracts.errors import ConfigurationError, ProviderError, ValidationError


class FakeProvider:
    """In-memory AIProvider double — lives in tests, never in src."""

    def __init__(self, name="fake", *, fail_with=None, stream_chunks=()):
        self._name = name
        self._fail_with = fail_with
        self._stream_chunks = stream_chunks
        self.seen: list[AIRequest] = []

    @property
    def name(self):
        return self._name

    async def complete(self, request):
        self.seen.append(request)
        if self._fail_with is not None:
            raise self._fail_with
        return AIResponse(
            content="done",
            tool_calls=(ToolCall(name="echo", arguments={}, call_id="c1"),),
            model="fake",
            usage={"prompt_tokens": 1},
        )

    async def stream(self, request):
        self.seen.append(request)
        if self._fail_with is not None:
            raise self._fail_with
        for chunk in self._stream_chunks:
            yield chunk
        yield AIStreamChunk(done=True)


def _settings(overrides: dict | None = None):
    env = {"CHAOS_AI_PROVIDER": "fake"}
    env.update(overrides or {})
    return ChaosSettings.from_env(env)


def _messages(*texts, role=Role.USER):
    return tuple(AIMessage(role=role, content=text) for text in texts)


def test_estimate_heuristic():
    assert estimate_tokens("") == 1
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcdefgh") == 2


def test_budget_passthrough_and_fit():
    messages = _messages("hi")
    assert apply_budget(messages, None) == messages
    assert apply_budget(messages, 100) == messages


def test_budget_drops_oldest_non_system_first():
    system = AIMessage(role=Role.SYSTEM, content="sys")
    old = AIMessage(role=Role.USER, content="x" * 40)
    new = AIMessage(role=Role.USER, content="y" * 40)
    kept = apply_budget((system, old, new), 15)
    assert [m.content for m in kept] == ["sys", "y" * 40]


def test_budget_never_truncates_content():
    huge = AIMessage(role=Role.USER, content="z" * 1000)
    assert apply_budget((huge,), 10) == (huge,)


def test_empty_messages_ok():
    assert apply_budget((), 10) == ()


def test_empty_registry_rejected():
    with pytest.raises(ConfigurationError, match="at least one provider"):
        BrainRuntime({}, ChaosSettings.defaults())


def test_provider_selection():
    brain = BrainRuntime({"fake": FakeProvider()}, _settings())
    assert brain.provider_names == ("fake",)
    assert "fake" in repr(brain)
    with pytest.raises(ConfigurationError, match="unknown AI provider"):
        asyncio.run(brain.complete(_messages("hi"), provider="ghost"))


def test_complete_wires_settings():
    provider = FakeProvider()
    brain = BrainRuntime({"fake": provider}, _settings({"CHAOS_REQUEST_TIMEOUT": "12"}))
    response = asyncio.run(brain.complete(_messages("hi")))
    assert response.content == "done"
    assert provider.seen[0].timeout_seconds == 12.0


def test_budget_applied_before_provider():
    provider = FakeProvider()
    brain = BrainRuntime({"fake": provider}, _settings({"CHAOS_AI_MAX_CONTEXT_TOKENS": "15"}))
    asyncio.run(brain.complete(_messages("a" * 40, "b" * 40)))
    assert [m.content for m in provider.seen[0].messages] == ["b" * 40]


def test_chaos_errors_pass_through_with_classification():
    brain = BrainRuntime({"fake": FakeProvider(fail_with=ValidationError("bad"))}, _settings())
    with pytest.raises(ValidationError, match="bad"):
        asyncio.run(brain.complete(_messages("hi")))


def test_unknown_errors_become_provider_errors():
    brain = BrainRuntime({"fake": FakeProvider(fail_with=ValueError("boom"))}, _settings())
    with pytest.raises(ProviderError, match="brain request failed"):
        asyncio.run(brain.complete(_messages("hi")))


def test_failure_logging_is_metadata_only_and_secret_free():
    secret = "s3cr3t-brain-value"
    brain = BrainRuntime(
        {"fake": FakeProvider(fail_with=ValueError(f"with {secret}"))},
        _settings({"CHAOS_AI_API_KEY": secret}),
    )
    records: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("chaos-test-brain")
    logger.addHandler(_Collector())
    logger.setLevel(logging.DEBUG)
    try:
        with pytest.raises(ProviderError):
            asyncio.run(
                brain.complete(_messages("user says hello"), logger_name="chaos-test-brain")
            )
    finally:
        logger.handlers.clear()
    assert len(records) == 1
    fields = records[0].args
    assert fields["event"] == "brain.turn.failed"
    assert secret not in repr(fields)
    assert "user says hello" not in repr(fields)


def test_completed_event_carries_metadata_not_content():
    brain = BrainRuntime({"fake": FakeProvider()}, _settings())
    records: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("chaos-test-brain-ok")
    logger.addHandler(_Collector())
    logger.setLevel(logging.DEBUG)
    try:
        asyncio.run(
            brain.complete(_messages("sensitive user text"), logger_name="chaos-test-brain-ok")
        )
    finally:
        logger.handlers.clear()
    fields = records[0].args
    assert fields["event"] == "brain.turn.completed"
    assert fields["payload"]["tool_calls"] == 1
    assert "sensitive user text" not in repr(fields)


def test_stream_passthrough():
    chunks = (AIStreamChunk(delta="a"), AIStreamChunk(delta="b"))
    brain = BrainRuntime({"fake": FakeProvider(stream_chunks=chunks)}, _settings())

    async def _collect():
        return [chunk async for chunk in brain.stream(_messages("hi"))]

    out = asyncio.run(_collect())
    assert [c.delta for c in out] == ["a", "b", ""]
    assert out[-1].done is True


def test_brain_never_touches_permission_or_execution():
    """The brain returns tool calls as data — no permission/executor imports."""
    tree = ast.parse(Path(brain_module.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            roots = [node.module.split(".")[0]] if node.module else []
        else:
            continue
        for root in roots:
            assert root != "subprocess", "brain must not touch subprocess"
    source = Path(brain_module.__file__).read_text(encoding="utf-8")
    assert "PermissionEngine" not in source
    assert "bao_mat" not in source
    assert "cong_cu" not in source
