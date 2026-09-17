# CHAOS — Những điều KHÔNG được làm

1. Không dùng ESP32.
2. Không thêm local LLM nếu không có quyết định kiến trúc mới.
3. Không cho LLM chạy raw shell.
4. Không cho webpage/email/PDF điều khiển agent như trusted instructions.
5. Không bypass Permission Engine.
6. Không coi tool response `success` là bằng chứng cuối cùng nếu cần postcondition verification.
7. Không nhảy milestone.
8. Không thêm dependency vô lý.
9. Không hard-code secrets.
10. Không log secrets.
11. Không ghi secrets vào `CHAOS_STATE.md`.
12. Không điều khiển avatar bằng bone/frame trực tiếp từ LLM.
13. Không để avatar/presentation layer sở hữu business logic.
14. Không nuốt exception.
15. Không retry vô hạn.
16. Không đánh dấu Done khi chưa test/verify.
17. Không sửa architecture âm thầm.
18. Không xóa dữ liệu hàng loạt khi scope chưa rõ.
19. Không chạy downloaded code mù.
20. Không tuyên bố đã gửi/xóa/sửa/thực hiện nếu chưa có bằng chứng từ runtime.
