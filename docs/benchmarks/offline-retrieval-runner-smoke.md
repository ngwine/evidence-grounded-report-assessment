# Offline retrieval runner — smoke verification

## Mục tiêu

Xác nhận orchestration chạy được trước khi có MongoDB/API, không đánh giá chất
lượng model nghiên cứu. Fixture gồm ba tài liệu tiếng Việt synthetic, ba query
và gold evidence theo raw span.

## Phạm vi đã chạy

- fixed-window + BM25;
- structure-aware chunk + BM25;
- structure-aware chunk + Dense interface;
- BM25 + Dense → RRF;
- Recall@K, MRR@K và nDCG@K;
- predictions, metrics và run manifest.

Dense smoke test dùng `KeywordFixtureEncoder` được inject trong test và mọi run
đều mang `result_classification=TEST_ONLY`. Đây chỉ là test interface/ranking,
không phải embedding baseline và không được đưa vào bảng kết quả luận văn.

## Kết quả kiểm chứng

- Hai lần chạy độc lập tạo `predictions.jsonl` giống byte-for-byte.
- Hai lần chạy độc lập tạo `metrics.json` giống byte-for-byte.
- Manifest có commit/dirty fingerprint, dataset/version/file checksum,
  governance/split, resolved config hash, seed, encoder revision, hardware,
  stage timing và artifact checksum.
- Validator từ chối dataset không `APPROVED`.
- Gold relevance được đối chiếu bằng `document_id + raw span`, không dùng chunk
  ID nên có thể so fixed-window và structure-aware chunking công bằng.
- Toàn test trên nhánh tại thời điểm chạy: `8 passed, 1 skipped`; test bị skip
  là báo cáo DOCX thật không nằm trong repository.

## Điều kiện trước pilot thật

1. Chọn dataset version có license/consent, checksum, split và approver.
2. Dùng Python 3.12 research environment riêng.
3. Khóa SentenceTransformers model bằng immutable remote revision hoặc checksum
   thư mục model local; runner không tự download.
4. Chạy cùng corpus/split/config/hardware cho bốn phương pháp.
5. Chỉ dùng output có manifest sạch và encoder thật cho phân tích khoa học.
