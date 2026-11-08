# Kiểm chứng trước push luồng demo — 25/10/2026

Branch `feat/demo-workspace-ui` nối tiếp
`feat/w8-w10-item-review-evaluation`. Bản này bổ sung direct upload,
rubric mới nhập bằng form, launcher local và tài liệu báo cáo giữa kỳ.
Các kiểm tra dưới đây chạy trên working tree chuẩn bị commit; CI của chính
head PR vẫn phải được kiểm riêng.

## Kết quả

| Kiểm tra | Kết quả |
|---|---|
| Python research/backend không opt-in Mongo/model | 643 passed, 21 skipped; 54,24 giây |
| Python research/backend với dedicated Mongo và cached models sau cập nhật dependency | 663 passed, 1 skipped; 82,98 giây |
| Upload-declaration tests sau đổi tên synthetic operation fixture | 25 passed |
| Mock browser auth/rubric/item review | 6 passed; 18,1 giây |
| Real browser → Mongo → PARSE/INDEX/ANALYZE | 1 passed; 24,7 giây |
| TypeScript/Vite build | PASS |
| Ruff core + launcher; Mypy DB/citation slice; Bandit backend | PASS |
| OpenAPI YAML/schema và 633 internal references; diff whitespace | PASS |
| Python dependency audit và dependency compatibility | Không có known vulnerability; `pip check` đạt |
| Web dependency audit, gồm dev dependencies | high=0, critical=0, moderate=0, low=0 |
| Gitleaks theo image/digest và scope snapshot của CI | Không có leak; không thêm suppression/allowlist |

Một test bị skip khi bật đầy đủ vì private DOCX không có. Test models dùng
cache offline, không tải weight mới và không sử dụng gold dataset đang PENDING.

## Real-browser scope

Test chạy latest `apps/web/tests/authenticated.mongo.ts` với API8002/web5175,
proxy tới đúng API thử nghiệm và chỉ thêm origin5175 vào allowlist của fixture.
Không thay các kiểm tra CSRF/RBAC/quyền tài liệu. Tài khoản/workspace và hai
database identities thuộc database thử ngẫu nhiên; không seed approval,
rubric hoặc kết quả.

Browser chọn file rồi bấm tải lên, không có checkbox xác nhận. Dòng ghi chú
cạnh nút xác định ý nghĩa thao tác; backend tiếp tục ràng buộc declaration
với người dùng, bytes SHA-256, filename, kind và document version. Test kiểm
report/source mới, report version2, rubric nhập từ form rồi publish, BOTH,
evidence, review từng mục, JSON export và reload.

Database/identities của lượt thử đã được dọn, cổng thử đóng. App demo8001/5173
tiếp tục hoạt động; không dừng Mongo hoặc sửa database demo.

## Sửa lỗi phát hiện khi preflight

- Gitleaks nhận nhầm một literal idempotency operation trong fixture thành
  generic API key. Đổi tên thành synthetic test operation; không miễn trừ
  rule hoặc đưa secret thật vào test.
- Python audit phát hiện bốn advisory trong `filelock4.0.7` và
  `setuptools84.0.0`. Kiểm tra lại với `filelock4.2.1` và `setuptools84.1.0`
  đạt; thêm lower bounds tương ứng vào research requirements. Không nâng
  model hoặc thay revision thuật toán.

Các kết quả này xác minh phần mềm và dependency ở thời điểm kiểm tra,
không chứng minh chất lượng semantic classifier/verifier hoặc thay thế
gold độc lập, quyền dataset và review chéo trước merge.
