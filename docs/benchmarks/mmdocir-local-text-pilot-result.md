# MMDocIR — LOCAL retrieval trên PDF thật

Ngày chạy: 18/10/2026. Code: `research/mmdocir_pilot.py`.

Pilot dùng PDF và annotation chính thức được ghi trong sheet `Dataset mapping`,
dòng 6 của workbook `Quản lý KLTN - 52200229, 523H0087-4.xlsx`. Workbook chọn
MMDocIR để dùng và ghi nhận quyền sử dụng; chưa có ngày phê duyệt một pack/split
cụ thể. Đây là lượt chạy thăm dò trước khi bổ sung pack-approval gate, không
dùng riêng kết quả này làm số liệu cuối cho bài báo. Hai file tải khớp SHA-256
trong workbook:

- `MMDocIR_annotations.jsonl`: `812d14b22d92389a1d9b288c0143b0ffc31fba6d114322e2e75cab2528833e09`.
- `doc_pdfs.rar`: `360e0c7907f1c78012bbc9016623a0ec0d05cb3308ec6ded7c8b46e582b785df`.

Nguồn: [MMDocIR Evaluation Dataset](https://huggingface.co/datasets/MMDocIR/MMDocIR_Evaluation_Dataset).

## Protocol

Từ 213 tài liệu có câu hỏi thuộc type `text-only` hoặc
`['Pure-text (Plain-text)']`, chọn 5 tên tài liệu có SHA256(`20261018:doc_name`)
nhỏ nhất. Chạy toàn bộ 7 câu hỏi thuộc hai type đó trong 5 tài liệu; không chọn
theo kết quả. Tổng cộng 190 trang PDF, 754 chunks:

| PDF | Trang | Chunks |
|---|---:|---:|
| P18-1125.pdf | 12 | 57 |
| NYSE_ACN_2020.pdf | 106 | 455 |
| FBS_PM_29NOV2023_Public.pdf | 32 | 54 |
| N19-1170.pdf | 22 | 116 |
| 2020.emnlp-main.213.pdf | 18 | 72 |

Mỗi PDF đi qua parser/chunker hiện có. Retrieval gọi trực tiếp `_rank_local`
của `research/core_mvp/assessment.py`, chỉ truyền câu hỏi Q; không truyền câu
trả lời A hoặc gold page vào query. So sánh BM25-only và BM25 + E5 + RRF +
Cross-Encoder, cùng candidate depth 12, rerank depth 8, top-k evidence chunks 5.
Các tham số/model giữ nguyên từ `research/configs/core-mvp-v0.json`.

Cache Dense phân biệt query/passage prefix, giữ nguyên embedding để tránh mã
hóa lặp một PDF cho nhiều câu hỏi. Không dùng OCR/ảnh hay dữ liệu parquet đã
trích xuất sẵn của tác giả.

## Kết quả

| Cấu hình | Có trang gold | Recall các trang gold | Đủ tất cả trang gold |
|---|---:|---:|---:|
| BM25 | 7/7 | 1,0000 | 7/7 |
| LOCAL BM25 + E5 + RRF + Cross-Encoder | 7/7 | 1,0000 | 7/7 |

Metric lấy union các `page_index` từ provenance của Top-5 **chunks**, rồi so
với `page_id` của annotation. Một chunk có thể qua nhiều trang; đây không phải
official page-ranking Recall@5 hay bbox-overlap metric. Cả 7 câu được chọn đều
có một trang gold, nên ba metric cùng cho một kết quả; pilot chưa kiểm tra
khả năng gom nhiều trang evidence cho một câu hỏi.

Lượt chạy mất 30,65 giây trên CPU Apple Silicon. Kết quả xác nhận nhánh LOCAL
hiện tại xử lý được PDF chính thức và tìm đúng trang evidence trong pilot nhỏ.
Hai cấu hình đang bằng nhau; chưa có cơ sở khẳng định hybrid tốt hơn BM25.
Chưa đo answer generation, semantic verification, rubric scoring hoặc câu hỏi
đa phương thức.

## Tái lập

Đặt hai file chính thức ở `var/datasets/raw/mmdocir-eval`, cài `unar`, cache
model đúng revision trong config. Trước khi chạy lại, đối chiếu và duyệt
`dataset-manifest.json` cho đúng hai file, năm PDF, mục đích chạy và thời hạn
lưu trữ theo [hướng dẫn pack](../../research/datasets/assessment/mmdocir-local-evidence-pilot-v1/README.md).
Script hiện từ chối chạy nếu manifest còn `PENDING`. Sau khi được duyệt, chạy từ
repo root:

```bash
HF_HOME=var/models/hf-home HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
TOKENIZERS_PARALLELISM=false .venv-research/bin/python -m research.mmdocir_pilot \
  --dataset-manifest var/datasets/raw/mmdocir-eval/dataset-manifest.json
```

Kết quả tại `research/results/rq2-mmdocir/local-text-p5-s20261018` gồm metrics
theo query ID, trang gold/truy xuất, checksum input/code/model config và thời
gian. Script từ chối ghi đè lượt chạy đã có. Dữ liệu raw và PDF không được
thêm vào Git hoặc ZIP benchmark.
