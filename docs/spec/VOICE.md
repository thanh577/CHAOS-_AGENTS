# Voice

Pipeline:
Mic → VAD → Streaming STT → Cloud LLM → Streaming TTS → Speaker
                                     ↘ Lip-sync → Avatar

Requirements:
- provider adapters;
- streaming;
- barge-in;
- low perceived latency;
- non-blocking UI;
- measurable latency;
- natural Vietnamese support.

Do not lock architecture to one provider.
