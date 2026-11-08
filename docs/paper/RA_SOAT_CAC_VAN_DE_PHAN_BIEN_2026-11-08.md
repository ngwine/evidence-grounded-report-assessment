# Đối chiếu các nhận xét phản biện — 08/11/2026

Phạm vi: bản Markdown và DOCX hiện tại, kết quả PAN DEV0/DEV1, QASPER đã
xác nhận lại, pilot SEFORA 07/11 và rà soát bất đồng 08/11. Đây là kiểm tra
hiện trạng; chưa sửa bản thảo, đổi nhãn hoặc chạy model mới. TEST0 giữ kín.

## Kết quả tổng quát

| Nhận xét | Hiện trạng |
| --- | --- |
| 1. Tiêu đề/phạm vi rộng hơn bằng chứng rubric | Còn. Bản thảo đã thừa nhận prototype, nhưng tiêu đề vẫn rộng; SEFORA mới chưa được đưa vào. |
| 2. PAN nhỏ; thiếu phân tích obfuscation/translation | Còn. DEV1 là bộ phát triển riêng, không làm DEV0 thành một nghiên cứu lớn hơn hoặc holdout. |
| 3. Kết luận CE bị ảnh hưởng checkpoint/input | Đã xử lý một phần: giới hạn kết luận theo cấu hình và có DEV1 A5/A6; vẫn chưa xác định nguyên nhân hay tổng quát cho CE. |
| 4. Thiếu baseline | Còn ở bản thảo. Vừa tính thêm baseline ngẫu nhiên QASPER bằng công thức trên đúng cohort; chưa chèn vào bài. Baseline PAN chuyên tác vụ chưa có. |
| 5. Thủ tục nội bộ và declarations | Còn phần trình bày cần rút gọn; thiếu hai khai báo là đúng. “Phần lớn bài” và xem mọi “gate” là thủ tục là nhận xét quá mạnh. |

## 1. Phạm vi và dữ liệu sinh viên

Tiêu đề vẫn là *An Evidence-Grounded Framework for Similarity Analysis and
Rubric-Based Assessment of Student Reports*. Abstract đã nói rubric-grading
effectiveness chưa được xác nhận; Introduction và §3.3 cũng thu hẹp rõ.
Vì vậy vấn đề hiện tại là phạm vi tiêu đề rộng hơn phần kiểm chứng, không
phải bài hoàn toàn che giấu giới hạn.

Cả Markdown và DOCX chưa có SEFORA. Repository thì **đã có bài luận sinh
viên tiếng Anh** và đã chạy 15 bài × 3 checklist, đối chiếu một tham chiếu
có Claude hỗ trợ: một bước 37/45, hai bước 32/45, baseline MET 42/45.
Nhận xét “không có dữ liệu sinh viên nào” không còn đúng ở cấp dự án, nhưng
bản thảo chưa phản ánh dữ liệu mới. Đây cũng chưa phải đánh giá trên báo cáo
kỹ thuật dài hoặc báo cáo sinh viên Việt Nam.

Pilot SEFORA hỗ trợ bổ sung một nghiên cứu thăm dò có kết quả âm. Nó chưa
đóng khoảng trống kiểm chứng chất lượng chấm rubric: một người gán, phân
bố lệch lớp, không có CA tham chiếu, quy tắc UNMET do vắng nội dung chưa
khớp hoàn toàn verifier, và ít nhất ba body có đoạn giống feedback. Không
được dùng 179 proof đúng tọa độ thay cho xác minh ngữ nghĩa.

Đối chiếu: bản thảo dòng 1, 9, 21, 101, 109, 134;
[SEFORA đã chạy](../benchmarks/sefora-p2-single-reference-result-2026-11-07.md);
[rà soát nhãn và nguồn](../benchmarks/sefora-p2-disagreement-review-2026-11-08.md).

## 2. Quy mô PAN, ngẫu nhiên, khoảng tin cậy và phân tầng

DEV0 có 30 parent annotations từ 30 suspicious documents, 320 cửa sổ tương
quan, 200 tài liệu nguồn; mỗi query có một tài liệu liên quan. Với một xếp
hạng đều ngẫu nhiên trên toàn pool, kỳ vọng Recall@K là K/200 khi K≤200:

- Recall@100 = 0,5: nhận xét đúng, chỉ số ở cutoff chiếm nửa pool cần ngữ cảnh.
- Recall@10 = 0,05: không thể suy mọi kết quả đều gần ngẫu nhiên; kết quả
  early retrieval của các phương pháp vẫn cao hơn mức này.

DEV1 thêm một comparison riêng 30 parents/207 windows/200 sources. Không
gộp hai bộ thành một sample duy nhất hoặc gọi DEV1 là TEST0. Bootstrap theo
parent tránh thổi phồng 320 cửa sổ thành 320 mẫu độc lập, nhưng không tự
tăng kích thước hay độ bao phủ dữ liệu.

Trong bốn contrast Recall@10 của DEV0, **3/4 khoảng paired chứa 0**. Ngoại
lệ A4−A2 là −0,1622 với CI95% [−0,2848; −0,0476]. Tính cả ba metric của bốn
contrast, 7/12 interval chứa 0. Cả ba contrast A6−A5 trên DEV1 chứa 0.
Đây là CI của *chênh lệch*; không nhầm với CI của một metric riêng hoặc
coi chứa 0 là bằng chứng hai phương pháp tương đương.

Bản thảo chưa có kết quả theo obfuscation hoặc translation. Metadata XML
gốc của các parent DEV đã đối chiếu checksum còn giữ:

| Cohort | Loại parent | Obfuscation | Translation |
| --- | --- | --- | --- |
| DEV0 | 25 artificial, 3 translation, 2 simulated | 14 high, 11 low, 5 không có trường | 2 de→en, 1 es→en |
| DEV1 | 28 artificial, 2 translation | 15 high, 13 low, 2 không có trường | 2 de→en |

Có thể bổ sung phân tầng hậu kiểm từ dự đoán cũ mà không gọi model lại.
Phải ghi số mẫu từng nhóm; n=3 hoặc n=2 không đủ cho kết luận mạnh về đạo
văn dịch. Không ghi MISSING thành “không obfuscation” nếu nguồn không nói vậy.

Hồ sơ: [PAN audit JSON](../../var/paper/reviewer-audit-2026-11-08/pan-findings.json).
Các điểm tựa bản thảo: dòng 119–121, 150–158, 177–183, 225–232.

## 3. Cross-Encoder và cấu hình thí nghiệm

Checkpoint đúng là `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`. Model card
mô tả huấn luyện mMARCO và dùng xếp hạng query–passage; mục tiêu này khác
truy tìm đoạn tái sử dụng giữa các văn bản. Domain/input mismatch là yếu tố
cần kiểm tra, không phải bằng chứng mọi Cross-Encoder không phù hợp.
([Model card](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1).)

DEV0 có 34.669/35.569 pair bị truncation (97,5%). Bản thảo hiện đã nói rõ
kết quả âm thuộc checkpoint, lựa chọn support, top-50 gate và cách cắt hiện
tại; không còn kết luận chung rằng Cross-Encoder làm giảm hiệu năng.

Đã có đối chứng DEV1 A5/A6:

- A5: 19.742/20.700 support requests bị model truncation.
- A6: 0/20.700 bị truncation bổ sung sau chính sách dựng input.
- Chênh Recall@10 A6−A5 = −0,0346; CI95% [−0,1028; 0,0369]. Chưa cho thấy
  cải thiện hoặc suy giảm đáng tin cậy.

A6 phối hợp query-prefix crop và lexical passage-window selection. Nó
không tách riêng tác động truncation, không loại trừ mất nội dung do crop,
và không đo domain adaptation. Vì vậy cũng chưa thể kết luận phần lớn
suy giảm “do truncation” hoặc “do checkpoint” từ các số này.

Đối chiếu: [DEV1 A5/A6](../benchmarks/pan-pc-11-short-evidence-dev1-result.md),
bản thảo dòng 249–268 và phần kết luận.

## 4. Baseline

### PAN

Đã có BM25, Dense và RRF. Chưa có baseline tạo truy vấn hoặc
fingerprint/shingle-based retrieval; hash dữ liệu trong hồ sơ không phải
baseline fingerprinting phát hiện tái sử dụng.

Cần so trên cùng corpus, đơn vị đầu vào và budget. Không thể chép trực tiếp
số của PAN source retrieval trên web sang closed pool 200 tài liệu với
oracle suspicious spans: [task PAN source retrieval chính thức](https://pan.webis.de/clef13/pan13-web/source-retrieval.html)
nhận cả suspicious document và search API, đồng thời đánh giá chi phí truy
vấn/tải trang. Baseline trích từ tác vụ khác không tự tạo một so sánh công bằng.

### QASPER

Trong runner/kết quả gốc và bản thảo chỉ có BM25, E5, RRF; chưa có random.
Lần kiểm tra này tính thêm **kỳ vọng phân tích hậu kiểm** của một ranking
ngẫu nhiên đều không hoàn lại, trên đúng 646 câu/255 paper đủ điều kiện:

`P(Hit@K) = 1 − C(N−m, min(K,N)) / C(N, min(K,N))`,

với N là số paragraph ứng viên trong paper của câu hỏi và m là số paragraph
khác nhau thuộc hợp của các annotation hợp lệ. Lấy trung bình xác suất theo
đúng question-macro, không thay N bằng “48 đoạn trung bình”.

| Phương pháp | Hit@1 | Hit@5 | Hit@10 |
| --- | ---: | ---: | ---: |
| Ngẫu nhiên — kỳ vọng phân tích mới | 4,76% | 21,53% | **38,56%** |
| BM25 — kết quả cũ | 18,73% | 56,97% | 76,93% |
| E5 — kết quả cũ | 30,19% | 71,98% | 86,69% |
| RRF — kết quả cũ | 26,16% | 69,97% | 87,15% |

Pool cho các câu đủ điều kiện có mean 47,53, median 44, min 8, max 290;
union evidence có mean 1,918 paragraph. Các phương pháp cao hơn random kỳ
vọng về mặt mô tả; không phát sinh kiểm định significance hoặc xác nhận
chất lượng P2. Số random trên chỉ cho Hit, không gán sang Complete, recall
theo annotation hoặc MRR.

Đã kiểm cùng dữ liệu/mapping/coverage/hash với lượt xác nhận cũ; kiểm công
thức bằng liệt kê tổ hợp pool nhỏ và 6 test QASPER hiện có đạt. Không gọi
model, không sửa output đã khóa. Đây không phải baseline định trước trong
thí nghiệm ban đầu và **chưa được thêm vào bản thảo**.

[Mã tính tái tạo](../../var/paper/reviewer-audit-2026-11-08/qasper/analytic_random_baseline.py)
và [kết quả](../../var/paper/reviewer-audit-2026-11-08/qasper/analytic-random-baseline.json).

## 5. Trình bày và khai báo

Trong bản thảo có Table 4 về đường dẫn/hash, các đoạn kể clean commit,
checksum, lịch sử xác nhận lại và trạng thái approval. Nên chuyển các phần
này sang phụ lục/artifact note, giữ Methods tập trung vào câu hỏi, dữ liệu,
sampling, model, input, metric và thiết kế đối chứng.

Tuy vậy, “phần lớn bài là thủ tục” là quá mạnh: sáu đoạn hỗn hợp có nhắc
commit/hash/approval khoảng 552 từ trên khoảng 7.195 từ phần chính, chưa
kể Table 4; không phải toàn bộ 552 từ là hành chính. Trong bảy lần “gate”,
sáu lần là chặn top-50 hoặc evidence gating thuộc thuật toán, chỉ một lần
là dataset-acceptance gates. Không xoá giải thích top-50 gate vì đó là cơ
chế thất bại cần phân tích. Seed, split, checkpoint revision, hardware và
anti-leakage cũng là thông tin tái lập phù hợp.

Markdown và DOCX đều thiếu Disclosure of Interests và khai báo AI hỗ trợ.
[Hướng dẫn proceedings LNCS](https://dam.springernature.com/file/FaWtzbohqK79m98VYbDjiX/%2A/CS_Editors_Proceedings_guidelines%20new.pdf)
có mục Disclosure of Interests. Nội dung xung đột lợi ích phải do tác giả
xác nhận, không tự điền “không có” thay họ.

Springer yêu cầu minh bạch hỗ trợ AI và trách nhiệm tác giả.
([Chính sách AI manuscript](https://www.springernature.com/gp/policies/editorial-policies/ai-manuscript-preparation).)
Với dự án này, cần phân biệt các vai trò thực tế đã có: Codex hỗ trợ code,
script, soạn thảo/phân tích; Claude tham gia quá trình tạo nhãn Yến;
Qwen là verifier trong phương pháp thử nghiệm. Mô tả Qwen trong Methods
không thay thế việc khai báo hai vai trò hỗ trợ còn lại. Không tự xác nhận
mọi nội dung AI đã được con người kiểm nếu chưa có căn cứ.

## Ưu tiên xử lý

1. Chốt lại phạm vi/tiêu đề và đồng bộ bản thảo với pilot P2 đúng mức thăm
   dò, gồm kết quả âm, nhãn AI-assisted, lệch quy tắc UNMET và dấu hiệu
   feedback lẫn nguồn. Không thêm riêng bảng 82,22% rồi coi P2 được xác nhận.
2. Thêm random baseline QASPER/PAN; bổ sung phân tầng PAN từ dự đoán đã có,
   báo n và giới hạn của nhóm translation nhỏ. Các bổ sung hậu kiểm phải
   được ghi đúng thời điểm thiết kế.
3. Rút thông tin commit/hash/lịch sử nội bộ sang phụ lục và bổ sung hai
   khai báo trung thực. Giữ thông tin thiết kế thuật toán/tái lập cần thiết.
4. Để tạo bằng chứng mạnh hơn: protocol PAN với pool lớn hơn, thêm baseline
   chuyên tác vụ và đánh giá frozen method trên cohort chưa dùng sửa code.
   Chỉ mở TEST0 khi phương pháp/phạm vi đã chốt; không dùng nó thử nhiều
   cách rồi chọn kết quả tốt.

Các bước 1–3 sửa chất lượng và tính đầy đủ của bài với kết quả sẵn có. Chúng
không tự giải quyết sample size, khả năng tổng quát hoặc xác nhận chấm
báo cáo sinh viên Việt Nam. Bản thảo gốc chưa bị thay đổi trong đợt audit này.
