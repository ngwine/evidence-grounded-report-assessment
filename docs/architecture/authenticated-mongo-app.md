# Authenticated MongoDB app — local integration

> Bổ sung: [index → hai pipeline → result/evidence/review](./version-locked-analysis-app.md)
> đã được nối tiếp. Các đoạn mô tả "chưa nối" bên dưới là ranh giới của slice
> auth/ingestion ban đầu; phạm vi hiện hành và phần còn thiếu ở tài liệu mới.

Luồng mới dùng `/api/v1`, MongoDB replica set và hai database identities tách
quyền. Nó không âm thầm chuyển demo `/api/local/v1` sang MongoDB. Hai chế độ
hiện cùng tồn tại để giữ được luồng hai pipeline đã chạy trước đó.

## Phần đã nối

```text
Web authenticated → session/CSRF → current workspace/ownership policy
  ├─ rubric draft → edit/revision → compile → immutable publication → clone
  └─ approved report/source → private file + version + PARSE job (transaction)
       → worker claim/lease → bounded parser → elements/chunks (transaction)
       → GET job/version/chunks with exact source spans
```

- Password dùng scrypt; không có tài khoản hoặc mật khẩu mặc định. Session
  token và CSRF token chỉ được lưu dạng SHA-256 ở server. Cookie HttpOnly;
  token CSRF nằm trong bộ nhớ web, không vào local/session storage.
- Quyền được đọc lại từ user/membership/workspace, không lấy role từ request.
  Student chỉ thấy report của mình; Lecturer làm việc trong workspace được
  gán. OPERATOR/DATA_APPROVER không tự có quyền đọc nội dung học thuật; ADMIN
  không tự trở thành Lecturer.
- Login có throttling và concurrency limit. Session hết hạn tuyệt đối sau
  8 giờ, idle 30 phút; TTL chỉ dọn dữ liệu, không quyết định còn quyền hay không.
- Rubric có draft, version list, CAS bằng `If-Match`, publish immutable và
  idempotency. Published rubric được biên dịch/đối chiếu checksum khi dùng lại.
  Custom score levels và legacy free-text rules chưa được compiler hỗ trợ;
  publish từ chối thay vì diễn giải ngầm.
- Upload giới hạn 20 MiB/file, chỉ PDF/DOCX/UTF-8 TXT/MD. Filename không làm
  đường dẫn lưu trữ; file immutable 0600 trong thư mục riêng 0700. HTTP kiểm
  session/CSRF trước khi nhận body; body và multipart fields đều có giới hạn.
- Cả report và source phải có `governance_record_id` đã APPROVED đúng resource,
  workspace/purpose/thời hạn. Quyền chưa rõ bị chặn trước khi ghi file/job;
  worker kiểm lại current và version-pinned approval trước/sau parse và khi
  commit. Record APPROVED trong fixture chỉ áp dụng cho bytes test tự sinh,
  không phải phê duyệt report hoặc dataset của nhóm.
- Upload metadata/version/job/audit commit cùng transaction. Worker có lease
  fence và transaction cho toàn generation; lỗi giữa elements/chunks rollback,
  retry không nhân đôi. PARSE worker không claim INDEX/ANALYZE/DELETE.
- Chunks trả raw text, normalization map và exact per-element spans. DOCX
  không được gán page giả. Trạng thái cuối là `PARSED`, chưa phải `READY`:
  index generation và analysis jobs chưa được nối vào app này.

## Cách chạy

Từ root repository, cài Python dependencies trong README và npm dependencies.
Commit migration/bootstrap source trước khi apply: ledger phải trỏ đúng code.
Dừng API/worker trong lúc migration; không chạy hai migrator đồng thời.

```bash
.venv-research/bin/python scripts/prepare_mongodb_local.py
docker compose -f infra/mongodb/compose.yaml up -d --wait
.venv-research/bin/python scripts/setup_mongodb_local.py --operator ngwine
```

Tạo user bằng operator CLI; password nhập kín và xác nhận, không đưa vào CLI
argument, tài liệu hoặc Git. CLI dùng migration identity, không public signup.
Thay các ID bằng ID thật được trả về ở từng lệnh.

```bash
.venv-research/bin/python scripts/manage_local_identity.py user --email YOUR_EMAIL --display-name YOUR_NAME
.venv-research/bin/python scripts/manage_local_identity.py workspace --key thesis-dev --name Thesis --purpose INTERNAL_TEST
.venv-research/bin/python scripts/manage_local_identity.py membership --user-id USER_ID --workspace-id WORKSPACE_ID --role LECTURER
.venv-research/bin/uvicorn services.backend.src.kltn_ai.api.runtime:create_runtime_app --factory --host 127.0.0.1 --port 8001
```

Terminal khác:

```bash
VITE_APP_MODE=authenticated npm --prefix apps/web run dev -- --port 5173
.venv-research/bin/python scripts/run_mongo_worker.py --once
```

Web mới hiện cung cấp login/workspace/rubric authoring. Các route report/source
upload, job và chunk đã có ở HTTP; chưa có màn upload tương ứng trong web
authenticated. Approval workflow/UI cho dữ liệu chưa có: người có thẩm quyền
cần cung cấp hồ sơ quyền đúng schema trước upload, không tự đổi dataset
PENDING thành APPROVED để chạy demo.

API và worker mặc định cùng dùng `var/app-mongo`; đổi đường dẫn phải đổi cả
hai. URI riêng ở `var/infra/mongodb/api_app-uri` và `worker_app-uri`, được đọc
từ file private; runtime từ chối admin/root identity, file public hoặc URI
ngoài deployment loopback đã khai báo. Không công khai URI hoặc port ra LAN.

`GET /auth/csrf` cần `X-CSRF-Refresh: 1`; trả token mới sau reload. Refresh ở
tab khác làm token tab cũ hết hiệu lực: reload khi gặp CSRF_INVALID. API không
bật CORS. Cookie chưa Secure chỉ vì app bị giới hạn loopback; không dùng chế
độ này cho LAN/Internet khi chưa có TLS/proxy/session deployment review.

## Schema và test

Migration 001 giữ nguyên checksum. Migration 002 thêm credentials, sessions,
throttles, append-only audit và rubric lifecycle. Migration 003 thêm file,
document/version, governance, elements/chunks và upload idempotency. Chưa phải
toàn bộ collection catalog của ADR. Runtime không có quyền tạo index/migration
hoặc xóa dữ liệu; chưa có cascade purge hay backup/restore được kiểm chứng.

```bash
.venv-research/bin/python -m pytest research/tests services/backend/tests -q
.venv-research/bin/python scripts/test_mongodb_local.py
npm --prefix apps/web run build
cd apps/web
npx playwright test --config playwright.auth.config.ts
```

Script Mongo dùng URI private và chạy test trên database tên ngẫu nhiên riêng;
chỉ dọn dữ liệu do test tạo. `--restart` dành cho Compose project mặc định
`kltn-evidence-db`, không dùng với project tùy biến. Chromium auth tests dùng
mock API để kiểm tra UI contract; HTTP/worker integration dùng Mongo thật.
Hai loại test không thay thế nhau và không đo chất lượng retrieval/assessment.

## Phần tiếp theo

1. Nối INDEX/ANALYZE jobs, lexical/vector generations và immutable run/report
   persistence vào chính boundary này; không sao chép logic pipeline vào web.
2. Thêm web quản lý report/source/version và nối result/review sau auth.
3. Hoàn thiện account lifecycle (disable/reset/revoke), data approval workflow,
   lifecycle/purge, backup/restore và deployment security.
4. Extraction/graph worker, semantic verification và gold evaluation vẫn là
   task riêng; test hạ tầng không chứng minh hiệu quả học thuật của pipeline.
