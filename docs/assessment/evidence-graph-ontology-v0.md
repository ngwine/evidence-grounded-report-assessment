# W11.4 — Evidence Graph ontology v0
| Thuộc tính | Giá trị |
|---|---|
| Phiên bản | `0.1.0-draft` |
| Ngày | 19/10/2026 |
| Owner | Võ Thị Kim Yến (Y) |
| Reviewer | Nguyễn Trần Ngọc Quý (Q) |
| Trạng thái | Design draft; chưa có extraction/persistence |

## 1. Mục tiêu

Ontology này định nghĩa boundary tối thiểu để một node/edge trong Evidence
Graph luôn truy ngược được về report version, chunk, exact span và analysis run.
Nó phục vụ các checklist cần đối chiếu nhiều phần; không biến shared-term chunk
graph hiện tại thành claim graph và không khẳng định extraction đã chạy.

## 2. Node types

| Type | Nội dung | Field bắt buộc |
|---|---|---|
| `CLAIM` | Mệnh đề có thể kiểm chứng | canonical text, claim kind, polarity |
| `CONCEPT` | Khái niệm/thuật ngữ | canonical name, aliases |
| `METHOD` | Phương pháp/thuật toán/quy trình | name, version/config nếu có |
| `RESULT` | Kết quả định lượng hoặc định tính | value/text, unit, dataset/context |
| `CONCLUSION` | Kết luận rút ra trong report | canonical text |
| `SOURCE` | Tài liệu/report hoặc source version đã duyệt | document ID, version, rights state |
| `EVIDENCE_SPAN` | Span nguyên tử nối graph về nội dung | chunk ID, page/locator, raw/normalized range |

Mỗi node trích xuất phải có `node_id`, `graph_version`, `report_id`,
`document_version`, `analysis_run_id`, `extractor`, `model_or_rule_version`,
`confidence`, `created_at` và ít nhất một `evidence_span_id`.

## 3. Relation types

| Relation | Miền → đích | Diễn giải |
|---|---|---|
| `MENTIONS` | SOURCE/EVIDENCE_SPAN → node | Span/tài liệu nhắc đối tượng |
| `USES_METHOD` | CLAIM/RESULT → METHOD | Claim/result dùng phương pháp |
| `EVALUATED_ON` | METHOD/RESULT → SOURCE/CONCEPT | Dataset/bối cảnh đánh giá |
| `SUPPORTS` | EVIDENCE_SPAN/RESULT → CLAIM/CONCLUSION | Evidence hỗ trợ |
| `CONTRADICTS` | EVIDENCE_SPAN/CLAIM → CLAIM/CONCLUSION | Mâu thuẫn cùng ngữ cảnh |
| `REPORTS_RESULT` | METHOD/SOURCE → RESULT | Nguồn/phương pháp báo kết quả |
| `DRAWS_CONCLUSION` | RESULT/CLAIM → CONCLUSION | Quan hệ kết quả–kết luận |
| `REFERS_TO` | node → node | Liên kết tham chiếu trung tính |

Edge bắt buộc có `edge_id`, type, source/target node, confidence, extractor
version và evidence span. `SUPPORTS/CONTRADICTS` không được tạo chỉ từ lexical
co-occurrence; cần verifier riêng và trạng thái review.

## 4. Invariants

- Node/edge không được nối khác report/workspace nếu policy không cho phép.
- `document_version` và `graph_version` không được trộn trong một run.
- Xóa/tombstone source version phải làm graph dẫn xuất không còn retrievable.
- Rebuild cùng input/config phải idempotent; ID dựa trên canonical content +
  provenance, không dựa thứ tự insert.
- Dangling span/node/edge làm build fail closed.
- Người dùng phải mở ngược mọi rationale path về evidence span; không có span
  thì không dùng path để chấm.

## 5. Ví dụ

```text
[METHOD: Hybrid BM25 + Dense]
  ──REPORTS_RESULT──> [RESULT: Recall@10 = 0.83 on DEV0]
  ──EVALUATED_ON────> [SOURCE: PAN-derived DEV0]
[EVIDENCE_SPAN: Results table, page N]
  ──SUPPORTS────────> [RESULT]
[RESULT]
  ──DRAWS_CONCLUSION> [CONCLUSION: CE v1 is not selected as default]
```

Ví dụ chỉ minh họa schema. Extraction phải giữ nguyên dataset/split/context để
không suy diễn kết quả DEV0 thành kết luận tổng quát.

## 6. QA protocol tổng hợp

Trước khi dùng report thật, tạo fixture có ít nhất: one-hop support, multi-hop
method→result→conclusion, direct contradiction, missing edge, duplicate node,
cross-version edge và dangling evidence. Kiểm tra determinism, provenance,
idempotent rebuild, fail-closed isolation và đường LOCAL fallback.

Manual QA/precision cần sample graph trích xuất thật đã duyệt quyền và hai người
review. Vì extraction, persistence, query API và graph worker chưa tồn tại,
`W11.1–W11.3`, `W11.5–W11.6` vẫn chưa thể đóng.
