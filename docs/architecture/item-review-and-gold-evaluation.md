# Review từng mục và đánh giá bằng gold

Phần này nối tiếp [app hai pipeline](./version-locked-analysis-app.md). Có hai
luồng riêng; chúng không tự chuyển dữ liệu sang nhau.

```text
Kết quả máy đã lưu → review từng cặp/checklist → lịch sử sửa nhãn của người review

Hai phiếu gán nhãn độc lập → adjudication → approved pack → freeze gold
  → predictions đúng ID/version/config → metric tổng hợp + manifest
```

## Review trên app

Sau khi một run `SUCCEEDED`, giảng viên mở mục **Review từng mục**:

1. Đọc cặp report/source hoặc một checklist. Checklist không có evidence truy
   xuất vẫn xuất hiện; giảng viên có thể xem các parser span của report.
2. Chọn nhãn, evidence span và lý do. Với nhãn tương đồng dương, phải chọn
   evidence ở cả report và source; `MET`/`UNMET` cần evidence trong report.
3. Lưu một phiên bản review. Sửa lại tạo phiên bản mới; không ghi đè kết quả
   máy hoặc phiên bản review cũ.
4. Xem lịch sử hoặc export JSON riêng. Các thao tác chỉ trả review của tài khoản
   đang đăng nhập. Không tự công bố điểm hay kết luận đạo văn.

Các span dùng chunk-local raw character ranges, end-exclusive, trỏ tới parser
span đã kiểm provenance; đây không phải hình chữ nhật highlight trên PDF.
Nhãn người review là quyết định của người đó, không phải semantic verification
đã được mô hình xác nhận.

Review này mang `annotation_mode=MODEL_VISIBLE_REVIEW`,
`predictions_visible=true`, `independent_gold=false`. Vì người dùng đã có thể
nhìn thấy dự đoán máy, **không lấy export này làm hai phiếu gold độc lập**.

API mới dưới `/api/v1/workspaces/{workspace}/analysis-runs/{run}`:

- `GET /annotation-items`: item IDs ổn định theo pinned run, exact parser spans,
  nhãn mới nhất của tài khoản hiện tại và `run_revision`.
- `POST /item-annotations`: `If-Match` theo run revision, `Idempotency-Key`,
  nhãn + danh sách span IDs + rationale. Các thay đổi là append-only.
- `GET /item-annotations`: lịch sử có phân trang.
- `GET /item-annotations/export`: JSON riêng, không phải official grade/gold.

Current RBAC, ownership, quyền dữ liệu, retention, tombstones và hash
result/evidence đều được kiểm lại. Quyền bị thu hồi thì không đọc, export hoặc
ghi thêm nhãn được. Stale revision trả `409`; UI giữ nội dung chưa lưu để người
dùng đọc lại state trước khi gửi tiếp. Idempotent retry không tạo nhãn trùng.

Migration `005-model-visible-item-annotations-v1` chỉ thêm collection/index mới;
không sửa checksum migrations 001–004. API chỉ có quyền find/insert trên
`item_annotations`, worker không có quyền đọc/ghi collection này. Bootstrap
vẫn yêu cầu source migration đã commit và dừng writers trước khi apply.

## Gold và metric

[Hướng dẫn gold](../../research/gold_annotation/README.md) mô tả schema context,
protocol, freeze và evaluation CLI. Quy trình yêu cầu:

- Hai người gán nhãn độc lập, trước khi xem predictions hoặc nhãn của người kia;
  ghi rõ hai annotator IDs khác nhau và attestation trong pack protocol.
- Adjudication hoàn tất; không bỏ qua bất đồng evidence chỉ vì nhãn giống nhau.
- Pack có quyền `GOLD_EVALUATION`, version/split/checksum và PII/consent metadata
  theo registry. Code kiểm khai báo và file, không xác nhận thay con người.
- Predictions đúng toàn bộ item IDs, report/source/rubric versions và config đã
  khóa. Thiếu/duplicate/thừa item hoặc đổi metadata thì bị từ chối, không inner
  join để âm thầm loại case khó.
- Abstention là abstention; không đổi `null`/`NOT_RUN` thành `NONE` hoặc
  `CANNOT_ASSESS`. Classification và evidence quality được báo riêng.

Output gold và metric nằm trong thư mục mới dưới `var/`, không commit nội dung
report, quotes, phiếu nhãn hay predictions lên Git. Metric aggregate không có
đoạn trích hoặc item IDs. Chạy test bằng fixture tự viết chỉ kiểm tra công thức
và phần mềm; không phải kết quả chất lượng để đưa vào bài báo.

## Chưa được hoàn thành bởi phần này

Chưa có semantic/cross-source verifier, classifier paraphrase được hiệu chuẩn,
graph extraction/Mongo graph API, geometric PDF highlight, account lifecycle
hay backup/restore. Hai người vẫn cần gán nhãn và adjudicate dữ liệu thật được
phép để có metric thực nghiệm có ý nghĩa.
