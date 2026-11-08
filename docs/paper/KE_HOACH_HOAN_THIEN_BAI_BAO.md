# Hoàn thiện bài báo cùng hệ thống theo đúng đề tài đã đăng ký

Cập nhật 08/11/2026: người phụ trách yêu cầu **giữ nguyên phạm vi đề tài,
triển khai và đánh giá cho đủ**. Không cần chốt lại phạm vi hoặc đổi tên
thành một bài diagnostics để phù hợp phần đang làm được.

Nguồn yêu cầu là [mô tả đề tài gốc](../planning/MO_TA_DE_TAI_GOC.md).
Thứ tự công việc, code cần sửa và tiêu chí hoàn thành nằm trong
[kế hoạch toàn phạm vi](../planning/KE_HOACH_HOAN_THANH_PHAM_VI_DE_TAI.md).
Năm nhận xét về PAN, CE, baseline và trình bày được chi tiết tại
[kế hoạch xử lý phản biện](KE_HOACH_XU_LY_PHAN_BIEN.md).
Không đặt ngày hạn mới; vẫn dùng bản tiếng Anh/mẫu LNCS hiện có để gửi khoa.

## 1. Việc cần làm trước

| Ưu tiên | Phụ trách đề xuất | Đầu ra cụ thể | Kết quả cần đạt |
| --- | --- | --- | --- |
| 1 — code và dữ liệu | Q verifier/compiler; Y rubric/QA/dữ liệu | V1/V2: sửa P2 mất ngữ cảnh, nhầm người nói/nguồn, kiểm đủ bằng chứng; R1: mức đánh giá rubric; D1: report–rubric trong miền | Đầu ra có căn cứ; điểm tính theo rule; thêm dữ liệu đánh giá đúng loại báo cáo, không lấy số pilot làm nghiệm thu. |
| 2 — hoàn thiện hai hướng chính | Q/Y chia nhánh | LOCAL + nguồn đối chứng, GRAPH quan hệ thật; classifier bốn dạng và aggregation | Có đầy đủ chức năng hai pipeline trong đề cương, không dùng structure PPR thay claim graph. |
| 3 — luồng sử dụng | Q API/log; Y UI/đánh giá | Giảng viên sửa/duyệt điểm và nhận xét, final report; câu hỏi có mục tiêu và review | Giữ đề xuất AI gốc, ghi Feedback Log; câu hỏi có issue/evidence và được giảng viên xem xét. |
| 4 — thiết kế ngay, chạy sau khóa phương pháp | Q runner; Y nhãn; giảng viên đánh giá điểm | E1/E2/E3 theo đề cương | P1 retrieval + bốn dạng; P2 no-retrieval/LOCAL/LOCAL+GRAPH; rationale/điểm/câu hỏi có phép đo phù hợp. |
| Xuyên suốt | Y viết; Q tái tạo bảng/hình và kiểm số | Methods/Results/Discussion cập nhật, random/strata/baseline, phụ lục và khai báo AI/interests | Bài phản ánh việc thật, giữ kết quả âm; bản gửi góp ý không được gọi là đã hoàn thành các nghiên cứu chưa chạy. |

Không chờ dữ liệu mới để đứng yên: các lỗi đã biết dùng làm DEV, code và
contract có thể hoàn thiện/test trước. Không sử dụng lại chính ca đã sửa
để tuyên bố đánh giá độc lập.

Người phụ trách chọn tiếp tục **SEFORA** cho P2: bài chưa dùng sửa phương
pháp có thể làm tập đánh giá chính trên essay sinh viên tiếng Anh sau khi
có tham chiếu đúng nhiệm vụ; không bắt buộc R1/R2 mới được làm. Giữ giới
hạn áp dụng riêng với báo cáo kỹ thuật tiếng Việt và không tự chuyển điểm
SEFORA sang nhãn checklist khác rubric.

Đã thực hiện [vòng DEV giữ ngữ cảnh và so retrieval 08/11](../benchmarks/sefora-p2-context-retrieval-dev-2026-11-08.md):
không retrieval mới 35/45, LOCAL BM25 32/45, một bước cũ 37/45. Chưa có
cải thiện đủ căn cứ để chọn variant mới; giữ số âm, tiếp tục sửa trên DEV.
Đã có phiếu kiểm semantic support riêng nhưng chưa có đánh giá người trả
về; không dùng đúng offset để báo rationale đúng. Phần này chưa được chèn
thành bảng kết quả chính của bản thảo.

**Chọn cấu hình tốt hơn làm mặc định**, không mặc định GRAPH/hai bước là
tốt hơn. Quyết định trên DEV theo nhãn từng lớp, semantic support,
abstention và tài nguyên, rồi khóa trước tập đánh giá. GRAPH có thể chỉ
dùng cho nhóm checklist có ích; các phương pháp khác vẫn giữ làm đối chứng.
Giữ đủ nghiên cứu đã đăng ký không có nghĩa ép mọi phương pháp vào mọi lượt chạy.

## 2. Sử dụng đúng bằng chứng đã có

| Kết quả hiện có | Có thể trình bày | Chưa chứng minh |
| --- | --- | --- |
| PAN DEV0 A1–A5, DEV1 A5/A6 | Truy xuất nguồn trong pool đóng, ảnh hưởng cấu hình CE/input, uncertainty | Phân loại đủ bốn dạng, false positives hoặc toàn hệ thống kiểm tra đạo văn. |
| QASPER 646 câu đủ điều kiện | Truy xuất đoạn evidence trong cùng paper; BM25/E5/RRF và random phân tích hậu kiểm | Chấm rubric, quan hệ GRAPH, điểm báo cáo sinh viên. |
| SEFORA 15 bài/45 mục, 07/11 | Một bước 37/45, hai bước 32/45, luôn MET 42/45; hạn chế nhãn một người có Claude hỗ trợ | Hai bước tốt hơn, đủ ba trạng thái, no-retrieval/LOCAL/GRAPH hoặc chất lượng chấm toàn bài. |
| 179 proof hiện diện đúng nguồn/offset | Truy vết hình học/nguồn của các proof | 179 kết luận được hỗ trợ về ngữ nghĩa. |
| App Mongo/browser E2E; LIP và synthetic cases | Tích hợp kỹ thuật, minh họa và kiểm hồi quy/phát triển | Độ chính xác độc lập hoặc mức hữu ích với giảng viên. |

Giữ toàn bộ output, workbook, hash và phương pháp của lượt cũ. SEFORA đã
được xem lỗi trở thành DEV cho thay đổi sắp tới; bản nguồn làm sạch cần
version/offset và kiểm lại nhãn, không trở thành holdout mới. Rà soát AI
không tạo giám khảo thứ hai; không buộc người phụ trách làm phiếu thứ hai
để báo cáo pilot một tham chiếu hiện có.

## 3. Phần bài báo phải được hoàn thiện

- **Method:** đủ P1 bốn dạng/tổng hợp; rubric/compiler/mức/rule; LOCAL,
  graph quan hệ và router; verifier/rationale; giảng viên duyệt và câu hỏi.
  Phần chưa triển khai phải ghi đúng trạng thái trong bản đang làm.
- **Experiments P1:** BM25, Dense, RRF, reranker và pipeline hoàn chỉnh;
  baseline thích hợp, PAN lớn/phân tầng, nhãn trong miền, retrieval và
  classification/coverage tách biệt; tài nguyên và CI theo nhóm độc lập.
- **Experiments P2:** LLM không retrieval, LOCAL và LOCAL+GRAPH có chọn lọc
  trên cùng report/rubric/split; label metric, evidence, rationale support,
  nhận biết thiếu căn cứ và mức/điểm đối chiếu giảng viên. So verifier
  one-step/two-step nếu có là đối chứng khác, không thay ba cấu hình này.
- **Lecturer support:** dữ liệu đánh giá câu hỏi, relevance/grounding/
  answerability/usefulness và review/edit/reject; Feedback Log phục vụ
  phân tích khác biệt giữa đề xuất và quyết định thực tế.
- **Discussion:** trả lời bằng kết quả thực; giữ mất cân bằng nhãn,
  trường hợp CA/UNMET, lỗi người nói/nguồn và dữ liệu có feedback lẫn bài.
  Khi kết quả kém phải tiếp tục vòng sửa–đo trên DEV, không đổi mục tiêu
  hoặc nhãn để tạo tỷ lệ cao.
- **Presentation:** chuyển full SHA/path/approval history sang phụ lục;
  giữ thiết kế thực nghiệm, model/input/seed và thuật toán quan trọng.
  Disclosure of Interests do tác giả xác nhận; khai Codex/Claude/Qwen
  đúng vai trò thực tế, không tự ghi “không dùng AI”.

## 4. Hoàn thành và bản góp ý trung gian

Có thể gửi khoa/GVHD bản đang làm để góp ý cùng kết quả hiện có. Bản này
phải chỉ rõ phần triển khai/đánh giá còn thiếu, không thay thế bản hoàn
thành đúng đề tài. Chốt bản cuối khi các gói trong kế hoạch chính có output
và bằng chứng tương ứng; không đặt điều kiện mọi phương pháp mới phải thắng.

Bộ nộp gồm Markdown nguồn, DOCX/PDF, hình/bảng, code/config và kết quả phù
hợp quyền chia sẻ. Kiểm số từ artifacts, hình/mũi tên, phân trang, references
và nhất quán title–abstract–method–results–conclusion. Không kèm raw reports
riêng tư khi chưa có quyền chia sẻ.

## 5. File làm việc và lịch sử

- [Bài báo Markdown](BaiBao_523H0087_52200229_EN.md)
- [Bản DOCX](BaiBao_523H0087_52200229_EN_LNCS.docx)
- [Audit số liệu](EXPERIMENT_AUDIT.md)
- [Audit năm nhận xét](RA_SOAT_CAC_VAN_DE_PHAN_BIEN_2026-11-08.md)
- [Kết quả P2 một tham chiếu](../benchmarks/sefora-p2-single-reference-result-2026-11-07.md)
- [Rà soát bất đồng P2](../benchmarks/sefora-p2-disagreement-review-2026-11-08.md)
- [Sinh DOCX](../../scripts/generate_lncs_paper.py)
- [Ghi chú template](TEMPLATE_NOTES.md)
- [Kế hoạch trước đính chính, lưu lịch sử](history/KE_HOACH_HOAN_THIEN_BAI_BAO_TRUOC_DINH_CHINH_2026-11-08.md)

Lượt cập nhật kế hoạch này chưa sửa bản thảo, code tính năng hoặc kết quả
thực nghiệm; không tự đóng story/gate hoặc ghi nhận người duyệt.
