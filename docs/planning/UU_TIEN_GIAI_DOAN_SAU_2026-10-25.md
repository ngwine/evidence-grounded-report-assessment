# Ưu tiên sau giữa kỳ — cập nhật 25/10/2026

> **Lịch sử — đã thay thứ tự thực thi ngày 08/11/2026.** Theo chỉ đạo mới,
> giữ nguyên phạm vi đăng ký và hoàn thiện cho đủ. Dùng
> [kế hoạch hiện hành](KE_HOACH_HOAN_THANH_PHAM_VI_DE_TAI.md).
> Các đề xuất bên dưới thu hẹp bài vào P1, hoãn GRAPH/câu hỏi hoặc chỉ làm
> component pilot không còn là điều kiện hoàn thành hiện hành. Giữ văn bản
> này để truy vết, không thêm ngày hạn từ các cửa sổ lịch lịch sử.

Đây là đề xuất thứ tự thực thi dựa trên code, WBS và bản bài báo hiện có;
không tự thay baseline, capacity, data approvals hoặc trạng thái quality gate.
Cập nhật 28/10: mục tiêu trước mắt là bài báo nộp khoa, dùng mẫu đang có.
Thứ tự ưu tiên hiện hành xem [kế hoạch hoàn thiện bài báo](../paper/KE_HOACH_HOAN_THIEN_BAI_BAO.md).
Các cửa sổ lịch ở dưới là đề xuất cũ của bản 25/10, không phải hạn nộp đã xác nhận.

Cập nhật 30/10: phần thực hiện P2 có [hướng dẫn QASPER và SEFORA từng bước](../demo/huong-dan-kiem-chung-p2-qasper-sefora.md).
Đã chạy lại QASPER từ code sạch `9b9721d`: 646 câu đủ điều kiện, toàn bộ
aggregate metrics khớp lượt cũ; [bảng so sánh](../../var/paper/p2-preparation-2026-10-30/qasper/new-run-comparison-v1.json)
đã kiểm checksum và cùng dữ liệu/cấu hình. Nhóm 10 bài SEFORA cùng rubric có
phiếu trống, chưa có nhãn người. QASPER kiểm truy xuất bằng chứng LOCAL;
SEFORA cần người chốt checklist và bằng chứng trước khi đo chấm rubric.

## Căn cứ hiện tại

- Đã kiểm tra hai bản trong `docs/paper/`:
  `BaiBao_523H0087_52200229_EN.md` và
  `BaiBao_523H0087_52200229_EN_LNCS.docx`. Không thấy bản bài báo khác mới hơn
  trong `docs`. Hai bản cùng mô tả thực nghiệm DEV0 của Pipeline1.
- Bản thảo đã có đủ bố cục, khoảng 5.360 từ, tám phần, tám bảng và hai hình;
  không cần viết lại từ đầu. Trọng tâm còn thiếu là chốt contribution, bổ sung
  bằng chứng và đồng bộ claim với implementation hiện hành.
- Hai pipeline đã có app chạy được; P1 chưa có calibrated semantic classifier,
  P2 còn phrase/rule verifier; graph mới là structure/term baseline.
- Local preflight đạt 663 Python tests, sáu mocked browser tests và một
  real-Mongo browser test. CI trên PR23 vẫn có lỗi môi trường, cần xử lý riêng.
- WBS đặt benchmark freeze toàn dự án ngày 04/12 và thực nghiệm chính tháng12;
  mốc đó sau hạn bài báo dự kiến. Cần chốt phạm vi bài báo hoặc reforecast
  một cohort/protocol phù hợp, không tự mở TEST0 sớm hoặc bỏ gate.

## Thứ tự ưu tiên toàn dự án

| Ưu tiên | Nhiệm vụ | Hoàn thành khi | Phụ thuộc và phân công đề xuất |
|---|---|---|---|
| 0 — làm ngay | Ổn định CI và tích hợp các PR đã có | PR23 xanh trên đúng head; review chéo PR19→23 theo thứ tự phụ thuộc; cập nhật bases/checks sau merge; main chạy lại được | Q xử lý CI; Q/Y review chéo. Không tự approve/merge để đóng DoD |
| 1 — làm ngay | Chốt phạm vi bài báo, đóng góp và tiêu chí nghiệm thu với GVHD | Có phạm vi/RQs/baselines/metrics; xác nhận ngày/nơi nộp, hardware và mức graph/verification cần đạt; thống nhất rubric template và abstention | Q/Y + GVHD; làm song song với CI |
| 2 — chặn cả nghiên cứu lẫn bài báo | Hoàn thiện quyền dữ liệu, split và gold | Manifest/checksum/rights/PII/retention được xác nhận; split không leakage; hai phiếu độc lập và adjudication cho các task cần human gold | Q chuẩn bị tooling/pack; Q/Y đều gán độc lập, không xem prediction trước; cần data owner/GVHD khi áp dụng |
| 3 — ưu tiên trong tháng | Hoàn thiện thực nghiệm và bản bài báo theo phạm vi đã chốt | Có bảng từ raw artifacts, controlled ablation, uncertainty/error analysis và resource measurements; conclusions đúng evidence; GVHD review; DOCX/PDF đúng mẫu | Q chủ trì runner/số liệu; Y chủ trì viết và audit, Q/Y review; cần ưu tiên2 |
| 4 — core khóa luận, chạy song song | Hoàn thiện năng lực quyết định hai pipeline | P1 đánh giá được bốn nhãn và false positives; P2 semantic verification được kiểm trên evidence/gold, giữ CANNOT_ASSESS và deterministic scoring | Q chủ trì P1, Y chủ trì P2; chia pilot vừa sức, không mở nhiều model cùng lúc |
| 5 — sau LOCAL có baseline đáng tin | Evidence Graph có quan hệ và lợi ích đo được | Một số quan hệ được chốt, extraction có provenance/QA; graph build/query/version nối app khi thuộc scope; LOCAL vs GRAPH/SELECTIVE so trên cùng cases | Q persistence/API/worker; Y ontology/extraction/QA; cần checklist và gold phù hợp |
| 6 — xuyên suốt, đóng trước release | Parser, hiệu năng và trải nghiệm tối thiểu có kiểm chứng | Corpus report thật có quyền dùng; lỗi parse/chunk/evidence được phân loại; latency/RAM theo stage; luồng error/retry/review dùng được trên máy khác | Y corpus/UAT; Q parser/runtime/performance; sửa theo lỗi đo được |
| 7 — viết từ bây giờ | Hoàn thiện luận văn và tài liệu bàn giao | Các chương kiến trúc/hiện thực/phương pháp viết từ artifact đã có; phần kết quả cập nhật từ bảng khóa; thuật ngữ/code/paper thống nhất | Q hiện thực/kiến trúc/P1; Y related work/P2; review chéo, không chờ tháng1 mới viết |
| 8 — đóng gói và bảo vệ | Lifecycle, triển khai, backup/restore và bộ nộp | Account revoke/reset, archive/delete/retention theo scope; clean install/demo; backup có restore thử; tag/checksum/docs/known issues/slides/video/fallback | Q triển khai/runtime; Y tài liệu/hướng dẫn/slide; kiểm chéo và đối chiếu mốc WBS |

### Lỗi CI cần sửa đầu tiên

[PR23 run40116586017](https://github.com/ngwine/evidence-grounded-report-assessment/actions/runs/40116586017)
có ba job pass và hai job fail:

- `python-tests`: tải dependency bị ngắt (`pip incomplete-download`), chưa
  chạy tới pytest. Cần kiểm lại khả năng cài đặt/cache/retry và chạy lại.
- `browser-e2e`: Playwright1.56.1 không hỗ trợ `ubuntu26.04-x64` của
  `ubuntu-latest`. Cần khóa runner được hỗ trợ hoặc nâng Playwright có kiểm
  chứng; không đổi test để che lỗi.

## Bài báo: đường hoàn thành trong khoảng một tháng

### Phạm vi đề xuất

Giữ bài hiện tại tập trung **source retrieval và evidence-centred reranking**;
hai pipeline là bối cảnh kiến trúc. P2 prototype được mô tả đúng mức đã làm,
không coi app E2E là empirical validation cho chấm rubric. Đề xuất này cần
GVHD thống nhất với yêu cầu nơi nộp; nó không tự cắt scope hai pipeline của
khóa luận.

Không bắt bài báo đầu gánh cả classifier bốn nhãn, semantic grading, graph
extraction và nghiên cứu người dùng nếu không đủ dữ liệu/thời gian. Nếu nơi
nộp yêu cầu empirical contribution cho cả hai pipeline, phải chốt lại scope
và capacity ngay, vì khối lượng lớn hơn đáng kể.

### Những việc sửa bản thảo ngay

1. Đồng bộ title, abstract, contributions, RQs và conclusion theo phạm vi.
2. Sửa mô tả P2 từ “chỉ có thiết kế” thành “đã có prototype phrase/rule và app
   integration, chưa có semantic/end-to-end gold validation”.
3. Phân biệt offline PAN source-document retrieval (top100/rerank50) với cấu
   hình passage retrieval của app; giữ đúng cấu hình đã sinh bảng thực nghiệm.
4. Sửa cách nói về compiler và scoring: rubric có cấu trúc được biên dịch,
   chưa tự hiểu rubric tự do; checklist chưa đánh giá được giữ điểm liên quan
   và tổng điểm ở null theo code hiện hành.
5. Cập nhật EXPERIMENT_AUDIT theo snapshot mới; phân biệt pilot ngoài phạm vi
   bài với thực nghiệm chính, không tự nhập số component vào bảng end-to-end.
6. Rà metadata/DOI và nội dung nguồn gốc của references; generator và số bảng,
   captions, hình phải đi cùng bản Markdown mới.

### Phần thực nghiệm cần ưu tiên

- DEV0 tiếp tục frozen để chẩn đoán; không tune lặp lại trên30 parent.
- Regenerate DEV1 từ clean commit, khóa rights/checksum/split và review trước
  khi dùng chọn phương pháp.
- Ablation kiểm soát candidate selection, support passages và truncation;
  giữ BM25/Dense/RRF và reranker làm baseline đối chứng. Không đặt điều kiện
  “Hybrid bắt buộc phải thắng” rồi chọn lại dữ liệu.
- Khóa cấu hình trước holdout; chỉ dùng pack/test đúng quyền và protocol đã
  được duyệt. Nếu cần thay mốc freeze WBS để kịp bài, phải ghi reforecast rõ.
- Đo resource/latency riêng, với workload và cold/warm policy cố định; không
  dùng run có suspended intervals hoặc reuse score như thời gian end-to-end.
- Nếu báo false-positive/no-source rejection, phải có negative cohort và
  metric phù hợp. Positive oracle-span DEV0 không đủ để đưa ra claim đó.

### Lịch mục tiêu cho bài báo

| Cửa sổ | Kết quả cần có |
|---|---|
| 25–30/10 | Chốt scope với thầy; xử lý CI; rà quyền/split; bắt đầu gán nhãn; sửa claim lỗi thời trong bài hiện có |
| 31/10–06/11 | Có pack được duyệt cho thí nghiệm tiếp theo; pilot/controlled ablation và error analysis đầu; checkpoint tính khả thi của contribution |
| 07–13/11 | Khóa cấu hình và hoàn tất phép đánh giá được phép dùng; bảng/hình có provenance; bản thảo đầy đủ gửi GVHD |
| 14–20/11 | Resolve feedback, audit raw→table→claim, clean reproduction, references và DOCX/PDF; bản sẵn sàng nộp |
| 21–25/11 | Dự phòng sửa cuối và nộp theo hạn chính xác được xác nhận; lưu phiên bản nộp và biên nhận |

Nếu đến checkpoint06/11 vẫn chưa có dữ liệu được duyệt hoặc chưa thể đánh
giá độc lập, xin GVHD quyết định mức contribution có thể bảo vệ được và lịch
thực tế. Không đổi tên DEV0 thành holdout hoặc lấy model-visible review làm gold.

## Hai pipeline: phần còn lại để khóa luận đạt yêu cầu

### Pipeline1

- Hoàn thiện positive/negative/no-source/citation cases và guideline bốn nhãn.
- Chọn/hiệu chỉnh classifier trên dev, đánh giá trên split giữ riêng.
- Kiểm exact spans, aggregation, coverage và false positives trên corpus đại diện.
- Báo Recall/MRR/nDCG cho retrieval; macro/per-class F1 và evidence-span
  metrics cho classification/alignment; không trộn hai tầng metric.

### Pipeline2

- Chốt một nhóm rubric/checklist có thể đánh giá, thay vì hứa hiểu mọi rubric.
- Đánh giá retrieval và verification riêng để biết lỗi nằm ở đâu.
- Bổ sung semantic verifier có đầu ra schema/evidence kiểm được; kiểm phủ
  định, mâu thuẫn, thiếu evidence và abstention trên gold.
- Xác nhận với GVHD/giảng viên cách tính điểm, required items, custom levels
  và cách xử lý unknown; chỉ mở loại rule đã thực thi/test được.
- Chỉ mở cross-source verification theo một task và nguồn có thẩm quyền cụ
  thể; tránh gom mọi bài toán fact-check vào một bước.

### Graph

Tập trung ít quan hệ có thể gán nhãn và kiểm provenance, ví dụ kết quả trả lời
mục tiêu hoặc kết luận được evidence hỗ trợ. Chứng minh extraction đúng và
graph giúp nhóm checklist nào so với LOCAL. Nếu trễ, dùng cut-line/reforecast
đã được review; không dùng structure/term PPR để tuyên bố đã có claim graph.

## Những việc không mở rộng trước các điểm chặn

- UI polish lớn, theme/dashboard mới, highlight PDF tới glyph.
- OCR/full multimodal, full Docling/GROBID, AI-writing detector.
- Targeted Questions khi hai pipeline/gold còn chưa đạt gate.
- Thay database/vector engine hoặc chạy nhiều model khi chưa có lỗi/benchmark
  chứng minh cần thay.
- Container hóa toàn bộ stack chỉ để đồng nhất cách chạy, trong khi chưa có
  vấn đề triển khai cần giải quyết. Vẫn phải làm clean-install và hướng dẫn
  tái lập trước bàn giao; Docker có thể là lựa chọn ở bước đó.

## Các mốc toàn khóa luận cần giữ theo WBS

- 20/11: forecast graph assessment gate; chỉ PASS khi đủ evidence/approval.
- 27/11: Research RC1 và feature freeze.
- 04/12: benchmark/dataset freeze toàn dự án.
- Tháng12: thực nghiệm khóa RQ1/RQ2 và lecturer support, phân tích kết quả.
- 08/01/2027: luận văn đầy đủ v1 gửi GVHD.
- 15/01: Release1.0 và bộ bảo vệ nháp.
- 23/01: hạn nộp cứng và lưu submission receipt.

Hai người nên duy trì hai luồng chính: Q tập trung kỹ thuật/thực nghiệm P1,
Y tập trung bài báo/gold/P2; cả hai dành thời gian cố định cho annotation độc
lập và review. Capacity baseline tối đa13SP/người/tuần vẫn giữ; khi thêm việc
bài báo phải trừ phần capacity tương ứng, không cộng như việc ngoài kế hoạch.

## Nguồn đối chiếu

- [WBS và reforecast](./WBS_VA_PHAN_CONG.md)
- [Product backlog](./PRODUCT_BACKLOG.md)
- [Bài báo Markdown](../paper/BaiBao_523H0087_52200229_EN.md)
- [Bài báo Word](../paper/BaiBao_523H0087_52200229_EN_LNCS.docx)
- [Template notes](../paper/TEMPLATE_NOTES.md)
- [Dataset approval](../../research/governance/README.md)
- [Gold workflow](../../research/gold_annotation/README.md)
- [Model decision](../adr/ADR-003-provisional-model-selection.md)
