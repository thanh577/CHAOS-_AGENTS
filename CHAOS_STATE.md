# CHAOS_STATE.md — Persistent Working Memory

> Đây là bộ nhớ liên tục của Coding Agent.
> Mục đích: giúp phiên sau tiếp tục từ đúng trạng thái mà không phải đọc lại toàn bộ spec.
> Đây KHÔNG phải nguồn sự thật tuyệt đối. Nếu mâu thuẫn với code/spec/test, phải xác minh và sửa state.

## Current State

- **Status:** DONE (Milestone 3) — chờ lệnh milestone tiếp theo
- **Current Milestone:** 3 — Tool Framework (HOÀN THÀNH)
- **Current Task:** T3.3 DONE — Milestone 3 (Tool Framework) hoàn thành. Không tự sang M4.
- **Last Completed Task:** T3.3 — Boundary & Integration/DoD, chốt Milestone 3 (4 tests, 342 pass)
- **Blocked By:** Không
- **Next Action:** Chờ lệnh user cho Milestone 4 (Permission) hoặc push M3 lên GitHub qua bundle.
- **Last Updated:** 2026-09-17 (T3.3 complete — Milestone 3 DONE)

## Milestone 3 Plan — Tool Framework (ARCHITECTURE.md layer 5 "Tool Router", TASKS.md #3)

- **Scope:** `cong_cu/contracts/tool.py` (T0.2) đã khoá shape `Tool`/`ToolResult` và cấm module
  đó chạm `PermissionEngine`. M3 xây phần còn thiếu để một `ToolCall` thật sự chạy được:
  `ToolRouter` (không phải `Tool` contract — router là implementation, được phép biết khái
  niệm permission, chỉ không được có PermissionEngine THẬT vì M4 chưa tồn tại) thực hiện đúng
  core loop rút gọn của AGENTS.md (`validation → permission → executor`, verifier để dành M5):
  lookup tool theo tên → `tool.validate()` → permission placeholder bảo thủ (**chỉ tool
  `PermissionClass.SAFE` được tự chạy; `CONFIRM`/`BLOCK` bị từ chối thẳng bằng
  `PermissionDeniedError`** — không có cách nào bypass vì chưa có PermissionEngine thật; thay
  bằng policy thật ở M4 mà không đổi chữ ký `dispatch()`) → `tool.execute()` có timeout
  (`tool.timeout_seconds`, dùng `asyncio.wait_for`). `ToolRouter.dispatch()` KHÔNG BAO GIỜ
  raise — mọi nhánh lỗi (tool lạ, validate fail, permission fail, timeout, exception lạ từ
  tool) đều map về `ToolResult(ok=False, error=...)` (đúng tinh thần "Tool result should be
  standardized and machine-readable" của CONTRACTS.md — khác Brain M1 vốn raise vì Brain không
  có khái niệm Result). Registry là `Mapping[str, Tool]` phẳng, không class riêng (giữ tối
  giản, đúng precedent Brain M1 dùng dict thẳng cho provider).
- **Publish audit event qua EventBus (M2)** — đây chính là "event producer thật" mà M2 để dành:
  `tool.execution.started` / `.finished` / `.denied` / `.failed`, payload redact (không log
  raw arguments/data — đúng AGENTS.md §11 "raw tool arguments" không được log). `EventBus` và
  audit sink là optional (constructor param `event_bus: EventBus | None = None`) — router vẫn
  chạy được không có bus, đúng kiểu DI tường minh đã dùng xuyên suốt project.
- **T3.1 — ToolRouter core** (`cong_cu/router.py`): dispatch() như trên, không EventBus.
- **T3.2 — Audit events cho tool execution**: thêm publish qua `EventBus` (optional) vào
  `ToolRouter`, payload redact, verify qua `AuditEventSink` thật (tái dùng M2, không sửa).
- **T3.3 — Boundary & Integration/DoD:** boundary test (stdlib/chaos-only, không đụng
  `bao_mat` thật vì chưa tồn tại, không PermissionEngine literal ngoài tên biến/comment) + full
  verify + state + report.
- **Out of M3:** PermissionEngine thật (M4), Verifier thật (M5), tool cụ thể nào (browser M6,
  OS M7 mới có), agent loop tự động gọi router (M15), CONFIRM flow tương tác với user.

## Milestone 2 Plan — Event Bus (ARCHITECTURE.md layer 9, TASKS.md #2)

- **Scope:** `ha_tang/contracts/events.py` (T0.2/T0.4) đã định nghĩa envelope `Event` +
  `is_conventional_name`, docstring ghi rõ "Bus implementation, subscription, persistence
  and replay belong to later milestones" — M2 hiện thực đúng phần đó: in-process publish/
  subscribe (sync, stdlib-only), subscriber isolation (1 subscriber lỗi không phá subscriber
  khác/không phá publisher), và một sink nối Event Bus → `audit_events` repository đã có sẵn
  từ T0.6 (append-only, chưa ai ghi vào thực tế). KHÔNG async bus (foundation sync, theo
  precedent T0.6 MemoryStore-async-để-M8-quyết); KHÔNG wildcard prefix (`tool.*`) — chỉ exact
  match + wildcard toàn cục `"*"` (tối thiểu, reversible, mở rộng khi có consumer thật ở M3+
  cần). KHÔNG wire EventBus vào `ApplicationContext`/thay thế `log_event` trong
  `application.py` (giữ độc lập như Brain ở M1 — wiring thật để dành milestone cần dùng nó,
  ví dụ Tool Framework M3 hoặc Permission M4 phát sự kiện thật).
- **T2.1 — EventBus core** (`ha_tang/event_bus.py`): `subscribe(event_type_or_"*", subscriber)`
  trả `Subscription` token để `unsubscribe` (idempotent, không raise nếu gọi lại/token lạ);
  `publish(event)` validate `event.event_type` qua `is_conventional_name` (raise
  `ValidationError` nếu sai convention) rồi gọi các subscriber khớp (exact + `"*"`) theo đúng
  thứ tự đăng ký, snapshot danh sách subscriber trước khi gọi (an toàn nếu subscriber tự
  subscribe/unsubscribe trong lúc được gọi); subscriber ném lỗi → bắt, log qua `log_event`
  (ERROR, kèm event_type/source, không nuốt lỗi — có log, không phải `except: pass`), tiếp
  tục các subscriber còn lại, `publish()` không bao giờ raise vì lỗi subscriber. Một
  `threading.Lock` bảo vệ thao tác đọc/ghi danh sách subscriber (không cam kết concurrent
  publish ordering, chỉ tránh "mutate during iterate").
- **T2.2 — Audit persistence sink** (`ha_tang/event_sinks.py`): `AuditEventSink` bọc
  `Repository[AuditEvent]` (từ `repositories(db)["audit_events"]` đã có sẵn), khả dụng trực
  tiếp như một subscriber (`__call__(event)`); map `Event` → `AuditEvent` qua
  `event.safe_payload()` (redact trước khi persist — không bao giờ lưu secret thô, dùng lại
  `redact_mapping` đã có từ T0.4). Không đổi model/repository/schema hiện có.
- **T2.3 — Boundary & Integration/DoD:** `test_event_bus_boundaries.py` (theo đúng mẫu
  `test_brain_boundaries.py`: stdlib/chaos-only imports, không đụng `bao_mat`/`cong_cu`, không
  secret-shaped literal) cho cả `event_bus.py` + `event_sinks.py`; full suite + ruff +
  `uv run chaos` + state + report.
- **Out of M2:** wire EventBus vào Application/Runtime Service thật, wildcard prefix
  subscription, async subscriber, event replay API mới (list() của repository đã đủ dùng
  tạm), cross-process bus, persistence backend khác ngoài SQLite hiện có.

## Milestone 1 Plan — Cloud Brain (AGENTS.md §12)

- **Scope:** adapter/interface + config + streaming + timeout/retry/backoff + rate-limit +
  structured tool calls + context budget + graceful failure. Model không quyết permission
  (Brain chỉ trả tool calls dạng DATA — execution thuộc M3+, loop thuộc M15).
- **Không khóa vendor:** registry name→AIProvider + 1 reference adapter nói wire protocol mở
  (OpenAI-compatible chat-completions qua stdlib HTTP, không SDK) — dùng được với mọi endpoint
  tương thích, không chỉ OpenAI.
- **T1.1 — Brain configuration:** mở rộng `AISettings` (`max_retries`, `retry_backoff_seconds`,
  `max_context_tokens`) + env `CHAOS_AI_MAX_RETRIES/_RETRY_BACKOFF/_MAX_CONTEXT_TOKENS` +
  validation + tests. 0 dep mới.
- **T1.2 — HTTP transport:** sync core `http.client` + async wrapper (`asyncio.to_thread`,
  không aiohttp/httpx) trong `bo_nao/http_transport.py`: timeout (socket-level, không thread-leak),
  retry bounded (429 honor Retry-After capped + 5xx/connection-error; không retry 4xx),
  backoff hàm mũ, map lỗi → ProviderError/OperationTimeoutError, chỉ log status (không log body).
  Tests dùng fake `http.server` local (không network ngoài).
- **T1.3 — Reference adapter** (`bo_nao/openai_compat.py`): build JSON (model/messages/tools→
  functions/max_tokens/temperature/stream), parse response + tool_calls (arguments JSON hỏng →
  ValidationError), SSE parse (batch-read + async-yield deltas, incremental-network deferred —
  documented), usage passthrough, Bearer auth (expose tại send), endpoint http/https only.
- **T1.4 — Brain runtime** (`bo_nao/brain.py`): registry + chọn provider theo config (unknown →
  ConfigurationError), budget enforcement (estimate chars/4 heuristic, cắt messages cũ nhất giữ
  system, deterministic), single-turn orchestration, graceful failure (mọi lỗi → taxonomy CHAOS),
  log metadata-only (không log message content), boundary test (không import permission/executor).
- **T1.5 Integration/DoD:** full suite + scans + state + report. KHÔNG đưa Brain vào
  ApplicationContext (giữ independent như persistence pre-T0.7 — wire ở milestone sau).
- **Out of M1:** agent loop (M15), tool execution (M3), memory (M8), permission workflows (M4),
  vendor SDKs, adapter thứ hai, retry/recovery framework lớn.

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
- T0.6: `src/chaos/ha_tang/persistence/{__init__,models,repository,sqlite_store}.py` (mới) +
  4 test files (`test_persistence_models/sqlite/security/boundaries`). Không sửa tracked files.
- T0.6 compliance: `pyproject.toml` + `uv.lock` (SQLAlchemy), `sqlite_store.py` (Core backend +
  migrations), `test_persistence_{sqlite (text/mappings), boundaries (allow sqlalchemy Core-only),
  migrations (mới)}`. Models/ABC không đổi.
- T0.7: `src/chaos/ha_tang/{application.py (context+persistence wiring/startup-shutdown/events),
  logging.py (bỏ data_dir khỏi safe_summary), redaction.py (+scrub_known_secrets)}`,
  `tests/test_persistence_integration.py` (mới, 15 tests),
  `tests/test_{bootstrap, bootstrap_boundaries (pathlib-exempt application.py),
  runtime_orchestrator, redaction}` (adapt).
- T0.8: `src/chaos/ha_tang/persistence/{repository.py (ownership docs), sqlite_store.py
  (update timestamps, _convert_row mapping)}` (sửa) + `tests/test_persistence_hardening.py`
  (mới, 12 tests). Không sửa models/ABC-shape/backend-arch/migrations/app-integration.
- M1: `src/chaos/cau_hinh/settings.py` (AI knobs) + `.env.example` (3 vars) (sửa),
  `src/chaos/bo_nao/{http_transport,openai_compat,brain}.py` (mới),
  `tests/test_{brain_config,http_transport,openai_compat,brain,brain_boundaries}.py` (mới, 68 tests).
  `pyproject.toml`/`uv.lock` untouched.
- T2.1: `src/chaos/ha_tang/event_bus.py` (mới) + `tests/test_event_bus.py` (mới, 16 tests).
  Không sửa file nào khác; `pyproject.toml`/`uv.lock` untouched.
- T2.2: `src/chaos/ha_tang/event_sinks.py` (mới) + `tests/test_event_sinks.py` (mới, 7 tests).
  Không sửa models/repository/sqlite_store; `pyproject.toml`/`uv.lock` untouched.
- T2.3: `tests/test_event_bus_boundaries.py` (mới, 4 tests). Không sửa src nào.
- T3.1: `src/chaos/cong_cu/router.py` (mới) + `tests/test_tool_router.py` (mới, 11 tests).
  Không sửa `contracts/tool.py`/`common.py`/`errors.py`; `pyproject.toml`/`uv.lock` untouched.
- T3.2: `src/chaos/cong_cu/router.py` (sửa: thêm `event_bus` param + publish 4 loại event) +
  `tests/test_tool_router_events.py` (mới, 6 tests). Không sửa `event_bus.py`/`event_sinks.py`.
- T3.3: `tests/test_tool_router_boundaries.py` (mới, 4 tests). Không sửa src nào.

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
- T0.6: `uv run pytest -q` → **194 passed** (140 cũ giữ xanh + 54 mới: models/invariants/serialization;
  schema/CRUD/FK/tx/rollback/cleanup/append-only; injection/secret-safety; boundaries).
- Lint/format T0.6: `uvx ruff check .` → pass (auto-fix sort + PEP 695 generics sửa tay + DTZ001 noqa
  có lý do + SIM117 auto-fix); `uvx ruff format --check .` → 84 files pass; `uv run chaos` → exit 0.
- T0.6 compliance: `uv run pytest -q` → **199 passed** (194 adapt + 5 migration mới);
  `uvx ruff check .` → pass (I001/RUF022 auto-fix + SIM117); `uvx ruff format --check .` → pass;
  `uv run chaos` → exit 0; `uv sync --frozen` → consistent.
- T0.7: `uv run pytest -q` → **214 passed** (199 cũ adapt + 15 mới: context/startup/shutdown/failure/
  db-lifecycle/logging/isolation); `uvx ruff check .` → pass (RUF022/I001 auto-fix + BLE001 noqa
  có lý do cho unwind-handler); `uvx ruff format --check .` → 86 files pass;
  `uv run chaos` env sạch → exit 0 (tạo `./data/chaos.db` đúng kỳ vọng, đã xóa sau verify).
- T0.8: `uv run pytest -q` → **226 passed** (214 cũ xanh + 12 mới: update-timestamps/corrupt-row/
  ownership-composition/migration-ordering/settings-matrix/type-boundary);
  `uvx ruff check .` → pass (F841 dùng biến + SIM117 auto-style); `uvx ruff format --check .` → pass;
  `uv run chaos` env sạch → exit 0 (db verify đã xóa).
- M1: `uv run pytest -q` → **294 passed** (226 cũ xanh + 68 mới: config 21/transport 16/adapter 13/
  runtime 15/boundaries 3); `uvx ruff check .` → pass; `uvx ruff format --check .` → 93 files pass;
  `uv run chaos` env sạch → exit 0 (entrypoint M0 giữ nguyên, banner chưa đổi).
- T2.1: `uv run pytest -q` → **310 passed** (294 cũ xanh + 16 mới: exact/wildcard delivery,
  registration order, unsubscribe idempotent, malformed subscribe/publish target reject,
  subscriber isolation + error logging metadata-only, self-unsubscribe-during-publish snapshot
  an toàn, concurrent subscribe/publish smoke test); `uvx ruff check .` → pass (1 import-sort
  auto-fix + 2 BLE001 noqa có lý do cho smoke test); `uvx ruff format --check .` → 96 files pass.
- T2.2: `uv run pytest -q` → **317 passed** (310 cũ xanh + 7 mới: persist đúng field/timestamp,
  redact payload trước khi ghi, id riêng mỗi row, wire qua wildcard trên EventBus thật, lỗi
  sink bị EventBus cô lập, gọi sink trực tiếp thì lỗi repository thật vẫn propagate);
  `uvx ruff check .` → pass ngay lần đầu; `uvx ruff format --check .` → 97 files pass.
- T2.3: `uv run pytest -q` → **321 passed** (317 cũ xanh + 4 mới: boundary event_bus+event_sinks
  stdlib/chaos-only, no forbidden subsystem, no secret literal, event_bus.py độc lập
  persistence); `uvx ruff check .` → pass; `uvx ruff format --check .` → 98 files pass;
  `uv run chaos` env sạch → exit 0.
- T3.1: `uv run pytest -q` → **332 passed** (321 cũ xanh + 11 mới: safe tool chạy + validate
  coerce data, unknown-tool → ValidationError, validate fail → ValidationError, CONFIRM/BLOCK
  bị từ chối → PermissionDeniedError, timeout → OperationTimeoutError, exception lạ ở
  validate/execute không crash router, tool trả sai type bị bắt, call_id giữ nguyên qua mọi
  nhánh lỗi, tool_names sorted); `uvx ruff check .` → pass (1 import thừa tự sửa);
  `uvx ruff format --check .` → 100 files pass.
- T3.2: `uv run pytest -q` → **338 passed** (332 cũ xanh + 6 mới: không có bus vẫn chạy được,
  success → started+finished đúng thứ tự, unknown tool → chỉ failed, CONFIRM → chỉ denied
  (không started), payload không bao giờ mang raw arguments/data thật, event chảy được vào
  audit trail thật qua `AuditEventSink` từ M2); `uvx ruff check .` → pass; `uvx ruff format
  --check .` → 101 files pass (2 file tự format lại).
- T3.3: `uv run pytest -q` → **342 passed** (338 cũ xanh + 4 mới: imports stdlib/chaos-only cho
  `router.py`, không import/tên `bao_mat`/`PermissionEngine` thật ở AST-level (chỉ prose trong
  error message, không trip test), regex scan không match subprocess/socket/eval/exec/ORM/SDK,
  không secret-shaped literal); `uvx ruff check .` → pass ngay lần đầu; `uvx ruff format
  --check .` → 102 files pass; `uv run chaos` env sạch → exit 0 (`./data/chaos.db` verify đã xóa).

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
- T0.6: diff review → chỉ files mới (tracked files untouched, `pyproject.toml`/`uv.lock` untouched →
  dependency delta 0); secret scan → 0 match; forbidden-dep scan (orm/db-client/telemetry/…) → 0 match;
  AST import scan (stdlib/`chaos` only) + sqlite-là-driver-duy-nhất → pass; `.env` không tồn tại;
  không `.db` artifact trong repo (tests dùng `tmp_path`, `.gitignore` đã chặn `*.db`).
- T0.6 compliance: secret scan → 0 match; forbidden-dep scan (trừ sqlalchemy theo spec) → 0 match;
  AST scan (stdlib/`chaos`/`sqlalchemy`) + Core-only (`sqlalchemy.orm` cấm) → pass; `.env` không tồn tại.
- T0.7: diff review → 3 src sửa + 4 test adapt + 1 test mới (`pyproject.toml`/`uv.lock` untouched →
  dependency delta 0); secret scan → 0 match; forbidden-dep scan → 0 match;
  boundary scan (pathlib-exempt đúng `application.py`) → pass; `.env` không tồn tại;
  `./data/chaos.db` tạo bởi verify đã xóa, tree clean (`.gitignore` chặn `*.db`).
- T0.8: diff review → 2 src sửa + 1 test mới (`pyproject.toml`/`uv.lock` untouched →
  dependency delta 0); secret scan → 0 match; forbidden-dep scan → 0 match;
  boundary scan (persistence modules, sqlalchemy Core-only) → pass; `.env` không tồn tại;
  không `.db` artifact (tests `tmp_path`, db verify đã xóa).
- M1: diff review → 2 src sửa (settings, env.example) + 3 src mới (bo_nao) + 5 test mới
  (`pyproject.toml`/`uv.lock` untouched → dependency delta 0); secret scan → 0 match;
  forbidden-dep/SDK scan → 0 match; boundary scan (bo_nao: stdlib/chaos-only, no-ORM/SDK,
  no-permission/executor) → pass; `.env` không tồn tại; tests chỉ dùng fake local server.
- T2.1: diff review → 1 file mới (`event_bus.py`, stdlib + `chaos.ha_tang.*` only) + 1 test mới
  (`pyproject.toml`/`uv.lock` untouched → dependency delta 0); secret scan → 0 match;
  không đụng `bao_mat`/`cong_cu`/persistence; `.env` không tồn tại.
- T2.2: diff review → 1 file mới (`event_sinks.py`, chỉ dùng `Repository`/`AuditEvent`/`new_id`
  có sẵn, không sửa persistence) + 1 test mới (`pyproject.toml`/`uv.lock` untouched →
  dependency delta 0); secret scan → 0 match; redact-trước-khi-persist verify bằng test
  (`s3cr3t-real-value` không xuất hiện trong row đã lưu); `.env` không tồn tại.
- T2.3: diff review → 1 test file mới, không sửa src nào (`pyproject.toml`/`uv.lock`
  untouched → dependency delta 0); secret scan trên `event_bus.py`/`event_sinks.py`/toàn bộ
  test M2 → 0 match; boundary scan (stdlib/chaos-only, không `bao_mat`/`cong_cu`) → pass;
  `.env` không tồn tại; `./data/chaos.db` tạo bởi verify đã xóa.
- T3.1: diff review → 1 file mới (`router.py`, không sửa `contracts/tool.py`) + 1 test mới
  (`pyproject.toml`/`uv.lock` untouched → dependency delta 0); secret scan → 0 match; không
  import `bao_mat` (không tồn tại) hay tên `PermissionEngine` thật; `.env` không tồn tại.
- T3.2: diff review → 1 file sửa (`router.py`, thêm event_bus optional) + 1 test mới
  (`pyproject.toml`/`uv.lock` untouched → dependency delta 0); secret scan → 0 match; test
  riêng xác nhận payload event không mang `data`/`arguments` thật (chỉ tool/call_id/error đã
  redact); `.env` không tồn tại.
- T3.3: diff review → 1 test file mới, không sửa src nào (`pyproject.toml`/`uv.lock` untouched
  → dependency delta 0); secret scan trên `router.py`/toàn bộ test M3 → 0 match; boundary scan
  (stdlib/chaos-only, không `bao_mat` thật, không bare-name `PermissionEngine`) → pass; `.env`
  không tồn tại; `./data/chaos.db` tạo bởi verify đã xóa.

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
- T0.6: persistence ở `ha_tang/` (infrastructure, đúng precedent T0.2); sync vì foundation sync
  (MemoryStore async để M8 quyết bridge); `pathlib` chỉ mang path đã cấu hình (fs writer duy nhất
  là `sqlite3.connect` — boundary test ghi nhận ngoại lệ này); `AuditEvent` append-only ở repo level;
  settings giữ `id` uniform + `key` UNIQUE; `schema_version` thay migration framework.
- T0.6 compliance: Core-only thay ORM (không leak Session/Engine); Table metadata tách khỏi domain
  models (không duplicate semantics); explicit BEGIN chống self-commit của SAVEPOINT-first tx;
  engine chỉ gán sau migrate thành công (failed initialize → is_open False); column-evolution
  (ALTER TABLE) để dành migration v2+; `uv.lock` commit theo convention app.
- T0.7: Application sở hữu Runtime + Persistence như siblings (Runtime không sở hữu DB);
  persistence KHÔNG implement Service (hook-order không diễn đạt unwind — documented);
  DB = `data_dir/chaos.db`, không config field mới; mkdir + OSError→ConfigurationError (không log path);
  stop-fail không close (runtime còn sống); `persistence.created` cố tình không phát;
  `scrub_known_secrets` đóng leak secret-trong-exception-message.
- T0.8: `update()` giữ `created_at` + refresh `updated_at` + trả copy mới (không ghi nguyên entity);
  row hỏng → `ValidationError` (không rò ValueError/KeyError); ownership explicit trong contract;
  secret-category settings để tương lai (M0 settings là plain strings — documented).
- M1: registry name→AIProvider + 1 reference adapter OpenAI-compatible qua stdlib (không SDK,
  không khóa vendor); sync-core + `to_thread` (không aiohttp/httpx, dep delta 0);
  socket-timeout (không thread-leak); SSE batch-read + async-yield (incremental deferred);
  estimate chars/4 heuristic; Brain độc lập ApplicationContext; model không quyết permission
  (tool calls là DATA — boundary test cấm chạm bao_mat/cong_cu).
- T2.1: `EventBus` sync/in-process (không async, theo precedent foundation-sync); chỉ exact
  match + wildcard toàn cục `"*"` (không prefix wildcard — mở rộng khi có consumer thật);
  snapshot danh sách subscriber dưới lock trước khi gọi (subscriber tự (un)subscribe trong
  lúc publish không làm hỏng lượt publish hiện tại, không deadlock vì gọi subscriber ngoài
  `with self._lock`); subscriber lỗi → catch + `log_event` ERROR (metadata only) + tiếp tục,
  `publish()` không bao giờ raise vì lỗi subscriber; `publish()`/`subscribe()` validate
  `event_type` qua `is_conventional_name` (fail-fast, không âm thầm không khớp ai);
  `Subscription` là dataclass frozen mang token ẩn, không phải public contract để so sánh
  field; `unsubscribe` idempotent (bus lạ/token đã gỡ → no-op, không raise).
- T2.2: `AuditEventSink` chỉ là adapter mỏng (không thêm bảng/schema/migration mới) — nhận
  thẳng `Repository[AuditEvent]` đã có từ T0.6 thay vì tự mở `SqliteDatabase` (giữ dependency
  injection tường minh, tái dùng nguyên `repositories(db)["audit_events"]`); redact payload
  qua `Event.safe_payload()` trước khi tạo `AuditEvent` (không bao giờ trưng secret thô ra
  audit trail); gọi trực tiếp (không qua bus) thì lỗi repository propagate nguyên vẹn — cô
  lập lỗi là trách nhiệm của `EventBus`, không phải của sink; chưa wire vào
  `ApplicationContext` (để dành milestone có event producer thật, ví dụ M3 Tool Framework).
- T3.1: `ToolRouter` là implementation, không phải contract — được phép "biết" khái niệm
  permission (import `PermissionClass`/`PermissionDeniedError`) mà không vi phạm boundary test
  của `tool.py` (test đó chỉ khoá module `contracts/tool.py`, không khoá `router.py`); policy
  SAFE-only cố tình bỏ qua `call` (không đọc arguments để quyết permission) để không thể vô
  tình biến thành cách bypass; `dispatch()` không bao giờ raise (khác Brain M1 vốn raise) vì
  `ToolResult` đã có invariant ok/error sẵn — đúng tinh thần "standardized, machine-readable"
  của CONTRACTS.md; registry là `dict` phẳng, không class riêng (giữ nguyên mức tối giản như
  Brain M1); `execute()` nhận `ToolCall` mới với arguments đã validate/normalize (không phải
  arguments thô ban đầu) — tool luôn nhận input sạch.
- T3.2: `event_bus` là optional constructor param (router chạy được không cần bus, đúng kiểu
  DI tường minh); payload chỉ gồm `tool`/`call_id` (qua `correlation_id`)/`error` (đã redact
  qua `format_error`) — không bao giờ đưa `data`/`arguments` thật vào event (AGENTS.md §11);
  "started" chỉ publish SAU permission pass (không publish cho unknown-tool/validate-fail/
  denied — những nhánh đó publish thẳng "failed"/"denied", không có "started" trước đó vì
  chưa từng thực sự chuẩn bị chạy); "finished" publish cả khi `result.ok=False` do chính tool
  tự báo lỗi nghiệp vụ (khác với "failed" — đó là lỗi ở tầng router, không execute được).
- T3.3: boundary test tách rõ 2 kiểu check để tránh false-positive: (1) AST-based cho
  import/tên thật (`ast.Import`/`ast.ImportFrom`/`ast.Name`) — chỉ trip nếu có `import bao_mat`
  hay bare identifier `PermissionEngine`/`bao_mat` dùng như code; (2) regex trên raw source cho
  các pattern khác (subprocess/socket/eval/exec/ORM/SDK) nhưng CỐ TÌNH loại `PermissionEngine`
  khỏi list regex vì router hợp lệ nhắc tên đó trong docstring/error message dạng prose — đây
  là khác biệt so với `test_brain_boundaries.py`/`test_event_bus_boundaries.py` (không có nhu
  cầu nhắc permission trong prose) nên không copy y nguyên mẫu cũ mà tách check theo đúng lý do.
  Milestone 3 (Tool Framework) hoàn thành: ToolRouter chạy được core loop rút gọn thật, có audit
  trail thật, có boundary test xác nhận không lách qua bao_mat/PermissionEngine thật nào.

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
- Git `user.name`/`user.email`: đã set `Thanh <thanh.nv@bbi-tek.vn>` cho local repo (commit từ
  M1 trở đi dùng tên thật) — chỉ local, chưa set global; commit `98fd45c`–`746a947` (M0) vẫn
  đứng tên tạm `CHAOS Agent <chaos-agent@local>`, không rewrite lịch sử (AGENTS.md §19 cấm).
- `.venv/` tồn tại local (đúng git-ignored) — phiên sau chạy `uv sync --group dev` lại nếu thiếu.
- Scope M2+ (tool exec M3, permission M4, verifier M5, browser M6, OS M7, memory M8, desktop UI M9,
  voice M10-11, avatar M12-14, full agent loop M15...) cố tình chưa chạm — ghi nhận để không quên.
- **M2 — EventBus chưa wire vào `ApplicationContext`**: `application.py` vẫn gọi `log_event`
  trực tiếp như M0/M1, không publish qua bus. Cố tình để dành milestone có event producer thật
  (Tool Framework M3 hoặc Permission M4) — tránh refactor call site đang test/commit ổn định
  chỉ để "dùng cho có". Khi milestone đó cần publish sự kiện thật, đây là điểm nối.
- **M2 — chỉ hỗ trợ wildcard toàn cục `"*"`**, không có prefix wildcard kiểu `tool.*`. Thêm khi
  có consumer thật cần lọc theo namespace (không đoán trước, tránh over-engineering).
- **M3 — `ToolRouter` chưa wire vào `ApplicationContext`**: đứng độc lập (như `EventBus` ở M2),
  chưa có registry tool cụ thể nào (tool đầu tiên là M6 browser/M7 OS), permission vẫn là
  placeholder bảo thủ SAFE-only (PermissionEngine thật là M4 — khi đó thay `_is_permitted` mà
  không đổi chữ ký `dispatch()`), chưa có CONFIRM flow tương tác với user thật.
- Repo public trên GitHub (`https://github.com/thanh577/CHAOS-_AGENTS`), branch `main` — đã
  push đến hết Milestone 3 (`946b2e3`), bao gồm M2 (`0fd263b`/`fa77611`/`02cba96`) và M3
  (`23ba3d1`/`83dbe91`/`946b2e3`). Lưu ý: cloud container bị chặn push trực tiếp lên repo này
  (org egress-proxy policy) — quy trình chuẩn từ nay là commit ở cloud clone
  (`/home/claude/chaos`) → git bundle → SendUserFile → device_commit_files vào máy thật của
  user → fetch+merge --ff-only trên máy → verify test → push bằng PAT (`repo`+`workflow`
  scope) từ máy thật.
- T0.2 không phát hiện mâu thuẫn spec: `CONTRACTS.md`/`ARCHITECTURE.md` đủ rõ để định nghĩa shape.

## Do Not Repeat

- Không đọc lại toàn bộ spec ở mỗi phiên nếu `CHAOS_STATE.md` đã có trạng thái đáng tin cậy.
- Không nhảy sang milestone kế tiếp.
- Không cho LLM chạy raw shell/filesystem command.
- Không ghi secret vào state/log/code.
- Không đánh dấu Done nếu chưa test + verify.

## Spec References Used

- T0.8: `AGENTS.md`, `CHAOS_STATE.md`, `README.md`, `docs/README.md`, `docs/spec/ARCHITECTURE.md`,
  `docs/spec/CONTRACTS.md`, `docs/spec/DATA_MODEL.md`, `docs/spec/SECURITY.md`, `docs/spec/TESTING.md`,
  `docs/spec/DEFINITION_OF_DONE.md`, `docs/spec/AGENT_RULES.md` (+ nền T0.1–T0.7 giữ nguyên).
- T0.7: `AGENTS.md`, `CHAOS_STATE.md`, `README.md`, `docs/README.md`, `docs/spec/ARCHITECTURE.md`,
  `docs/spec/CONTRACTS.md`, `docs/spec/DATA_MODEL.md`, `docs/spec/SECURITY.md`, `docs/spec/TESTING.md`,
  `docs/spec/DEFINITION_OF_DONE.md`, `docs/spec/AGENT_RULES.md` (+ nền T0.1–T0.6 giữ nguyên).
- T0.6/T0.6-compliance: `AGENTS.md`, `docs/spec/DATA_MODEL.md`, `docs/spec/ARCHITECTURE.md`,
  `docs/spec/AGENT_RULES.md` (+ nền T0.1–T0.5 giữ nguyên).
- T0.5/T0.5-gap-audit: `AGENTS.md`, `docs/spec/ARCHITECTURE.md`, `docs/spec/CONTRACTS.md`,
  `docs/spec/SECURITY.md` (+ nền T0.1–T0.4 giữ nguyên).
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
2026-09-17 — T0.6 hoàn tất: 9 models + generic Repository + sqlite stdlib (schema_version 1,
SAVEPOINT tx, append-only audit), 194 tests pass, ruff/format pass, dep delta 0, chaos exit 0.
DoD 27/27 có evidence. Không T0.7/M1+.
2026-09-17 — T0.6 compliance (Case B) hoàn tất: SQLAlchemy Core 2.0.54 + Migration registry,
giữ nguyên models/ABC/API, 199 tests pass, ruff/format pass, dep delta = sqlalchemy theo spec,
chaos exit 0, uv.lock consistent. Không T0.7/M1+.
2026-09-17 — T0.8 hoàn tất: audit persistence contract, fix update-timestamps + corrupt-row mapping +
ownership docs, 226 tests pass, ruff/format pass, dep delta 0, chaos exit 0. DoD 26/26. Không T0.9/M1+.
2026-09-17 — T0.7 hoàn tất: Application sở hữu Runtime + Persistence (siblings), frozen context
+ persistence, startup/shutdown ordering + failure unwind + persistence events + scrub_known_secrets,
214 tests pass, ruff/format pass, dep delta 0, chaos env sạch exit 0. DoD 26/26. Không T0.8/M1+.

- **T0.6 — Persistence Foundation & Data Model (2026-09-17):**
  - Spec basis: `DATA_MODEL.md` chỉ định nghĩa 9 tên bảng + SQLite/SQLAlchemy + migrations —
    fields/relations/semantics do agent định nghĩa tối thiểu, reversible (ghi rõ trong report).
  - Backend: stdlib `sqlite3` (đủ cho foundation) — KHÔNG SQLAlchemy/Alembic/Pydantic;
    `Repository[T]` ABC backend-agnostic nên SQLAlchemy có thể thay thế sau không phá contract.
  - `ha_tang/persistence/`: `models.py` (9 frozen dataclasses: id + UTC aware timestamps +
    to_dict/from_dict, JSON deterministic cho metadata/payload); `repository.py` (generic sync
    CRUD ABC — sync vì foundation sync); `sqlite_store.py` (`SqliteDatabase`: explicit path,
    lazy connect, idempotent schema + `schema_version`=1, FK ON, SAVEPOINT nested transactions,
    explicit close; `SqliteRepository[T]` parameterized-only; `ReadOnlyRepository` cho audit_events;
    errors map về `ValidationError`/`ExecutionError` giữ `from` context, message không embed values).
  - FKs chỉ cho cặp cha-con hiển nhiên (messages→sessions, task_steps→tasks,
    tool_runs.task_id NULL→tasks); status là str thuần (spec không định nghĩa lifecycle values).
  - Không tích hợp ApplicationContext (spec không yêu cầu — lifecycle độc lập, explicit;
    milestone sau có thể attach như Service). Không DB khi import.
  - Trong lúc test phát hiện transaction lồng nhau không rollback (repo tự commit) →
    sửa bằng SAVEPOINT nesting + tests (inner-rollback giữ outer, outer-rollback xóa hết).
  - 54 tests mới (tổng 194 pass); ruff + format pass; chaos exit 0. Dependency delta 0.
  - AC T0.6: DoD 27/27 đạt (xem T0.6 report). Không workflow M1+, không T0.7.

- **T0.6 Spec Compliance Review — Case B (2026-09-17, sau commit 2402f6a, KHÔNG rollback):**
  - Phân loại: SQLAlchemy = MANDATORY (AGENTS.md §17 "Dùng: SQLAlchemy" — Architecture rule,
    outrank task order; DATA_MODEL.md "SQLite + SQLAlchemy initially"); Migrations = MANDATORY
    (DATA_MODEL.md "Use migrations", AGENTS.md §17 "migration strategy" + "Không thay đổi schema
    tùy tiện mà không migration"). Không có chữ "recommended/optional" ở đâu → Case B.
  - KEEP: 9 domain models, `Repository[T]` ABC, public API backend (`SqliteDatabase`,
    `SqliteRepository`, `TABLES`, `repositories()`, errors mapping, savepoint tx semantics).
  - REPLACE internals: stdlib `sqlite3` → SQLAlchemy Core 2.0.54 (Table metadata + insert/select/
    update/delete constructs, engine ownership, `begin_nested` savepoints; KHÔNG ORM —
    `sqlalchemy.orm` bị boundary test cấm; domain models không chuyển sang ORM).
  - ADAPT: `Migration` registry + `migrate()` (ordered, idempotent, version marker, failure giữ
    version cũ); tests dùng internals cũ (row_factory/raw-SQL-`?`) chuyển sang `text()`/mappings;
    boundary tests cho phép đúng `sqlalchemy` (Core-only).
  - BUG THẬT phát hiện trong lúc chuyển backend: pysqlite legacy chỉ BEGIN ngầm trước DML nên
    transaction mở bằng SAVEPOINT tự commit ở RELEASE → fix bằng explicit `BEGIN` ở outer boundary
    (giữ DEFERRED semantics) + tests rollback/nested vẫn xanh; FK thiếu trong Table defs → thêm
    `ForeignKey` (đúng spec "foreign keys").
  - Dependency: `SQLAlchemy>=2.0,<3` (runtime, MIT license verified, 2.0.x active, py3.12 OK) +
    transitive greenlet/typing-extensions trong uv.lock. KHÔNG Alembic/Pydantic.
  - 199 tests pass (194 cũ adapt + 5 migration mới); ruff + format pass; chaos exit 0; dep delta
    đúng policy (spec precedence). Không T0.7/M1+.

- **T0.7 — Persistence/Application Lifecycle Integration (2026-09-17, sau commit 3536b49):**
  - Ownership (trả lời §3): Application tạo (từ settings.storage) + initialize + sở hữu +
    shutdown cả Runtime và Persistence như siblings — Runtime KHÔNG sở hữu DB (giữ Runtime tái dùng).
    Không singleton/locator/global/hidden-dep. Không Service thứ hai: persistence KHÔNG implement
    `Service` vì hook-order của Runtime không diễn đạt được "persistence trước, unwind khi runtime
    fail" nếu không thêm unwind machinery (rejected — minimal change).
  - Context: thêm field `persistence: SqliteDatabase` vào frozen `ApplicationContext`
    (settings/logger/runtime/persistence — không god-object). `create_application` giữ signature;
    direct constructions trong tests đã update.
  - Config: KHÔNG field mới — `data_dir` hiện có đủ; DB = `data_dir/chaos.db` (`DATABASE_FILENAME`).
    `create_application` mkdir parents + map OSError → `ConfigurationError` (không log path).
  - Startup: create (wiring, chưa mở DB) → persistence.initialize → runtime.initialize →
    runtime.start → RUNNING. Init-fail: runtime giữ CREATED. Start-fail: unwind persistence.close().
  - Shutdown: runtime.shutdown → persistence.close → STOPPED; `finally` đảm bảo close kể cả khi
    runtime halt fail; stop-fail KHÔNG close (runtime còn sống — không fake success).
  - Events: `persistence.initialized` (+schema_version) / `.initialization.failed` / `.shutdown` /
    `.shutdown.failed` qua `log_event` + per-run correlation; KHÔNG phát `persistence.created`
    (wiring thuần, tránh noise — documented). Payload safe, không path/secret.
  - Secret-safety: `safe_summary` bỏ key `data_dir` (§11 strict); `redaction.scrub_known_secrets`
    mới + dùng trong mọi failure payload (bắt leak thật: secret trong exception message).
  - 214 tests (199 cũ adapt + 15 mới); ruff + format pass; chaos env sạch exit 0; dep delta 0.
  - AC T0.7: DoD 26/26 đạt (xem T0.7 report). Không workflow M1+, không T0.8.

- **T0.8 — Persistence Contract Hardening (2026-09-17, sau commit 7f4e359):**
  - Audit toàn bộ persistence theo §3–§13: phần lớn VERIFIED bằng evidence (models, FK, tx nesting,
    migrations fresh/repeat/upgrade/failure/duplicate, error mapping, redaction, Core+bound params,
    audit append-only, settings unique, app integration, single-thread documented, no-ORM, no-timeout).
  - GAPS đã fix (minimal, không rewrite): (1) `update()` giờ giữ `created_at` immutable + refresh
    `updated_at` + trả bản copy mới (trước đây ghi nguyên entity caller đưa); (2) row hỏng
    (JSON vỡ, thiếu cột, naive time) trong get/list map về `ValidationError` thay vì rò
    ValueError/KeyError thô; (3) ownership ghi explicit vào contract (method tự transaction,
    caller compose qua outer tx); (4) tests bổ sung: multi-repo atomic, outer-commit giữ inner,
    migration ordering (input đảo vẫn sort), settings create-duplicate, empty list, value-update,
    non-leak backend types, JSON round-trip qua backend.
  - Không đổi: models, ABC shape, backend architecture, migrations, app integration, dependencies.
  - 226 tests (214 cũ xanh + 12 mới); ruff + format pass; chaos env sạch exit 0; dep delta 0.
  - AC T0.8: DoD 26/26 đạt (xem T0.8 report). Không workflow M1+, không T0.9.

- **M1 — Cloud Brain (2026-09-17, sau commit 746a947):**
  - T1.1 config: `AISettings` + `max_retries` (0..10), `retry_backoff_seconds` (0..60],
    `max_context_tokens` (positive|None) + 3 env vars + validation (21 tests).
  - T1.2 transport (`bo_nao/http_transport.py`, stdlib http.client + to_thread, 0 dep):
    socket-timeout, retry bounded (429 honor Retry-After capped; 5xx/conn-error; không retry 4xx),
    backoff mũ capped, map lỗi → ProviderError/OperationTimeoutError/ConfigurationError,
    body-cap 10MB, chỉ log status (16 tests vs fake local server).
  - T1.3 adapter (`bo_nao/openai_compat.py`): wire JSON (model/messages/tools→functions/stream),
    parse response + tool_calls (arguments hỏng → ValidationError), SSE batch-read + async-yield
    (incremental-network deferred, documented), Bearer auth tại send, endpoint http/https only (13 tests).
  - T1.4 runtime (`bo_nao/brain.py`): registry + chọn provider theo config, budget
    (estimate chars/4, giữ system, drop-cũ-nhất, không truncate content), single-turn orchestration,
    graceful failure (CHAOS pass-through, lạ → ProviderError), log metadata-only + scrub secrets,
    boundary (không chạm permission/executor) (15 tests).
  - T1.5: boundary tests M1 (stdlib/chaos-only, no-SDK/ORM, no-scope-leak) + full verify (3 tests).
  - 294 tests (226 cũ xanh + 68 mới); ruff + format pass; chaos exit 0; dep delta 0.
    Brain độc lập ApplicationContext (wire ở milestone sau). Không agent loop/tool-exec/M2.

- **T2.1 — EventBus Core (2026-09-17, sau commit e8783c6):**
  - Hiện thực đúng phần `ha_tang/contracts/events.py` (T0.2/T0.4) đã khai báo là để dành:
    "Bus implementation, subscription... belong to later milestones".
  - `ha_tang/event_bus.py`: `EventBus.subscribe(event_type|"*", subscriber) -> Subscription`,
    `unsubscribe(subscription)` (idempotent), `publish(event)` (validate naming convention,
    gọi subscriber khớp theo thứ tự đăng ký — exact trước, wildcard sau — snapshot dưới lock
    để an toàn khi subscriber tự (un)subscribe giữa lúc đang publish; subscriber lỗi bị bắt +
    log ERROR metadata-only qua `log_event`/`format_error`, không raise ra ngoài, không chặn
    subscriber còn lại). `subscriber_count()` cho test/introspection. Stdlib-only
    (`threading.Lock`), không dependency mới, không đụng persistence/bao_mat/cong_cu.
  - 16 tests mới (tổng 310 pass): exact/wildcard/multi-subscriber ordering, unsubscribe +
    idempotency, malformed-target reject (subscribe lẫn publish), subscriber-isolation +
    error-logging, self-unsubscribe-during-publish, concurrent subscribe/publish smoke test.
  - ruff + format pass; chaos exit 0 (không đổi entrypoint). Dependency delta 0.
  - AC T2.1: đúng scope Milestone 2 Plan, không chạm sang T2.2 (audit sink)/T2.3 (boundary+DoD).

- **T2.2 — Audit Persistence Sink (2026-09-17, sau commit 5efa2fa):**
  - `ha_tang/event_sinks.py`: `AuditEventSink(repository)` — callable subscriber, nhận
    `Repository[AuditEvent]` (từ `repositories(db)["audit_events"]` có sẵn từ T0.6), map
    `Event` → `AuditEvent` (id mới, `payload=event.safe_payload()` đã redact, `correlation_id`,
    `created_at=updated_at=event.occurred_at`). Không sửa models/repository/sqlite_store,
    không schema/migration mới.
  - 7 tests mới (tổng 317 pass): persist đúng field, giữ nguyên timestamp từ `occurred_at`,
    redact secret trước khi ghi (giá trị thật không xuất hiện trong row đã lưu), id riêng mỗi
    event, wire qua `EventBus` thật bằng wildcard, lỗi sink (DB đã đóng) bị `EventBus` cô lập
    (subscriber khác vẫn chạy, publish không raise), gọi sink trực tiếp (không qua bus) thì
    lỗi repository thật vẫn propagate nguyên vẹn.
  - ruff + format pass; chaos exit 0. Dependency delta 0.
  - AC T2.2: đúng scope, chưa wire vào ApplicationContext (để dành milestone có producer thật).

- **T2.3 — Boundary & Integration/DoD, chốt Milestone 2 (2026-09-17, sau commit e0ff076):**
  - `tests/test_event_bus_boundaries.py` (theo đúng mẫu `test_brain_boundaries.py`): imports
    stdlib/chaos-only cho `event_bus.py` + `event_sinks.py`; không đụng `bao_mat`/`cong_cu`/SDK/
    ORM literal; không secret-shaped literal; thêm 1 test riêng xác nhận `event_bus.py` (transport)
    không import `persistence` — chỉ `event_sinks.py` được biết về persistence layer.
  - Full verify: 321 tests pass (317 cũ xanh + 4 boundary mới); `ruff check`/`format --check` pass;
    `uv run chaos` env sạch exit 0; secret scan trên toàn bộ file M2 → 0 match; `pyproject.toml`/
    `uv.lock` untouched suốt M2 → dependency delta 0; `./data/chaos.db` verify đã xóa.
  - AC M2 (Milestone 2 Plan): EventBus publish/subscribe + subscriber isolation (T2.1) ✓, audit
    sink nối vào `audit_events` có sẵn + redact trước khi persist (T2.2) ✓, boundary tests +
    full verify (T2.3) ✓. Không wire ApplicationContext, không wildcard prefix, không async
    subscriber, không event replay API mới — đúng như Milestone 2 Plan đã ghi trước khi code.
    Không M3.

- **T3.1 — ToolRouter Core (2026-09-17, sau commit d982748):**
  - `cong_cu/router.py`: `ToolRouter(tools: Mapping[str, Tool]).dispatch(call) -> ToolResult`
    thực hiện đúng core loop rút gọn `validation → permission(placeholder) → executor` (verifier
    để dành M5). Permission placeholder bảo thủ: chỉ `PermissionClass.SAFE` được chạy;
    `CONFIRM`/`BLOCK` bị từ chối bằng `PermissionDeniedError` (chưa có PermissionEngine thật).
    Timeout qua `asyncio.wait_for(tool.timeout_seconds)` → `OperationTimeoutError`. `dispatch()`
    không bao giờ raise: tool lạ/validate fail/permission fail/timeout/exception lạ từ
    tool/tool trả sai type đều map về `ToolResult(ok=False, error=...)`.
  - 11 tests mới (tổng 332 pass): happy path (coerce data qua validate), unknown tool, validate
    fail, CONFIRM/BLOCK denied, timeout, exception lạ ở validate lẫn execute không crash router,
    tool trả sai type bị bắt, call_id giữ nguyên qua mọi nhánh lỗi, tool_names sorted.
  - ruff + format pass (1 import thừa tự sửa); chaos exit 0. Dependency delta 0.
  - AC T3.1: đúng scope Milestone 3 Plan, chưa publish EventBus (T3.2) và chưa boundary+DoD (T3.3).

- **T3.2 — Audit events cho Tool Execution (2026-09-17, sau commit 23ba3d1):**
  - `router.py` thêm `event_bus: EventBus | None = None` (optional, DI tường minh) + publish 4
    loại event qua `_publish`/`_fail`: `tool.execution.started` (chỉ sau khi qua permission,
    trước khi execute), `.finished` (execute xong, kể cả `result.ok=False` do tool tự báo),
    `.denied` (permission fail), `.failed` (mọi lỗi tầng router: unknown tool/validate/timeout/
    exception lạ/sai type). Payload chỉ `tool`/`error` (đã qua `format_error` — redact), không
    bao giờ có raw arguments/data; `correlation_id=call.call_id`.
  - 6 tests mới (tổng 338 pass): không có bus vẫn chạy bình thường, success →
    started+finished đúng thứ tự với payload đúng, unknown-tool → chỉ failed, CONFIRM → chỉ
    denied (không có started vì chưa qua permission), payload không bao giờ chứa raw
    argument/data thật (test trực tiếp), event chảy được vào audit trail thật qua
    `AuditEventSink` (M2) không sửa gì ở đó.
  - ruff + format pass (2 file tự format lại vì dòng dài); chaos exit 0. Dependency delta 0.
  - AC T3.2: đúng scope, EventBus/AuditEventSink của M2 không hề bị sửa — chỉ tái sử dụng.

- **T3.3 — Boundary & Integration/DoD, chốt Milestone 3 (2026-09-17, sau commit 83dbe91):**
  - `tests/test_tool_router_boundaries.py` (theo tinh thần `test_brain_boundaries.py`/
    `test_event_bus_boundaries.py` nhưng tách 2 kiểu check để tránh false-positive từ docstring/
    error-message prose của chính `router.py`): (1) AST-based imports stdlib/chaos-only; (2)
    AST-based `test_no_forbidden_subsystems_as_import_or_name` — chỉ trip trên `ast.Import`/
    `ast.ImportFrom`/`ast.Name` thật, không phải text search, nên chuỗi "PermissionEngine" trong
    error message không kích hoạt; (3) regex scan riêng cho các pattern khác (subprocess/socket/
    urllib/os.system/shutil/__import__/eval/exec/ctypes/sqlalchemy/pydantic/httpx/aiohttp/
    playwright/bao_mat) — CỐ TÌNH loại `PermissionEngine` khỏi regex list vì đó là literal hợp
    lệ trong prose, không phải code; (4) không secret-shaped literal.
  - Full verify: 342 tests pass (338 cũ xanh + 4 boundary mới); `ruff check`/`format --check`
    pass (102 files); `uv run chaos` env sạch exit 0; secret scan trên toàn bộ file M3 → 0
    match; `pyproject.toml`/`uv.lock` untouched suốt M3 → dependency delta 0; `./data/chaos.db`
    verify đã xóa.
  - AC M3 (Milestone 3 Plan): `ToolRouter` chạy đúng core loop rút gọn `validate → permission
    placeholder → executor` với timeout (T3.1) ✓, audit trail thật qua `EventBus`+
    `AuditEventSink` không sửa gì ở M2 (T3.2) ✓, boundary tests + full verify (T3.3) ✓. Không
    wire `ApplicationContext`, không PermissionEngine thật, không tool cụ thể nào, không CONFIRM
    flow tương tác — đúng như Milestone 3 Plan đã ghi trước khi code. Milestone 3 (Tool
    Framework) HOÀN THÀNH. Không tự sang M4 — chờ lệnh user.

---

# Session Log

> Sau mỗi phiên, thêm một entry ngắn. Không paste log terminal dài.

## 2026-09-17 T3.3 (chốt M3)
- Session: Milestone 3 — T3.3 Boundary tests + Integration/DoD
- Completed: T3.3 (`test_tool_router_boundaries.py`: stdlib/chaos-only imports, AST-based no
  bare `bao_mat`/`PermissionEngine` name-or-import (text trong prose không trip), regex scan
  loại trừ `PermissionEngine` cho các forbidden pattern khác, no secret-shaped literal; 4
  tests, 342 pass, ruff/format pass, chaos exit 0, dep delta 0). Milestone 3 (Tool Framework)
  DONE.
- Changed: 1 test file mới (xem Changed Files); không sửa src nào ở T3.3
- Tests: pytest 342 passed (338 cũ xanh + 4 mới); pass ngay lần đầu (chạy standalone 4 passed
  trước, rồi full suite)
- Decisions: tách AST-check (import/tên thật) khỏi regex-check (pattern khác) để
  `PermissionEngine` trong error-message prose của router không bị coi là vi phạm — khác
  `test_brain_boundaries.py`/`test_event_bus_boundaries.py` vì hai module đó không có lý do
  nhắc permission trong prose
- Blockers: không — DoD Milestone 3 có evidence đầy đủ
- Next: chờ lệnh milestone tiếp theo (M4 Permission theo TASKS.md); KHÔNG tự sang M4. Cần push
  3 commit M3 (T3.1/T3.2/T3.3) + 3 commit M2 còn thiếu lên GitHub qua bundle-transfer workflow
  khi có lệnh + PAT mới.

## 2026-09-17 T3.2
- Session: Milestone 3 — T3.2 Audit events cho Tool Execution
- Completed: T3.2 (`router.py` thêm event_bus optional + publish started/finished/denied/failed
  qua EventBus M2, payload redact không raw data; 6 tests, 338 pass, ruff/format pass, chaos
  exit 0, dep delta 0)
- Changed: 1 file sửa + 1 test mới (xem Changed Files); không sửa `event_bus.py`/`event_sinks.py`
- Tests: pytest 338 passed (332 cũ xanh + 6 mới); pass ngay lần đầu
- Decisions: started chỉ sau permission pass, finished kể cả ok=False (khác failed = lỗi
  router), payload chỉ tool/call_id/error đã redact, event_bus optional không phá caller cũ
- Blockers: không
- Next: T3.3 (boundary tests + full verify + state + commit cuối M3)

## 2026-09-17 T3.1
- Session: Milestone 3 — T3.1 ToolRouter Core
- Completed: T3.1 (`router.py`: validate → permission-placeholder (SAFE-only) → timeout-bounded
  execute, dispatch() never raises; 11 tests, 332 pass, ruff/format pass, chaos exit 0, dep delta 0)
- Changed: 1 file mới + 1 test mới (xem Changed Files); không sửa `contracts/tool.py`
- Tests: pytest 332 passed (321 cũ xanh + 11 mới); pass ngay lần đầu
- Decisions: SAFE-only permission placeholder cố tình bỏ qua `call`, dispatch() không raise
  (khác Brain), registry dict phẳng, execute() nhận arguments đã normalize
- Blockers: không
- Next: T3.2 (publish audit event qua EventBus cho tool execution)

## 2026-09-17 T2.3 (chốt M2)
- Session: Milestone 2 — T2.3 Boundary tests + Integration/DoD
- Completed: T2.3 (`test_event_bus_boundaries.py`: stdlib/chaos-only, no forbidden subsystem,
  no secret literal, event_bus độc lập persistence; full verify 321 tests pass, ruff/format
  pass, chaos exit 0, dep delta 0). Milestone 2 (Event Bus) DONE.
- Changed: 1 test file mới (xem Changed Files); không sửa src nào ở T2.3
- Tests: pytest 321 passed (317 cũ xanh + 4 mới); pass ngay lần đầu, 1 sửa nhỏ do bài test tự
  viết sai (dùng read_text thay vì _code_only nên "persistence" trong docstring bị tính nhầm)
- Decisions: EventBus (transport) và AuditEventSink (persistence-aware) tách file, boundary
  test ép event_bus.py không được biết đến persistence
- Blockers: không — DoD Milestone 2 có evidence đầy đủ
- Next: chờ lệnh milestone tiếp theo (M3 Tool Framework theo TASKS.md); KHÔNG tự sang M3

## 2026-09-17 T2.2
- Session: Milestone 2 — T2.2 Audit Persistence Sink
- Completed: T2.2 (`event_sinks.py`: AuditEventSink adapter Event→AuditEvent, redact trước khi
  persist, dùng nguyên Repository/audit_events có sẵn từ T0.6; 7 tests, 317 pass, ruff/format
  pass, chaos exit 0, dep delta 0)
- Changed: 1 file mới + 1 test mới (xem Changed Files); không sửa persistence hiện có
- Tests: pytest 317 passed (310 cũ xanh + 7 mới), pass ngay lần đầu không phải sửa gì
- Decisions: sink nhận Repository injected (không tự mở DB), lỗi trực tiếp thì propagate thật,
  cô lập lỗi là việc của EventBus; chưa wire ApplicationContext
- Blockers: không
- Next: T2.3 (boundary tests cho event_bus.py + event_sinks.py, full verify, DoD, commit cuối M2)

## 2026-09-17 T2.1
- Session: Milestone 2 — T2.1 EventBus Core
- Completed: T2.1 (`event_bus.py`: publish/subscribe sync in-process, exact+wildcard, subscriber
  isolation + error logging, unsubscribe idempotent, naming-convention validation; 16 tests, 310
  pass, ruff/format pass, chaos exit 0, dep delta 0)
- Changed: 1 file mới + 1 test mới (xem Changed Files); không sửa file nào khác
- Tests: pytest 310 passed (294 cũ xanh + 16 mới); 1 lỗi test-helper tự sửa trong lúc viết
  (`_event()` truyền `source` trùng keyword) — không phải lỗi implementation
- Decisions: sync/in-process only, exact+wildcard `"*"` (không prefix wildcard), snapshot dưới
  lock trước khi gọi subscriber, publish() không raise vì lỗi subscriber
- Blockers: không
- Next: T2.2 (audit persistence sink nối EventBus → audit_events repository có sẵn)

## 2026-09-17 M1 plan
- Session: Milestone 1 — Cloud Brain plan (read specs, no code yet)
- Completed: đọc ARCHITECTURE/CONTRACTS/SECURITY/AGENTS-§12 + code hiện tại; ghi T1.1–T1.5 breakdown vào state
- Changed: CHAOS_STATE.md (Current State + Milestone 1 Plan)
- Tests: chưa có (breakdown only)
- Decisions: registry + 1 reference adapter OpenAI-compatible qua stdlib (không SDK); sync-core + to_thread; SSE batch-read + async-yield; estimate chars/4; Brain độc lập ApplicationContext
- Blockers: không
- Next: implement T1.1; chỉ M1, không M2

## 2026-09-17 M0 review
- Session: Milestone 0 pre-M1 review (read-only, không sửa code)
- Completed: audit T0.1–T0.8 + spec compliance; baseline sống (226 pass/0 skip, ruff/format pass, chaos exit 0, tree clean); 7/7 contracts abstract; secret scan 0; dep SQLAlchemy 2.0.54 + pytest; không subsystem M1+
- Changed: chỉ entry này (không code)
- Tests: pytest 226 passed (không skip), không assert rỗng
- Decisions: M0 READY FOR M1; ghi nhận 2 drift comment cosmetic (env.example "no database in M0", thứ tự summary T0.8/T0.7) — không blocking, để milestone sau hoặc lệnh riêng
- Blockers: không
- Next: chờ lệnh M1 (cần order chi tiết như mọi task trước); KHÔNG tự sang M1

## 2026-09-17 T0.8
- Session: Milestone 0 — T0.8 Persistence Contract Hardening
- Completed: T0.8 (audit §3–§13; fix update-timestamps + corrupt-row mapping + ownership docs; 12 tests, 226 pass, ruff/format pass, chaos exit 0, dep delta 0)
- Changed: 2 src sửa + 1 test mới (xem Changed Files); models/ABC/backend/migrations/app-integration không đổi; pyproject/uv.lock không đổi
- Tests: pytest 226 passed (214 cũ xanh + 12 mới); không coverage-chasing
- Decisions: update giữ created_at + refresh updated_at + trả copy; corrupt-row → ValidationError; ownership explicit trong contract; secret-category settings để tương lai
- Blockers: không — DoD 26/26 có evidence
- Next: chờ lệnh milestone tiếp theo; KHÔNG T0.9/M1+

## 2026-09-17 T0.7
- Session: Milestone 0 — T0.7 Persistence/Application Lifecycle Integration
- Completed: T0.7 (ownership siblings, context+persistence, config data_dir/chaos.db, startup/shutdown ordering + unwind, 4 persistence events, scrub_known_secrets; 15 tests, 214 pass, ruff/format pass, chaos exit 0, dep delta 0)
- Changed: 3 src sửa + 4 test adapt + 1 test mới (xem Changed Files); pyproject/uv.lock không đổi
- Tests: pytest 214 passed (199 cũ adapt + 15 mới); 1 leak secret-thật bắt và fix trong lúc test
- Decisions: App owns Runtime+Persistence, không Service thứ hai, không field config mới, mkdir + no-path-log, stop-fail không close, bỏ data_dir khỏi summary, không phát persistence.created
- Blockers: không — DoD 26/26 có evidence
- Next: chờ lệnh milestone tiếp theo; KHÔNG T0.8/M1+

## 2026-09-17 T0.6 compliance
- Session: M0 T0.6 Spec Compliance Review — Case B (sau 2402f6a, không rollback)
- Completed: phân loại MANDATORY có evidence; SQLAlchemy Core backend + Migration registry giữ API; 199 tests pass
- Changed: pyproject/uv.lock + sqlite_store rewrite-internals + 2 tests adapt + 1 test migration mới (xem Changed Files)
- Tests: pytest 199 passed; ruff + format pass; chaos exit 0; uv sync --frozen ok
- Decisions: Core-only (cấm ORM), explicit BEGIN, engine-gán-sau-migrate, ALTER để v2+, Alembic không cần
- Bugs found & fixed: SAVEPOINT-first self-commit; missing ForeignKey; engine gán trước migrate
- Blockers: không
- Next: chờ lệnh milestone tiếp theo; KHÔNG T0.7/M1+

## 2026-09-17 T0.6
- Session: Milestone 0 — T0.6 Persistence Foundation & Data Model
- Completed: T0.6 (9 models + Repository ABC + SqliteDatabase/SqliteRepository + schema_version + SAVEPOINT tx; 54 tests, 194 pass, ruff/format pass, chaos exit 0, dep delta 0)
- Changed: 8 files mới (4 src + 4 tests, xem Changed Files); tracked files untouched
- Tests: pytest 194 passed (140 cũ giữ xanh); 1 bug tx-nesting phát hiện và sửa trong lúc test
- Decisions: stdlib sqlite3 (không SQLAlchemy), fields agent-defined tối thiểu, sync, FK tối thiểu, audit append-only, không tích hợp ApplicationContext, no-ORM descriptors
- Blockers: không — DoD 27/27 có evidence
- Next: chờ lệnh milestone tiếp theo; KHÔNG T0.7/M1+

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
