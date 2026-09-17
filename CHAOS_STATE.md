# CHAOS_STATE.md — Persistent Working Memory

> Đây là bộ nhớ liên tục của Coding Agent.
> Mục đích: giúp phiên sau tiếp tục từ đúng trạng thái mà không phải đọc lại toàn bộ spec.
> Đây KHÔNG phải nguồn sự thật tuyệt đối. Nếu mâu thuẫn với code/spec/test, phải xác minh và sửa state.

## Current State

- **Status:** IN_PROGRESS (Milestone 0)
- **Current Milestone:** 0 — Foundation
- **Current Task:** T0.1 DONE — T0.2 chưa được giao (waiting for command)
- **Last Completed Task:** T0.1 — Repository & Git Foundation (commit 98fd45c)
- **Blocked By:** Không
- **Next Action:** Chờ lệnh T0.2. Không tự chuyển milestone.
- **Last Updated:** 2026-09-17 (T0.1 complete)

## Completed Tasks

- **T0.1 — Repository & Git Foundation (2026-09-17, commit 98fd45c):**
  - Git init (branch `main`), root-commit baseline.
  - `.gitignore` (Python/uv/build/secrets/IDE/Node/SQLite/logs), `.env.example` (placeholder only), `.python-version` (3.12).
  - `pyproject.toml`: package `chaos` (src layout, requires-python >=3.12), dev group `pytest>=8`, ruff config, pytest testpaths.
  - `src/chaos/`: `__init__.py` (v0.0.1), `main.py` (entry `chaos`, returns 0), 9 subpackages `__init__.py` docstring-only theo `REPOSITORY.md`.
  - `tests/test_foundation.py`: 3 tests pass. `.github/workflows/ci.yml`, `scripts/.gitkeep`, `installer/windows/.gitkeep`, `uv.lock` (committed).
  - AC: git repo ✓, ignore/secrets ✓, python pinned ✓, uv toolchain ✓, package importable ✓, baseline tests ✓, commit ✓, no out-of-scope deps ✓.
  - Ghi nhận: `TASKS.md` chưa định nghĩa T0.x chi tiết — AC của T0.1 do agent lập từ Foundation requirements (đã báo trong T0.1 report).

## Changed Files

- T0.1 (commit 98fd45c, 41 files): `.gitignore`, `.env.example`, `.python-version`, `pyproject.toml`, `uv.lock`,
  `src/chaos/__init__.py`, `src/chaos/main.py`, 9× `src/chaos/<subpkg>/__init__.py`,
  `tests/test_foundation.py`, `.github/workflows/ci.yml`, `scripts/.gitkeep`, `installer/windows/.gitkeep`
  (+ toàn bộ spec/docs có sẵn được đưa vào root-commit baseline).

## Tests

- T0.1: `uv run pytest -q` → **3 passed** (`tests/test_foundation.py`: version, 9 subpackages importable, main returns 0).
- Lint/format: `uvx ruff check` → pass; `uvx ruff format --check` → 12 files formatted.
- Import/entry: `uv run python -c "import chaos"` → 0.0.1; `uv run chaos` → banner + exit 0.

## Verification

- T0.1: `git log` → root-commit 98fd45c trên `main`; `git status` sau commit → clean (ngoại trừ `CHAOS_STATE.md` update này, sẽ commit ở task tiếp theo hoặc khi có lệnh).
- Secret scan (rg patterns trên `.env.example`, `pyproject.toml`, `src`, `tests`, `.github`, `scripts`): chỉ match placeholder comment và docstring — không có secret thật; không tồn tại `.env`.
- Cấu trúc `find src tests scripts installer .github` khớp layout M0 yêu cầu.

## Important Technical Decisions

- Python **3.12** (system 3.12.3): tương thích stack dự kiến (PySide6/SQLAlchemy/Playwright) và được `uv` resolve thành công.
- Toolchain chính: **uv** (sync + venv + run + pytest), không dùng poetry/pipenv. `uv.lock` được **commit** (app, cần reproducible build).
- `pyproject.toml` build-backend **hatchling**, src-layout, entry `chaos = chaos.main:main`.
- Dependency T0.1: chỉ **pytest>=8 (dev)**. Từ chối theo policy: PySide6, SQLAlchemy, Playwright, Typer, PyInstaller, AI SDK, Electron — chờ milestone cần chúng.
- Subpackage `__init__.py` là docstring-only, ghi rõ milestone tương lai — không implementation giả.
- Git author tạm `CHAOS Agent <chaos-agent@local>` cho baseline commit (chưa có user git config); user nên set `git config user.name/email` thật trước commit tiếp theo.
- CI `.github/workflows/ci.yml`: setup-python từ `.python-version` + `uv sync --group dev` + `pytest -q`.

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

- `TASKS.md` chưa phân rã subtask/acceptance criteria cho M0 — T0.1 AC do agent lập, cần user xác nhận khi review.
- Git `user.name`/`user.email` chưa cấu hình thật (baseline commit dùng author tạm) — set trước commit tiếp theo.
- `.venv/` tồn tại local (đúng git-ignored) — phiên sau chạy `uv sync --group dev` lại nếu thiếu.
- Scope M1+ (AI provider, tool exec, browser, memory, voice, avatar, permission/verifier đầy đủ) cố tình chưa chạm — ghi nhận để không quên, không triển khai sớm.

## Do Not Repeat

- Không đọc lại toàn bộ spec ở mỗi phiên nếu `CHAOS_STATE.md` đã có trạng thái đáng tin cậy.
- Không nhảy sang milestone kế tiếp.
- Không cho LLM chạy raw shell/filesystem command.
- Không ghi secret vào state/log/code.
- Không đánh dấu Done nếu chưa test + verify.

## Spec References Used

- T0.1: `AGENTS.md`, `docs/spec/TASKS.md`, `docs/spec/REPOSITORY.md`, `docs/spec/ARCHITECTURE.md`,
  `docs/spec/SECURITY.md`, `docs/spec/TESTING.md`, `docs/spec/DEFINITION_OF_DONE.md`,
  `docs/spec/AGENT_RULES.md`, `docs/agent/PROJECT_CHECKLIST.md`, `docs/agent/STARTUP_INSTRUCTIONS.md`, `README.md`.

## Last Session Summary

2026-09-17 — Startup baseline report (NOT_STARTED, M0) + triển khai T0.1 hoàn tất: repo sạch spec-only →
git + foundation + 3 tests pass + baseline commit 98fd45c. Không drift kiến trúc, không secret, không vượt scope M0.

---

# Session Log

> Sau mỗi phiên, thêm một entry ngắn. Không paste log terminal dài.

## 2026-09-17 T0.1
- Session: Milestone 0 — T0.1 Repository & Git Foundation
- Completed: T0.1 (git, ignore, env template, python 3.12, uv+pyproject, src/chaos layout, 3 tests, CI, baseline commit 98fd45c)
- Changed: 41 files (xem Changed Files); state update này chưa commit
- Tests: pytest 3 passed; ruff check + format pass; import/entry verified; secret scan clean
- Decisions: uv toolchain, uv.lock committed, chỉ pytest dev-dep, docstring-only subpackages, hatchling src-layout
- Blockers: không (lưu ý git user config tạm)
- Next: chờ lệnh T0.2; không tự chuyển task/milestone

## YYYY-MM-DD HH:MM
- Session: Chưa bắt đầu
- Completed:
- Changed:
- Tests:
- Decisions:
- Blockers:
- Next:
