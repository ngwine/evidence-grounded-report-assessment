# P2 DEV: giữ ngữ cảnh evidence và so sánh LOCAL retrieval — 08/11/2026

**Đã chạy thật đủ 90/90 quyết định trên 15 bài SEFORA, không có lỗi kỹ
thuật. Biến thể ngữ cảnh mới chưa cải thiện khớp nhãn; chưa chọn làm mặc
định hoặc dùng làm bảng chính chứng minh hiệu quả P2.**

Lượt này phục vụ yêu cầu triển khai và đo P2, dùng đúng 15 bài/45 mục đã
được xem lỗi. Các bài đó là **DEV**, không phải tập đánh giá mới chưa xem.
Nhãn Yến có Claude hỗ trợ, 42 MET/3 UNMET/0 CANNOT_ASSESS, được giữ nguyên.
[Lượt 07/11](sefora-p2-single-reference-result-2026-11-07.md) không bị ghi đè.

## Thay đổi được kiểm tra

- Policy nghiên cứu `context_bundles_v1` giữ unit trong một source span
  liền mạch, tối đa 1.800 ký tự; không cắt tại dấu chấm của initials như
  `C.S.` hoặc `J.`. Chunks/source spans dài vẫn có thể là phần của paragraph,
  nên không khẳng định mọi unit chứa toàn bộ đoạn gốc.
- Prompt/version mới yêu cầu phân biệt người viết với người được trích,
  kiểm quotation theo đúng số lượng/nguồn, không đếm title/term thành quote.
  Thay unit construction **và prompt** là một can thiệp kết hợp, không cô
  lập tác dụng riêng của từng yếu tố.
- So **LLM không retrieval** (tất cả parsed chunks của báo cáo ngắn dưới
  budget) với **LOCAL BM25 top-5**. Cùng Qwen3.5 4B Q4_K_M, digest, seed,
  verifier một bước, citation cap 3, rubric và deterministic scorer.
- Không retrieval từ chối báo cáo quá budget khi chuẩn bị, không crop hoặc
  âm thầm dùng ranked fallback. LOCAL hiện là BM25, không gọi là hybrid đủ.
- Semantic GRAPH vẫn `NOT_IMPLEMENTED_NOT_RUN`. Không lấy structure/term
  PageRank làm dòng kết quả GRAPH.

Input/code/config/prompt/schema được khóa trước request đầu tiên; không
retry, sửa phương pháp hoặc đổi nhãn giữa lượt. Nhãn/rationale tham chiếu
không truyền vào verifier. 45/45 pack của nhánh không retrieval giống pack
chung của lượt cũ; catalog/prompt thay đổi. Thứ tự hai phương pháp theo hash.

## Kết quả khớp nhãn

| Cấu hình | Khớp / tổng | Tỷ lệ | Macro F1 MET/UNMET | Lỗi kỹ thuật |
| --- | ---: | ---: | ---: | ---: |
| Một bước cũ, 07/11 | 37/45 | 82,22% | 0,4625 | 0 |
| Hai bước cũ, 07/11 | 32/45 | 71,11% | 0,4211 | 0 |
| Ngữ cảnh mới, không retrieval | 35/45 | 77,78% | 0,4487 | 0 |
| Ngữ cảnh mới, LOCAL BM25 | 32/45 | 71,11% | 0,4211 | 0 |
| Baseline luôn MET | 42/45 | 93,33% | 0,4828 | — |

Hai nhánh mới không vượt baseline mất cân bằng hoặc cấu hình một bước cũ.
Luôn MET là đối chứng, không phải phương pháp grading có bằng chứng.
Nhánh không retrieval mới sửa đúng thêm 3 mục nhưng làm lệch thêm 5 mục so
với một bước cũ; net −2. Không chọn riêng những ca cải thiện để kết luận.

| Checklist | Một bước cũ | Không retrieval mới | LOCAL BM25 mới |
| --- | ---: | ---: | ---: |
| CLM001 — Luận điểm của người viết | 12/15 | 13/15 | 13/15 |
| EXP001 — Trải nghiệm phát triển ý | 15/15 | 13/15 | 15/15 |
| QUO001 — Hai quotation cùng nguồn | 10/15 | 9/15 | 4/15 |

Không retrieval mới trả 36 MET/3 UNMET/6 CA; cả ba UNMET lệch nhãn MET
tham chiếu. LOCAL trả 34 MET/0 UNMET/11 CA. Chưa cấu hình nào khớp ba mục
UNMET tham chiếu; bộ không có CA tham chiếu nên không đo được recall CA.

LOCAL trừ không retrieval chênh **−6,67 điểm phần trăm** khớp nhãn. Paired
report bootstrap hậu kiểm mô tả (15 report, 5.000 lượt, seed 20261108) có
khoảng percentile 95% **[−20,00; +8,89] điểm phần trăm**. Khoảng chứa 0;
không kết luận ưu thế thống kê, tương đương hoặc cơ chế nhân quả. Khoảng
không bao gồm bất định do nhãn hoặc lựa chọn phương pháp/cohort.

## Tìm thiếu evidence và đọc sai evidence là hai vấn đề

Nhánh toàn parsed report trung bình 10,2 chunks/checklist; LOCAL có 5.
Trên 42 mục SPAN_SET, độ phủ **ký tự vị trí người gán chọn** của input
lần lượt 100% và 56,79%. Đây là overlap với một lựa chọn tham chiếu, không
phải precision/recall ngữ nghĩa đầy đủ; có thể có evidence thay thế hợp lệ.

Có dấu hiệu lỗi đọc/kết luận ngay khi pack có đủ toàn bài:

- C2-04-ID0029/EXP001: relation là CONTRADICTED nhưng rationale lại mô tả
  các trải nghiệm cụ thể đáp ứng yêu cầu. Schema hợp lệ không bảo đảm
  relation, rationale và proof nhất quán về nghĩa.
- C2-04-ID0029 và C2-08-ID0061/QUO001: model kết luận chỉ có một quote
  phù hợp dù rà soát DEV có căn cứ cho MET. Không sửa nhãn chỉ vì model
  không chọn/đếm đủ; selection của model không chứng minh vắng toàn văn.
- LOCAL chỉ khớp 4/15 QUO001; cần xử lý retrieval theo các điều kiện của
  checklist và bảo toàn attribution, không chỉ tăng độ dài citation.

Các ví dụ là phân tích lỗi sau lượt chạy, không phải tỷ lệ semantic support
đã được giám khảo kiểm trên toàn bộ output.

## Proof audit và phần còn chờ con người

90/90 proof của không retrieval và 59/59 proof của LOCAL trỏ đúng nguồn/
tọa độ. **149/149 source-bound không có nghĩa 149 kết luận đúng.** F1 ký
tự proof so vị trí tham chiếu lần lượt 0,3523 và 0,2607, không dùng riêng
chỉ số này để kết luận rationale tốt hơn vì các đoạn dẫn dài/ngữ cảnh khác.

Đã tạo phiếu che tên phương pháp cho **73 quyết định MET/UNMET**, có báo cáo
và trích dẫn để đọc. Rating/người kiểm/AI assistance đều để trống; mapping
phương pháp lưu riêng. CA và technical được đếm riêng, không được tự xem
là grounded. Chưa có phiếu người trả về nên semantic support rate vẫn null.

Mỗi nhánh có 45 calls; prompt/output tokens được ghi đầy đủ. Thời gian một
lượt có cache và có tác vụ kiểm thử đồng thời, không phải benchmark latency
kiểm soát và không dùng để chọn phương pháp nhanh hơn.

## Quyết định và bước tiếp

Giữ cấu hình cũ và kết quả cũ; chưa promote policy mới thành app default.
Thay đổi biểu diễn/prompt đơn thuần chưa giải quyết chất lượng P2. Tiếp
theo cần xử lý nhất quán relation–rationale–evidence, chính sách UNMET do
vắng nội dung có phạm vi kiểm tra, retrieval quotation/attribution, rồi
mới khóa phương pháp và dùng nhóm SEFORA khác để đánh giá tiếp.

SEFORA vẫn dùng được: nguồn bài/rubric/điểm đã có. Cần chọn cohort theo
rubric/nhóm nguồn và tham chiếu đúng nhiệm vụ; không bắt buộc R1/R2. Điểm
rubric gốc sáu tiêu chí không thay nhãn ba checklist text-only. Graph quan
hệ thật và custom rubric levels còn mở. Không gọi lượt DEV này là hoàn
thành nghiên cứu ba cấu hình hoặc bằng chứng P2 chấm toàn bài hiệu quả.

## Artifacts và kiểm tra

Gốc: `var/paper/p2-main-study-preparation-2026-11-08/`.

- [Kiểm chứng cuối](../../var/paper/p2-main-study-preparation-2026-11-08/final-dev-verification-v1.json).
- [Bảng nhãn và lỗi](../../var/paper/p2-main-study-preparation-2026-11-08/context-retrieval-dev-evaluation-v1/KET_QUA_P2_THAM_DO.md),
  [metrics](../../var/paper/p2-main-study-preparation-2026-11-08/context-retrieval-dev-run-v1/metrics.json),
  [mismatches](../../var/paper/p2-main-study-preparation-2026-11-08/context-retrieval-dev-evaluation-v1/mismatches.csv).
- [Audit evidence/retrieval](../../var/paper/p2-main-study-preparation-2026-11-08/context-retrieval-dev-analysis-v1/evidence-and-retrieval-audit.json).
- [Phiếu semantic support](../../var/paper/p2-main-study-preparation-2026-11-08/semantic-review-v1/PHIEU_KIEM_BANG_CHUNG.csv),
  [hướng dẫn](../../var/paper/p2-main-study-preparation-2026-11-08/semantic-review-v1/README_KIEM_BANG_CHUNG.md).
- [Readiness/candidate inventory](p2-experiment-readiness-2026-11-08.md),
  [protocol](../../research/protocols/rq2-assessment/p2-main-study-v1.md).

Research/backend: **1.387 passed, 21 skipped**; thêm sáu test phân tích
retrieval/bootstrap đạt, các thay đổi evidence-review đã kiểm lại tập liên
quan. Ruff critical và `git diff --check` đạt. Những test này kiểm phần mềm,
không chứng minh chất lượng model. Bản thảo Markdown/DOCX không được thay
bằng một bảng kết quả tích cực không có căn cứ trong lượt này.
