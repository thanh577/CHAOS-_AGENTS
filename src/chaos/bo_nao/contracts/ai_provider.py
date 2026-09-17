"""AIProvider contract — vendor-neutral Cloud Brain boundary.

Defines the request/response/tool-call/streaming shapes the Brain
Runtime needs. No adapter for any concrete vendor here; no network,
no API keys, no calls. Timeout *enforcement* is the runtime's job
in a later milestone — this contract only carries the timeout value.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from chaos.ha_tang.contracts.common import ToolCall


class Role(Enum):
    """Message roles in a provider-agnostic conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class AIMessage:
    """One message in an AI request. ``TOOL`` messages carry the tool
    result back and reference the originating call via ``tool_call_id``.
    """

    role: Role
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    """Advertises one callable tool to the provider.

    ``input_schema`` is a plain JSON-schema-shaped mapping so the
    contract stays dependency-free (no pydantic).
    """

    name: str
    description: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIRequest:
    """Everything the runtime sends to the provider in one turn."""

    messages: tuple[AIMessage, ...]
    tools: tuple[ToolSpec, ...] = ()
    timeout_seconds: float = 60.0
    max_tokens: int | None = None
    temperature: float | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIResponse:
    """One completed turn. ``model`` is an opaque label supplied by
    the adapter — never a hardcoded vendor dependency in this contract.
    """

    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    model: str | None = None
    usage: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIStreamChunk:
    """One streaming delta. ``done=True`` marks the final chunk."""

    delta: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    done: bool = False


class AIProvider(ABC):
    """Interface every cloud-AI adapter must implement (Milestone 1+)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Opaque adapter label (e.g. configured by the operator)."""
        raise NotImplementedError

    @abstractmethod
    async def complete(self, request: AIRequest) -> AIResponse:
        """Run one non-streaming turn."""
        raise NotImplementedError

    @abstractmethod
    async def stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        """Run one streaming turn, yielding deltas until ``done``."""
        raise NotImplementedError
        yield  # pragma: no cover — keeps this an async generator


__all__ = [
    "AIMessage",
    "AIProvider",
    "AIRequest",
    "AIResponse",
    "AIStreamChunk",
    "Role",
    "ToolSpec",
]
