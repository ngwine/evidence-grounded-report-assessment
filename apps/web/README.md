# Web local demo

Có thêm chế độ `VITE_APP_MODE=authenticated` cho login/workspace/rubric authoring
qua `/api/v1`, cookie session và CSRF trong bộ nhớ. Xem
[authenticated Mongo app](../../docs/architecture/authenticated-mongo-app.md).
Chế độ mặc định bên dưới vẫn chạy demo hai pipeline `/api/local/v1`; không
trộn kết quả/review local thành kết quả đã xác thực của app mới.

Giao diện React/Vite/TypeScript cho luồng chạy thử hai pipeline. Frontend chỉ gọi
`/api/local/v1`; API lưu input và giao job cho worker riêng. Không có xử lý
parser/model trong trình duyệt, không kết nối MongoDB, và không phải giao diện
production của API contract `/api/v1`.

## Chạy cục bộ

1. Chuẩn bị và chạy backend API/worker theo `services/backend/README.md`. API
   phải lắng nghe ở `127.0.0.1:8001`; các nguồn đối chứng phải được người phụ
   trách phê duyệt quyền/checksum trước khi tạo job.
2. Trong `apps/web`, chạy `npm install`, rồi `npm run dev`.
3. Mở `http://127.0.0.1:5173`. Vite chỉ bind loopback và proxy
   `/api/local/v1` tới API local; không cấu hình CORS/public URL.
4. Chọn một report (PDF/DOCX/MD/TXT), một hoặc nhiều source cùng định dạng,
   rubric JSON theo schema core MVP. `BM25 smoke` là phép kiểm tra tích hợp
   nhanh; `Research v0` dùng cấu hình Dense/RRF/Cross-Encoder đã khóa và có thể
   cần model được cài sẵn trên máy worker.
5. Theo dõi trạng thái job, xem bằng chứng của Pipeline 1 và checklist/evidence
   của Pipeline 2, rồi lưu một phản hồi review **local** nếu cần.

Trình duyệt chỉ lưu `run_id` gần nhất để mở lại sau khi refresh; không lưu bản
sao PDF hay nội dung evidence vào browser storage.

`npm run build` kiểm tra TypeScript và tạo bản static trong `dist/` (thư mục
build không cần đưa vào Git). Khi API trả `409` do nguồn chưa được phê duyệt,
người phụ trách cần xử lý quyền và checksum ở backend; web không có nút tự duyệt.

## Cách diễn giải kết quả

- Pipeline 1 tách khớp nguyên văn có span xác định với ứng viên chỉ cần review.
  Coverage của khớp nguyên văn không phải tỷ lệ đạo văn. Dense/Cross-Encoder và
  heuristic v0 chưa tạo một tỷ lệ tương đồng đã hiệu chuẩn.
- Pipeline 2 hiển thị `MET`, `UNMET`, `CANNOT_ASSESS`, rationale và evidence
  trong báo cáo. Chưa xác minh claim với PDF ngoài. Nếu còn mục không thể đánh
  giá, điểm tổng đề xuất có thể `null`; không nên diễn giải thành 0 hay điểm tối
  đa.
- Nút review chỉ ghi phản hồi với tên người nhập cục bộ; chưa có đăng nhập
  giảng viên, RBAC hoặc publish. Không dùng màn hình này làm kết luận học thuật,
  điểm chính thức hay kết quả nghiên cứu đã được kiểm định.

Dữ liệu upload, kết quả và quyền nguồn do backend local quản lý. Không commit
báo cáo thật, PDF nguồn, rubric nhạy cảm hoặc thư mục `var/` vào repo.

## Browser E2E trên fixture tổng hợp

Bài test Playwright chạy trình duyệt Chromium thật qua web, API và worker local:
trạng thái chưa có kết quả; nguồn chưa duyệt bị chặn; upload report/source/rubric;
hai tab evidence; review cục bộ; và lỗi revision conflict. Chỉ các fixture do
repo tự viết trong `research/tests/fixtures/core_mvp/` được dùng. Bootstrap tạo
`LocalStore` riêng, private trong thư mục tạm và chỉ phê duyệt checksum của
`source-overlap.txt` cho phiên test. Nó không dùng report thật, TEST0, model
download hay thư mục `var/app-local/` hiện có. Cổng 8001 hoặc 5173 đang bận thì
test từ chối chạy thay vì gắn vào server khác.

Từ `apps/web`:

```bash
npm ci
npx playwright install chromium
npm run test:e2e
```

Yêu cầu backend dependencies đã cài trong `.venv-research`. Test này xác nhận
luồng local BM25 smoke và trạng thái giao diện, **không** kiểm định độ chính xác
model, không thay thế review chéo, và không chứng minh auth/RBAC production.
Workflow CI có job `browser-e2e` tạo môi trường Python riêng và tải Chromium để
chạy lại phép kiểm này trên fixture. Một lần chạy thành công trên máy phát triển
không đồng nghĩa job GitHub Actions đã xanh; cần kiểm tra kết quả của chính
workflow trên commit/PR tương ứng.

Auth UI contract tests chạy riêng bằng
`npx playwright test --config playwright.auth.config.ts`: login, CSRF reload,
workspace capability, rubric draft/edit/publish/clone/version history và 409.
Bộ này dùng mock API; real-Mongo HTTP/worker tests nằm ở backend. Chưa coi
mock browser test là browser→Mongo E2E.
