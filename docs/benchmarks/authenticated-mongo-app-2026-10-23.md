# Authenticated Mongo app — kiểm chứng 23/10/2026

Source được tách thành backend commit `619283e` và web/CI commit `b037ea8`
trên `feat/w3-mongo-auth-app`, kế thừa baseline hardening `c9b0405`.
Hướng dẫn và phạm vi: [authenticated Mongo app](../architecture/authenticated-mongo-app.md).
Đây là kiểm thử triển khai, không phải thực nghiệm chứng minh chất lượng AI.

## Kết quả chạy

| Kiểm tra | Kết quả | Phạm vi |
|---|---|---|
| Toàn bộ `research/tests services/backend/tests`, bật URI Mongo private | **513 passed, 1 skipped** | Unit/contract/synthetic và 16 live-Mongo cases; test private DOCX thiếu file vẫn skip, không thay bằng dữ liệu giả |
| Suite Mongo queue/schema/auth/rubric/ingestion | **68 passed** | Có cả unit và live cases; không gọi cả 68 là test database thật |
| Web TypeScript + Vite | **PASS** | Build frontend hiện hành |
| Chromium authenticated UI contract | **3 passed** | Mock API: login/CSRF, workspace quyền, create/edit/publish/clone/version history và 409 |
| Chromium demo hai pipeline cũ | **1 passed** | Web → local API → local worker → hai evidence views → local review |
| Ruff E4/E7/E9/F | **PASS** | Backend, offline retrieval, core MVP, graph |
| Mypy DB catalog | **PASS, 7 files** | Check-untyped-defs, follow-imports silent |
| Mypy auth/domain/API/worker slice | **PASS, 12 files** | Explicit namespace packages; imports skipped/missing third-party stubs ignored, không phải full-repository typing |
| Bandit medium/high | **PASS** | Backend source |
| `git diff --check` | **PASS** | Không có lỗi whitespace |

Bootstrap từ source đã commit cũng đã chạy thành công migrations 001–003;
worker CLI `--once` kết nối đúng worker identity và thoát khi queue rỗng.
Runtime factory kết nối bằng API identity, từ chối request chưa đăng nhập
bằng 401, không fallback thành local Lecturer. Không tạo account mặc định.

Secret scan lịch sử nhận nhầm hai idempotency keys tổng hợp trong HTTP tests
là generic API keys. Đây không phải credential; fixture đã đổi sang ID dễ
nhận biết hơn, không thêm allowlist hoặc giảm rule của scanner.

MongoDB test dùng image 8.0.34 đã pin trong Compose, single-node replica set
`kltn-rs`, project riêng `kltn-auth-app-check`, port loopback 27188. Không dùng
MongoDB của project khác. Test tạo database/user/role tên ngẫu nhiên và chỉ
dọn state do mình tạo. Không tắt kernel guard hoặc dùng admin identity cho
request/worker runtime được kiểm thử.

## Các tình huống thực sự được kiểm tra

- Real scrypt login; session hash/cookie/expiry/CSRF/revocation và current
  membership/credential revision. Student không đọc report/version/job/chunk
  của Student khác; OPERATOR/ADMIN không tự có quyền Lecturer.
- Rubric transaction create/edit/CAS/publish/clone, rollback, concurrent clone,
  publication immutable và phát hiện compiled/definition bị thay đổi.
- Migration 001 giữ nguyên checksum; migration 002 idempotent và từ chối
  TTL/checksum drift. Migration 003 strict catalog được apply/reapply trước
  upload, không dùng collection không validator để làm test pass.
- HTTP upload và PARSE worker dùng **hai tài khoản DB API/worker khác nhau**;
  chạy parser subprocess thật với TXT, PDF hai trang và DOCX có heading/table.
  Kiểm tra chunks trỏ đúng BSON element/version và exact raw span tồn tại.
- Fault injection sau ghi element/trước chunk: transaction rollback, không có
  generation nửa chừng hoặc audit PARSED giả; retry thành công, không nhân đôi.
- Quyền/tombstone/content hash bị thay đổi trước hoặc trong parse; stale lease,
  job-type isolation và exhausted-lease reconciliation.
- Request/form/file giới hạn kích thước, Origin/CSRF, private path/permission,
  symlink/FIFO credential rejection và safe error envelope.

## Lỗi tìm thấy và sửa

Strict-Mongo tests bắt được PDF/DOCX luôn quay về `PARSE_INTERNAL_ERROR`, dù
TXT thành công: `source_refs` offline là danh sách page/paragraph integers,
trong khi collection schema cần locator objects. Worker hiện canonicalize từ
exact source-span locators sau khi gắn BSON element IDs. Không đổi output
legacy của research parser và không nới validator để bỏ qua lỗi. Cả real-Mongo
format tests lẫn always-on regressions đã chạy lại thành công.

## Điều chưa được kết luận

- Chưa có full browser → authenticated Mongo → hai pipelines → lecturer review.
  Web mới quản lý login/workspace/rubric; HTTP mới nối upload/PARSE/chunks.
- `PARSED` không phải index-ready `READY`. INDEX/ANALYZE/run/result/review,
  lexical/vector generation activation và Evidence Graph worker/API vẫn mở.
- Account lifecycle tooling, data approval workflow, backup/restore,
  retention/cascade purge, TLS/network deployment và review chéo chưa hoàn tất.
- Không có approval/consent/gold labels nào được tự tạo cho dữ liệu thật.
  Fixtures tổng hợp chỉ kiểm tra phần mềm, không dùng làm số liệu chất lượng
  retrieval, semantic verification hoặc bài báo.
- Kết quả local không thay thế CI trên chính commit/PR mới hoặc approval của
  reviewer. Baseline CI của PR #19 không được tính là CI cho feature mới này.

Chạy lại theo [hướng dẫn](../architecture/authenticated-mongo-app.md). Không
đưa URI, input report hoặc file trong `var/` vào Git/báo cáo.
