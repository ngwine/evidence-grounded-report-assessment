# Hoàn thành hệ thống và thực nghiệm theo phạm vi đề tài đã đăng ký

Cập nhật theo chỉ đạo ngày 08/11/2026: **giữ nguyên phạm vi đề tài; hoàn
thiện những gì còn thiếu để đáp ứng phạm vi đó**. Căn cứ là
[mô tả gốc do người phụ trách cung cấp](MO_TA_DE_TAI_GOC.md), không phải
khả năng hiện tại của bản demo hoặc số liệu đã có trong bài báo.

Không cần chốt lại phạm vi hay đổi tên thành một nghiên cứu diagnostics.
Tài liệu này sửa hướng ưu tiên trước đó; không xác nhận thay giảng viên,
không đổi lịch baseline và không tự nâng trạng thái DONE của backlog/WBS.
Không đặt ngày hạn mới.

## 1. Đích hoàn thành

Giữ hai hướng nghiên cứu chính và một hướng hỗ trợ:

1. **P1:** hybrid retrieval → reranking → phân loại verbatim/paraphrase/
   summary/không tương đồng đáng kể → tổng hợp → Similarity Report.
2. **P2:** rubric chuẩn → compiler → LOCAL/GRAPH → xác minh checklist →
   rationale có bằng chứng → mức đánh giá/điểm theo quy tắc → giảng viên duyệt.
3. **Hỗ trợ:** câu hỏi có mục tiêu từ issue/evidence/rubric, Feedback Log và
   báo cáo cuối. Câu hỏi làm sau đầu ra hai pipeline nhưng vẫn phải hoàn thành.

Nền chung phải xử lý PDF/DOCX tiếng Việt/Anh, quản lý báo cáo/nguồn/người
dùng, giữ vị trí và phiên bản để truy vết. Cần thực nghiệm trên benchmark
công khai **và dữ liệu trong miền báo cáo sinh viên**, theo mục 6 đề cương.

Không tự thêm yêu cầu ngoài đề cương: OCR, giao diện song ngữ, đăng nhập
Google, DOI checker, tìm nguồn toàn Internet, highlight từng ký tự hoặc
Docker toàn bộ stack không phải điều kiện mới của kế hoạch này. Cảnh báo
AI-writing/phong cách là phần có thể bổ sung trong đề cương; cảnh báo thiếu
bằng chứng và bất nhất liên quan rubric thuộc phần P2 phải thực hiện.

## 2. Đối chiếu yêu cầu với code và bằng chứng hiện có

“Có code” không đồng nghĩa “đã chứng minh chất lượng”. Các trạng thái dưới
đây là kết quả đối chiếu working tree, chưa phải biên bản nghiệm thu.

| Mục đề cương | Yêu cầu cần đạt | Hiện có | Phần phải hoàn thành |
| --- | --- | --- | --- |
| 3.1, 4 | Người dùng, báo cáo, kho nguồn, upload và version | Auth/session/RBAC, MongoDB, upload và workers chạy thật | Kiểm luồng trên dữ liệu trong miền; hoàn thiện lifecycle và quyền của luồng cuối. |
| 2, 3.1 | PDF/DOCX Việt/Anh, chương/mục/đoạn/vị trí | Parser, chunker, raw spans và locators đã có | Đo lỗi/coverage trên báo cáo thực hai ngôn ngữ; hiện golden parser chỉ hai fixture tổng hợp. |
| 3.1, 4.1 | BM25, dense, RRF, reranking | Đường chạy và index thật đã có | Chọn cấu hình từ đo chất lượng/tài nguyên; khai đúng profile web nào bật thành phần nào. |
| 3.2, 4.1 | Bốn dạng tương đồng | Exact và NLI đề xuất paraphrase có; SUMMARY chưa có | Classifier đủ bốn dạng, hard negatives, trường hợp bất định và kiểm chứng độc lập. |
| 3.2, 4.1 | Tổng hợp và Similarity Report | Exact token coverage chống đếm trùng; viewer/evidence đã có | Tổng hợp các dạng được chấp nhận theo công thức rõ; không đổi tên exact coverage thành tổng tỷ lệ semantic. |
| 3.3, 4.2 | Rubric có tiêu chí/checklist/evidence/trọng số/mức/rule | Template/compiler/version có; điểm proportional và một số rule có | `levels` hiện bị từ chối; triển khai mức đánh giá có điều kiện và tính điểm bằng code xuyên compiler/API/UI/export. |
| 3.3, 4.2 | LOCAL hybrid, bằng chứng báo cáo và kho nguồn | LOCAL có hybrid path; profile LLM chủ yếu BM25; P2 chỉ nhận report chunks | Nối nguồn có provenance và quyền; phân biệt bằng chứng nội dung báo cáo với tài liệu đối chứng. |
| 3.3, 4.2, 5.2 | GRAPH claim/concept/method/result/conclusion và suy luận liên kết | Contract/store đồ thị có; runtime hiện chỉ cấu trúc/chung từ + PPR | Extraction quan hệ có evidence, graph version, query/router và xác minh quan hệ; nối worker/P2/web. |
| 3.3, 4.2 | MET/UNMET/CA và rationale đúng bằng chứng | Verifier V4/Qwen, guards ID/quote/offset có | Sửa mất ngữ cảnh/nhầm người nói/nhầm nguồn; quy tắc vắng nội dung có phạm vi kiểm tra; đo semantic support. |
| 3.3, 4.2 | Phát hiện thiếu căn cứ, bất nhất mục tiêu–phương pháp–kết quả–kết luận | Một số cảnh báo insufficient có; chưa có kiểm chứng quan hệ học thuật đầy đủ | Cases có nhãn, evidence hai phía, quan hệ đúng/sai/không đủ căn cứ; không dùng keyword overlap làm chứng minh. |
| 3.4 | Giảng viên chấp nhận/sửa/bỏ nhận xét và điểm | ACCEPT/REJECT, sửa nhãn/evidence/rationale từng mục và lịch sử có | Sửa/duyệt điểm; overlay kết quả cuối từ quyết định người dùng; giữ đề xuất AI gốc. |
| 3.4, 7 | Feedback Log và báo cáo tổng hợp | Review logs, proposal JSON và item export riêng có | Gộp quyết định, điểm cuối, evidence và lịch sử vào final report; chỉ giảng viên có quyền chốt. |
| 3.4, 5.3, 6.3 | Sinh và duyệt câu hỏi có mục tiêu | Mới có mô tả/protocol/scaffold | Generator, contract, API/UI, review/export và đánh giá bốn tiêu chí đã đăng ký. |
| 6.1 | Đánh giá P1 retrieval + classification | PAN retrieval/CE diagnostics có | Baseline, cohort lớn/phân tầng, bốn lớp, negatives, span/coverage, dữ liệu trong miền và thời gian xử lý. |
| 6.2 | Không retrieval vs LOCAL vs LOCAL+GRAPH | QASPER retrieval component; SEFORA one-step/two-step pilot có | Chạy đúng ba cấu hình; đo evidence, nhãn, rationale, thiếu bằng chứng, điểm so với giảng viên. |
| 6.1–6.3, 7 | Bằng chứng thực nghiệm và sản phẩm web | App E2E kỹ thuật, artifact và bản thảo có | Đánh giá chất lượng đúng task/split; luồng web đầy đủ, nghiệm thu người dùng và bài báo khớp kết quả. |

## 3. Các gói thực hiện và phụ thuộc

Q/Y là phân công đề xuất theo ownership hiện có; không ghi thay việc đã làm
hoặc quyết định nhãn của hai người. Codex triển khai code/tooling/tài liệu
trong phần được giao, không tự biến rà soát AI thành đánh giá của giảng viên.

| ID / ưu tiên | Phụ trách đề xuất | Đầu ra cụ thể | Kết quả cần đạt / kiểm tra | Phụ thuộc |
| --- | --- | --- | --- | --- |
| **D1 — làm song song từ đầu** | Q tooling; Y dữ liệu/rubric | Inventory report–source–rubric VI/EN; guideline P1/P2 và các split có version | Báo cáo thực có quyền dùng; evidence/nhãn có nguồn gốc; chia theo report/source family trước khi tune; mẫu đủ khảo sát các loại muốn kết luận. Không lấy ca AI tự tạo làm gold người. | Tiếp nối dữ liệu hiện có; dữ liệu mới có thể bổ sung trong khi sửa trên DEV. |
| **V1 — sửa chất lượng P2 trước** | Q triển khai; Y kiểm rubric/lỗi | Evidence bundle giữ đoạn liên tục, người phát ngôn, nguồn và vị trí; profile mới | Không đếm tiêu đề/thuật ngữ thành quote; không ghép hai nguồn thành một; không gán ý người được trích cho tác giả; test cả ca đúng và sai, đo lại trên DEV đã xem. | Dùng lỗi đã xác định ở SEFORA làm ca phát triển. |
| **V2 — quyết định đủ căn cứ** | Q contract/verifier; Y guideline | Chính sách verification theo loại checklist, biểu diễn kiểm tra vắng nội dung và giới hạn đầu vào | Selection rỗng/thiếu phần báo cáo → CA. UNMET do vắng yêu cầu chỉ khi rule cho phép và đã kiểm đủ phạm vi; không đổi mọi CA thành UNMET. Evidence thực sự phải hỗ trợ kết luận. | V1; thống nhất rule theo checklist, không sửa nhãn để khớp máy. |
| **R1 — rubric đủ chức năng** | Q compiler/API; Y rubric/UI | Mức đánh giá và điều kiện theo checklist; deterministic scorer; schema/UI/export cùng contract | Nhiều mức, trọng số, required items, sai ID, rule xung đột và CA đều có hành vi rõ. Rubric cũ giữ kết quả cũ; model không tự cho điểm. | Thiết kế contract trước code; làm song song V1/V2. |
| **L1 — LOCAL và nguồn đối chứng** | Q retrieval/worker; Y task/evidence | Evidence pack phân biệt REPORT/SOURCE, version/locator; hybrid/rerank config đo được | Không dùng tài liệu nguồn để giả rằng báo cáo đã viết điều đó; retrieval đúng scope/quyền; chẩn đoán tách lỗi tìm thiếu và đọc sai. | V1; index và hybrid hiện có được tái sử dụng. |
| **G1 — GRAPH thực sự** | Y ontology/QA; Q graph/runtime | Extract claim/concept/phương pháp/kết quả/kết luận; edges có provenance; graph query/router nối P2 | Trả chuỗi evidence kiểm được cho đối chiếu nhiều phần; kiểm cạnh sai, thiếu cạnh, mâu thuẫn và out-of-scope. Chunk adjacency/PPR giữ làm baseline. | D1 + V1/V2; dùng contract/store hiện có, không bắt buộc đổi database. |
| **S1 — P1 đủ bốn dạng** | Q classifier/runtime; Y nhãn/error analysis | Classifier verbatim/paraphrase/summary/none có rationale và spans hai phía | Không suy summary chỉ từ đoạn ngắn hoặc entailment một chiều; hard-negative/cùng chủ đề/citation có kiểm; đo per-class F1 và abstention riêng. | D1; tái sử dụng exact/NLI/hybrid và baseline đã có. |
| **S2 — báo cáo tương đồng đầy đủ** | Q aggregation; Y viewer/QA | Union coverage và tổng hợp nguồn cho các loại đã xác minh, công thức versioned | Không đếm overlap hai lần; chỉ cộng vùng có căn cứ được chấp nhận; phân biệt similarity coverage, score và kết luận đạo văn. Test spans/nguồn/citation trên web. | S1; giữ nguyên metric exact coverage cũ để so. |
| **H1 — giảng viên chốt kết quả** | Q API/log/scorer; Y review UI | Accept/Edit/Reject nhãn, rationale, evidence, điểm; final report có version | Sửa nhãn tính lại đề xuất bằng rule; sửa điểm cuối lưu lý do/before–after; export gồm quyết định người duyệt và giữ nguyên đề xuất AI. Kiểm quyền, reload/concurrent edits. | R1 + V2; tích hợp S2/G1 khi có output. |
| **Q1 — câu hỏi có mục tiêu** | Y generator/đánh giá; Q contract/API | Issue → câu hỏi/evidence/rubric/purpose → giảng viên sửa/duyệt/bỏ → export | Mỗi câu trỏ đúng vấn đề; không bịa căn cứ/đáp án; có kiểm relevance, grounding, answerability và usefulness. | Output P1/P2 có schema/evidence hợp lệ và H1; không bị bỏ vì là hướng bổ sung. |
| **E1 — thực nghiệm P1** | Q runner/metric; Y đối chiếu | Baselines, PAN phân tầng/cohort mới, bốn loại trong miền, error/resource analysis | Đánh giá retrieval và classification riêng, CI theo đơn vị độc lập; khóa DEV trước tập chưa dùng sửa code; giữ cả kết quả âm. | D1 + S1/S2; chi tiết xử lý PAN/CE ở kế hoạch phản biện. |
| **E2 — thực nghiệm P2** | Q runner; Y rubric/nhãn; giảng viên cho phần điểm | LLM không retrieval, LOCAL, LOCAL+GRAPH chọn lọc; cùng report/rubric/split và điều kiện so đã khai | Evidence recall/precision, nhãn từng lớp, semantic support của rationale, nhận biết thiếu evidence, điểm so giảng viên và tài nguyên. Giữ verifier/scorer chung khi so retrieval. | D1 + V2/R1/L1/G1. |
| **E3 — kiểm định hỗ trợ và web** | Y UAT/đánh giá; Q tích hợp/runtime | Luồng upload → hai pipeline → câu hỏi → review → final report; đánh giá câu hỏi và cài/chạy lại | Người dùng mở đúng vị trí, sửa và xuất được kết quả; đo lỗi parser và giới hạn báo cáo dài; test kỹ thuật không thay thang đánh giá chất lượng. | H1 + Q1; hồi quy E2E xuyên suốt. |
| **B1 — bài báo và bộ nộp** | Y nội dung; Q bảng/hình/tái lập; cả hai đọc | Methods/Results đủ hai pipeline và hướng hỗ trợ; DOCX/PDF/code/artifact | Mọi claim khớp đúng dữ liệu/task. Không đổi đề tài để hợp số cũ; không gọi bản có các phần còn thiếu là hoàn thành nghiên cứu. | Viết song song; chốt kết quả theo E1/E2/E3. |

## 4. Thứ tự bắt đầu, không chờ dữ liệu để đứng yên

1. **Bắt đầu V1 + R1; D1 chạy song song.** V1 xử lý nguyên nhân đầu ra P2
   đang sai, R1 đóng khoảng trống chức năng mức đánh giá rubric. Có thể
   viết/test bằng ca DEV và fixture, chưa cần chạy lại cohort đánh giá.
2. V2 và L1 nối tiếp evidence contract; G1 phát triển quan hệ thật.
   S1 làm song song với nhóm P2 khi đã có guideline/dữ liệu phù hợp.
3. S2/H1 ghép kết quả vào web; Q1 nối issue/evidence hợp lệ để sinh câu hỏi.
4. E1/E2/E3 được thiết kế từ đầu, chạy tập đánh giá sau khi khóa phương
   pháp. Không chờ xong toàn bộ UI mới thiết kế nhãn và phép so.
5. Bài báo cập nhật theo từng gói. Có thể gửi bản đang làm cho thầy góp ý,
   nhưng bản đó phải ghi phần thiếu; bản góp ý không thay nghiệm thu đề tài.

Không khởi động lại từ đầu: giữ parser/index, app, contracts, exact/NLI,
rubric lifecycle, logs, graph store và các benchmark đã có. Mỗi thay đổi
phương pháp dùng version/profile/run mới, không ghi đè output cũ.

## 5. Sử dụng đúng các bộ hiện tại

- **PAN DEV0/DEV1:** retrieval/CE development và phân tích bổ sung; chưa đo
  đủ bốn loại/end-to-end. TEST0 không dùng để sửa phương pháp.
- **QASPER:** bằng chứng cho thành phần tìm evidence LOCAL; không phải nhãn
  rubric, GRAPH hoặc điểm báo cáo sinh viên.
- **LIP, SEFORA 10 bài cũ và 15 bài đã xem lỗi:** DEV cho các thay đổi mới.
  Làm sạch lại chính 15 bài không biến chúng thành một holdout chưa xem.
- **SEFORA 07/11:** giữ nguyên 37/45 một bước, 32/45 hai bước, baseline MET
  42/45; nhãn một người có Claude hỗ trợ. Đối chứng này là one-step/two-step
  trên pack báo cáo ngắn, **không phải** ba cấu hình retrieval mục 6.2.
- **Nguồn có feedback lẫn bài:** tạo bản sạch riêng khi có căn cứ, lưu
  removal ledger/hash/offset mới và kiểm lại nhãn chịu ảnh hưởng. Không xóa
  âm thầm, không dùng AI rà soát làm giám khảo thứ hai.

Cần thêm report–rubric trong miền, nhãn checklist/evidence và đánh giá điểm
của giảng viên cho mục tiêu tương ứng. Phương pháp tạo nhãn phải khai thật;
không ép lớp thiểu số bằng cách đổi nhãn, không lấy phân bố gần toàn MET để
kết luận hệ thống đã biết phân biệt cả ba trạng thái.

### Chọn phương pháp tốt hơn làm mặc định

Theo trao đổi tiếp ngày 08/11: triển khai các phương pháp để so sánh đúng
phạm vi, **cấu hình tốt hơn được chọn cho luồng chính**. Không bắt buộc
hybrid, GRAPH hoặc verifier hai bước phải thắng hay luôn được bật.

- So trên cùng report/rubric/split, model và điều kiện đã khai. Chọn bằng
  DEV, sau đó khóa router/config trước lượt đánh giá chưa dùng sửa code.
- Xét nhãn từng lớp/macro F1, false MET, khả năng nhận biết thiếu bằng
  chứng, semantic support và tài nguyên. Không chọn chỉ bằng accuracy
  khi đa số nhãn là MET; không dùng telemetry một lượt không kiểm soát
  làm bằng chứng phương pháp nhanh hơn.
- Nếu GRAPH chỉ có ích cho checklist liên phần, dùng router chọn lọc;
  các checklist LOCAL chạy đường tốt hơn. Nếu chưa thấy lợi ích, giữ graph
  như phương pháp đã triển khai/đánh giá và báo kết quả âm, không buộc nó
  vào mọi request hoặc bỏ yêu cầu nghiên cứu graph khỏi đề tài.
- Nếu chênh lệch còn bất định hoặc lợi ích nhỏ trong khi chi phí tăng,
  ưu tiên phương pháp đơn giản/ổn định hơn theo tiêu chí ghi trước.
  Giữ baseline/code/config và số liệu để tái lập, không xóa phương pháp thua.

37/45 so với 32/45 hiện chỉ nghiêng về một bước trong pilot đã xem; cả hai
chưa chứng minh năng lực đủ ba trạng thái. Luôn MET 42/45 là đối chứng mất
cân bằng, không phải phương pháp chấm được chọn cho sản phẩm.

Trong E2, **không retrieval** nghĩa là LLM đọc báo cáo theo chính sách
context đã khóa, không phải không cung cấp nội dung báo cáo. LOCAL và
LOCAL+GRAPH chọn evidence khác nhau từ cùng nguồn đầu vào hợp lệ; giữ
verifier/scorer chung để so chiến lược retrieval. Khai rõ token/pack/
compute và cách xử lý báo cáo vượt context trước khi chạy. Không ép ba
nhánh nhận cùng evidence pack, vì như vậy không còn đo tác dụng retrieval.

## 6. Tiêu chí hoàn thành và quan hệ với năm nhận xét phản biện

Mỗi gói cần cả phần mềm hoạt động và bằng chứng đúng nhiệm vụ. Tiêu chí,
split và chỉ số dùng chọn phương pháp phải được ghi trước lượt đánh giá;
không tự đặt một tỷ lệ đẹp rồi chọn ca để đạt. Nếu phương pháp mới kém,
giữ kết quả âm, phân tích lỗi và tiếp tục phát triển trên DEV; chưa gọi là
đạt chất lượng chỉ vì API chạy xong.

| Nhận xét | Cách giải quyết giữ đúng đề tài |
| --- | --- |
| 1. Hứa nhiều hơn bằng chứng | Hoàn thành V1/V2/R1/L1/G1/H1 và E2 trên dữ liệu phù hợp; bài báo phản ánh trung thực quá trình và kết quả. Không xử lý bằng đổi tên thành diagnostics. |
| 2. PAN nhỏ, thiếu nhóm | E1 gồm cohort/đối chứng pool lớn hơn, strata/translation và uncertainty; retrieval không thay đánh giá classifier trong miền. |
| 3. CE bị cấu hình chi phối | Giữ kết luận theo checkpoint/input đã đo; controlled contrasts riêng, không mặc định CE phải thắng. |
| 4. Thiếu baseline | Thêm random PAN/QASPER, PAN query/fingerprint; P2 đủ no-retrieval/LOCAL/LOCAL+GRAPH; giữ luôn-MET và báo mất cân bằng. |
| 5. Trình bày/khai báo | Viết song song: chuyển hồ sơ nội bộ dài sang phụ lục, giữ thiết kế khoa học; khai AI/interests đúng thực tế, sinh lại hình/DOCX/PDF. |

Chi tiết phân tích và đối chứng PAN/CE vẫn dùng
[kế hoạch xử lý phản biện](../paper/KE_HOACH_XU_LY_PHAN_BIEN.md).
Những cut-line cũ cho phép bỏ GRAPH hoặc bỏ câu hỏi không còn là tiêu chí
hoàn thành hiện hành. Các ngày/SP/trạng thái lịch sử ở backlog/WBS giữ để
truy vết, không có nghĩa các chức năng còn thiếu đã được nghiệm thu.

## 7. Các điểm code cần sửa tiếp

- **V1/V2:** `research/core_mvp/llm_assessment.py`, `assessment.py`,
  `research/schemas/assessment-report-v1.schema.json` và profile P2 mới;
  `research/p2_comparison/` dùng đo DEV, không sửa lượt đã khóa.
- **R1:** `research/core_mvp/rubric.py`, `rubric_api.py`,
  `services/backend/src/kltn_ai/domain/rubrics.py`, OpenAPI và
  `apps/web/src/RubricVisualEditor.tsx`; hợp đồng mới phải đi hết các lớp.
- **L1/G1:** `research/core_mvp/runner.py`, `assessment.py`, `graph.py`,
  `research/evidence_graph/` và bounded/Mongo analysis worker.
- **S1/S2:** `research/core_mvp/similarity.py`, `semantic_verification.py`,
  similarity schema, analysis profile và `apps/web/src/AuthenticatedResults.tsx`.
- **H1:** `services/backend/src/kltn_ai/domain/analysis.py`,
  `item_annotations.py`, các API review/export và `AuthenticatedItemAnnotations.tsx`.
- **Q1:** bổ sung code dưới `services/backend/src/kltn_ai/modules/questions/`
  cùng contract/research runner; thư mục và README hiện chưa phải tính năng.

## 8. Thực hiện tiếp theo yêu cầu ngày 08/11

- **V1 có implementation nghiên cứu:** `context_bundles_v1` giữ source span
  liên tục và cập nhật prompt về người nói/nguồn quotation. Không đổi mode
  cũ khi bỏ setting này; chưa chứng minh chất lượng chỉ từ unit tests.
- **E2 có runner DEV:** không retrieval vs LOCAL BM25 với cùng verifier/
  scorer; GRAPH ngữ nghĩa vẫn `NOT_IMPLEMENTED_NOT_RUN`. Đây chưa phải
  hoàn thành phép so ba cấu hình hoặc custom rubric levels.
  [Lượt 08/11 đã chạy đủ](../benchmarks/sefora-p2-context-retrieval-dev-2026-11-08.md):
  35/45 và 32/45, chưa cải thiện cấu hình một bước cũ 37/45; không promote
  biến thể mới hoặc gọi đây là kiểm chứng độc lập.
- **Evidence audit:** kiểm vị trí/độ phủ tham chiếu bằng code và phiếu
  semantic support riêng, mọi trường người đánh giá để trống ban đầu.
- **D1 theo chỉ đạo dùng SEFORA:** nguồn bài/rubric đã có; đã lập danh
  sách metadata ứng viên ngoài DEV. Có thể đánh giá P2 trên essay sinh viên
  tiếng Anh, không bắt buộc R1/R2. Chọn cohort và tham chiếu đúng nhiệm vụ
  trước khi đánh giá; điểm rubric gốc không tự thành nhãn ba checklist.

[Readiness và artifacts](../benchmarks/p2-experiment-readiness-2026-11-08.md),
[protocol](../../research/protocols/rq2-assessment/p2-main-study-v1.md).
Trạng thái chất lượng được ghi theo lượt chạy/kiểm thực tế; không tự đóng
story/gate, phê duyệt nhãn hoặc coi cohort DEV là đánh giá chưa từng xem.
