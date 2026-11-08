# Luồng demo từ file và rubric mới — 24/10/2026

## Phạm vi

Luồng authenticated cho phép thao tác từ đầu trên web:

`Upload report + source → parse → tạo/publish rubric → index → BOTH → evidence/review/export`.

Không cần seed tài liệu, rubric, approval hoặc kết quả. Tài khoản và workspace
vẫn phải được provision trước; đây không phải tính năng đăng ký công khai.
Các thay đổi này hoàn thiện luồng sử dụng, không bổ sung một mô hình chấm
ngữ nghĩa hay chứng minh hiệu quả khoa học của hai pipeline.

## Các phần đã hiện thực

- Form upload cho phép khai báo quyền với tài liệu do người dùng/nhóm tự tạo.
  Dòng ghi chú cạnh nút upload cho biết thao tác tải lên xác nhận quyền sử
  dụng, đã rà thông tin cá nhân và chỉ xử lý nội bộ; không có checkbox bắt
  buộc. Lựa chọn hồ sơ quyền đã có vẫn được giữ cho nguồn bên thứ ba; payload
  ba xác nhận và policy backend giữ nguyên, ghi nhận theo từng lần tải file.
- `POST /api/v1/workspaces/{workspace_id}/upload-declarations` ghi consent của
  người khai báo, scope nội bộ, SHA-256, tên file, loại tài liệu và thời hạn.
  Upload kiểm tra người khai báo và đúng bytes trước khi ghi file và trong
  transaction. Retry giữ idempotency; khai báo version mới gắn với document
  đang có thay vì chuyển sang document khác.
- Rubric mới có khung trống: tiêu chí, điểm, checklist và yêu cầu evidence.
  Form hỗ trợ các cách diễn đạt và `contradiction_patterns`; không tự suy ra
  các yêu cầu từ tên tiêu chí. Draft phải lưu và publish trước khi chạy.
- Phân tích tiếp tục dùng API/worker thật; report/source/rubric được khóa
  version. Không thay kết quả model bằng dữ liệu giả ở frontend.

## Quyền và giới hạn

Consent tự khai báo chỉ có hiệu lực trong workspace `LOCAL_DEMO` hoặc
`INTERNAL_TEST`, cho việc nội bộ với tài liệu tự tạo mà người khai báo có đủ
quyền và đã rà PII. Consent này không phải quyết định của một DATA_APPROVER
độc lập (`independent_approval=false`); không cho phép phân phối, dùng làm
gold data, công bố hoặc tự duyệt dataset/tài liệu bên thứ ba.

Thời hạn sử dụng là 30 ngày. Các lần dùng sau vẫn kiểm tra quyền hiện tại,
purpose, expiry và tombstone. Chưa có cam kết tự động xóa bytes sau 30 ngày;
physical deletion/lifecycle là công việc riêng.

Rubric chạy baseline theo các yêu cầu và cụm bằng chứng do người soạn nhập,
không phải hiểu/chấm mọi rubric viết tự do. Pipeline 2 chưa xác minh claim
với nguồn ngoài. Pipeline 1 phân biệt exact match với ứng viên chưa được xác
nhận; coverage không phải tỷ lệ đạo văn.

## Kiểm chứng

Các kiểm thử được bổ sung/cập nhật cho luồng này:

- Backend: consent hợp lệ và audit; exact-file mismatch; RBAC/ownership;
  scope nghiên cứu bị từ chối; thiếu xác nhận; retry/conflict; expiry/revocation;
  upload version mới và ràng buộc unique governance version.
- Mock browser: rubric mới trống; nhập và publish bằng form; lưu các cụm
  không đáp ứng; giữ quy tắc published/read-only và conflict.
- Browser → Mongo thật: database thử nghiệm không có approval/rubric/kết quả;
  upload hai file tự viết với các xác nhận rõ ràng; tạo rubric bằng form;
  chạy BOTH qua worker; kiểm tra evidence, review/export và mở lại sau reload.

| Kiểm tra | Kết quả |
|---|---|
| Python `research/tests` và `services/backend/tests`, dedicated Mongo + cached models | 663 passed, 1 skipped (private DOCX không có), 100,06 giây |
| Python không opt-in Mongo/model | 643 passed, 21 skipped |
| Backend upload/declaration/selector, gồm negative cases | 60 passed |
| Mock browser auth/rubric/item review | 6 passed, 17,8 giây |
| Browser → Mongo → worker: file mới, report version 2, rubric mới, BOTH, evidence/review/export/reload | 1 passed, 20,3 giây (lượt kiểm tra cuối) |
| TypeScript/Vite authenticated build; Ruff; Mypy slice; Bandit backend | PASS |
| OpenAPI YAML, schema và internal references; diff whitespace | PASS |

Hồ sơ quyền dùng unique index thật `(resource_type, resource_id, record_version)`.
Khai báo cho version mới cấp record version tiếp theo trong transaction; không
ghi đè hồ sơ cũ. Upload mới cũng cập nhật lựa chọn report version trên web,
không âm thầm dùng version đã chọn trước khi upload.

Các fixture tổng hợp chỉ xác nhận luồng phần mềm, không thay thế gold data
độc lập hoặc thực nghiệm chất lượng trên dataset nghiên cứu.

Lượt kiểm tra trước push ngày 25/10, gồm giao diện không checkbox và audit
dependency mới, được ghi riêng tại [demo preflight](./demo-pre-push-2026-10-25.md).
