# CHAOS_STATE.md — Persistent Working Memory

> Đây là bộ nhớ liên tục của Coding Agent.
> Mục đích: giúp phiên sau tiếp tục từ đúng trạng thái mà không phải đọc lại toàn bộ spec.
> Đây KHÔNG phải nguồn sự thật tuyệt đối. Nếu mâu thuẫn với code/spec/test, phải xác minh và sửa state.

## Current State

- **Status:** IN_PROGRESS (Milestone 0)
- **Current Milestone:** 0 — Foundation
- **Current Task:** T0.5 gap-audit DONE — Milestone 0 COMPLETE (chờ lệnh milestone tiếp theo)
- **Last Completed Task:** T0.5 gap verification — Application Runtime Orchestration Foundation
- **Blocked By:** Không
- **Next Action:** Chờ lệnh milestone tiếp theo. Không tự chuyển milestone. Không T0.6/M1+.
- **Last Updated:** 2026-09-17 (T0.5 gap-audit complete)

## Completed Tasks

- **T0.1 — Repository & Git Foundation (2026-09-17, commit 98fd45c):**
  - Git init (branch `main`), root-commit baseline.
  - `.gitignore` (Python/uv/build/secrets/IDE/Node/SQLite/logs), `.env.example` (placeholder only), `.python-version` (3.12).
  - `pyproject.toml`: package `chaos` (src layout, requires-python >=3.12), dev group `pytest>=8`, ruff config, pytest testpaths.
  - `src/chaos/`: `__init__.py` (v0.0.1), `main.py` (entry `chaos`, returns 0), 9 subpackages `__init__.py` docstring-only theo `REPOSITORY.md`.
  - `tests/test_foundation.py`: 3 tests pass. `.github/workflows/ci.yml`, `scripts/.gitkeep`, `installer/windows/.gitkeep`, `uv.lock` (committed).
  - AC: git repo ✓, ignore/secrets ✓, python pinned ✓, uv toolchain ✓, package importable ✓, baseline tests ✓, commit ✓, no out-of-scope deps ✓.
  - Ghi nhận: `TASKS.md` chưa định nghĩa T0.x chi tiết — AC của T0.1 do agent lập từ Foundation requirements (đã báo trong T0.1 report).

- **T0.2 — Core Foundation Contracts (2026-09-17):**
  - 7 contracts theo `CONTRACTS.md`: `AIProvider` (+Role/AIRequest/AIResponse/AIStreamChunk/ToolSpec),
    `Tool` (+ToolResult), `MemoryStore` (+MemoryRecord/MemoryQuery), `PermissionEngine`
    (+PermissionRequest/PermissionDecision/PermissionVerdict), `Verifier`
    (+VerificationExpectation/VerificationResult/VerificationVerdict),
    `STTProvider`, `TTSProvider` (+AudioFormat/TranscriptChunk/Transcription/SpeechRequest/SpeechChunk).
  - Shared kernel `ha_tang/contracts/`: `ErrorCode` + `ChaosError` hierarchy (7 loại),
    `PermissionClass` (SAFE/CONFIRM/BLOCK), `ToolCall`, `Event`.
  - Layout theo `REPOSITORY.md` (contracts/ trong từng subpackage hiện có); voice đặt trong
    `bo_nao/contracts/` theo precedent AIProvider (reversible, xem report).
  - Stdlib only (`dataclasses`, `abc`, `enum`, `collections.abc`, `uuid`, `datetime`) — 0 dependency mới.
  - 47 tests contract mới (tổng 50 pass); ruff check + format pass; boundary tests chứng minh
    stdlib-only, no network/shell/fs, Tool không chạm PermissionEngine, AI/voice không vendor-lock.
  - AC T0.2: 17/17 đạt (xem T0.2 report). Không implementation thật, không vượt scope M0.

- **T0.3 — Configuration & Application Bootstrap (2026-09-17):**
  - `cau_hinh/`: `Secret` (repr/str redacted, chỉ `expose()`), 6 nhóm settings frozen
    (App/Logging/Runtime/AI-placeholder/Storage-location/Security), `ChaosSettings.from_env`
    đọc `CHAOS_*` từ mapping truyền vào hoặc process env — không đọc `.env`, không dotenv.
    Validation bằng `ConfigurationError`: env/level/bool/timeout(0< t <=600)/data_dir/debug-vs-prod;
    production yêu cầu AI credentials (message chỉ nêu tên biến, không echo giá trị).
  - `ha_tang/`: `Runtime` (CREATED→INITIALIZED→RUNNING→STOPPING→STOPPED + history, sai thứ tự
    raise `ValidationError`), `ApplicationContext` + `Application` (DI rõ ràng, không singleton),
    `configure_logging`/`safe_summary` (stdlib, deterministic, secrets excluded).
  - `main.py`: load config → banner CLI → `create_application().run()` → exit code
    (0 ok, 2 config error ra stderr); CI-safe không cần API key.
  - `.env.example` cập nhật đúng tên biến loader (commented placeholders).
  - 30 tests mới (tổng 80 pass); ruff + format pass; boundary tests chứng minh stdlib-only,
    no network/shell/fs/dotenv, no secret literals. 0 dependency mới.
  - AC T0.3: 26/26 đạt (xem T0.3 report). Không AI/executor/DB/GUI/voice/avatar, không vượt scope M0.

- **T0.4 — Logging, Error Model & Observability Foundation (2026-09-17):**
  - Review code T0.2/T0.3 trước khi làm: khớp report, không mâu thuẫn spec — error model đã đủ
    7 categories nên chỉ thêm additive `ChaosError.to_dict()` (không rename, không phá contract).
  - Mới `ha_tang/redaction.py` (stdlib, zero-chaos-import để kernel dùng không cycle):
    `redact`/`redact_mapping`/`redact_text` (keys + Bearer/Basic + key=value, recurse dict/list/tuple,
    Secret nhận diện duck-typing), `format_error` (`[code] message` đã redact),
    `error_details` (bản sao details đã redact).
  - Mới `ha_tang/context.py`: `TraceContext` frozen (correlation/session/task/tool_run ids) +
    `use_context`/`get_context`/`clear_context` trên `contextvars` (async-safe, nesting, missing→None).
  - `ha_tang/logging.py` mở rộng tương thích ngược: `LOG_FORMAT`/`STRUCTURED_FIELDS` constants,
    `resolve_level` (tên/số, sai → `ConfigurationError`), `log_event` (redact payload + gắn ids
    từ context hiện tại, message shape cố định). `Event` thêm `safe_payload()` +
    `EVENT_NAME_RE`/`is_conventional_name` (convention `tool.execution.started`, không bus implementation).
  - 37 tests mới (tổng 117 pass); ruff + format pass; `uv run chaos` exit 0. 0 dependency mới.
  - AC T0.4: 20/20 đạt (xem T0.4 report). Không subsystem cấm, không vượt scope M0.

- **T0.5 — Application Runtime Orchestration Foundation (2026-09-17):**
  - LƯU Ý LỆNH: order T0.5 bị cắt ngang giữa mục 6 + không nhận được trả lời làm rõ —
    chỉ triển khai các mục 1–5 đã nhận đầy đủ + quy trình chuẩn T0.1–T0.4; phần suy luận ghi rõ ở đây.
  - `ha_tang/runtime.py`: `Service` ABC (name + startup/shutdown no-op) làm empty hook;
    `Runtime(services=())` tương thích ngược; hooks chạy TRƯỚC khi ghi transition
    (startup fail → vẫn CREATED, teardown fail → vẫn RUNNING, exception gốc propagate).
    `stop()` idempotent từ STOPPED; `shutdown()` từ INITIALIZED (không giả RUNNING) /
    RUNNING / STOPPED (no-op); cấm restart từ STOPPED; không thêm state FAILED.
  - `ha_tang/application.py`: `ApplicationContext` frozen + thêm field `logger`
    (settings/runtime/logger — không god object); `Application.run()` log lỗi an toàn
    (`format_error`) rồi re-raise giữ classification; thêm `Application.shutdown()` public.
  - 19 tests mới (tổng 136 pass); ruff + format pass; `uv run chaos` exit 0. 0 dependency mới.
  - Không AI/executor/DB/GUI/voice/avatar, không execution loop, không vượt scope M0.

- **T0.5 gap-audit — Completion Gap Verification (2026-09-17, sau commit a38b6d2, KHÔNG rollback):**
  - VERIFIED EXISTING (code/test evidence, không suy luận): initialize/start/stop/shutdown failure
    semantics ở runtime level; ownership Application→Runtime→Services; context isolation T0.4
    nguyên vẹn; lifecycle deterministic/history/no-restart/idempotency; run() happy-path +
    init-failure path; boundaries stdlib-only; T0.1–T0.4 xanh.
  - IMPLEMENTED DURING GAP AUDIT (3 gaps thật, minimal additive, không refactor style):
    1. run() start-failure và stop-failure có behavior nhưng 0 test evidence → thêm 2 tests
       (state INITIALIZED/RUNNING, classification giữ, event + correlation).
    2. run() chỉ log free-text, không phát lifecycle event có cấu trúc → chuyển sang `log_event`
       (`application.started/stopped/start.failed/stop.failed`) + per-run `TraceContext`.
       Cố tình KHÔNG phát created/initialized/stopping riêng (trùng history, tránh noise).
    3. BUG THẬT do audit phát hiện: `_is_sensitive_key` substring-match nuốt cả flag
       `ai_api_key_present`/`mask_secrets_in_logs` (boolean → `***`, phá hợp đồng safe_summary)
       → đổi sang exact/endswith stems + regression test (`*_present`, `token_count`,
       `secretary`, `auth`-block an toàn; `x-api-key`/`my_token` vẫn redact).
  - Sau audit: 140 tests pass; ruff + format pass; `uv run chaos` env sạch exit 0
    (events có cùng correlation_id). 0 dependency mới. Không T0.6/M1+.

## Changed Files

- T0.1 (commit 98fd45c, 41 files): `.gitignore`, `.env.example`, `.python-version`, `pyproject.toml`, `uv.lock`,
  `src/chaos/__init__.py`, `src/chaos/main.py`, 9× `src/chaos/<subpkg>/__init__.py`,
  `tests/test_foundation.py`, `.github/workflows/ci.yml`, `scripts/.gitkeep`, `installer/windows/.gitkeep`
  (+ toàn bộ spec/docs có sẵn được đưa vào root-commit baseline).
- T0.2: 6× `src/chaos/*/contracts/__init__.py` + 10 contract modules
  (`ha_tang`: errors/common/events; `bo_nao`: ai_provider/stt_provider/tts_provider;
  `cong_cu`: tool; `tri_nho`: memory_store; `bao_mat`: permission_engine; `kiem_tra`: verifier)
  + 8 test files (`test_contract_kernel/tool/ai_provider/memory/permission/verifier/voice/boundaries`).
- T0.3: `src/chaos/cau_hinh/{secrets,settings}.py` (mới) + `__init__.py` (re-export),
  `src/chaos/ha_tang/{runtime,logging,application}.py` (mới), `src/chaos/main.py` (bootstrap),
  `.env.example` (tên biến khớp loader), 3 test files (`test_config/bootstrap/bootstrap_boundaries`).
- T0.4: `src/chaos/ha_tang/{redaction,context}.py` (mới), `logging.py` (structured helpers),
  `contracts/{errors.py: +to_dict, events.py: +safe_payload/naming, __init__.py: re-export}`,
  6 test files (`test_error_model/redaction/trace_context/structured_logging/events_foundation/observability_boundaries`).
- T0.5: `src/chaos/ha_tang/{runtime,application}.py` (sửa: Service hooks, shutdown, frozen context,
  failure classification) + `tests/test_runtime_orchestrator.py` (mới, 19 tests).
- T0.5 gap-audit: `src/chaos/ha_tang/{application.py (log_event + per-run context), redaction.py
  (exact/endswith key match)}` + bổ sung `tests/test_runtime_orchestrator.py` (3 failure/event tests)
  và `tests/test_redaction.py` (1 precision regression test).

## Tests

- T0.1: `uv run pytest -q` → **3 passed** (`tests/test_foundation.py`: version, 9 subpackages importable, main returns 0).
- T0.2: `uv run pytest -q` → **50 passed** (3 foundation + 47 contract mới).
  Kernel (error codes/model, permission classes, ToolCall, Event) · Tool (shape, Result invariants,
  async surface, AST no-bypass) · AIProvider (DTOs, fake complete/stream, vendor-lock scan) ·
  Memory (CRUD double) · Permission (3 verdicts, CONFIRM prompt invariant) ·
  Verifier (3 states round-trip) · Voice (STT/TTS + streaming doubles, SDK scan) ·
  Boundaries (AST stdlib-only imports, regex no network/shell/fs).
- Lint/format: `uvx ruff check` → pass (12 lỗi auto-fix ban đầu: `typing.Mapping`→`collections.abc`,
  `__all__` sort, `datetime.UTC`, import sort); `uvx ruff format --check` → pass.
- Import/entry: `uv run python -c "import chaos"` → 0.0.1; `uv run chaos` → banner + exit 0.
- T0.3: `uv run pytest -q` → **80 passed** (50 cũ + 30 mới: config defaults/override/validation/
  production-required/redaction; bootstrap wiring/lifecycle/entrypoint; boundaries stdlib-only +
  no network/shell/fs/dotenv + no secret literals).
- Lint/format T0.3: `uvx ruff check` → pass (1 lỗi auto-fix: `__all__` sort);
  `uvx ruff format --check` → 44 files pass.
- T0.4: `uv run pytest -q` → **117 passed** (80 cũ + 37 mới: error codes/model/safe-format;
  redaction keys/bearer/nesting/holders; context set/nested/async-isolation; logging levels/events;
  event envelope/naming/safe-payload; boundaries stdlib-only + no forbidden subsystems).
- Lint/format T0.4: `uvx ruff check .` → pass (3 lỗi: 2 auto-fix `__all__` sort + `datetime.UTC`,
  1 sửa tay B017 blind-Exception → `FrozenInstanceError`); `uvx ruff format --check .` → pass
  (1 file reformat `__all__` multi-line); `uv run chaos` → exit 0.
- Trong lúc test phát hiện và sửa 3 kỳ vọng sai phía test (không phải lỗi implementation):
  bare string không key-context không thể phân loại; `LogRecord.args` unwrap dict đơn.
- T0.5: `uv run pytest -q` → **136 passed** (117 cũ giữ xanh + 19 mới: hook order/failure,
  shutdown paths, idempotency, no-restart, invalid transitions, frozen context, run failure classification).
- Lint/format T0.5: `uvx ruff check .` → pass ngay lần đầu; `uvx ruff format --check .` → 74 files pass;
  `uv run chaos` → exit 0 (không đổi behavior entrypoint).
- T0.5 gap-audit: `uv run pytest -q` → **140 passed** (136 cũ + 4 mới); `uvx ruff check .` → pass;
  `uvx ruff format --check .` → pass (1 file reformat); `uv run chaos` env sạch → exit 0.

## Verification

- T0.1: `git log` → root-commit 98fd45c trên `main`; `git status` sau commit → clean (ngoại trừ `CHAOS_STATE.md` update này, sẽ commit ở task tiếp theo hoặc khi có lệnh).
- Secret scan (rg patterns trên `.env.example`, `pyproject.toml`, `src`, `tests`, `.github`, `scripts`): chỉ match placeholder comment và docstring — không có secret thật; không tồn tại `.env`.
- Cấu trúc `find src tests scripts installer .github` khớp layout M0 yêu cầu.
- T0.2: `git status` trước commit → chỉ file mới T0.2 (tracked files untouched, `pyproject.toml`/`uv.lock`
  không đổi → 0 dependency mới); secret scan (key/token/private-key/password patterns trên
  src/tests/pyproject/env-example) → 0 match; `.env` không tồn tại.
- T0.3: diff review → 3 files sửa (`main.py` bootstrap, `cau_hinh/__init__.py` re-export,
  `.env.example` tên biến) + 8 files mới; `pyproject.toml`/`uv.lock` untouched → 0 dep mới;
  secret scan → 0 match; forbidden-dep scan (pydantic/dotenv/SDK/…) → 0 match; `.env` không tồn tại.
- T0.4: diff review → 4 files sửa (additive, không phá T0.1–T0.3) + 8 files mới;
  `pyproject.toml`/`uv.lock` untouched → 0 dep mới; secret scan → 0 match;
  forbidden-subsystem scan (sdk/db/ui/network/…) → 0 match; `.env` không tồn tại.
- T0.5: diff review → 2 files sửa + 1 test mới (không phá T0.1–T0.4: `Runtime()` không args
  và `run()` history giữ nguyên shape); `pyproject.toml`/`uv.lock` untouched → 0 dep mới;
  secret scan → 0 match; forbidden-dep scan → 0 match; `.env` không tồn tại.
- T0.5 gap-audit: diff review → 2 files sửa + 2 test files bổ sung (không phá T0.1–T0.5);
  `pyproject.toml`/`uv.lock` untouched → dependency delta 0; secret scan → 0 match;
  forbidden-subsystem scan (sdk/db/ui/network/sqlite/…) → 0 match; `.env` không tồn tại.

## Important Technical Decisions

- Python **3.12** (system 3.12.3): tương thích stack dự kiến (PySide6/SQLAlchemy/Playwright) và được `uv` resolve thành công.
- Toolchain chính: **uv** (sync + venv + run + pytest), không dùng poetry/pipenv. `uv.lock` được **commit** (app, cần reproducible build).
- `pyproject.toml` build-backend **hatchling**, src-layout, entry `chaos = chaos.main:main`.
- Dependency T0.1: chỉ **pytest>=8 (dev)**. Từ chối theo policy: PySide6, SQLAlchemy, Playwright, Typer, PyInstaller, AI SDK, Electron — chờ milestone cần chúng.
- Subpackage `__init__.py` là docstring-only, ghi rõ milestone tương lai — không implementation giả.
- Git author tạm `CHAOS Agent <chaos-agent@local>` cho baseline commit (chưa có user git config); user nên set `git config user.name/email` thật trước commit tiếp theo.
- CI `.github/workflows/ci.yml`: setup-python từ `.python-version` + `uv sync --group dev` + `pytest -q`.
- T0.2: shared kernel (`PermissionClass`, `ToolCall`, errors, `Event`) đặt trong `ha_tang/contracts/`
  để tránh coupling `cong_cu`↔`bao_mat` và tránh package top-level mới ngoài `REPOSITORY.md` (reversible).
- T0.2: voice contracts (`STT/TTSProvider`, `AudioFormat`) đặt trong `bo_nao/contracts/` theo precedent
  AIProvider (external provider boundary của brain); `giao_dien` để dành cho UI M9 (reversible).
- T0.2: `AudioFormat` định nghĩa trong `stt_provider.py`, `tts_provider.py` import lại (cùng package, không cycle).
- T0.2: schema dùng `Mapping` hình JSON-schema (không pydantic, theo dependency policy).
  Async surface test bằng `asyncio.run` + `inspect.iscoroutinefunction/isasyncgenfunction` (không pytest-asyncio).
- T0.2: `ToolResult(ok=True)` cấm error / `(ok=False)` bắt buộc error; `PermissionDecision(CONFIRM)`
  bắt buộc `confirmation_prompt` — ép bằng `__post_init__` + test.
- T0.2: tên lỗi tránh shadow builtin — `PermissionDeniedError` (không `PermissionError`),
  `OperationTimeoutError` (không `TimeoutError`).
- T0.3: bootstrap/context/runtime/logging đặt trong `ha_tang/` (infrastructure) để giữ layout
  `REPOSITORY.md` (không package top-level mới); `cau_hinh/` giữ config (reversible).
- T0.3: blank env var = unset (fallback default) cho mọi biến; production-gate yêu cầu AI credentials.
- T0.3: `main()` không parse CLI args (không Typer theo policy); testability qua explicit mapping + monkeypatch env.
- T0.3: `configure_logging` first-call-wins (deterministic); chỉ `safe_summary` (booleans, không values) được log.
- T0.4: redaction zero-chaos-import (tránh cycle contracts↔cau_hinh); Secret nhận diện duck-typing qua `expose`.
- T0.4: `Event` giữ nguyên fields (correlation_id + payload đã đủ theo spec §7) — chỉ thêm helper,
  không đổi contract; lazy import redaction trong `safe_payload` để kernel import nhẹ.
- T0.4: `log_event` nhận `str|int` level và validate qua `resolve_level`; `logger.log(n, "%s", fields)`
  (lưu ý stdlib unwrap dict-arg đơn vào `record.args` — test đọc đúng chỗ).
- T0.5: hooks-before-record (fail không để lại state mơ hồ); `Service` zero-default, sync,
  stdlib-only; context frozen nhưng `Runtime` mutable có chủ đích (state machine);
  suy luận phần lệnh thiếu: failure → safe-log + re-raise (không nuốt lỗi, đúng AGENTS.md).
- T0.5 gap-audit: per-run `TraceContext` trong `run()` (reset khi exit, isolation giữ nguyên);
  `log_event` tái dùng thay vì log text mới; redaction exact/endswith (bare `auth` cố tình
  không phải stem để block có cấu trúc được recurse); không tạo recovery/retry framework.

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
- T0.2 không phát hiện mâu thuẫn spec: `CONTRACTS.md`/`ARCHITECTURE.md` đủ rõ để định nghĩa shape;
  các điểm thiếu (subtask breakdown, policy tables, bus semantics) thuộc milestone sau, đã ghi nhận không làm sớm.

## Do Not Repeat

- Không đọc lại toàn bộ spec ở mỗi phiên nếu `CHAOS_STATE.md` đã có trạng thái đáng tin cậy.
- Không nhảy sang milestone kế tiếp.
- Không cho LLM chạy raw shell/filesystem command.
- Không ghi secret vào state/log/code.
- Không đánh dấu Done nếu chưa test + verify.

## Spec References Used

- T0.4: `AGENTS.md`, `README.md`, `docs/README.md`, `docs/spec/ARCHITECTURE.md`, `docs/spec/CONTRACTS.md`,
  `docs/spec/SECURITY.md`, `docs/spec/TESTING.md`, `docs/spec/DEFINITION_OF_DONE.md`, `docs/spec/AGENT_RULES.md`
  (+ nền T0.1–T0.3 giữ nguyên).
- T0.3: `AGENTS.md`, `docs/spec/REPOSITORY.md`, `docs/spec/ARCHITECTURE.md`, `docs/spec/SECURITY.md`
  (+ nền T0.1/T0.2 giữ nguyên).
- T0.2: `AGENTS.md`, `docs/spec/CONTRACTS.md`, `docs/spec/ARCHITECTURE.md`, `docs/spec/REPOSITORY.md`
  (+ nền T0.1 giữ nguyên).
- T0.1: `AGENTS.md`, `docs/spec/TASKS.md`, `docs/spec/REPOSITORY.md`, `docs/spec/ARCHITECTURE.md`,
  `docs/spec/SECURITY.md`, `docs/spec/TESTING.md`, `docs/spec/DEFINITION_OF_DONE.md`,
  `docs/spec/AGENT_RULES.md`, `docs/agent/PROJECT_CHECKLIST.md`, `docs/agent/STARTUP_INSTRUCTIONS.md`, `README.md`.

## Last Session Summary

2026-09-17 — Startup baseline report (NOT_STARTED, M0) + triển khai T0.1 hoàn tất: repo sạch spec-only →
git + foundation + 3 tests pass + baseline commit 98fd45c. Không drift kiến trúc, không secret, không vượt scope M0.
2026-09-17 — T0.2 hoàn tất: 7 contracts + shared kernel (errors/events/common), stdlib-only, 50 tests pass,
ruff/format pass, 0 dep mới. AC 17/17. Dừng ở M0, chờ lệnh T0.3.
2026-09-17 — T0.3 hoàn tất: config layer + bootstrap + runtime skeleton + logging, 80 tests pass,
ruff/format pass, 0 dep mới. AC 26/26. Dừng ở M0, chờ lệnh T0.4.
2026-09-17 — T0.4 hoàn tất: redaction + trace context + structured logging + event helpers,
error model chỉ thêm additive `to_dict`, 117 tests pass, ruff/format pass, 0 dep mới.
AC 20/20. Dừng ở M0, chờ lệnh T0.5.
2026-09-17 — T0.5 hoàn tất (lệnh bị cắt ngang, làm theo mục 1–5 + quy trình chuẩn):
Service hooks + shutdown/idempotency/no-restart + frozen context + failure classification,
136 tests pass, ruff/format pass, 0 dep mới. Milestone 0 xong phần orchestration.
2026-09-17 — T0.5 gap-audit hoàn tất (không rollback a38b6d2): VERIFIED phần lớn yêu cầu;
IMPLEMENTED 3 gaps (failure-path tests, lifecycle events + per-run context, redaction precision bug);
140 tests pass, ruff/format pass, dep delta 0, chaos exit 0. DoD 21/21 có evidence.

---

# Session Log

> Sau mỗi phiên, thêm một entry ngắn. Không paste log terminal dài.

## 2026-09-17 T0.5 gap-audit
- Session: M0 T0.5 Completion Gap Verification (sau a38b6d2, không rollback)
- Completed: audit failure/ownership/logging/events/context/boundary; 3 gaps implemented (2 failure-path tests + structured lifecycle events + redaction precision fix); 140 tests pass
- Changed: 2 src sửa + 2 test bổ sung (xem Changed Files); pyproject/uv.lock không đổi
- Tests: pytest 140 passed; ruff + format pass; chaos env sạch exit 0
- Decisions: VERIFIED vs IMPLEMENTED phân biệt rõ; không phát event cho mọi transition; bare auth không phải stem
- Blockers: không — DoD 21/21 có evidence
- Next: chờ lệnh milestone tiếp theo; KHÔNG T0.6/M1+

## 2026-09-17 T0.5
- Session: Milestone 0 — T0.5 Application Runtime Orchestration Foundation
- Completed: T0.5 (Service ABC + hooks-before-record, shutdown/idempotent-stop/no-restart, frozen context + logger, run failure classification; 19 tests, 136 pass, ruff/format pass, chaos exit 0)
- Changed: 2 sửa + 1 test mới (xem Changed Files); pyproject/uv.lock không đổi
- Tests: pytest 136 passed (117 cũ giữ xanh, history shape run() không đổi)
- Decisions: hooks-before-record, shutdown từ INITIALIZED bỏ qua RUNNING, stop/shutdown idempotent từ STOPPED, context frozen + Runtime mutable có chủ đích
- Blockers: lệnh T0.5 bị cắt ngang mục 6 và không có trả lời làm rõ — đã scope-lock theo mục 1–5, cần user xác nhận khi review
- Next: chờ lệnh milestone tiếp theo; không tự chuyển milestone

## 2026-09-17 T0.4
- Session: Milestone 0 — T0.4 Logging, Error Model & Observability Foundation
- Completed: T0.4 (redaction, TraceContext, log_event/resolve_level, Event safe_payload+naming, to_dict; 6 test files, 117 tests pass, ruff/format pass, chaos exit 0)
- Changed: 4 sửa (additive) + 8 mới (xem Changed Files); pyproject/uv.lock không đổi
- Tests: pytest 117 passed (80 cũ giữ xanh); 3 kỳ vọng sai phía test đã sửa, implementation không lỗi
- Decisions: redaction zero-import + duck-typing Secret, Event không thêm field, log_event str|int level, đọc record.args đúng semantics stdlib
- Blockers: không
- Next: chờ lệnh T0.5; không tự chuyển task/milestone

## 2026-09-17 T0.3
- Session: Milestone 0 — T0.3 Configuration & Application Bootstrap
- Completed: T0.3 (Secret+6 settings groups+from_env validation, Runtime lifecycle, Application DI, logging, main bootstrap, .env.example; 3 test files, 80 tests pass, ruff/format pass)
- Changed: 3 sửa + 8 mới (xem Changed Files); pyproject/uv.lock không đổi
- Tests: pytest 80 passed (1 case blank-data_dir sửa thiết kế: blank=unset); boundary tests mới
- Decisions: bootstrap/runtime/logging ở ha_tang, blank=unset, production-gate AI creds, main không CLI args, logging first-call-wins + safe_summary
- Blockers: không
- Next: chờ lệnh T0.4; không tự chuyển task/milestone

## 2026-09-17 T0.2
- Session: Milestone 0 — T0.2 Core Foundation Contracts
- Completed: T0.2 (7 contracts + kernel errors/events/common, 8 test files, 50 tests pass, ruff/format pass)
- Changed: 24 files mới (16 src contracts + 8 tests); pyproject/uv.lock không đổi
- Tests: pytest 50 passed; boundary tests (stdlib-only, no side-effect, no-bypass, no vendor-lock)
- Decisions: shared kernel ở ha_tang, voice ở bo_nao, AudioFormat trong stt_provider, Mapping thay pydantic, asyncio.run thay pytest-asyncio, invariant __post_init__, tên lỗi tránh shadow builtin
- Blockers: không
- Next: chờ lệnh T0.3; không tự chuyển task/milestone

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
