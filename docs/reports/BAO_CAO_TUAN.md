# BÁO CÁO TUẦN

**Đề tài:** Xây dựng hệ thống hỗ trợ kiểm tra đạo văn và đánh giá báo cáo sinh viên dựa trên bằng chứng.

**Thành viên:** Nguyễn Trần Ngọc Quý — 523H0087; Võ Thị Kim Yến — 52200229.

Trong tuần, nhóm tập trung triển khai, kiểm tra Pipeline 2 (P2) và rà soát các nhận xét thực nghiệm. Phạm vi đề tài được giữ nguyên.

## 1. Công việc đã thực hiện

| Hạng mục | Đầu ra và kết quả |
| --- | --- |
| Verifier LLM local | Tích hợp Qwen xác minh checklist; kiểm schema, ID, phiên bản và bằng chứng. Code tổng hợp nhãn, tính điểm theo quy tắc. |
| Tiếp nhận nhãn SEFORA | Kiểm phiếu Excel 15 bài, 45 mục; giữ bản gốc riêng. Phân biệt đoạn trích với hồ sơ xác nhận vắng nội dung. |
| So sánh cách xác minh | Chạy một bước/hai bước trên cùng evidence; lưu từng quyết định và cấu hình. Tách lỗi kỹ thuật khỏi CANNOT_ASSESS. |
| Thử giữ ngữ cảnh và retrieval | Thêm unit theo source span; so đọc toàn báo cáo ngắn với LOCAL BM25. Lượt chạy hoàn tất nhưng chưa cải thiện khớp nhãn. |
| Phân tích bằng chứng | Kiểm tọa độ proof, độ phủ vị trí tham chiếu; tạo phiếu che tên phương pháp để người kiểm đánh giá ngữ nghĩa. |
| Kiểm thử và rà soát | Research/backend: 1.387 test đạt, 21 bỏ qua; sáu test phân tích mới đạt riêng. Tính thêm random baseline QASPER và rà soát thực nghiệm. |

Mã chính: `02_MaNguon/research/core_mvp/llm_assessment.py`, `02_MaNguon/research/gold_annotation/p2_workbook_intake.py` và `02_MaNguon/research/p2_comparison/`. Số liệu nằm trong `03_KetQua`; công việc tiếp theo ở `04_KeHoach`.

## 2. Kết quả P2 và nhận định

Hai lượt chạy sử dụng **cùng 15 bài và 45 mục tham chiếu**, tạo tổng cộng 180 bản ghi quyết định; đây không phải 180 mẫu độc lập.

| Cấu hình | Khớp nhãn | Tỷ lệ |
| --- | ---: | ---: |
| Một bước | 37/45 | 82,22% |
| Hai bước | 32/45 | 71,11% |
| Ngữ cảnh mới, đọc toàn báo cáo | 35/45 | 77,78% |
| Ngữ cảnh mới, LOCAL BM25 | 32/45 | 71,11% |
| Đối chứng luôn MET | 42/45 | 93,33% |

Không có lỗi kỹ thuật. Cấu hình mới chưa vượt một bước cũ hoặc đối chứng luôn MET, nên chưa được chọn làm mặc định.

Tham chiếu một người có Claude hỗ trợ gồm 42 MET, ba UNMET, không có CA; chưa đo được đủ ba trạng thái. Bộ đã xem lỗi được dùng làm DEV.

149 proof của lượt mới đúng nguồn/tọa độ, chưa chứng minh hỗ trợ đúng kết luận. Lỗi nổi bật: thiếu quotation, nhầm nguồn/người nói, relation lệch rationale. Phiếu kiểm ngữ nghĩa chưa được trả về nên chưa có tỷ lệ semantic support.

## 3. Đối chiếu ngắn các nhận xét

| Nhận xét | Đã xử lý và phần còn thiếu |
| --- | --- |
| Bằng chứng P2 chưa tương xứng phạm vi | Đã có thực nghiệm SEFORA và phân tích lỗi; chưa đủ xác nhận chất lượng chấm toàn báo cáo. |
| PAN nhỏ, thiếu phân tầng | Đã kiểm lại quy mô, CI và metadata; chưa mở rộng cohort hoặc có kết quả metric phân tầng mới. |
| CE chịu ảnh hưởng cấu hình | Đã rà lại cách diễn giải theo checkpoint/input; đối chứng A5/A6 là kết quả đã có, không phải lượt chạy mới trong tuần. |
| Thiếu baseline | Bổ sung kỳ vọng random QASPER Hit@10 = 38,56% và đối chứng luôn MET. Baseline PAN query/fingerprint chưa triển khai. |
| Trình bày và khai báo | Đã xác định nội dung cần rút gọn và khai báo AI; bản thảo chưa được cập nhật các phần này. |

## 4. Công việc tiếp theo và nội dung dự kiến cho bài báo

Nhóm tiếp tục sửa cơ chế xác minh để nhãn–rationale–evidence nhất quán, xử lý xác nhận vắng nội dung và retrieval quotation; hoàn thiện mức rubric, GRAPH quan hệ và giảng viên chốt điểm. Giữ nguyên nhãn tham chiếu và kết quả đã chạy.

SEFORA tiếp tục là nguồn thực nghiệm: chọn nhóm chưa dùng sửa phương pháp và chuẩn bị tham chiếu phù hợp. Điểm sẵn chỉ dùng với đúng rubric, không thay nhãn ba checklist.

Bài báo dự kiến thêm phép so không retrieval/LOCAL/LOCAL+GRAPH khi sẵn sàng; đo nhãn, bằng chứng hỗ trợ rationale, thiếu căn cứ và điểm rubric. Chỉ kết luận khi có phép đo đáng tin cậy, giữ cả kết quả âm; không chọn riêng tỷ lệ cao để báo cáo.
