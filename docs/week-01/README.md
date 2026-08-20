# Hồ sơ công việc tuần 1

**Thời gian:** 08/08/2026–14/08/2026  
**Phiên bản hồ sơ:** 1.2-review-candidate  
**Ngày lập:** 13/08/2026

## Mục đích

Thư mục này chứa năm đầu ra của tuần 1. “Content-complete” nghĩa là nội dung đã đủ để review; không đồng nghĩa đã được GVHD/người dùng phê duyệt.

| Mã | Đầu ra | Trạng thái hoàn thành được hiểu như thế nào |
|---|---|---|
| W1-01 | Khảo sát quy trình đánh giá | Có bộ câu hỏi, mẫu biên bản và mô hình AS-IS/TO-BE để xác nhận; chỉ chuyển sang “đã xác nhận” sau khi có phản hồi thực tế từ ít nhất một giảng viên |
| W1-02 | Khảo sát kỹ thuật | Có so sánh bốn nhóm kỹ thuật, baseline, metrics, ưu/nhược điểm, nguồn sơ cấp và khuyến nghị cho đề tài |
| W1-03 | Đặc tả yêu cầu v1 | Có phạm vi, yêu cầu chức năng/phi chức năng, tiêu chí nghiệm thu và ma trận truy vết; nội dung đủ review nhưng chưa thành baseline cho đến khi GVHD phê duyệt |
| W1-04 | Bộ Use Case | Có sơ đồ tổng thể, 17 Use Case chi tiết, luồng lỗi/an toàn và acceptance scenarios; vẫn chờ xác nhận workflow thực tế |
| W1-05 | Backlog/WBS | Có Epic → Story → Task, ưu tiên, ước lượng, phụ thuộc, roadmap 24 tuần, critical path, gate và DoD; phải rebaseline sau khi chốt nhân lực/phạm vi |

## Danh mục tài liệu

- [W1-01 – Hồ sơ khảo sát quy trình](./W1-01-khao-sat-quy-trinh.md)
- [W1-01 – Bộ câu hỏi phỏng vấn](./W1-01-cau-hoi-phong-van.md)
- [W1-01 – Quy trình AS-IS/TO-BE](./W1-01-as-is-to-be.md)
- [W1-02 – Khảo sát kỹ thuật](./W1-02-khao-sat-ky-thuat.md)
- [W1-03 – Đặc tả yêu cầu v1](./W1-03-dac-ta-yeu-cau-v1.md)
- [W1-04 – Bộ Use Case](./W1-04-bo-use-case.md)
- [W1-05 – Product Backlog và WBS](./W1-05-backlog-wbs.md)

## Căn cứ lập tài liệu

1. `Schedule_KLTN.xlsx`, sheet **FILE KẾ HOẠCH MẪU**, dòng tuần 1 (08/08/2026–14/08/2026).
2. `KLTN_He_thong_danh_gia_bao_cao_AI_cuc_bo.docx`, phiên bản 1.0 ngày 29/07/2026.
3. Phản hồi phỏng vấn giảng viên sẽ được bổ sung sau và phải ghi rõ người xác nhận, ngày xác nhận.

Hai tài liệu nguồn đang mâu thuẫn về cơ sở dữ liệu. Theo quyết định của chủ dự án ngày 13/08/2026, hồ sơ chọn **MongoDB** đúng với file kế hoạch; bản DOCX đang ghi PostgreSQL + pgvector phải được cập nhật bằng change record. Deployment và cơ chế Search/Vector Search vẫn cần chốt ở OQ-04.

## Cách sử dụng

1. Gửi bộ câu hỏi W1-01 cho giảng viên trước buổi trao đổi.
2. Trong hoặc ngay sau buổi trao đổi, điền biên bản và đánh dấu từng giả định là `Xác nhận`, `Bác bỏ` hoặc `Cần làm rõ`.
3. Cập nhật sơ đồ AS-IS theo quy trình thực tế; chỉ khi đó mới coi AS-IS là kết quả khảo sát.
4. Dùng W1-02 để thống nhất baseline và metrics trước khi thiết kế thực nghiệm chi tiết.
5. Review W1-03 cùng GVHD; ghi quyết định vào changelog trước khi đổi trạng thái từ `Review Candidate` sang `Approved/Baselined`.
6. Dùng W1-04 để đối chiếu actor, workflow, quyền và các kịch bản lỗi với giảng viên; sau đó chuyển acceptance scenarios thành test case.
7. Sau khi chốt nhân lực, deadline, dữ liệu, rubric và nhánh Search Provider, rebaseline W1-05 rồi đưa các Story được duyệt lên issue board với nguyên ID.

## Điểm cần xác nhận với GVHD

- Quy trình và rubric hiện đang được giảng viên sử dụng trong thực tế.
- Loại, số lượng và quyền sử dụng báo cáo/dữ liệu phục vụ phát triển và benchmark.
- GVHD ghi nhận lựa chọn MongoDB; nhóm chốt Community self-managed hay Atlas, phiên bản và cách triển khai lexical/BM25 + vector search.
- Phương án cho RQ2/A5: không dùng Gemini Grounding để thu thập URL hoặc làm đầu vào crawl/index theo điều khoản hiện hành; chỉ bật Search Provider có quyền sử dụng phù hợp, hoặc chính thức sửa phạm vi và dùng corpus được cấp phép.
- Ngưỡng nghiệm thu, cách lấy ground truth và số người chấm cho thí nghiệm rubric.
- Chính sách lưu giữ, ẩn danh và gửi truy vấn ra dịch vụ tìm kiếm bên ngoài.
- Căn cứ sử dụng dữ liệu, data owner, quyền yêu cầu/duyệt xóa, retention cho toàn bộ dữ liệu dẫn xuất và deletion SLA.
- Nhân lực chính thức, deadline 23/01/2027 hay 07/02/2027, cấu hình máy demo và capacity thực tế.

Không mục nào trong hồ sơ được xem là lời xác nhận của giảng viên nếu chưa có tên/ngày và bằng chứng phản hồi tương ứng.
