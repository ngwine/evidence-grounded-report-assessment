# Scripts

Chứa script bootstrap, lint/test, migration/backfill, rebuild index và đóng gói.
Script phải idempotent khi phù hợp, có help text và không chứa secret.

`dev_app.py` quản lý web authenticated, API và worker chạy nền trên macOS qua
launchd. Từ thư mục gốc repository, dùng
`.venv-research/bin/python scripts/dev_app.py start` để chạy; thay `start` bằng
`status`, `restart` hoặc `stop` để kiểm tra, khởi động lại hoặc dừng. Cần cài
dependencies và chạy MongoDB riêng của dự án trước. Script không seed, migrate
hoặc reset dữ liệu. Service tồn tại trong phiên đăng nhập hiện tại, giữ chạy
khi đóng chat/terminal; chưa tự chạy sau logout/reboot. Worker được mở lại khi
vòng lặp có giới hạn kết thúc. Logs/plists ở `var/runtime/dev-app/`; xem thêm
[hướng dẫn web](../apps/web/README.md).

