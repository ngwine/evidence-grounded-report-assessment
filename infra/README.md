# Infrastructure

Thư mục dành cho Docker và cấu hình MongoDB. [ADR-001](../docs/adr/ADR-001-mongodb-provenance-storage.md)
đã chọn baseline MongoDB Community 8.0.x chạy bằng Docker Compose dưới dạng
single-node replica set `rs0`. `compose.yaml`, init role/validator/index và
clean-environment smoke test thuộc `W3.1`, nên chưa được tuyên bố là chạy được.

Baseline chỉ expose MongoDB qua `127.0.0.1` khi phát triển, dùng credential
riêng cho API/worker/migration/backup và phải có health check. Không được mặc
định image `mongod` thông thường hỗ trợ Search/Vector Search; lexical/vector
index dùng adapter dẫn xuất và chỉ khóa engine sau benchmark `G-03/W5`.

Khi hiện thực `W3.1`, phải pin patch version hoặc image digest, khởi tạo `rs0`,
bật authentication, dùng secret ngoài Git và kiểm tra migration/index drift
theo [data dictionary](../docs/architecture/data-dictionary.md).
