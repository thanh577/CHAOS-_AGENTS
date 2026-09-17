# CHAOS_STATE.md — Persistent Working Memory

> Đây là bộ nhớ liên tục của Coding Agent.
> Mục đích: giúp phiên sau tiếp tục từ đúng trạng thái mà không phải đọc lại toàn bộ spec.
> Đây KHÔNG phải nguồn sự thật tuyệt đối. Nếu mâu thuẫn với code/spec/test, phải xác minh và sửa state.

## Current State

- **Status:** NOT_STARTED
- **Current Milestone:** 0 — Foundation
- **Current Task:** Chưa bắt đầu
- **Last Completed Task:** Chưa có
- **Blocked By:** Không
- **Next Action:** Inspect repository → xác nhận baseline → bắt đầu T0.1 theo `TASKS.md`
- **Last Updated:** Chưa bắt đầu

## Completed Tasks

- Chưa có.

## Changed Files

- Chưa có.

## Tests

- Chưa có.

## Verification

- Chưa có.

## Important Technical Decisions

- Cloud AI/API là Brain.
- Không ESP32.
- Không local LLM.
- Python runtime là execution/control layer.
- API > CLI > Browser automation > GUI automation > Computer Use.
- LLM không được thực thi shell/filesystem trực tiếp.
- Mọi tool đi qua validation → permission → execution → verification.
- SQLite + SQLAlchemy ban đầu.
- Playwright cho browser automation.
- PySide6 cho desktop UI.
- Electron + Three.js + VRM/VRMA cho avatar runtime.
- STT/TTS dùng provider adapters và streaming.
- Personality: “Hỗn ở lớp giao tiếp, nghiêm túc ở lớp kiến thức/làm việc.”

## Known Issues

- Chưa có implementation baseline.
- Chưa xác nhận toolchain/dependencies của repository thực tế.

## Do Not Repeat

- Không đọc lại toàn bộ spec ở mỗi phiên nếu `CHAOS_STATE.md` đã có trạng thái đáng tin cậy.
- Không nhảy sang milestone kế tiếp.
- Không cho LLM chạy raw shell/filesystem command.
- Không ghi secret vào state/log/code.
- Không đánh dấu Done nếu chưa test + verify.

## Spec References Used

- Chưa có.

## Last Session Summary

Chưa có phiên coding.

---

# Session Log

> Sau mỗi phiên, thêm một entry ngắn. Không paste log terminal dài.

## YYYY-MM-DD HH:MM
- Session: Chưa bắt đầu
- Completed:
- Changed:
- Tests:
- Decisions:
- Blockers:
- Next:
