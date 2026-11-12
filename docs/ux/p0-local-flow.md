# W2.4 — Luồng P0, wireframe và ma trận quyền
| Thuộc tính | Giá trị |
|---|---|
| Phiên bản | `0.1.0` |
| Ngày đối chiếu | 19/10/2026 |
| Owner | Võ Thị Kim Yến (Y) |
| Reviewer | Nguyễn Trần Ngọc Quý (Q) |
| Trạng thái | Review candidate |
| Phạm vi | Luồng local MVP và đích `/api/v1`; chưa phải UX production |

## 1. Mục tiêu

Luồng P0 cho phép người dùng đưa một báo cáo, nguồn đối chứng và rubric vào một
lượt phân tích; theo dõi job; xem hai nhóm kết quả có evidence; sau đó giảng
viên ghi quyết định review. Giao diện không được trình bày retrieval score như
xác suất đạo văn, không tự công bố điểm và không cho người dùng tự duyệt quyền
nguồn.

## 2. Navigation map

```text
Tạo lượt phân tích
├─ Chọn report
├─ Chọn 1–5 nguồn đã được duyệt quyền
├─ Chọn rubric JSON
└─ Chọn BM25 smoke hoặc Research v0
   ↓
Theo dõi lượt chạy
├─ QUEUED
├─ RUNNING
├─ FAILED / BLOCKED
└─ SUCCEEDED
   ↓
Kết quả
├─ Pipeline 1: coverage chính xác + ứng viên cần review
└─ Pipeline 2: checklist + evidence + điểm đề xuất nếu đủ căn cứ
   ↓
Review local
└─ ACCEPT / REJECT / DEFER + ghi chú + revision conflict
```

Web hiện tại giữ `run_id` gần nhất để mở lại sau refresh. Nó chưa có trang danh
sách report/source/rubric, session đăng nhập hay route theo workspace.

## 3. Wireframe hành vi

```text
┌──────────────────────────── TẠO LƯỢT CHẠY ────────────────────────────┐
│ Report [chọn tệp]                                                     │
│ Sources [chọn nhiều tệp]  Rubric [chọn JSON]                         │
│ (•) BM25 smoke     ( ) Research v0                                   │
│ [Chạy hai pipeline]                                                   │
│ Notice: local-only; nguồn phải được duyệt theo checksum              │
└───────────────────────────────────────────────────────────────────────┘

┌──────────────────────────── TRẠNG THÁI JOB ───────────────────────────┐
│ Run ID · QUEUED/RUNNING/SUCCEEDED/FAILED/BLOCKED                      │
│ Cảnh báo phương pháp và lỗi an toàn nếu có                            │
└───────────────────────────────────────────────────────────────────────┘

┌────────────────────────────── KẾT QUẢ ────────────────────────────────┐
│ [Similarity] [Assessment]                                             │
│ P1: report span | source span | page/offset | trạng thái xác minh     │
│ P2: checklist | MET/UNMET/CANNOT_ASSESS | rationale | evidence       │
│ [ACCEPT] [REJECT] [DEFER] [Ghi chú]                                   │
└───────────────────────────────────────────────────────────────────────┘
```

## 4. Trạng thái bắt buộc

| Màn hình | Loading | Empty | Error/blocked | Success |
|---|---|---|---|---|
| Upload | Khóa nút, hiển thị `Đang gửi tệp…` | Chưa đủ report/source/rubric thì không gửi | Sai extension/signature/rubric; duplicate; report trùng source; nguồn chưa duyệt | Nhận `202`, lưu `run_id` và chuyển sang theo dõi |
| Job | `QUEUED` hoặc `RUNNING`, tự poll | Run chưa sinh artifact | `FAILED`, `BLOCKED`, mất kết nối; không hiển thị kết quả bị thu hồi quyền | `SUCCEEDED`, mở hai tab kết quả |
| Similarity | Skeleton hoặc thông báo đang chạy | Không có match: nêu rằng đây không chứng minh “không tương đồng” | Thiếu/invalid evidence thì không tính coverage | Chỉ exact evidence vào coverage; semantic candidate ở hàng chờ review |
| Assessment | Skeleton hoặc thông báo đang chạy | Không có checklist/evidence | CANNOT_ASSESS giữ điểm tổng `null`; không đổi thành 0 | Hiển thị outcome, rationale, evidence và giới hạn |
| Review | Khóa nút lúc gửi | Chưa có review | Run chưa xong, quyền nguồn bị thu hồi hoặc revision conflict | Lưu quyết định/ghi chú/revision; local record không publish |

Mọi lỗi phải dùng lời giải thích có hành động tiếp theo và không lộ filesystem,
stack trace, secret hay nội dung ngoài quyền.

## 5. Ma trận quyền đích

| Hành động | Student | Lecturer | Admin | Local MVP hiện tại |
|---|---:|---:|---:|---|
| Upload/xem report của mình | Có | Có trong scope | Không mặc định | Không có identity; người đang ngồi máy local |
| Upload/quản lý nguồn đối chứng | Không | Có trong scope | Không mặc định | Operator duyệt checksum bằng CLI; web không tự duyệt |
| Tạo/publish rubric | Không | Có | Không mặc định | Chỉ upload rubric JSON, không publish |
| Chạy similarity/assessment | Không | Có trong scope | Không mặc định | Local operator tạo run |
| Xem evidence của report | Report của mình nếu policy cho phép | Có khi được phân công | Chỉ theo authority record | Không có tenant/workspace; chỉ localhost |
| Accept/Edit/Reject và publish | Không | Có trong scope | Không mặc định | Chỉ ACCEPT/REJECT/DEFER; tên reviewer chưa xác minh; không publish |
| Archive/delete | Có điều kiện | Có điều kiện | Theo authority record | Chưa hiện thực lifecycle |

Đích production lấy actor/role/workspace từ session và authoritative store,
không tin role hay user ID do client gửi. Cross-scope resource phải fail closed.

## 6. Khoảng cách còn lại

- React/Vite hiện có upload, trạng thái, hai tab evidence và local review; build
  production đã được dùng như static smoke check.
- Chưa có authentication, RBAC, navigation nhiều trang, report/source library,
  rubric lifecycle, audit danh tính thật, publish và archive/delete.
- Vì vậy artifact này đóng phần mô tả/wireframe của `W2.4`, nhưng việc review
  chéo và các acceptance test production vẫn cần thực hiện trước khi đánh dấu
  toàn bộ work package là `DONE`.
