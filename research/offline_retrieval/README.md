# Offline Retrieval Runner

Runner này cho phép kiểm tra retrieval trước khi có MongoDB, API hoặc worker.
Bốn biến thể chạy trên cùng dataset manifest, query và gold raw span:

1. `fixed_window_bm25` — baseline fixed window + BM25;
2. `structure_bm25` — chunk có cấu trúc + BM25;
3. `structure_dense` — chunk có cấu trúc + embedding model thật;
4. `structure_hybrid_rrf` — hợp nhất BM25/Dense bằng RRF.

Gold evidence được lưu bằng `document_id + [raw_start, raw_end)`, không phụ
thuộc chunk ID. Vì vậy fixed-window và structure-aware chunking được so sánh
trên cùng bằng chứng, không thiên vị một cách chia chunk.

Với source retrieval, đặt `metrics.target_scope=document`. Mỗi scorer gom toàn
bộ chunk đã chấm điểm về source document trước khi cắt top-k, giữ
`candidate_retrieval_depth` source duy nhất cho fusion, rồi mới thực hiện RRF và
tính Recall/MRR/nDCG. Chunk tốt nhất vẫn được giữ trong `supporting_chunk_id` để
truy vết. Nhờ đó một source có nhiều chunk không chiếm nhiều vị trí hoặc đẩy
source khác khỏi bảng xếp hạng.

## Input

Dataset manifest phải khóa checksum cho bốn JSONL:

- `documents`: `document_id`, `version`, `text`;
- `chunks`: `chunk_id`, `document_id`, `text`, `source_spans`;
- `queries`: `query_id`, `text`;
- `qrels`: `query_id`, `document_id`, `raw_start`, `raw_end`, `relevance`.

Runner fail closed nếu governance không `APPROVED`, purpose không có
`RETRIEVAL_EXPERIMENT`, checksum sai, split thiếu document hoặc span vượt biên.
Mọi query trong pilot phải có ít nhất một positive qrel; negative/no-plagiarism
evaluation cần protocol precision/false-positive riêng và không bị âm thầm bỏ
qua bởi runner này.

## Chạy

Tạo môi trường Dense riêng; không dùng `.venv` Python 3.14 hiện tại cho paper
run:

```bash
python3.12 -m venv .venv-research
./.venv-research/bin/pip install -r research/requirements-research.txt
```

Sao chép config mẫu và thay `revision` bằng model revision chính xác hoặc dùng
đường dẫn model local kèm checksum đã khóa. Adapter luôn dùng
`local_files_only=True`; runner không tự tải model:

```bash
cp research/configs/retrieval/pilot-v1.example.json \
  research/configs/retrieval/pilot-v1.local.json

./.venv-research/bin/python -m research.offline_retrieval model-checksum \
  --model-dir /path/to/local/model

./.venv-research/bin/python -m research.offline_retrieval validate \
  --dataset-manifest /path/to/dataset-manifest.json \
  --config research/configs/retrieval/pilot-v1.local.json

./.venv-research/bin/python -m research.offline_retrieval run \
  --dataset-manifest /path/to/dataset-manifest.json \
  --config research/configs/retrieval/pilot-v1.local.json \
  --output-dir research/results/rq1-pilot/run-001
```

Config mẫu cố tình chứa placeholder và sẽ bị validator từ chối cho đến khi
model revision được khóa.

Hai config PAN đầu tiên đã khóa model revision và protocol riêng:

- `research/configs/retrieval/pan-pc-11-pilot-v1.json`: source-document
  retrieval diagnostic;
- `research/configs/retrieval/pan13-component-pilot-v1.json`: source-span
  component diagnostic, không phải official PAN13 text alignment.

Model vẫn phải được tải/cache có chủ đích trước khi chạy; adapter không tự truy
cập mạng.

## Output

- `predictions.jsonl`: raw ranking của cả bốn phương pháp;
- `metrics.json`: Recall@K, MRR@K, nDCG@K theo query và macro;
- `run_manifest.json`: commit/dirty diff, dataset/version/checksum/split/
  governance, resolved config, seed, model/revision, Python/package/hardware,
  stage timing và checksum artifact.

Kết quả test dùng injected encoder luôn mang `result_classification=TEST_ONLY`.
Không được dùng encoder fixture hoặc số liệu synthetic làm kết quả bài báo.

## Test không cần model

```bash
./.venv/bin/python -m pytest research/tests -q
```

Bộ test dùng một encoder được inject rõ là test-only để kiểm tra orchestration,
Dense ranking và RRF; nó không giả danh model embedding nghiên cứu.
