# RQ1 – Phát hiện và truy xuất nội dung tương đồng

## Mô tả

Nghiên cứu kiến trúc phát hiện nội dung tương đồng nhiều tầng, trong đó Hybrid
Retrieval được sử dụng để tăng khả năng tìm kiếm cả trường hợp trùng khớp từ
vựng và tương đồng ngữ nghĩa.

## Các thành phần khảo sát

- BM25 Retrieval
- Dense Vector Retrieval
- Reciprocal Rank Fusion (RRF)
- Semantic Re-ranking (Cross-Encoder)
- Mô hình phân loại dạng tương đồng (verbatim / paraphrase / summary / none)
- Phương pháp tổng hợp similarity từ cấp đoạn lên cấp tài liệu

## Cấu hình so sánh

1. BM25
2. Dense Retrieval
3. BM25 + Dense + RRF
4. BM25 + Dense + RRF + Semantic Re-ranking
5. Pipeline nhiều tầng hoàn chỉnh

Ánh xạ ablation retrieval/reranking hiện tại:

- A1: fixed-window BM25;
- A2: structure-aware Dense;
- A3: A1 + A2, RRF `k=60`;
- A4: A2 candidates + Cross-Encoder;
- A5: A3 candidates + Cross-Encoder.

Ba mươi parent annotation hiện có được giữ cố định dưới vai trò `DEV0` để
phân tích cơ chế và kiểm tra code. Không tiếp tục chọn tham số trên DEV0; model
selection cần development split mới và kết luận cuối cần test split chưa mở.

Hai split kế tiếp đã được dẫn xuất bằng chính sách loại trừ theo manifest:

- `DEV1`: seed `20261012`, loại toàn bộ parent annotation, suspicious document
  và candidate source document của DEV0;
- `TEST0`: seed `20261013`, loại toàn bộ các nhóm trên của cả DEV0 và DEV1.

DEV1 và TEST0 hiện vẫn ở trạng thái governance `PENDING`, vì vậy chưa được chạy
thực nghiệm. TEST0 phải được giữ kín cho đến khi khóa phương pháp và cấu hình
trên DEV1. Xem biên bản kỹ thuật tại
[`pan-pc-11-split-readiness.md`](pan-pc-11-split-readiness.md).

## Chỉ số đánh giá

- Recall@K, MRR, nDCG
- Precision, Recall, F1-score
- F1 theo từng loại tương đồng
- Thời gian truy xuất và xử lý

## Dataset

Pilot công khai tách đúng nhiệm vụ:

- PAN-PC-11: core source-retrieval diagnostic, query là suspicious span đã gán
  nhãn và kết quả được gom theo source document;
- PAN13 Text Alignment: span-retrieval component diagnostic; không dùng số liệu
  Recall/MRR/nDCG này thay cho official Precision/Recall/Granularity/PlagDet.

Dataset trong miền vẫn bắt buộc cho đánh giá end-to-end, gồm các cặp đoạn được
gán `verbatim`, `paraphrase`, `summary`, `none` và hard negatives. Public PAN
corpora không thay thế ground truth báo cáo sinh viên trong miền.

Xem `research/datasets/similarity/`.
