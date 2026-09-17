# CHAOS — AI Desktop Agent Specification

Đây là bộ tài liệu baseline để giao cho Coding Agent.

## Đọc gì trước?
- `AGENTS.md`: luật bắt buộc.
- `CHAOS_STATE.md`: bộ nhớ tiến độ.
- `STARTUP_INSTRUCTIONS.md`: cách giao việc.
- `docs/spec/`: đặc tả kỹ thuật.
- `PROJECT_CHECKLIST.md`: checklist.
- `DO_NOT_DO.md`: các lỗi kiến trúc/hành vi cần tránh.
- `CODING_AGENT_PROMPT.md`: prompt tổng hợp.

## Cách vận hành

Phiên 1:
AGENTS → STATE → full relevant spec → inspect repo → report → code milestone được giao.

Phiên sau:
AGENTS → STATE → Git status/diff → relevant spec → continue.

`CHAOS_STATE.md` được cập nhật liên tục để agent không phải đọc lại toàn bộ plan/rule mỗi lần.

## Kiến trúc
Cloud AI = Brain.
Python runtime = Nervous System.
Tools = Hands.
STT = Ears.
TTS = Voice.
Avatar = Body.
Memory = Long-term memory.
Permission Firewall = Safety boundary.
Verifier = Reality check.

## Stack dự kiến
Python + PySide6 + SQLite/SQLAlchemy + Playwright + Cloud AI API.
Avatar: Electron + Three.js + VRM/VRMA.
Target: Ubuntu + Windows.

## Trạng thái
Package này là baseline/final handoff spec. Implementation vẫn phải được Coding Agent xây dựng theo milestone.

## Repository layout

```text
CHAOS/
├── AGENTS.md
├── CHAOS_STATE.md
├── README.md
├── docs/
│   ├── spec/
│   ├── agent/
│   └── decisions/
├── src/
├── tests/
├── scripts/
├── installer/
└── .github/
```

This package is a clean coding-agent handoff/specification package. The implementation directories (`src/`, `tests/`, etc.) are created in the actual CHAOS repository as development begins.
