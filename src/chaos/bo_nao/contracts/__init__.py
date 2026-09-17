"""bo_nao.contracts — brain boundaries: AI, STT, TTS provider contracts."""

from chaos.bo_nao.contracts.ai_provider import (
    AIMessage,
    AIProvider,
    AIRequest,
    AIResponse,
    AIStreamChunk,
    Role,
    ToolSpec,
)
from chaos.bo_nao.contracts.stt_provider import (
    AudioFormat,
    STTProvider,
    TranscriptChunk,
    Transcription,
)
from chaos.bo_nao.contracts.tts_provider import SpeechChunk, SpeechRequest, TTSProvider

__all__ = [
    "AIMessage",
    "AIProvider",
    "AIRequest",
    "AIResponse",
    "AIStreamChunk",
    "AudioFormat",
    "Role",
    "STTProvider",
    "SpeechChunk",
    "SpeechRequest",
    "TTSProvider",
    "ToolSpec",
    "TranscriptChunk",
    "Transcription",
]
