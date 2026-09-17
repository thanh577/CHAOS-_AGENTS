# STARTUP_INSTRUCTIONS.md — Cách giao việc cho Coding Agent

## Phiên đầu tiên

Gửi agent:

> Đọc `AGENTS.md` trước. Sau đó đọc `CHAOS_STATE.md` và toàn bộ các spec cần thiết trong `docs/spec/`.
> Không code ngay.
> Inspect repository, Git status, toolchain và cấu trúc hiện tại.
> Xác định milestone hiện tại theo `TASKS.md`.
> Nếu repository mới thì bắt đầu từ Milestone 0.
> Báo cáo: hiểu kiến trúc, repo hiện trạng, milestone/task hiện tại, files dự kiến, tests, risks/blockers.
> Không tự ý triển khai milestone khác.

Sau khi agent xác nhận baseline:

> Được. Bắt đầu triển khai Milestone 0 theo `docs/spec/TASKS.md`.
> Chỉ làm Milestone 0.
> Thực hiện từng task theo thứ tự, test sau mỗi task, cập nhật `CHAOS_STATE.md` sau mỗi task.
> Sau toàn bộ milestone, chạy kiểm tra theo `DEFINITION_OF_DONE.md`.
> Không triển khai Milestone 1.
> Báo cáo đúng format trong `AGENTS.md`.

## Phiên tiếp theo

Chỉ cần:

> Đọc `AGENTS.md` và `CHAOS_STATE.md`. Kiểm tra `git status`, diff và commit gần nhất. Tiếp tục đúng từ `Next Action` trong `CHAOS_STATE.md`. Chỉ làm task/milestone đã được giao. Không đọc lại toàn bộ spec trừ khi task hiện tại cần hoặc state/code/spec có mâu thuẫn.

## Khi đổi milestone

Sau khi milestone trước đã được kiểm thử và Done:

> Milestone trước đã được xác nhận. Bắt đầu Milestone X theo `TASKS.md`. Chỉ làm Milestone X. Cập nhật state sau từng task và không nhảy sang milestone kế tiếp.

## Khi agent muốn thay đổi kiến trúc

Yêu cầu agent:
- giải thích lý do;
- nêu files/spec bị ảnh hưởng;
- nêu trade-off;
- cập nhật spec;
- chờ xác nhận nếu vượt scope.

## Khi agent báo Done

Kiểm tra:
- tests;
- diff;
- `CHAOS_STATE.md`;
- Definition of Done;
- không có secret;
- không có raw LLM→shell/filesystem;
- không có architecture drift.
