# Kịch bản demo giữa kỳ

Thời lượng dự kiến: 7–8 phút. Quý thao tác web xuyên suốt và trình bày kiến
trúc, Pipeline 1; Yến trình bày rubric, Pipeline 2 và hướng hoàn thiện. Nếu
chỉ một người trình bày, giữ nguyên thứ tự bên dưới.

## Chuẩn bị

- Mở giao diện authenticated, đăng nhập và chọn workspace demo. API, MongoDB
  và worker phải đang chạy; chỉ mở web thôi chưa đủ.
- Chuẩn bị một report và một hoặc hai source đọc được bằng parser. Ưu tiên
  PDF có text hoặc DOCX; PDF scan/OCR chưa được kiểm chứng trong luồng demo này.
- Kiểm tra quyền và PII trước buổi trình bày. Chỉ chọn khai báo tài liệu tự
  tạo khi đúng là tài liệu của người dùng/nhóm và được các tác giả cho phép.
  Sách, bài báo hoặc dataset bên ngoài phải dùng hồ sơ quyền đã có.
- Chuẩn bị 2–3 checklist phù hợp yêu cầu môn học, không lấy kết quả cần đạt
  làm căn cứ viết rubric. Với baseline hiện tại, người soạn phải khai báo các
  cụm evidence và cách diễn đạt được chấp nhận. Giải thích rõ giới hạn này.
- Thử toàn bộ luồng một lần trước buổi demo. Giữ một lượt đã chạy để dự phòng;
  nếu dùng lượt đó, nói rõ đây là kết quả lưu trước, không phải lượt vừa chạy.
- Mặc định demo `BM25 · chạy thử luồng nhanh`. Chỉ demo `Hybrid` nếu đã chạy
  thử chính report/source đó, model có sẵn và thời gian phù hợp. Không gọi
  lượt BM25 là Hybrid, không đổi cấu hình âm thầm khi lỗi.

## 1. Mở đầu — 30 giây

**Thao tác:** mở màn hình Phân tích báo cáo.

> Thưa thầy, hôm nay nhóm demo luồng từ đầu vào đến kết quả trên web: tải báo
> cáo và nguồn đối chứng, tạo rubric, chạy hai pipeline, rồi xem và review
> bằng chứng. Pipeline 1 hỗ trợ đối chiếu nội dung với nguồn; Pipeline 2 hỗ
> trợ kiểm tra báo cáo theo rubric. Kết quả là đề xuất để giảng viên xem xét,
> không tự kết luận đạo văn hoặc công bố điểm chính thức.

## 2. Upload report và source — 1 phút

**Thao tác:** Kho tài liệu → Báo cáo sinh viên → chọn file, đặt tên → chọn
cách xác nhận quyền phù hợp → Tải lên và xử lý tài liệu. Làm tương tự cho
Nguồn đối chứng; đợi hai tài liệu sẵn sàng.

> Đây là báo cáo cần kiểm tra, còn đây là nguồn đối chứng được đưa vào phạm
> vi tìm kiếm. Hệ thống chỉ so sánh với các nguồn đã chọn, chưa tự tìm trên
> toàn bộ Internet. Sau khi nhận file, backend lưu một phiên bản riêng và
> worker đọc nội dung, chia thành các đoạn có thông tin vị trí để dùng cho
> truy xuất và dẫn chứng.

Nếu dùng tài liệu minh họa tự viết, thêm:

> Hai tài liệu này được tự viết để minh họa tình huống kiểm tra. Demo này
> xác nhận luồng phần mềm chạy được, không phải kết quả thực nghiệm khoa học.

Nếu dùng report thật của nhóm, chỉ giới thiệu đúng nguồn gốc thực tế; không
đọc câu về tài liệu minh họa. Không nói file đã ẩn danh nếu chưa rà soát.

**Nếu thầy hỏi vì sao cần xác nhận quyền:**

> Vì report có thể chứa thông tin sinh viên, còn nguồn đối chứng có thể có
> ràng buộc bản quyền. Với tài liệu tự tạo, nhóm có thể khai báo quyền dùng
> nội bộ ngay trên web; đó không phải phê duyệt độc lập cho dataset nghiên cứu.

## 3. Nhập rubric trên web — 1–1,5 phút

**Thao tác:** Rubric đánh giá → Tạo rubric → nhập mã, tên, điểm tối đa và
trọng số tiêu chí → nhập checklist, các cách diễn đạt của yêu cầu evidence →
Lưu draft → Kiểm tra & publish. Tổng trọng số phải bằng điểm tối đa.

> Rubric này do người dùng nhập trực tiếp trên form, không phải kết quả đã
> gắn sẵn với báo cáo. Mỗi tiêu chí được tách thành những yêu cầu nhỏ có thể
> kiểm tra. Khi publish, phiên bản rubric được khóa để một lượt đánh giá luôn
> xác định được đã dùng bộ tiêu chí nào.

> Ở phiên bản hiện tại, nhóm còn phải nhập các cụm bằng chứng được chấp nhận
> cho từng yêu cầu. Hệ thống chưa tự hiểu đầy đủ một rubric viết tự do. Cách
> này giúp kiểm tra luồng và truy vết quyết định trước khi phát triển phần
> xác minh ngữ nghĩa.

**Ví dụ để giải thích cách nhập, không phải rubric mặc định cho mọi report:**

| Trường | Ví dụ |
|---|---|
| Tiêu chí | Thực nghiệm và đánh giá |
| Checklist | Báo cáo nêu metric dùng để đánh giá |
| Một yêu cầu evidence | Có metric F1 |
| Các cách diễn đạt của cùng yêu cầu | `F1-score`, `macro F1` |

Chỉ dùng ví dụ này nếu rubric thực sự yêu cầu F1. Các alternatives là những
cách diễn đạt tương đương, không phải những yêu cầu độc lập. Muốn bắt buộc
cả hai nội dung thì tạo hai yêu cầu evidence riêng.

## 4. Chạy cả hai pipeline — 30–45 giây

**Thao tác:** Phân tích báo cáo → chọn report, source, published rubric
version → Cả hai pipeline → Phân tích báo cáo.

> Lượt này chạy cấu hình BM25 baseline để trình bày luồng tích hợp. Web gửi
> yêu cầu cho API; worker chuẩn bị index của nguồn và chạy phân tích. Kết quả
> được lưu cùng version của báo cáo, nguồn, rubric và cấu hình, không tính
> sẵn ở frontend.

Trong lúc chờ, nói ngắn về thuật toán:

> Với Pipeline 1, các đoạn báo cáo được dùng để truy xuất nguồn bằng BM25,
> sau đó kiểm tra đoạn trùng và xác định vị trí bằng chứng. Với Pipeline 2,
> checklist được dùng để truy xuất các đoạn trong chính báo cáo và kiểm tra
> những yêu cầu evidence đã khai báo.

Nếu thực sự chọn `research-v0`, thay phần cấu hình bằng:

> Lượt này dùng cấu hình Hybrid: kết hợp BM25 và embedding multilingual
> E5-small, hợp nhất bằng RRF rồi xếp hạng lại bằng Cross-Encoder. Đây là
> phương án đang được đánh giá; nhóm chưa kết luận nhiều mô hình ghép lại sẽ
> luôn tốt hơn baseline.

Không nói Cross-Encoder là bộ xác minh đúng/sai hoặc bộ phân loại đạo văn:
mức liên quan khi truy xuất không tương đương quan hệ entailment hay đạo văn.

## 5. Pipeline 1: đối chiếu nguồn — 1 phút

**Thao tác:** tab Đối chiếu nguồn → Khớp nguyên văn → mở một cặp đoạn
report–source → mở file ở vị trí bằng chứng nếu cần. Sau đó chỉ qua mục
Ứng viên cần review, nếu có.

> Ở đây hệ thống đặt đoạn báo cáo và đoạn nguồn cạnh nhau để người xem kiểm
> tra. Những đoạn có khớp nguyên văn được tách riêng khỏi ứng viên chỉ có
> liên quan khi truy xuất. Chỉ có điểm truy xuất cao thì chưa đủ để gắn nhãn
> diễn giải lại hoặc tóm tắt.

> Con số coverage này thể hiện phần nội dung được xác định khớp theo cách
> tính hiện tại, không phải tỷ lệ đạo văn. Trích dẫn hợp lệ, nội dung phổ biến
> và ngữ cảnh sử dụng vẫn cần giảng viên xem xét.

Nếu không có khớp: trình bày đúng là chưa ghi nhận trong corpus đã chọn,
không kết luận report không có đạo văn. Không đọc một con số chuẩn bị trước
nếu kết quả trên màn hình khác.

## 6. Pipeline 2: đánh giá theo rubric — 1 phút

**Thao tác:** tab Đánh giá rubric → mở một checklist → chỉ kết luận, lý do
và đoạn evidence. Nếu các trạng thái khác có xuất hiện, đối chiếu thêm một mục.

> Pipeline 2 trình bày kết quả theo từng checklist, gồm trạng thái, lý do và
> bằng chứng tìm trong báo cáo. MET là có bằng chứng đáp ứng yêu cầu đã khai
> báo; UNMET là có căn cứ cho thấy không đáp ứng theo quy tắc hiện tại;
> CANNOT_ASSESS là chưa đủ cơ sở để kết luận. Không tìm thấy evidence không
> tự động có nghĩa là báo cáo làm sai.

> Điểm hiển thị là điểm đề xuất theo tỷ lệ checklist, chưa phải giảng viên
> chấm chính thức. Nếu còn mục chưa đánh giá được, hệ thống có thể chưa đưa
> ra điểm tổng thay vì tự gán điểm tối đa hay xem như bằng không.

Nếu được hỏi report nói A, nguồn ngoài nói B:

> Phiên bản đang demo chưa tự xác minh mâu thuẫn giữa report và tài liệu
> ngoài. Nguồn được chọn ở đây phục vụ Pipeline 1; Pipeline 2 hiện kiểm tra
> evidence trong report. Phần đối chiếu claim với nguồn ngoài vẫn cần phát
> triển và đánh giá riêng.

## 7. Review, export và mở lại — 30–45 giây

**Thao tác:** Review chi tiết từng cặp đoạn / checklist → chọn một mục →
chọn nhãn, evidence và nhập lý do → lưu. Export JSON kết quả; có thể reload
và mở lượt phân tích đã lưu để chứng minh persistence.

> Giảng viên có thể kiểm tra bằng chứng và ghi lại nhận xét riêng. Review
> được lưu tách khỏi đầu ra của máy, không sửa âm thầm kết quả ban đầu. Lượt
> phân tích có thể mở lại cùng đầu vào đã khóa và export để kiểm tra sau.

Nếu không đủ thời gian, chỉ làm một mục review và export, không thao tác tất
cả checklist. Review đã xem dự đoán của máy không phải gold annotation độc lập.

## 8. Kết thúc: phần còn thiếu và kế hoạch — 1 phút

> Hiện nhóm đã nối được luồng upload, xử lý tài liệu, nhập rubric, chạy hai
> pipeline và xem/review bằng chứng trên web. Phần cần làm tiếp không chỉ là
> thêm giao diện mà là nâng chất lượng quyết định của hai pipeline.

> Với Pipeline 1, nhóm cần hoàn thiện và đánh giá phân loại các trường hợp
> diễn giải lại, tóm tắt và không tương đồng; không chỉ dựa vào mức liên quan
> của truy xuất. Với Pipeline 2, nhóm cần giảm phụ thuộc vào cụm từ do người
> soạn nhập, bổ sung xác minh ngữ nghĩa và đối chiếu claim với nguồn ngoài.
> Các phần này sẽ được kiểm chứng bằng dữ liệu gán nhãn độc lập trước khi
> dùng để kết luận hiệu quả phương pháp.

Nếu thầy muốn kế hoạch chi tiết hơn:

| Phần còn thiếu | Việc làm tiếp | Cách kiểm chứng |
|---|---|---|
| Phân loại semantic ở Pipeline 1 chưa hiệu chỉnh | Xây bộ cặp VERBATIM/PARAPHRASE/SUMMARY/NONE, gán nhãn độc lập và xử lý bất đồng; hiệu chỉnh ngưỡng trên dev | Đánh giá trên tập giữ riêng; macro F1 từng lớp, evidence span và lỗi false positive |
| Pipeline 2 còn baseline theo phrase/rule | Xác minh claim–evidence, xử lý phủ định/mâu thuẫn và nguồn ngoài; giữ khả năng từ chối kết luận | Gold checklist có evidence; F1 ba trạng thái, độ đúng evidence, mức đồng thuận với người chấm |
| Rubric chưa hiểu tự do/thang điểm tùy chỉnh đầy đủ | Hỗ trợ biên soạn rubric có bước người dùng kiểm tra; thực thi score levels và rule conflict rõ ràng | Bộ test rubric và đối chiếu điểm với người chấm; không đồng nhất tìm thấy từ khóa với chất lượng nội dung |
| Evidence Graph chưa hoàn chỉnh end-to-end | Extraction claim/entity/relation → persistence → provenance API → graph QA | Kiểm tra cạnh/nguồn, chất lượng extraction và lợi ích so với LOCAL trên cùng dữ liệu |
| PDF mới mở trang, chưa highlight chính xác vùng | Nối tọa độ/span với PDF viewer; mở rộng parser/citation benchmark | Test nhiều bố cục/tài liệu dài; đối chiếu highlight với trang gốc |
| Chất lượng tổng quát và vận hành chưa được kiểm chứng đủ | Mở rộng corpus có quyền dùng, chia tập tránh leakage; đo tài nguyên; hoàn thiện lifecycle, backup/restore và triển khai bảo mật | Held-out evaluation, ablation, latency/resource measurements và thử khôi phục/xóa dữ liệu |

Không coi tất cả các phần mở rộng là cam kết phải làm ngay. Ưu tiên gần nhất:
gold data → đánh giá và sửa lỗi hai pipeline → semantic verification; sau đó
mới mở rộng graph, trải nghiệm PDF và triển khai.

## Câu trả lời ngắn khi thầy hỏi

**“Hai pipeline đã hoàn thành chưa?”**

> Đã chạy end-to-end trong phạm vi baseline hiện tại, nhưng chưa hoàn thành
> toàn bộ khả năng ngữ nghĩa theo thiết kế. Pipeline 1 chưa có bộ phân loại
> paraphrase/summary được kiểm định; Pipeline 2 chưa xác minh cross-source.

**“Đây có phải chỉ tìm từ khóa?”**

> Assessment hiện vẫn dùng các yêu cầu và phrase/rule do người soạn khai
> báo, nên nhóm trình bày nó là baseline. Hybrid retrieval giúp tìm đoạn liên
> quan nhưng không tự chứng minh đoạn đó đáp ứng hay mâu thuẫn với yêu cầu.

**“Có chứng minh phương pháp hiệu quả chưa?”**

> Demo này chứng minh tính khả thi của luồng tích hợp. Các thực nghiệm
> retrieval hiện có là đánh giá thành phần; muốn kết luận cho phương pháp
> đầy đủ còn cần gold độc lập và đối chứng/ablation trên tập kiểm thử giữ riêng.

**“Vì sao không tìm thấy đoạn hoặc không chấm được?”**

> Có thể thiếu nguồn trong corpus, parser/truy xuất bỏ sót hoặc evidence chưa
> đủ theo rubric. Nhóm xem đó là trường hợp cần phân tích, không đổi thành
> kết luận report sai hay chắc chắn không đạo văn.

**“File nào chứng minh?”**

- [Test browser qua Mongo và worker thật](../../apps/web/tests/authenticated.mongo.ts):
  upload file mới, report version 2, nhập rubric bằng form, chạy BOTH, review,
  export và reload; không seed hồ sơ quyền, rubric hay kết quả.
- [Kiểm chứng luồng mới](../benchmarks/direct-upload-rubric-demo-2026-10-24.md):
  phạm vi, kiểm thử và các giới hạn đã xác định.
- [Thực nghiệm A1–A5 trên DEV0](../benchmarks/pan-pc-11-cross-encoder-ablation-dev0-result.md):
  kết quả thành phần Pipeline 1, không phải đánh giá toàn hệ thống. Cross-Encoder
  trong cấu hình đã chạy không cải thiện pilot này; không trình bày ngược kết quả.
- Ngay trên web: file version, evidence, cấu hình và JSON export của lượt vừa chạy.

**“Nhiều test pass có nghĩa mô hình chính xác không?”**

> Không. Test phần mềm kiểm tra hành vi và luồng chạy. Độ chính xác học thuật
> phải đo trên dữ liệu có nhãn độc lập, không suy ra từ số test pass.
