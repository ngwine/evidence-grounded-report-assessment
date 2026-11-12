# W10 technical slice — kiểm tra bằng dữ liệu giả lập

Ngày chạy: 18/10/2026. Đây là phần việc còn làm được của W10 theo bảng
reforecast trong `docs/planning/WBS_VA_PHAN_CONG.md`, không phải kết quả thực
nghiệm trên tập dữ liệu của bài báo. Bảng WBS gốc `W10.1–W10.6` (LOCAL
assessment) đã được reforecast sang W12.

## Đã chạy

- Pipeline 1 dùng một lệnh trên [report và hai source giả lập](../../research/tests/fixtures/similarity_w10/README.md): parse/chunk → BM25 + Dense → RRF và quota-union → Cross-Encoder → exact-span/classification baseline → aggregation → JSON report.
- [Cấu hình](../../research/configs/core-mvp-w10-synthetic-quota-union.json) khóa model revision, seed, candidate quotas và giới hạn hai passage ứng viên cho mỗi source/report chunk. Mặc định cũ vẫn là RRF; cấu hình này chỉ là biến thể chẩn đoán, chưa được chọn làm phương pháp cuối.
- Output cục bộ: `var/results/core-mvp/w10-versioned-fixture-quota-union-2026-10-18/` gồm `similarity-report.json`, `mvp-summary.json` và `run-manifest.json`. Manifest ghi commit, dirty worktree, checksum input/output, model, phần cứng và timing.
- Kết quả smoke: 5 report chunks, 5 source chunks, 2 match `VERBATIM` có exact evidence, thời gian toàn run 5,74 giây trên máy đang dùng. `calibrated_similarity_percentage` vẫn `null`.
- Unit/integration test kiểm tra quota-union cứu ứng viên Dense bị RRF đẩy xuống, budget chống một nguồn chiếm hết top-k, exact overlap không tính hai lần, no-source/hard-negative/quote và provenance của Evidence Pack. Fixture quote chỉ xác nhận độ tương đồng; code **chưa xác minh trích dẫn hợp lệ**.

Lệnh chạy lại có trong [hướng dẫn core MVP](../../research/core_mvp/README.md). Các số trên chỉ chứng minh code nối được và artifact có thể kiểm tra. Không tính F1, không tuyên bố quota-union tốt hơn RRF, không dùng để xác nhận `G-04` hay `G-05`.

## Chưa đóng được

- W10 yêu cầu tích hợp branch quan trọng vào `main` và baseline sạch. Run này ghi `dirty=true`; các PR/branch còn chờ review và merge, nên chưa đạt điều kiện đó.
- Bộ case giả lập chưa được hai người gán nhãn độc lập. Dataset report–source thật còn thiếu xác nhận quyền, kiểm tra PII và gold/adjudication; không được dùng kết quả này thay cho DEV1/TEST0.
- Evidence Pack validator mới ở research-core offline; chưa có persistence, authorization/tenant isolation, timeout/retry đầy đủ hay API sản phẩm. Các mục `W10.1–W10.6` theo lịch gốc vẫn là công việc W12 của bản reforecast.
