"""Brain runtime — single-turn Cloud Brain orchestration (Milestone 1).

Owns provider selection, context-budget enforcement and graceful
failure mapping. It does NOT execute tools, decide permissions, run an
agent loop or keep memory — those are M3/M4/M8/M15. The brain returns
tool calls as data; execution happens elsewhere.
"""

import logging
from collections.abc import AsyncIterator, Mapping

from chaos.bo_nao.contracts.ai_provider import (
    AIMessage,
    AIProvider,
    AIRequest,
    AIResponse,
    AIStreamChunk,
    Role,
    ToolSpec,
)
from chaos.cau_hinh.settings import ChaosSettings
from chaos.ha_tang.contracts.errors import ChaosError, ConfigurationError, ProviderError
from chaos.ha_tang.logging import log_event
from chaos.ha_tang.redaction import format_error, scrub_known_secrets

CHARS_PER_TOKEN_ESTIMATE = 4


def estimate_tokens(text: str) -> int:
    """Rough token estimate (characters/4). A documented heuristic for
    budget enforcement — never a billing-grade count."""
    return max(1, len(text) // CHARS_PER_TOKEN_ESTIMATE)


def apply_budget(messages: tuple[AIMessage, ...], max_tokens: int | None) -> tuple[AIMessage, ...]:
    """Drop oldest non-system messages until the estimate fits.

    System messages are always kept; content is never truncated, only
    whole messages are dropped; a single over-budget message is kept as
    best effort. Deterministic. ``None`` budget passes through.
    """
    if max_tokens is None:
        return messages
    total = sum(estimate_tokens(message.content) for message in messages)
    if total <= max_tokens:
        return messages
    system = [message for message in messages if message.role is Role.SYSTEM]
    rest = [message for message in messages if message.role is not Role.SYSTEM]
    while rest:
        estimated = sum(estimate_tokens(message.content) for message in (*system, *rest))
        if estimated <= max_tokens:
            break
        rest.pop(0)
    kept = (*system, *rest)
    if not kept:
        return messages[-1:]
    return kept


class BrainRuntime:
    """Single-turn orchestrator over registered AI providers."""

    def __init__(self, providers: Mapping[str, AIProvider], settings: ChaosSettings) -> None:
        if not providers:
            raise ConfigurationError("brain requires at least one provider")
        self._providers = dict(providers)
        self._settings = settings

    def __repr__(self) -> str:
        return f"BrainRuntime(providers={sorted(self._providers)})"

    @property
    def provider_names(self) -> tuple[str, ...]:
        """Registered adapter names."""
        return tuple(sorted(self._providers))

    def _select(self, name: str | None) -> AIProvider:
        wanted = name or self._settings.ai.provider_name or "default"
        try:
            return self._providers[wanted]
        except KeyError:
            raise ConfigurationError(
                f"unknown AI provider: {wanted!r} (available: {', '.join(self.provider_names)})"
            ) from None

    def _known_secrets(self) -> list[str]:
        if self._settings.ai.api_key is not None:
            return [self._settings.ai.api_key.expose()]
        return []

    def _build_request(
        self,
        messages: tuple[AIMessage, ...],
        tools: tuple[ToolSpec, ...],
        max_tokens: int | None,
        temperature: float | None,
    ) -> AIRequest:
        budgeted = apply_budget(messages, self._settings.ai.max_context_tokens)
        return AIRequest(
            messages=budgeted,
            tools=tools,
            timeout_seconds=self._settings.runtime.request_timeout_seconds,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def _log_completed(self, logger_name: str, response: AIResponse, provider: str) -> None:
        log_event(
            logging.getLogger(logger_name),
            "INFO",
            "brain.turn.completed",
            {
                "provider": provider,
                "model": response.model,
                "tool_calls": len(response.tool_calls),
                "usage": dict(response.usage),
            },
        )

    async def complete(
        self,
        messages: tuple[AIMessage, ...],
        tools: tuple[ToolSpec, ...] = (),
        *,
        provider: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        logger_name: str = "chaos",
    ) -> AIResponse:
        """Run one turn: budget → provider → mapped response."""
        adapter = self._select(provider)
        request = self._build_request(messages, tools, max_tokens, temperature)
        try:
            response = await adapter.complete(request)
        except Exception as exc:
            log_event(
                logging.getLogger(logger_name),
                "ERROR",
                "brain.turn.failed",
                {"error": scrub_known_secrets(format_error(exc), self._known_secrets())},
            )
            if isinstance(exc, ChaosError):
                raise
            raise ProviderError("brain request failed") from exc
        self._log_completed(logger_name, response, adapter.name)
        return response

    async def stream(
        self,
        messages: tuple[AIMessage, ...],
        tools: tuple[ToolSpec, ...] = (),
        *,
        provider: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[AIStreamChunk]:
        """Run one streaming turn (budget applies, same selection)."""
        adapter = self._select(provider)
        request = self._build_request(messages, tools, max_tokens, temperature)
        async for chunk in adapter.stream(request):
            yield chunk


__all__ = ["CHARS_PER_TOKEN_ESTIMATE", "BrainRuntime", "apply_budget", "estimate_tokens"]
