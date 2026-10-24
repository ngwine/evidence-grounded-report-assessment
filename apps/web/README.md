# Web local demo

## Giao diện authenticated hiện tại

Giao diện có sidebar **Phân tích báo cáo / Kho tài liệu / Rubric đánh giá**.
Form phân tích tự chuẩn bị index của nguồn đã chọn; người dùng không phải nhập
run ID hoặc mở JSON để chạy luồng chính. Hai result tabs hiển thị đoạn report–
source cạnh nhau và checklist kèm evidence; cấu hình/version/hash nằm trong
phần nâng cao. Rubric có form tiêu chí/checklist/requirements; JSON vẫn có để
kiểm tra cấu hình chi tiết. Mọi kết quả và quyền vẫn do backend kiểm tra.

### Chạy nền trên macOS

Sau khi cài dependencies và khởi động MongoDB riêng của dự án theo
[hướng dẫn app](../../docs/architecture/version-locked-analysis-app.md), chạy
từ thư mục gốc repository:

```bash
.venv-research/bin/python scripts/dev_app.py start
.venv-research/bin/python scripts/dev_app.py status
```

Mở `http://127.0.0.1:5173`. Script dùng launchd để giữ web, API và worker chạy
qua lúc đóng chat hoặc terminal. Worker tự được mở lại khi vòng lặp có giới hạn
kết thúc. Logs và launchd plists nằm trong `var/runtime/dev-app/`.

Để khởi động lại hoặc dừng app:

```bash
.venv-research/bin/python scripts/dev_app.py restart
.venv-research/bin/python scripts/dev_app.py stop
```

Các service thuộc phiên đăng nhập macOS hiện tại; chưa tự chạy lại sau
logout hoặc reboot. Script không seed, migrate hoặc reset dữ liệu. MongoDB
cần tiếp tục chạy riêng. Các lệnh foreground dưới đây vẫn dùng được và phụ
thuộc terminal đang mở.

```bash
VITE_APP_MODE=authenticated npm --prefix apps/web run dev -- --port 5173
```

API/worker/MongoDB cần chạy theo
[hướng dẫn app](../../docs/architecture/version-locked-analysis-app.md).
Tài khoản demo không có trong mã nguồn và không được tự tạo khi chạy web.

### Demo trực tiếp từ file và rubric mới

Không cần chạy seed hoặc mở kết quả đã lưu để thực hiện luồng này:

1. Vào **Kho tài liệu**, chọn báo cáo hoặc nguồn đối chứng và chọn file
   PDF/DOCX/TXT/MD (tối đa 20 MB). Với tài liệu do người dùng/nhóm tự tạo, chọn
   **Khai báo tài liệu của tôi/nhóm** và bấm **Tải lên và xử lý tài liệu**.
   Dòng ghi chú cạnh nút cho biết thao tác tải lên xác nhận quyền dùng file,
   đã rà thông tin cá nhân và chỉ sử dụng nội bộ; không cần tick checkbox.
   Đợi trạng thái sẵn sàng; thực hiện tương tự cho nguồn đối chứng.
2. Vào **Rubric đánh giá → Tạo rubric**. Form mới để trống nội dung, không tự
   chèn yêu cầu mẫu. Nhập tên, tiêu chí, trọng số, checklist và các cụm bằng
   chứng cần tìm; thêm cụm thể hiện không đáp ứng nếu cần. Bấm **Lưu draft**,
   rồi **Kiểm tra & publish**. Không cần JSON cho các trường này.
3. Vào **Phân tích báo cáo**, chọn đúng report/source vừa upload và rubric vừa
   publish, chọn cả hai pipeline rồi bấm **Phân tích báo cáo**. Web chuẩn bị
   index, API enqueue job và worker chạy trên các phiên bản đã khóa.
4. Mở các tab đối chiếu nguồn/rubric/evidence, kiểm tra bằng chứng, review và
   export JSON nếu cần. Kết quả được tạo bởi backend/worker thật, không phải
   số liệu nhập sẵn ở giao diện.

Khai báo tài liệu tự tạo chỉ được chấp nhận trong workspace có purpose
`LOCAL_DEMO` hoặc `INTERNAL_TEST`. Backend ràng buộc đúng người khai báo, loại
tài liệu, tên file và SHA-256; không thể tái dùng cho một file khác. Quyền nội
bộ có thời hạn 30 ngày; hết hạn sẽ chặn sử dụng tiếp, **không có nghĩa file sẽ
tự động bị xóa sau 30 ngày**. Đây là sự đồng ý của tác giả, không phải approval
độc lập và không cấp quyền dùng làm gold data, công bố hoặc phân phối lại.
Dataset, bài báo, sách và tài liệu bên thứ ba vẫn dùng **Dùng hồ sơ quyền đã
có** với hồ sơ đã được người phụ trách xác nhận; không chọn khai báo tự tạo
cho những nguồn đó.

Rubric hiện chạy baseline theo checklist và các cụm bằng chứng do người soạn
khai báo. Gõ một yêu cầu tự do mà không chỉ rõ yêu cầu evidence chưa đủ để máy
hiểu và chấm ngữ nghĩa; luồng này cũng chưa xác minh claim với nguồn ngoài.
Demo thao tác thành công không chứng minh chất lượng chấm hoặc độ chính xác
phát hiện paraphrase.

### Dữ liệu minh họa nạp sẵn (không bắt buộc)

`scripts/seed_ui_demo.py --confirm-self-authored-demo` chỉ chuẩn bị hai PDF tự
viết và rubric trong **workspace demo đã được tạo riêng**; không nạp hoặc duyệt
dataset/report thật. Các file `[DEMO]` và banner minh họa không phải số liệu bài
báo. Seed đi qua Document/Rubric/Index/Analysis services và worker thật, không
ghi kết quả giả vào frontend. Chọn một lượt phân tích đã lưu hoặc chạy lại bằng
nút **Phân tích báo cáo** sau khi chọn nguồn.

Phần còn lại bên dưới mô tả chế độ `/api/local/v1` cũ, không phải màn chính
authenticated. Không trộn review hoặc kết quả giữa hai chế độ.

Chế độ `VITE_APP_MODE=authenticated` có login/workspace/rubric authoring,
report/source upload/version, index, hai pipeline, evidence/review và JSON export;
xem [version-locked analysis app](../../docs/architecture/version-locked-analysis-app.md).
Auth
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

`npx playwright test --config playwright.mongo.config.ts` là bộ E2E Mongo thật
riêng: tự tạo database/users/workspace thử nghiệm, **không seed approval,
rubric hoặc kết quả**. Trình duyệt khai báo quyền cho hai file tự viết, upload,
nhập rubric mới bằng form và publish; ba worker chạy để tạo BOTH results, sau
đó kiểm tra review/export/reload. Test dọn đúng state đã tạo. Cần Compose test
loopback riêng chạy sẵn; không dùng dataset/report thật. Cổng 8001/5173 đang
bận sẽ làm test từ chối chạy; không dùng nhầm service demo đang mở.
