"""Voice contract tests: vendor-neutral STT/TTS incl. streaming shapes."""

import asyncio
import inspect

import pytest

from chaos.bo_nao.contracts.stt_provider import (
    AudioFormat,
    STTProvider,
    TranscriptChunk,
    Transcription,
)
from chaos.bo_nao.contracts.tts_provider import SpeechChunk, SpeechRequest, TTSProvider


class FakeSTT(STTProvider):
    """In-memory test double — lives in tests, never in src."""

    @property
    def name(self) -> str:
        return "fake-stt"

    async def transcribe(self, audio: bytes, *, audio_format: AudioFormat, language=None):
        assert isinstance(audio_format, AudioFormat)
        return Transcription(text=f"{len(audio)}-bytes", language=language)

    async def stream_transcribe(self, audio_chunks, *, audio_format: AudioFormat, language=None):
        total = 0
        async for chunk in audio_chunks:
            total += len(chunk)
            yield TranscriptChunk(text="partial", is_final=False)
        yield TranscriptChunk(text=f"{total}-bytes", is_final=True)


class FakeTTS(TTSProvider):
    """In-memory test double — lives in tests, never in src."""

    @property
    def name(self) -> str:
        return "fake-tts"

    async def synthesize(self, request: SpeechRequest) -> bytes:
        return request.text.encode("utf-8")

    async def stream_synthesize(self, request: SpeechRequest):
        yield SpeechChunk(audio=b"he")
        yield SpeechChunk(audio=b"llo", done=True)


def test_providers_are_abstract():
    with pytest.raises(TypeError):
        STTProvider()  # type: ignore[abstract]
    with pytest.raises(TypeError):
        TTSProvider()  # type: ignore[abstract]


def test_surfaces_are_async_and_streaming():
    assert inspect.iscoroutinefunction(STTProvider.transcribe)
    assert inspect.iscoroutinefunction(TTSProvider.synthesize)
    assert inspect.isasyncgenfunction(FakeSTT.stream_transcribe)
    assert inspect.isasyncgenfunction(FakeTTS.stream_synthesize)


def test_audio_format_defaults():
    fmt = AudioFormat()
    assert (fmt.sample_rate_hz, fmt.channels, fmt.encoding) == (16000, 1, "pcm_s16le")


def test_stt_transcribe_and_stream():
    provider = FakeSTT()
    out = asyncio.run(provider.transcribe(b"\x00" * 8, audio_format=AudioFormat()))
    assert out.text == "8-bytes"

    async def _run():
        async def _audio():
            yield b"\x00" * 4
            yield b"\x00" * 4

        return [c async for c in provider.stream_transcribe(_audio(), audio_format=AudioFormat())]

    chunks = asyncio.run(_run())
    assert [c.is_final for c in chunks] == [False, False, True]
    assert chunks[-1].text == "8-bytes"


def test_tts_synthesize_and_stream():
    provider = FakeTTS()
    request = SpeechRequest(text="hi", voice="operator-voice", language="vi")
    assert asyncio.run(provider.synthesize(request)) == b"hi"

    async def _run():
        return [c async for c in provider.stream_synthesize(request)]

    chunks = asyncio.run(_run())
    assert b"".join(c.audio for c in chunks) == b"hello"
    assert chunks[-1].done is True


def test_no_vendor_sdk_in_voice_contracts():
    import io
    import tokenize
    from pathlib import Path

    import chaos.bo_nao.contracts.stt_provider as stt
    import chaos.bo_nao.contracts.tts_provider as tts

    def _code_only(module) -> str:
        """Source minus strings/comments, so prose can't trip the scan."""
        tokens = tokenize.generate_tokens(
            io.StringIO(Path(module.__file__).read_text(encoding="utf-8")).readline
        )
        kept = [t.string for t in tokens if t.type not in (tokenize.STRING, tokenize.COMMENT)]
        return "\n".join(kept).lower()

    for module in (stt, tts):
        code = _code_only(module)
        for token in ("openai", "google", "azure", "aws", "elevenlabs", "sdk"):
            assert token not in code
