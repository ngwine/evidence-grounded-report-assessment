# ADR-003 — Cấu hình retrieval/reranker tạm thời

| Thuộc tính | Giá trị |
|---|---|
| Trạng thái | Provisional; final selection blocked by approved DEV1 |
| Ngày | 19/10/2026 |
| WBS | `W5.5`, `W5.6`, `W7.6` |

## Quyết định hiện tại

1. Giữ BM25 làm baseline bắt buộc.
2. Giữ `intfloat/multilingual-e5-small` làm Dense candidate vì hỗ trợ truy xuất
   semantic và đã chạy được local trên máy Apple Silicon 16 GB.
3. Giữ RRF là cấu hình thí nghiệm, không mặc định tuyên bố tốt hơn BM25.
4. **Không chọn** `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` cấu hình v1 làm
   reranker mặc định. Khi chạy DEV0, nó làm giảm early-ranking so với candidate
   baseline; phần lớn pair bị truncation và một số relevant source bị loại trước
   khi reranker nhìn thấy.
5. Đường chạy local phải có BM25-only fallback khi model semantic không sẵn có
   hoặc vượt resource/time budget.

## Bằng chứng chẩn đoán

Trên 30 parent annotations DEV0, parent-balanced Recall@10 lần lượt là BM25
0,8594; Dense 0,8219; RRF 0,8300; Dense+CE 0,6597; RRF+CE 0,7558. Đây là
component diagnostic, không phải final holdout hay bằng chứng phương pháp tổng
quát. Báo cáo và uncertainty analysis nằm tại:

- `docs/benchmarks/pan-pc-11-cross-encoder-ablation-dev0-result.md`;
- `docs/benchmarks/pan-pc-11-parent-bootstrap-dev0-result.md`.

Kết quả âm được giữ lại: thêm reranker off-the-shelf không tự động cải thiện
Pipeline 1. Candidate gating, support-passage selection và input truncation phải
được kiểm soát như các biến thiết kế riêng.

## Điều kiện mở lại quyết định

- khóa quota-union/evidence-centred input trước khi xem DEV1;
- DEV1 phải được duyệt quyền và parent/source-disjoint với DEV0;
- so cùng corpus, split, hardware, candidate depth và metric;
- lưu recall/MRR/nDCG, timing, RAM, truncation và run manifest;
- TEST0 tiếp tục sealed đến khi config cuối đã khóa.

Cho tới lúc đó, `research-v0` là cấu hình feasibility cần human review, không
phải production model selection.
