"""TTSProvider contract — vendor-neutral streaming text-to-speech.

Speech crosses the boundary as raw ``bytes`` plus ``AudioFormat``
(see ``stt_provider``); ``voice`` is an opaque operator-configured
label, never a vendor-specific identifier in this contract.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from chaos.bo_nao.contracts.stt_provider import AudioFormat


@dataclass(frozen=True)
class SpeechRequest:
    """One synthesis request."""

    text: str
    voice: str | None = None
    language: str | None = None
    audio_format: AudioFormat | None = None


@dataclass(frozen=True)
class SpeechChunk:
    """One streaming audio chunk. ``done=True`` marks the final chunk."""

    audio: bytes
    done: bool = False


class TTSProvider(ABC):
    """Interface every TTS adapter must implement (voice milestones)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Opaque adapter label."""
        raise NotImplementedError

    @abstractmethod
    async def synthesize(self, request: SpeechRequest) -> bytes:
        """Synthesize one complete utterance."""
        raise NotImplementedError

    @abstractmethod
    async def stream_synthesize(self, request: SpeechRequest) -> AsyncIterator[SpeechChunk]:
        """Synthesize incrementally, yielding audio until ``done``."""
        raise NotImplementedError
        yield  # pragma: no cover — keeps this an async generator


__all__ = ["SpeechChunk", "SpeechRequest", "TTSProvider"]
