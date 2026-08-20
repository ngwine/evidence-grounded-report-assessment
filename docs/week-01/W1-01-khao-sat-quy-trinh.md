# W1-01 — Hồ sơ khảo sát quy trình đánh giá báo cáo

| Thuộc tính | Giá trị |
|---|---|
| Mã công việc | W1-01 |
| Phiên bản | 1.0-draft |
| Ngày lập | 13/08/2026 |
| Trạng thái | **Chờ phỏng vấn và xác nhận** |
| Chủ trì | Nguyễn Trần Ngọc Quý |
| Đối tượng cần khảo sát | Ít nhất 01 giảng viên có kinh nghiệm giao/chấm báo cáo sinh viên |
| Thời lượng dự kiến | 30–45 phút/người |
| Tài liệu liên quan | [Bộ câu hỏi phỏng vấn](./W1-01-cau-hoi-phong-van.md), [Mô hình AS-IS/TO-BE](./W1-01-as-is-to-be.md) |

> Tài liệu này **không phải biên bản phỏng vấn đã hoàn thành**. Tại thời điểm lập, chưa có câu trả lời thực tế, tên người tham gia hoặc bằng chứng xác nhận nào được cung cấp. Các mô tả về quy trình hiện tại được đánh dấu `H` (giả thuyết) và không được trích dẫn như phát hiện khảo sát.

## 1. Mục tiêu khảo sát

Khảo sát nhằm trả lời sáu câu hỏi nghiệp vụ:

1. Giảng viên thực tế tiếp nhận, đọc, kiểm tra, chấm và phản hồi báo cáo theo trình tự nào?
2. Đầu vào, công cụ, tiêu chí/rubric và đầu ra hiện dùng là gì?
3. Khâu nào tốn thời gian, khó kiểm tra nhất hoặc dễ thiếu nhất quán?
4. Loại bằng chứng nào giảng viên cần trước khi tin hoặc sử dụng một cảnh báo/điểm do AI đề xuất?
5. Dữ liệu nào có thể dùng để phát triển và đánh giá hệ thống, với điều kiện bảo mật nào?
6. Luồng TO-BE nào tạo giá trị mà vẫn giữ giảng viên là người quyết định cuối cùng?

Kết quả khảo sát sẽ được dùng để hiệu chỉnh AS-IS/TO-BE, đặc tả yêu cầu, Use Case, rubric mẫu, dataset plan và tiêu chí nghiệm thu. Đây không phải hoạt động đánh giá năng lực người được phỏng vấn.

## 2. Quy ước về mức độ xác thực

| Ký hiệu | Ý nghĩa | Được dùng làm căn cứ yêu cầu? |
|---|---|---|
| `D` — Đã có trong tài liệu | Có thể truy về lịch hoặc bản mô tả khóa luận; chưa đồng nghĩa đã được giảng viên khảo sát xác nhận | Có, nhưng phải ghi nguồn và vẫn có thể cần duyệt |
| `H` — Giả thuyết | Suy đoán hợp lý để dẫn dắt phỏng vấn | Không |
| `C` — Đã xác nhận | Có người xác nhận, ngày xác nhận và bằng chứng/ghi chép đi kèm | Có |
| `R` — Bị bác bỏ | Người tham gia cho biết không đúng với thực tế | Không; giữ lại để truy vết |
| `O` — Chưa rõ | Câu trả lời thiếu, khác nhau giữa người tham gia hoặc cần kiểm tra thêm | Không |

Không chuyển một mục từ `H/D` sang `C` nếu thiếu tối thiểu: người xác nhận, vai trò, ngày và nội dung trả lời tương ứng.

## 3. Những gì đã biết từ tài liệu

Các mục dưới đây là dữ kiện từ tài liệu dự án, **không phải kết quả phỏng vấn**.

| ID | Mệnh đề | Trạng thái | Nguồn |
|---|---|---|---|
| D-01 | Người dùng dự kiến gồm sinh viên, giảng viên và quản trị viên. | D | Bản mô tả khóa luận, mục 4.4 |
| D-02 | Hệ thống được đề xuất nhận báo cáo PDF/DOCX tiếng Việt hoặc tiếng Anh. | D | Bản mô tả, mục 3.2 và 5.1 |
| D-03 | Các nhóm hỗ trợ dự kiến gồm phát hiện tương đồng, chấm theo rubric có bằng chứng, kiểm tra văn phong/logic, xác thực tài liệu tham khảo và sinh câu hỏi. | D | Bản mô tả, mục 5 |
| D-04 | AI chỉ đề xuất; giảng viên phê duyệt kết quả chính thức. | D | Tóm tắt và mục 5.8 của bản mô tả |
| D-05 | Mỗi nhận xét quan trọng được đề xuất gắn với vị trí trong báo cáo hoặc nguồn đối chứng. | D | Tóm tắt và mục 5.3 của bản mô tả |
| D-06 | Định hướng là local-first; không gửi toàn bộ báo cáo ra công cụ tìm kiếm, chỉ gửi truy vấn được chọn lọc và nên loại PII. | D | Bản mô tả, mục 1 và 10.2 |
| D-07 | Tuần 1 yêu cầu khảo sát quy trình giảng viên đánh giá báo cáo và tạo tài liệu khảo sát ban đầu. | D | `Schedule_KLTN.xlsx`, tuần 1 (08/08–14/08/2026) |
| D-08 | Bản mô tả nêu nhận định rằng giảng viên thường phải đọc nhiều báo cáo dài trong thời gian ngắn và phải kiểm tra đồng thời nhiều khía cạnh. | D | Bản mô tả, mục 2 |

`D-08` là nhận định trong đề xuất, chưa phải bằng chứng thực địa. Cần dùng câu hỏi Q06–Q09 để kiểm tra mức độ đúng và đo quy mô thực tế.

## 4. Giả thuyết cần kiểm chứng

| ID | Giả thuyết ban đầu | Câu hỏi kiểm chứng | Trạng thái sau phỏng vấn | Ghi chú/bằng chứng |
|---|---|---|---|---|
| H-01 | Báo cáo được nộp qua một hoặc nhiều kênh như LMS, email hoặc thư mục dùng chung. | Q03 | Chưa khảo sát | — |
| H-02 | Giảng viên kiểm tra điều kiện nộp trước khi đọc nội dung. | Q04 | Chưa khảo sát | — |
| H-03 | Cách dùng rubric và trọng số khác nhau tùy môn hoặc loại báo cáo. | Q05, Q10 | Chưa khảo sát | — |
| H-04 | Giảng viên phải chuyển qua nhiều công cụ để kiểm tra tương đồng, nguồn và hình thức. | Q07 | Chưa khảo sát | — |
| H-05 | Tìm nguồn đối chứng và kiểm tra trích dẫn là các bước tốn thời gian. | Q06, Q08 | Chưa khảo sát | — |
| H-06 | Chất lượng chấm có thể bị ảnh hưởng bởi số lượng bài và thời hạn. | Q06, Q09 | Chưa khảo sát | — |
| H-07 | Giảng viên chỉ chấp nhận gợi ý AI khi xem được đoạn báo cáo, đoạn nguồn và lý do. | Q11, Q12 | Chưa khảo sát | — |
| H-08 | Sinh viên chỉ nên xem nội dung đã được giảng viên công bố. | Q14 | Chưa khảo sát | — |
| H-09 | Có thể dùng một tập báo cáo đã ẩn danh để phát triển/benchmark nếu được phê duyệt. | Q15–Q17 | Chưa khảo sát | — |
| H-10 | Luồng TO-BE trong tài liệu liên quan phù hợp với hoạt động giảng dạy thực tế. | Q18–Q20 | Chưa khảo sát | — |

## 5. Kế hoạch thực hiện khảo sát

### 5.1. Chọn người tham gia

Tiêu chí tối thiểu:

- Đã từng chấm báo cáo môn học, đồ án hoặc khóa luận;
- Trực tiếp sử dụng tiêu chí/rubric hoặc chịu trách nhiệm quyết định điểm;
- Đồng ý dành 30–45 phút và cho phép ghi chép;
- Có thể mô tả ít nhất một trường hợp chấm gần đây, không cần tiết lộ danh tính sinh viên.

Mẫu tối thiểu của W1-01 là 01 giảng viên. Nếu quy trình khác nhau đáng kể theo môn, nên bổ sung người thứ hai để tránh xem một trường hợp cá nhân là quy trình chung.

### 5.2. Trình tự

1. Gửi mục tiêu và nhóm câu hỏi trước buổi trao đổi; không gửi giả định như kết luận đã có.
2. Xin đồng ý ghi chép; chỉ ghi âm khi người tham gia đồng ý rõ ràng.
3. Phỏng vấn bán cấu trúc theo [bộ câu hỏi](./W1-01-cau-hoi-phong-van.md), ưu tiên một trường hợp chấm gần đây.
4. Vẽ/cập nhật quy trình ngay trong buổi trao đổi nếu có thể.
5. Sau buổi phỏng vấn, tách rõ phát biểu trực tiếp, diễn giải của người ghi và quyết định yêu cầu.
6. Gửi bản tóm tắt và sơ đồ cho người tham gia xác nhận; lưu ngày và kênh xác nhận.
7. Cập nhật từng `H` thành `C`, `R` hoặc `O`; không xóa lịch sử giả thuyết bị bác bỏ.

### 5.3. Bằng chứng nên lưu

- Biên bản đã điền;
- Ảnh/chụp màn hình hoặc file rubric mẫu nếu được phép;
- Email/tin nhắn xác nhận bản tóm tắt;
- File ghi âm chỉ khi có đồng ý và có thời hạn xóa;
- Tài liệu mẫu phải được ẩn danh; không đưa báo cáo thật vào Git.

## 6. Mẫu biên bản phỏng vấn

Sao chép phần này cho từng người tham gia. Không điền thay người tham gia bằng suy đoán.

### 6.1. Thông tin phiên

| Trường | Nội dung cần điền |
|---|---|
| Mã phiên | INT-____ |
| Ngày/giờ | ____ |
| Hình thức/địa điểm | ____ |
| Người phỏng vấn | ____ |
| Người tham gia | ____ |
| Vai trò/khoa/môn (nếu được phép ghi) | ____ |
| Kinh nghiệm chấm loại báo cáo này | ____ |
| Đồng ý ghi chép | Có / Không |
| Đồng ý ghi âm | Có / Không / Không đề nghị |
| Phạm vi được phép sử dụng nội dung | Nội bộ dự án / Đưa vào luận văn đã ẩn danh / Khác: ____ |
| Thời hạn lưu/xóa ghi âm (nếu có) | ____ |

### 6.2. Bối cảnh trường hợp được mô tả

| Nội dung | Câu trả lời/ghi chú |
|---|---|
| Loại báo cáo/môn học | ____ |
| Số lượng bài trong một đợt | ____ |
| Độ dài/định dạng thường gặp | ____ |
| Thời gian chấm mỗi bài/đợt | ____ |
| Người cùng tham gia chấm | ____ |
| Công cụ/kênh nộp bài | ____ |
| Rubric/thang điểm/quy định đang dùng | ____ |

### 6.3. Ghi nhận quy trình thực tế

| Bước | Người thực hiện | Đầu vào | Hành động/công cụ | Đầu ra | Thời gian ước tính | Lỗi/ngoại lệ |
|---:|---|---|---|---|---:|---|
| 1 | ____ | ____ | ____ | ____ | ____ | ____ |
| 2 | ____ | ____ | ____ | ____ | ____ | ____ |
| 3 | ____ | ____ | ____ | ____ | ____ | ____ |
| 4 | ____ | ____ | ____ | ____ | ____ | ____ |
| 5 | ____ | ____ | ____ | ____ | ____ | ____ |
| 6 | ____ | ____ | ____ | ____ | ____ | ____ |

### 6.4. Pain points được người tham gia nêu

| ID | Vấn đề (ghi sát ý người tham gia) | Tần suất | Mức ảnh hưởng 1–5 | Cách xử lý hiện tại | Bằng chứng/ví dụ | Cơ hội hỗ trợ |
|---|---|---|---:|---|---|---|
| P-01 | ____ | ____ | ____ | ____ | ____ | ____ |
| P-02 | ____ | ____ | ____ | ____ | ____ | ____ |
| P-03 | ____ | ____ | ____ | ____ | ____ | ____ |

### 6.5. Dữ liệu đầu vào và đầu ra mong muốn

| Nhóm | Nội dung thực tế | Bắt buộc? | Định dạng/nguồn | Nhạy cảm? | Ai được xem? |
|---|---|---|---|---|---|
| Báo cáo sinh viên | ____ | ____ | ____ | ____ | ____ |
| Yêu cầu đề bài | ____ | ____ | ____ | ____ | ____ |
| Rubric/thang điểm | ____ | ____ | ____ | ____ | ____ |
| Kho bài/nguồn đối chiếu | ____ | ____ | ____ | ____ | ____ |
| Nhận xét/điểm lịch sử | ____ | ____ | ____ | ____ | ____ |
| Đầu ra khác | ____ | ____ | ____ | ____ | ____ |

### 6.6. Đánh giá đề xuất TO-BE

| Hạng mục đề xuất | Giá trị 1–5 | Rủi ro/lo ngại | Bằng chứng tối thiểu cần hiển thị | Có thể tự động đến mức nào? |
|---|---:|---|---|---|
| Phát hiện tương đồng | ____ | ____ | ____ | ____ |
| Đề xuất điểm theo rubric | ____ | ____ | ____ | ____ |
| Kiểm tra văn phong/logic | ____ | ____ | ____ | ____ |
| Kiểm tra tài liệu tham khảo | ____ | ____ | ____ | ____ |
| Sinh câu hỏi vấn đáp | ____ | ____ | ____ | ____ |
| Xuất báo cáo tổng hợp | ____ | ____ | ____ | ____ |

### 6.7. Tóm tắt và xác nhận

**Ba phát hiện chính**

1. ____
2. ____
3. ____

**Ba yêu cầu/ưu tiên được đề xuất**

1. ____
2. ____
3. ____

**Điểm còn mâu thuẫn hoặc cần hỏi lại:** ____

**Tóm tắt được người tham gia xác nhận:** Chưa / Có, ngày ____ qua ____

**Người ghi biên bản:** ____  
**Người xác nhận (nếu áp dụng):** ____

## 7. Bảng tổng hợp sau khảo sát

Chỉ điền khi đã có ít nhất một biên bản thực tế.

| Chủ đề | Phát hiện đã xác nhận | Người/bằng chứng | Tác động đến hệ thống | Quyết định hoặc việc tiếp theo |
|---|---|---|---|---|
| Quy trình AS-IS | Chưa có dữ liệu | — | Chưa kết luận | Thực hiện INT-01 |
| Rubric/cách chấm | Chưa có dữ liệu | — | Chưa khóa cấu trúc rubric | Thực hiện INT-01 |
| Pain points | Chưa có dữ liệu thực địa | — | Chưa xếp hạng ưu tiên | Thực hiện INT-01 |
| Dữ liệu có thể sử dụng | Chưa có dữ liệu | — | Chưa thể chốt dataset thật | Xin phép và xác nhận chính sách |
| Đầu ra mong muốn | Chưa có dữ liệu | — | Dùng bản đề xuất làm draft | Cho giảng viên review TO-BE |

## 8. Quyết định và vấn đề mở

| ID | Vấn đề cần quyết định | Chủ sở hữu | Hạn mong muốn | Trạng thái |
|---|---|---|---|---|
| O-01 | Ai là giảng viên tham gia INT-01 và lịch trao đổi? | Sinh viên/GVHD | Tuần 1 | Mở |
| O-02 | Có rubric và báo cáo mẫu nào được phép cung cấp không? | Giảng viên | Sau INT-01 | Mở |
| O-03 | Báo cáo thật có được dùng cho phát triển/benchmark sau khi ẩn danh không? | GVHD/đơn vị có thẩm quyền | Trước thu thập dataset | Mở |
| O-04 | Nội dung nào sinh viên được phép xem trong phản hồi? | Giảng viên | Trước thiết kế phân quyền | Mở |
| O-05 | Có được gửi truy vấn đã loại PII đến dịch vụ tìm kiếm ngoài không? | GVHD/đơn vị có thẩm quyền | Trước tích hợp web search | Mở |

## 9. Definition of Done cho W1-01

W1-01 chỉ chuyển sang `Hoàn thành` khi:

- Có ít nhất 01 biên bản phỏng vấn được điền từ trao đổi thực tế;
- Người tham gia, vai trò và ngày trao đổi được ghi lại (có thể dùng mã ẩn danh trong bản công khai);
- Quy trình AS-IS được cập nhật và người tham gia xác nhận hoặc có ghi chú rõ phần chưa xác nhận;
- Có danh sách pain point, input và output mong muốn dựa trên câu trả lời thực;
- Từng giả thuyết H-01…H-10 được đánh dấu `C`, `R` hoặc `O` kèm căn cứ;
- Mọi dữ liệu nhạy cảm/tài liệu mẫu có quyền sử dụng và cách ẩn danh rõ ràng;
- Các thay đổi kéo theo cho yêu cầu, Use Case và TO-BE được ghi vào bảng quyết định.

Hiện trạng: **chưa đạt Definition of Done vì chưa có cuộc phỏng vấn thực tế**. Bộ hồ sơ hiện đã sẵn sàng để tiến hành INT-01.

## 10. Nguồn

1. `Schedule_KLTN.xlsx`, sheet **FILE KẾ HOẠCH MẪU**, tuần 1 (08/08/2026–14/08/2026).
2. `KLTN_He_thong_danh_gia_bao_cao_AI_cuc_bo.docx`, phiên bản 1.0, cập nhật 29/07/2026.

