"""STTProvider contract — vendor-neutral streaming speech-to-text.

Audio crosses the boundary as raw ``bytes`` plus an ``AudioFormat``
descriptor so no vendor SDK types leak into the contract.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class AudioFormat:
    """Describes raw audio bytes without depending on any SDK."""

    sample_rate_hz: int = 16000
    channels: int = 1
    encoding: str = "pcm_s16le"


@dataclass(frozen=True)
class Transcription:
    """Final transcription of one utterance."""

    text: str
    language: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class TranscriptChunk:
    """One streaming chunk. ``is_final=True`` marks a stable segment."""

    text: str
    is_final: bool = False
    language: str | None = None
    confidence: float | None = None


class STTProvider(ABC):
    """Interface every STT adapter must implement (voice milestones)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Opaque adapter label."""
        raise NotImplementedError

    @abstractmethod
    async def transcribe(
        self,
        audio: bytes,
        *,
        audio_format: AudioFormat,
        language: str | None = None,
    ) -> Transcription:
        """Transcribe one complete audio buffer."""
        raise NotImplementedError

    @abstractmethod
    async def stream_transcribe(
        self,
        audio_chunks: AsyncIterator[bytes],
        *,
        audio_format: AudioFormat,
        language: str | None = None,
    ) -> AsyncIterator[TranscriptChunk]:
        """Transcribe a live audio stream, yielding partial/final chunks."""
        raise NotImplementedError
        yield  # pragma: no cover — keeps this an async generator


__all__ = [
    "AudioFormat",
    "STTProvider",
    "TranscriptChunk",
    "Transcription",
]
