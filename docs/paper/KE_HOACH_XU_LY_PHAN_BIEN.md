# Kế hoạch xử lý các nhận xét phản biện

Căn cứ: [audit năm nhận xét](RA_SOAT_CAC_VAN_DE_PHAN_BIEN_2026-11-08.md).
Theo chỉ đạo ngày 08/11, **giữ nguyên phạm vi đề tài đã đăng ký, triển khai
và đánh giá cho đủ**. Kế hoạch chính là
[hoàn thành đúng phạm vi đề tài](../planning/KE_HOACH_HOAN_THANH_PHAM_VI_DE_TAI.md).
Tài liệu này chi tiết hóa năm nhận xét; không dùng đổi tên/thu hẹp bài thành
diagnostics để thay cho phần chức năng và thực nghiệm còn thiếu.
Không đặt ngày hạn mới.

Phân công là đề xuất theo ownership hiện tại: **Quý (Q)** phụ trách dữ
liệu, runner, metric và tái lập; **Yến (Y)** phụ trách rubric, nội dung,
diễn giải và định dạng. Hai người kiểm chéo. Codex hỗ trợ code, bảng và
bản thảo trong việc được giao; quyết định nhãn con người, đóng góp tác giả
và thông tin xung đột lợi ích không được điền thay.

## 1. Thứ tự thực hiện

| Đợt | Ưu tiên | Phụ trách đề xuất | Đầu ra cụ thể | Kết quả cần đạt |
| --- | --- | --- | --- | --- |
| Triển khai — bắt đầu trước | 1 | Q + Y | Đối chiếu đề cương → code → bằng chứng → khoảng trống | Giữ đủ P1/P2/GRAPH/rubric/review/câu hỏi; không cần chốt lại phạm vi. |
| Triển khai | 2 | Q verifier/compiler; Y rubric/QA | Các gói V1/V2/R1/L1/G1 trong kế hoạch chính | P2 đúng ngữ cảnh, có mức đánh giá, nguồn đối chứng và graph quan hệ; dữ liệu D1 làm song song. |
| Triển khai | 3 | Q + Y | S1/S2, H1/Q1 và luồng web hoàn chỉnh | P1 đủ bốn dạng, tổng hợp; giảng viên sửa/duyệt điểm và câu hỏi có bằng chứng. |
| Phân tích/viết song song | Không chặn code | Q xuất số; Y kiểm/viết | Random PAN/QASPER, strata, SEFORA, diễn giải CE, phụ lục và khai báo | Tận dụng kết quả thật đang có, không dùng chúng thay thực nghiệm toàn hệ thống. |
| Thực nghiệm P1 | Theo dependency | Q runner; Y kiểm | Baseline query/fingerprint, cohort lớn, pool-size và controlled CE | Giải quyết hạn chế PAN; bổ sung đánh giá classifier trong miền theo E1. |
| Thực nghiệm P2/hỗ trợ | Thiết kế ngay, chạy sau khóa phương pháp | Q runner; Y nhãn; giảng viên đánh giá | No-retrieval/LOCAL/LOCAL+GRAPH, nhãn/evidence/điểm, câu hỏi | E2/E3 đúng thiết kế đề cương; không thay bằng one-step/two-step hoặc QASPER. |
| Bài báo/bộ nộp | Viết xuyên suốt; chốt sau đánh giá | Q + Y | Markdown, Word, PDF, artifacts và bảng trả lời nhận xét | Phương pháp và bằng chứng đáp ứng đề tài; bản góp ý trung gian chỉ rõ phần chưa xong. |

V1/R1 và D1 bắt đầu trước; phân tích/viết làm song song. Không xếp GRAPH,
semantic assessment và câu hỏi vào phần có thể bỏ sau bài báo. Các mục
R2/R3/R4 dưới đây vẫn giải quyết hạn chế PAN/CE thực sự; sửa câu chữ không
thay thế được triển khai, tăng dữ liệu và thêm đối chứng.

## 2. Nhận xét 1 — tiêu đề và bằng chứng rubric

### R1.1 — Đối chiếu và hoàn thiện theo phạm vi đã đăng ký

**Phụ trách:** Q + Y. **Đầu vào:** audit đã có, bắt đầu được ngay.

- Dùng bảng yêu cầu → code → đánh giá → khoảng trống ở kế hoạch chính;
  không xin chốt lại phạm vi hoặc tự đổi tên bài thành diagnostics.
- Hoàn thiện P1 bốn dạng và tổng hợp, P2 LOCAL/GRAPH/verifier/rubric levels,
  giảng viên sửa/duyệt điểm và hướng câu hỏi; giữ benchmark và dữ liệu trong miền.
- Lập bảng claim → loại bằng chứng → artifact → giới hạn cho bản đang làm.
  QASPER chỉ kiểm retriever, SEFORA hiện chỉ pilot ba checklist; không tự
  gọi hai kết quả này là thực nghiệm hoàn chỉnh của P2.
- Đồng bộ Abstract, RQs, Results và Conclusion theo phần đã thực sự làm;
  các khoảng trống tiếp tục triển khai, không loại khỏi mục tiêu cuối.

**Đầu ra:** đối chiếu đủ phạm vi và các gói triển khai/đánh giá có dependency.
**Hoàn thành khi:** không bỏ yêu cầu để khớp số cũ; mọi claim hiện tại có
bằng chứng đúng task/cohort; không tuyên bố P2 hiệu quả trái số liệu.

### R1.2 — Đưa SEFORA vào đầy đủ, giữ đúng nguồn gốc nhãn

**Phụ trách:** Y viết; Q tạo bảng từ JSON. **Phụ thuộc:** R1.1.

- Thêm §4.7 thiết kế, §5.7 kết quả; đồng bộ Table 2, Discussion,
  Limitations, Abstract/Conclusion và hình nếu mô tả bị ảnh hưởng.
- Báo 15 bài/45 mục, một người gán có Claude hỗ trợ, ba checklist, dữ liệu
  và phương pháp khóa trước suy luận. 45 mục không phải 45 bài độc lập.
- Trình bày **37/45**, **32/45**, baseline MET **42/45**, macro F1 trên lớp
  có mẫu, từng checklist, CA và lỗi kỹ thuật. V4 chưa chạy trên cohort này
  thì không trình bày nó như baseline đã có kết quả.
- Tách source traceability khỏi semantic support; budget bằng nhau mỗi
  request khỏi tổng compute. Telemetry một lượt không chứng minh latency.
- Ghi lệch quy tắc UNMET do vắng nội dung và ít nhất ba body có đoạn giống
  feedback. Báo nguồn đúng như đã chạy, không gọi là essay text thuần sạch.
- Giữ phiếu Yến và output gốc. Rà soát AI 14/15 mục không tạo annotator
  thứ hai; mục CLM001 của C2-08-ID0061 còn cần thống nhất centrality.
  Mọi quyết định thực tế mới của người phụ trách lưu riêng có version.
- Nếu Q làm thêm phiếu sau khi xem báo cáo bất đồng, ghi đúng exposure;
  không gọi phiếu đó hoàn toàn mù. Không bắt buộc thêm cả phiếu mới để
  đưa pilot hiện tại vào bài.

**Đầu ra:** mục P2 đầy đủ, bảng tái tạo từ
`var/paper/p2-single-reference-eval-2026-11-07/evaluation-v1/` và limitations.
**Hoàn thành khi:** số khớp artifact; kết quả âm/giới hạn xuất hiện cả
Methods lẫn kết luận; không thay nhãn cho khớp máy hoặc dùng AI làm người duyệt.

## 3. Nhận xét 2 — PAN nhỏ, CI rộng, thiếu phân tầng

### R2.1 — Phân tích bổ sung trên output hiện có

**Phụ trách:** Q viết script; Y đối chiếu bảng. **Bắt đầu được ngay.**

1. Join parent ID với XML đã kiểm checksum, giữ loại plagiarism,
   obfuscation và ngôn ngữ. Không đổi MISSING thành “không obfuscation”.
2. Xuất Recall@10, MRR@10, nDCG@10 và n parent từng nhóm; giữ DEV0/DEV1
   riêng. Dùng aggregation/resampling theo parent hoặc document group nếu
   một document có nhiều parent, không đếm windows thành mẫu độc lập.
3. Viết đúng 3/4 CI chênh Recall@10 DEV0 chứa 0, A4−A2 là ngoại lệ. Không
   suy hai phương pháp tương đương khi CI chứa 0.
4. Ghi phân tầng là hậu kiểm; nhóm translation n=3/n=2 chỉ dùng mô tả.

**Đầu ra:** script phân tầng, bảng theo loại/obfuscation/ngôn ngữ, bảng CI.
**Hoàn thành khi:** tổng parent từng nhóm khớp 30/cohort, chỉ số toàn bộ
khớp số cũ, không chạy model hoặc sửa dự đoán gốc.

### R2.2 — Chuẩn bị PAN lớn hơn

**Phụ trách:** Q chuẩn bị, Y kiểm protocol. **Phụ thuộc:** tác vụ và
baseline R4.2 đã định nghĩa; đo tài nguyên trước lượt lớn.

Mục tiêu lập kế hoạch khoảng **100–150 parent độc lập, pool 1.000 nguồn**
cho một cohort mới; cần xác định riêng DEV và tập đánh giá chưa xem. Đây
là mốc ước lượng tài nguyên, không phải ngưỡng chứng minh đủ power.

- Sampling theo strata trước khi nhìn lỗi. Nếu tăng translation có chủ
  đích, báo số mẫu và quy tắc trọng số, không giả đó là tỷ lệ tự nhiên.
- Ưu tiên một parent/suspicious document; nhóm nguồn trùng/bản liên quan
  để tránh leakage giữa development và evaluation.
- Giữ DEV0/DEV1/TEST0 cũ nguyên trạng. Lập protocol, manifest, split và
  kiểm overlap riêng; chốt quy mô cuối trước suy luận đánh giá.
- Với M4 16 GB, đo chunk count, RAM, embedding time, cache và CE requests
  trên pilot tài nguyên bằng DEV. Có thể khóa một representative window
  mỗi parent theo quy tắc xác định trước; mô tả đúng đơn vị query mới và
  không chọn cửa sổ theo khả năng model trả đúng.

**Đầu ra:** protocol cohort/split mới, manifest, kiểm leakage, feasibility.
**Hoàn thành khi:** dữ liệu, số parent/group, pool, sampling, query và
metric khóa rõ; không cam kết CI phải loại 0 hoặc điểm phải tăng.

### R2.3 — Chạy ảnh hưởng pool và đánh giá cuối

**Phụ trách:** Q chạy; Y kiểm artifact. **Phụ thuộc:** R2.2, R4.2 và R3.2
nếu CE thuộc cấu hình cuối.

- So pool 200/1.000 trên **cùng parent/query**; pool nhỏ là tập con pool
  lớn, cả hai có relevant sources đã biết. Nguồn bổ sung lấy theo chính
  sách khóa trước, không theo phương pháp nào thắng.
- So BM25, Dense, RRF, baseline mới và CE đã chốt với input/budget rõ.
  Báo random theo N, early ranking, CI theo nhóm độc lập và strata.
- Khóa phương pháp trên DEV trước khi chạy cohort chưa dùng sửa code.
  Nếu chỉ dùng TEST0 nhỏ hiện có vẫn phải nêu hạn chế cỡ mẫu; muốn giải
  quyết quy mô cần tập đánh giá lớn riêng.
- Chỉ bổ sung negative/no-source cohort khi muốn tuyên bố precision hoặc
  rejection; positive-only source retrieval phải giữ đúng phạm vi đó.

**Đầu ra:** pool-size comparison và lượt đánh giá mới có manifest.
**Hoàn thành khi:** phép so cùng dữ liệu kiểm chứng được, không trộn delta
khác cohort, không thử nhiều cách trên TEST rồi thay lượt đầu.

## 4. Nhận xét 3 — Cross-Encoder và cấu hình

### R3.1 — Hoàn thiện diễn giải hiện có

**Phụ trách:** Y viết; Q kiểm số. **Làm ngay, không cần model run.**

Nêu domain mismatch mMARCO/query–passage; giữ số truncation DEV0 và đối
chứng A5/A6 DEV1; nói rõ A6 loại truncation bổ sung nhưng chưa cải thiện
rõ Recall@10. Tách giả thuyết domain, support selection, hard gating và
mất nội dung. Không quy phần lớn lỗi cho một nguyên nhân chưa được cô lập.

**Đầu ra:** Results/Discussion/Conclusion thống nhất.
**Hoàn thành khi:** kết quả âm gắn cấu hình đã thử, không kết luận CE nói
chung kém hoặc input ngắn tự giải quyết lỗi.

### R3.2 — Đối chứng CE kiểm soát hơn

**Phụ trách:** Q chạy; Y kiểm protocol. **Sau baseline và feasibility đợt B.**

1. Chốt input policy trên DEV, ghi tokenizer-visible strings, độ dài và
   nội dung bị crop; không chỉ ghi max_length.
2. Cố định candidate/support IDs, thứ tự đầu vào, top-50 gate, scoring,
   pooling và tail trong từng contrast.
3. So no-CE/CE trên input đã khai. Nếu so input policies thì nói rõ yếu tố
   thay; thay checkpoint là contrast riêng, dùng cùng input.
4. Chỉ mở thêm checkpoint sau khi kiểm tài liệu nguồn, license, revision,
   khả năng chạy và câu hỏi cần đo. Không để việc đổi model chặn các gói
   chức năng còn thiếu hoặc biên tập từ kết quả đã có.

**Đầu ra:** protocol/control matrix; recall, rank transitions, truncation,
support coverage và telemetry.
**Hoàn thành khi:** mỗi kết luận có contrast tương ứng. Đổi cả query crop
và passage selection vẫn là input-construction comparison, không phải phép
cô lập truncation. Giữ kết quả âm nếu không thấy cải thiện.

## 5. Nhận xét 4 — thiếu baseline

### R4.1 — Random baseline, làm trước

**Phụ trách:** Q xuất bảng; Y kiểm. **Đầu vào đã có.**

- PAN: expected Recall@10 **5%**, Recall@100 **50%** trên pool 200 có một
  relevant source/query; công thức K/N. Không gán các mức này cho random
  reorder một danh sách ứng viên đã được retriever lựa chọn.
- QASPER: expected Hit@1/5/10 **4,76% / 21,53% / 38,56%**, đúng 646 câu.
  Ghi đây là baseline phân tích hậu kiểm, không prespecified.
- Giữ đủ metric đã có của BM25/E5/RRF. Random chỉ điền metric đã tính,
  không dùng Hit thay Complete hoặc MRR.

**Đầu ra:** bảng baseline, công thức và provenance ngắn trong Methods.
**Hoàn thành khi:** cùng cohort/pool/metric, tính lại được và không đổi số cũ.

### R4.2 — Baseline PAN chuyên tác vụ

**Phụ trách:** Q triển khai; Y kiểm tính công bằng. **Phụ thuộc:** R1.1.

- Short-query BM25: tạo query ngắn theo quy tắc từ chính oracle window,
  chọn/khóa số và loại term trên DEV. Full-report query discovery là task
  riêng, không trộn vào cùng bảng.
- Fingerprint/shingle retrieval: word-shingle hoặc winnowing, mô tả
  normalization, tham số và score; đây là retrieval thật, khác SHA file.
- So cùng oracle window đầu vào/cohort/pool/qrels/top-K; phép tạo query
  ngắn là khác biệt được khai báo, không gọi là chỉ thay retriever. Giữ
  deterministic ties; báo điểm yếu khi translation làm mất surface overlap.
  Chỉ chọn tham số trên DEV.

**Đầu ra:** hai baseline có config, test phù hợp, lệnh chạy và output cùng
format với phương pháp hiện có.
**Hoàn thành khi:** tái lập được, không dùng nhãn relevant source hoặc nội
dung gold source để chọn term/rank. Oracle suspicious window vẫn là đầu
vào được cấp theo task đã khai. Không trộn số closed-pool với PAN web task.

## 6. Nhận xét 5 — trình bày và khai báo

### R5.1 — Rút thông tin thủ tục

**Phụ trách:** Y biên tập; Q giữ hồ sơ. **Sau R1.1.**

Chuyển Table 4 path/hash, full commit/SHA, lịch sử revalidation/approval
sang phụ lục/artifact note. Giữ sampling, split, seed, checkpoint revision,
input budget, metric, hardware, anti-leakage và top-50 gate. Viết phần
chính theo vấn đề → phương pháp → phép so → kết quả → diễn giải.

**Đầu ra:** bản thảo dễ đọc và phụ lục tái lập có liên kết.
**Hoàn thành khi:** rút chi tiết vận hành mà không mất thiết kế và cơ chế
thuật toán cần giải thích kết quả.

### R5.2 — Disclosure of Interests và khai báo AI

**Phụ trách:** Q/Y soạn; hai tác giả xác nhận thông tin thực tế.

Phân biệt Codex hỗ trợ code/script/soạn thảo/phân tích, Claude tham gia tạo
nhãn, Qwen là verifier được nghiên cứu. Chỉ điền version/vai trò có căn
cứ. Chuẩn bị Disclosure theo mẫu đang dùng, không điền “None” thay tác giả
hoặc tự khẳng định mọi nội dung AI đã được con người kiểm.

**Đầu ra:** hai khai báo ở vị trí phù hợp trong bản thảo.
**Hoàn thành khi:** đúng thực tế và được tác giả đọc xác nhận. Việc soạn
các phần còn lại vẫn tiếp tục khi thông tin xác nhận này chưa có.

### R5.3 — Xuất bản gửi khoa và bảng trả lời nhận xét

**Phụ trách:** Y định dạng/đọc; Q tái tạo/kiểm số; cả hai đọc chéo.

Tạo bảng năm nhận xét → việc làm → vị trí sửa → artifact → hạn chế còn mở.
Sinh lại DOCX/PDF từ Markdown; kiểm hình/bảng/caption/references/cross-reference.
Mỗi số truy về JSON, giữ raw essays/dữ liệu riêng khỏi gói gửi.

**Đầu ra:** Markdown + DOCX + PDF + figures/tables + response matrix.
**Hoàn thành khi:** title–abstract–results–conclusion nhất quán, số khớp,
hình/bảng không vỡ; phần công việc theo đề tài có kết quả và giới hạn được
báo đầy đủ. Có thể gửi bản trung gian góp ý trong lúc tiếp tục triển khai,
nhưng không gọi đó là đã hoàn thành đề tài hoặc xác nhận grading.

## 7. P2 phải hoàn thành: nguồn sạch, chức năng và đánh giá đúng đề cương

Phần này thuộc đường găng hoàn thành đề tài, không phải extension tùy chọn.
Không hồi tố thay đổi lượt đã chạy. Y dẫn rubric/nhãn, Q dẫn nguồn/verifier/runner.
Thực hiện V1/V2/R1/L1/G1/H1 và E2 ở kế hoạch chính, gồm mức đánh giá,
nguồn đối chứng, graph quan hệ, điểm theo rule và quyền chốt của giảng viên.

1. Tạo version nguồn sạch riêng, removal ledger khi xác định được feedback;
   phần chưa chắc giữ flag. Không cắt theo regex cảm tính hoặc sửa nguồn cũ.
2. Tạo lại body hash/version/offset; kiểm nhãn/spans chịu ảnh hưởng, không
   tự tái dùng offset hay nhãn chỉ vì body gần giống.
3. Chốt UNMET do vắng nội dung và CA do thiếu đầu vào. Muốn xác nhận vắng
   cần phạm vi toàn văn, không dựa vào selection rỗng hay quote giả.
4. Dùng 15 bài đã xem làm DEV cho sửa phương pháp; cohort đánh giá cần mới,
   không dùng bản làm sạch của chính 15 bài làm “holdout chưa xem”.
5. Thiết kế nhãn phù hợp phạm vi, không ép mọi lớp phải có mẫu. Đo semantic
   support riêng với source traceability; quyết định con người lưu riêng.
6. Chuẩn bị báo cáo sinh viên Việt/Anh trong miền với rubric, quyền dùng và
   nhãn phù hợp; SEFORA/QASPER không tự thay thế báo cáo kỹ thuật trong miền.
7. Chạy đúng no-retrieval/LOCAL/LOCAL+GRAPH; đo riêng evidence, nhãn,
   rationale support, nhận biết thiếu bằng chứng và điểm so giảng viên.
   One-step/two-step trên pack ngắn không thay phép so này.
   No-retrieval vẫn được đọc báo cáo theo chính sách context khóa trước;
   các nhánh chọn evidence khác nhau từ cùng nguồn hợp lệ, dùng chung
   verifier/scorer và khai rõ budget/báo cáo vượt context.

## 8. Gói bắt đầu và trạng thái

**Gói mở đầu:** đối chiếu R1.1 đã có; bắt đầu V1/R1 và D1 theo kế hoạch
chính. Song song R4.1 + R2.1 (phân tích số), R1.2 + R3.1 (viết kết quả),
R5.1 + R5.2 (biên tập/khai báo). P2/GRAPH, classifier bốn dạng, review/câu
hỏi và đánh giá trong miền tiếp tục theo dependency, không đợi xong bản gửi.
Triển khai R4.2/R2.2/R3.2; đánh giá cuối R2.3 khi phương pháp khóa.

- Audit, random QASPER và rà soát 15 mục SEFORA: **đã có đầu vào**.
- Chèn bổ sung vào bài, stratified metrics, baseline PAN mới, cohort lớn
  và controlled CE mới: **chưa thực hiện theo kế hoạch này**.
- Đây là kế hoạch phần phản biện; không tự nâng DONE trong backlog/WBS
  hoặc sửa lịch baseline của toàn khóa luận.

Hoàn thành từng việc theo đầu ra và tiêu chí trên, không theo điều kiện
“phải ra số cao hơn”. Kết quả âm được giữ và giải thích đúng phạm vi.
