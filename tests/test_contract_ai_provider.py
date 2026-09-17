"""AIProvider contract tests: DTOs, tool-call representation, streaming shape."""

import asyncio
import inspect

import pytest

from chaos.bo_nao.contracts.ai_provider import (
    AIMessage,
    AIProvider,
    AIRequest,
    AIResponse,
    AIStreamChunk,
    Role,
    ToolSpec,
)
from chaos.ha_tang.contracts.common import ToolCall


class FakeAI(AIProvider):
    """In-memory test double — lives in tests, never in src."""

    def __init__(self) -> None:
        self.seen: list[AIRequest] = []

    @property
    def name(self) -> str:
        return "fake-ai"

    async def complete(self, request: AIRequest) -> AIResponse:
        self.seen.append(request)
        calls = tuple(
            ToolCall(name=t.name, arguments={}, call_id="call-1") for t in request.tools[:1]
        )
        return AIResponse(content="done", tool_calls=calls, model="fake-label")

    async def stream(self, request: AIRequest):
        yield AIStreamChunk(delta="he")
        yield AIStreamChunk(delta="llo", tool_calls=(), done=False)
        yield AIStreamChunk(done=True)


def test_provider_is_abstract():
    with pytest.raises(TypeError):
        AIProvider()  # type: ignore[abstract]


def test_provider_async_and_streaming_surface():
    assert inspect.iscoroutinefunction(AIProvider.complete)
    assert inspect.isasyncgenfunction(FakeAI.stream)


def test_request_response_dtos():
    request = AIRequest(
        messages=(AIMessage(role=Role.USER, content="hi"),),
        tools=(ToolSpec(name="echo", description="e", input_schema={"type": "object"}),),
        timeout_seconds=10.0,
    )
    assert request.messages[0].role is Role.USER
    assert request.timeout_seconds == 10.0
    provider = FakeAI()
    response = asyncio.run(provider.complete(request))
    assert response.content == "done"
    assert response.tool_calls[0].name == "echo"
    assert provider.seen == [request]


def test_streaming_contract_order_and_done():
    chunks = asyncio.run(_collect(FakeAI(), AIRequest(messages=())))
    assert [c.delta for c in chunks] == ["he", "llo", ""]
    assert chunks[-1].done is True
    assert all(c.done is False for c in chunks[:-1])


async def _collect(provider: FakeAI, request: AIRequest):
    return [chunk async for chunk in provider.stream(request)]


def test_tool_message_references_call():
    msg = AIMessage(role=Role.TOOL, content="{}", tool_call_id="call-1")
    assert msg.tool_call_id == "call-1"
    assert msg.tool_calls == ()


def test_no_vendor_lock_in_contract():
    from pathlib import Path

    import chaos.bo_nao.contracts.ai_provider as module

    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    for vendor in ("openai", "anthropic", "gemini", "azure", "bedrock"):
        assert vendor not in source
