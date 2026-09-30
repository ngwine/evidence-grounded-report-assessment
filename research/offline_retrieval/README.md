# Offline Retrieval Runner

Runner này cho phép kiểm tra retrieval trước khi có MongoDB, API hoặc worker.
Bảy biến thể có thể chạy trên cùng dataset manifest, query và gold raw span:

1. `fixed_window_bm25` — baseline fixed window + BM25;
2. `structure_bm25` — chunk có cấu trúc + BM25;
3. `structure_dense` — chunk có cấu trúc + embedding model thật;
4. `structure_hybrid_rrf` — hợp nhất BM25/Dense bằng RRF;
5. `multiview_hybrid_rrf` — hợp nhất fixed-window BM25 và structure-aware
   Dense bằng RRF ở cấp source document;
6. `dense_cross_encoder` — rerank Top-N source của Dense bằng Cross-Encoder;
7. `multiview_hybrid_cross_encoder` — rerank Top-N source sau multi-view RRF,
   chấm cả passage BM25 và Dense rồi lấy điểm cao nhất cho mỗi source.

Gold evidence được lưu bằng `document_id + [raw_start, raw_end)`, không phụ
thuộc chunk ID. Vì vậy fixed-window và structure-aware chunking được so sánh
trên cùng bằng chứng, không thiên vị một cách chia chunk.

Với source retrieval, đặt `metrics.target_scope=document`. Mỗi scorer gom toàn
bộ chunk đã chấm điểm về source document trước khi cắt top-k, giữ
`candidate_retrieval_depth` source duy nhất cho fusion, rồi mới thực hiện RRF và
tính Recall/MRR/nDCG. Chunk tốt nhất vẫn được giữ trong `supporting_chunk_id` để
truy vết. Nhờ đó một source có nhiều chunk không chiếm nhiều vị trí hoặc đẩy
source khác khỏi bảng xếp hạng.

`multiview_hybrid_rrf` chỉ hợp lệ với `metrics.target_scope=document`: hai view
dùng chunk ID khác nhau, nên mỗi view phải gom về source document trước rồi mới
có thể fusion một cách có nghĩa.

Hai phương pháp Cross-Encoder cũng chỉ chạy ở document scope. Runner giữ
`pre_rerank_rank`, điểm candidate, điểm Cross-Encoder, support passage/method và
raw span thắng cuộc. Chỉ phần đầu `cross_encoder.rerank_depth` được chấm lại;
phần đuôi candidate được giữ nguyên để Recall@100 vẫn đo cùng candidate pool,
nhưng có `score=null`, `reranked=false` để không giả vờ đã được Cross-Encoder
chấm. Các cặp query–passage giống hệt giữa A4/A5 được memoize; số cache hit và
số cặp thật sự inference được ghi trong run manifest.

Kết quả `DEV0` đã cho thấy một giới hạn quan trọng: reranking không thể cứu
source bị RRF đẩy ra ngoài `rerank_depth`, và đúng source document chưa chắc đã
được đại diện bằng đúng evidence passage. Báo cáo A1–A5 cùng phân tích hai nhóm
36/22 trường hợp nằm tại
`docs/benchmarks/pan-pc-11-cross-encoder-ablation-dev0-result.md`. `DEV0` được
đóng băng sau phân tích này; không điều chỉnh tham số tiếp trên 30 parent đó.

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
- `research/configs/retrieval/pan-pc-11-cross-encoder-dev0-v1.json`: ablation
  A1–A5 trên 30 parent hiện tại. Tập này được khóa là `DEV0` để chẩn đoán;
  không dùng để tiếp tục dò RRF, chunk size hay chọn kết quả cuối.

Model vẫn phải được tải/cache có chủ đích trước khi chạy; adapter không tự truy
cập mạng.

## Output

- `predictions.jsonl`: raw ranking của các phương pháp được chọn trong config;
- `metrics.json`: Recall@K, MRR@K, nDCG@K theo query và query-macro; nếu
  qrels có `parent_annotation_id`, runner ghi thêm parent-balanced macro để các
  annotation sinh nhiều overlapping window không chi phối kết quả;
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

Kiểm tra lại artifact A1–A5 mà không chạy model:

```bash
python3 research/offline_retrieval/analysis/analyze_cross_encoder_ablation.py \
  --predictions /path/to/predictions.jsonl \
  --metrics /path/to/metrics.json \
  --run-manifest /path/to/run_manifest.json \
  --dataset-dir /path/to/pan-pc-11-pilot-v1 \
  --cutoff 10 --pretty
```
