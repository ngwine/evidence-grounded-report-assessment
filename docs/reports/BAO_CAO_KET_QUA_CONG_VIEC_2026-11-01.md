# BÁO CÁO TUẦN

**Đề tài:** Xây dựng hệ thống hỗ trợ kiểm tra đạo văn và đánh giá báo cáo sinh viên dựa trên bằng chứng

**Sinh viên:** Nguyễn Trần Ngọc Quý — 523H0087; Võ Thị Kim Yến — 52200229

**Đợt báo cáo:** 19/10–01/11/2026, gồm tuần 19–25/10 và tuần 26/10–01/11.
**Ngày cập nhật:** 01/11/2026.

## 1. Kết quả tổng quát

Hệ thống đã có luồng web → API → worker → MongoDB cho quản lý tài liệu,
rubric, chạy hai pipeline, xem bằng chứng và lưu quyết định review. Báo cáo
PDF/DOCX được phân tích thành các đoạn có định danh, phiên bản và vị trí nguồn.
Pipeline 1 hỗ trợ đối chiếu nguồn; Pipeline 2 kiểm các yêu cầu rubric bằng
bằng chứng, đưa ra kết luận và điểm đề xuất theo quy tắc. Đây là prototype
đã tích hợp; chất lượng đánh giá trên báo cáo sinh viên mới vẫn cần kiểm chứng.

## 2. Công việc triển khai theo tuần

### 2.1 Tuần 19–25/10: tích hợp và hoàn thiện luồng demo

| Hạng mục | Kết quả trong tuần |
|---|---|
| Backend và MongoDB | Triển khai đăng nhập/session, CSRF, phân quyền theo workspace; rubric draft/publish/version. Nối upload → PARSE → INDEX → ANALYZE với MongoDB; khóa phiên bản report/source/rubric/index/config, lưu kết quả và bằng chứng bằng transaction. |
| Worker và review | Kiểm lease/heartbeat, stale worker, retry/idempotency, rollback và thu hồi quyền. Review gắn tài khoản/revision; lưu riêng kết quả máy, quyết định người kiểm và JSON export. Đã chạy luồng bằng trình duyệt với MongoDB thật. |
| Giao diện và đầu vào | Tổ chức kho tài liệu, rubric và kết quả theo luồng; hỗ trợ upload file mới/version mới, nhập rubric từ form trống, publish, tự chuẩn bị index và mở lại lượt đã lưu. |
| Vận hành demo | Bổ sung launcher dùng launchd trên macOS để web/API/worker tiếp tục chạy ngoài phiên chat; cập nhật kịch bản và tổng hợp backend cho báo cáo giữa kỳ. Đây vẫn là môi trường phát triển local. |

### 2.2 Tuần 26/10–01/11: cải thiện đầu ra và bổ sung thực nghiệm

| Hạng mục | Kết quả hiện có |
|---|---|
| Pipeline 1 — đối chiếu nguồn | Sửa điều kiện nhận diện đoạn nguyên văn tiếng Việt; bổ sung NLI hai chiều để đề xuất paraphrase theo đoạn được so sánh. Giữ riêng khớp nguyên văn, đề xuất ngữ nghĩa và trường hợp chưa đủ căn cứ. |
| Pipeline 2 — đánh giá rubric | Verifier V4 phân biệt công việc đã hoàn tất với kế hoạch, trạng thái chờ và khả năng của công cụ; xử lý một số ngữ cảnh phủ định, giả định và mâu thuẫn. Mục chưa đủ căn cứ được giữ CANNOT_ASSESS. |
| Tính toàn vẹn bằng chứng | Bổ sung kiểm tra tọa độ nằm trong đoạn, vùng chữ có nguồn và liên kết từ kết luận về đúng Evidence Pack. Chặn MET/UNMET khi mất bằng chứng hoặc đổi nguồn/phiên bản. |
| Tích hợp ứng dụng | Đã chạy hai pipeline qua web/API/MongoDB/worker; kết quả gốc được giữ riêng với quyết định review. Metadata thiết bị chạy model đã được sửa và xác nhận lại. |

Đề xuất paraphrase không cộng vào độ phủ khớp nguyên văn. P2 dùng yêu cầu do
người soạn khai báo và quy tắc từ vựng/ngữ cảnh, chưa suy luận ngữ nghĩa đầy
đủ. Checklist CANNOT_ASSESS giữ điểm tiêu chí và tổng ở null để giảng viên xem xét.

## 3. Kết quả thực nghiệm và kiểm tra

### 3.1 Đối chứng A5/A6 trên PAN-PC-11 DEV1

Đã chạy mô hình thật trên 30 nhóm annotation, 207 cửa sổ truy vấn và 200 nguồn,
tách khỏi DEV0. A6 giữ candidate pool/reranker của A5, đổi chính sách tạo đầu
vào thành query prefix và passage window giới hạn token.

| Chỉ số | A5 | A6 |
|---|---:|---:|
| Parent-balanced Recall@10 | 77,29% | 73,84% |
| Yêu cầu chấm bị truncation tại model | 19.742/20.700 | 0/20.700 |

Chênh lệch Recall@10 là −3,46 điểm phần trăm, khoảng 95% từ −10,28 đến +3,69,
bao gồm 0. Đầu vào ngắn hơn loại được truncation bổ sung nhưng chưa cho thấy
truy xuất tốt hơn. Kết quả âm được giữ trong bài báo; TEST0 chưa mở. Đây là
phép đo truy xuất nguồn, chưa phải độ chính xác phát hiện đạo văn toàn hệ thống.

### 3.2 Truy xuất bằng chứng QASPER

Lượt xác nhận ngày 30/10 từ code sạch tái hiện aggregate cũ. Tập DEV gồm
281 paper, 1.005 câu; 646 câu ánh xạ được bằng chứng sang đoạn văn được chấm,
359 câu bị loại theo protocol.

| Phương pháp | Hit@10 | Complete@10 |
|---|---:|---:|
| BM25 | 76,93% | 61,76% |
| E5 Dense | 86,69% | 74,30% |
| BM25 + E5 + RRF | 87,15% | 72,45% |

Hit@10 đo việc tìm ít nhất một đoạn đúng; Complete@10 đo việc tìm đủ bộ bằng
chứng của ít nhất một annotation. RRF cao hơn ở Hit@10, Dense cao hơn ở
Complete@10; chưa có phương pháp thắng toàn diện. Benchmark chỉ gọi retriever
dùng chung, chưa chạy checklist/verifier/scoring P2; đây không phải độ chính
xác chấm rubric.

### 3.3 Chạy ứng dụng và kiểm tra phần mềm

P2 trên báo cáo LIP qua web trả 6 MET, 3 UNMET, 1 CANNOT_ASSESS và điểm tổng
null. Ca này đã dùng phát triển. Bộ ca tổng hợp khớp 6/6 DEV, 11/12 challenge;
nhãn do trợ lý soạn, chưa phải nhãn người độc lập.

Nhóm regression/contract tests ngày 01/11 đạt **288 pass, 3 skip**. Ba ca
MongoDB thật chưa chạy do thiếu cấu hình môi trường tương ứng. Số này thuộc
nhóm test đã chọn, không phải tổng test dự án hoặc mẫu đánh giá chất lượng model.

Hồ sơ ngày 25/10 ghi **663 pass, 1 skip** khi bật dedicated MongoDB và cached
models, cùng kiểm thử trình duyệt upload → hai pipeline → review/export/reload.
Hai lượt khác snapshot và phạm vi; không cộng gộp hoặc dùng chênh lệch số lượng
để suy chất lượng tăng/giảm.

## 4. Bài báo và dữ liệu chuẩn bị

Bản tiếng Anh đã bổ sung phương pháp QASPER ở §4.6, kết quả ở §5.6/Table 10,
đồng bộ abstract, discussion, limitations và conclusion. Markdown và Word
đã đối chiếu 10 bảng nội dung, 3 bảng bố trí phương trình và 2 hình; 18 ô
metric QASPER khớp artifact gốc. Phân trang Word chưa được kiểm trực quan.

Đã tải PAWS/SEFORA và chuẩn bị 10 bài SEFORA cùng rubric, mã đoạn và phiếu
riêng cho hai người. Hiện có 6 tiêu chí tạm, 60 dòng trống/người; số dòng có
thể đổi khi tách tiêu chí. Chưa có nhãn người hoặc kết quả P2 trên SEFORA.
Phần này chuyển sang tuần sau.

## 5. Phần còn thiếu và kế hoạch tiếp theo

| Ưu tiên | Công việc tiếp theo | Đầu ra cần đạt |
|---|---|---|
| 1 | Chốt ý nghĩa và độ nguyên tử của rubric SEFORA; gán nhãn riêng, phân xử cả nhãn và bằng chứng. | Checklist có phiên bản, nhãn độc lập, bằng chứng và bộ đánh giá đã khóa. |
| 2 | Chạy P2 LOCAL trên bộ đã chuẩn hóa; tách lỗi truy xuất với lỗi xác minh. | Label metric, evidence correctness/recall, abstention và phân tích lỗi theo phạm vi pilot. |
| 3 | Đọc chéo bài báo, kiểm phân trang/hình/bảng và hồ sơ nguồn dữ liệu. | Bản thảo nhất quán, đủ thông tin để giảng viên góp ý. |

P2 chưa có đánh giá hiệu quả đầy đủ trên nhãn người độc lập; G-05 vẫn mở.
GRAPH hiện mới có baseline cấu trúc/từ khóa và PPR, chưa hoàn thiện extraction
claim/entity/relation. Một số thay đổi mới còn ở nhánh làm việc, chưa hoàn tất
review/merge. Hồ sơ phê duyệt pack QASPER còn thiếu; việc báo cáo aggregate
không thay thế quyết định quản trị dữ liệu hoặc nghiệm thu chất lượng P2.

## 6. Nội dung xin ý kiến giảng viên

1. Phạm vi P1 và QASPER đã phù hợp với đóng góp bài báo và số liệu hiện có chưa?
2. Đánh giá P2 LOCAL bằng rubric/nhãn/evidence hai người kiểm độc lập cần bổ
   sung tiêu chí nào trước khi đo?
3. Nhóm bài SEFORA cùng đề có phù hợp cho vòng đầu không; nên mở rộng thế nào
   trước khi kết luận về báo cáo sinh viên Việt Nam?

**Minh chứng đọc kèm:** bài báo `BaiBao_523H0087_52200229_EN_LNCS.docx`;
các báo cáo `pan-pc-11-short-evidence-dev1-result.md`,
`qasper-v03-local-evidence-dev-result.md`,
`output-quality-development-2026-10-29.md` và
`local-assessment-w12-readiness-2026-11-01.md`. Minh chứng tuần trước gồm
`authenticated-mongo-app-2026-10-23.md`,
`version-locked-analysis-2026-10-23.md`,
`direct-upload-rubric-demo-2026-10-24.md` và
`demo-pre-push-2026-10-25.md`.
