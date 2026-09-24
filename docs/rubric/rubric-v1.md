# W2.5 - Rubric Template, Checklist, Quy tắc gắn nhãn và Annotation/Adjudication guideline V1

| Thuộc tính | Giá trị                    |
| ------------ | ---------------------------- |
| Phiên bản  | 1                            |
| Ngày        | 19/09/2026                   |
| WBS          | `W2.5`                     |
| Owner        | Võ Thị Kim Yến (Y)        |
| Reviewer     | Nguyễn Trần Ngọc Quý (Q) |

## 1. Mục đích và giới hạn

Tài liệu này trả lời những câu hỏi liên quan đến Rubric và chấm điểm báo cáo theo Rubric:

1. Thiết kế Rubric Template v1;
2. Checklist LOCAL/GRAPH;
3. Quy tắc gán nhãn Checklist;
4. Quy tắc quyết định;
5. Annotation/Adjudication guideline.

*Tài liệu này không bao gồm toàn bộ quy trình Đánh giá báo cáo dựa trên bằng chứng (Pipeline 2).*

## 2. Rubric Template

Rubric template là giao diện nhập liệu dành cho GV khi tạo rubric đánh giá (Tầng 1). GV chỉ thao tác trên 3 thành phần: tiêu chí, trọng số và mức đánh giá (kèm thang điểm tương ứng cho từng mức). Từ rubric template này, hệ thống tự động phân tách thành checklist chi tiết và áp dụng quy tắc quyết định để đánh giá báo cáo.
Rubric gồm 4 thành phần: **tiêu chí, trọng số, mức độ đánh giá, thang điểm đánh giá.**

| Tiêu chí          | Trọng số | Mức độ 1 | Mức độ 2 | ... | Mức độ 6 |
| ------------------- | :--------: | :---------: | :---------: | :-: | :---------: |
| TC 1: ............. |    ...    |     ...     |     ...     | ... |     ...     |
| TC 2: ............. |    ...    |     ...     |     ...     | ... |     ...     |
| TC 3: ............. |    ...    |     ...     |     ...     | ... |     ...     |

- **Tiêu chí**: do GV tự định nghĩa, có thể viết chung chung hoặc chi tiết tuỳ ý (tối thiểu 3, tối đa 15 tiêu chí). Hệ thống có trách nhiệm tự động phân tách mỗi tiêu chí thành các điều kiện/checklist chi tiết (Tầng 2), đo lường được, để đảm bảo tính nhất quán khi đánh giá - không phụ thuộc vào độ chi tiết của input ban đầu.
- **Trọng số**: GV cần định nghĩa trọng số (điểm tối đa) cho mỗi tiêu chí trong rubric. Trọng số thể hiện mức độ quan trọng của từng tiêu chí trong rubric.
- **Mức độ đánh giá**: GV có thể định nghĩa tối thiểu 2 và tối đa 6 mức độ đánh giá trong rubric, toàn bộ tiêu chí đều có cùng số lượng mức độ đánh giá giống nhau. Mức độ đánh giá thể hiện rằng bài báo cáo của sinh viên đã hoàn thành ở mức độ nào của tiêu chí.
- **Thang điểm đánh giá**: GV cần định nghĩa điểm cụ thể cho mỗi mức độ của từng tiêu chí bằng cách nhập [điểm thấp nhất, điểm cao nhất] cho mỗi mức, điểm được làm tròn đến 1 chữ số thập phân (ví dụ: 7.9, 8.0). Các ràng buộc cho thang điểm đánh giá:

  - (1) Điểm thấp nhất và cao nhất của mỗi mức đều nằm trong khoảng [0, Trọng số của tiêu chí].;
  - (2) Cận trên (điểm cao nhất) của mức cao nhất phải bằng đúng Trọng số.;
  - (3) Các khoảng không chồng lấn nhau và giảm dần theo thứ tự cột mức độ: cận dưới của 1 mức phải lớn hơn cận trên của mức kế tiếp (mức thấp hơn); ví dụ mức 1 (Tốt) = [8.0, 10.0], mức 2 (Khá) = [5.0, 8.0), không được có mức nào trùng khoảng với mức khác.

  Lưu ý: Tất cả các giá trị số trong rubric (Trọng số, điểm mỗi mức độ) đều thống nhất dùng số thập phân, định dạng 1 chữ số thập phân.

## 3. Ví dụ minh hoạ - Rubric cho đề tài Mobile Banking App

Ví dụ minh họa được xây dựng bám theo đề tài `FinalProject_2024_2025.pdf` của báo cáo **InDomain_R1_anonymized** (Course: Mobile Apps Development, TDT University).

* Các thang mức độ đánh giá: **4 mức - Tốt / Khá / Trung bình / Yếu**.
* Tổng trọng số = 100

*Thực tế tổng điểm báo cáo chiếm 4/10 điểm, src code chiếm 6/10 điểm*

*→ Điểm báo cáo = (Điểm hệ thống chấm được trên thang 100 / 100) * 4*

### Nhóm A - Chức năng nghiệp vụ (Business Requirements)

| Tiêu chí                  | Trọng số | Tốt         | Khá         | Trung bình  | Yếu        |
| --------------------------- | ---------- | ------------ | ------------ | ------------ | ----------- |
| A1 - User profiles          | 10         | [8.5, 10.0]  | [7.0, 8.5)   | [5.0, 7.0)   | [0.0, 5.0)  |
| A2 - Security               | 20         | [17.0, 20.0] | [14.0, 17.0) | [10.0, 14.0) | [0.0, 10.0) |
| A3 - Account management     | 15         | [12.8, 15.0] | [10.5, 12.8) | [7.5, 10.5)  | [0.0, 7.5)  |
| A4 - Transaction management | 15         | [12.8, 15.0] | [10.5, 12.8) | [7.5, 10.5)  | [0.0, 7.5)  |
| A5 - Utilities              | 5          | [4.3, 5.0]   | [3.5, 4.3)   | [2.5, 3.5)   | [0.0, 2.5)  |
| A6 - Navigation             | 5          | [4.3, 5.0]   | [3.5, 4.3)   | [2.5, 3.5)   | [0.0, 2.5)  |

### Nhóm B - Kỹ thuật & báo cáo (Technical Requirements)

| Tiêu chí                                     | Trọng số | Tốt        | Khá       | Trung bình | Yếu       |
| ---------------------------------------------- | ---------- | ----------- | ---------- | ----------- | ---------- |
| B1 - Phân tích & thiết kế                  | 10         | [8.5, 10.0] | [7.0, 8.5) | [5.0, 7.0)  | [0.0, 5.0) |
| B2 - Implementation                            | 10         | [8.5, 10.0] | [7.0, 8.5) | [5.0, 7.0)  | [0.0, 5.0) |
| B3 - User Interface                            | 5          | [4.3, 5.0]  | [3.5, 4.3) | [2.5, 3.5)  | [0.0, 2.5) |
| B4 - Tính nhất quán & đầy đủ tổng thể | 5          | [4.3, 5.0]  | [3.5, 4.3) | [2.5, 3.5)  | [0.0, 2.5) |

### Mô tả nội dung từng tiêu chí

- **A1 - User profiles**: Phân quyền 2 loại người dùng (customer/officer), officer tạo/sửa tài khoản customer, customer xem/sửa thông tin của mình.
- **A2 - Security**: Đăng nhập, eKYC xác thực danh tính (sinh trắc học/scan mặt), 2FA/OTP cho mọi giao dịch giá trị.
- **A3 - Account management**: 3 loại tài khoản (checking/saving/mortgage), xem số dư, lãi suất, lịch trả góp, lịch sử giao dịch, nạp/rút tiền.
- **A4 - Transaction management**: Chuyển tiền cùng/khác ngân hàng, tích hợp cổng thanh toán (VNPay/Stripe), kiểm tra hợp lệ trước khi lưu.
- **A5 - Utilities**: Thanh toán điện/nước, nạp tiền điện thoại, mua vé máy bay/phim/khách sạn/thương mại điện tử.
- **A6 - Navigation**: Định vị người dùng, hiển thị chi nhánh gần nhất trên bản đồ, gợi ý đường đi ngắn nhất.
- **B1 - Phân tích & thiết kế**: Có đầy đủ class diagram, ER diagram, use-case diagram, solution diagram; giải thích nguyên tắc/pattern thiết kế đã áp dụng.
- **B2 - Implementation**: Giải thích cấu trúc code, công nghệ sử dụng, khớp với thiết kế ở B1.
- **B3 - User Interface**: Trình bày đầy đủ giao diện thể hiện tất cả chức năng đã nêu ở Nhóm A.
- **B4 - Tính nhất quán & đầy đủ tổng thể**: Các phần (nghiệp vụ → thiết kế → hiện thực → giao diện) khớp nhau, không mâu thuẫn, không thiếu mục bắt buộc.

## 4. Checklist LOCAL / GRAPH

**Checklist là các điều kiện nguyên tử** (atomic), cụ thể và đo lường được, do **hệ thống tự động tách ra từ mỗi tiêu chí ở Rubric template** (Tầng 1), bất kể tiêu chí đó được GV viết chung chung hay chi tiết. Mục đích của việc tách checklist là **biến 1 tiêu chí** **(vốn có thể diễn đạt mơ hồ, nhiều cách hiểu)** **thành nhiều câu kiểm tra rõ ràng**, mỗi câu chỉ trả lời đúng 1 câu hỏi "**có/không**", giúp việc đánh giá nhất quán và có thể giải thích được, thay vì để hệ thống tự phán đoán mơ hồ trên cả 1 tiêu chí lớn.

Mỗi checklist được phân loại thành 1 trong 2 dạng:

- **LOCAL**: Chỉ cần xem 1 đoạn hoặc 1 số đoạn cụ thể trong báo cáo là đủ để kiểm tra được, không cần đối chiếu thêm phần nào khác.
- **GRAPH**: Cần đối chiếu thông tin và các quan hệ tri thức (giữa claim, phương pháp, kết quả, kết luận) thuộc nhiều phần của báo cáo (hoặc nhiều nguồn dữ liệu) mới kết luận được, vì bản chất câu hỏi đòi hỏi tính nhất quán/liên kết giữa các phần.

Sau khi được phân tách, hệ thống sẽ tự động dự đoán và gán nhãn thuộc tính Cốt lõi/Bắt buộc/Không bắt buộc cho từng checklist; GV hoàn toàn có quyền tinh chỉnh lại các nhãn này. Bước tiếp theo, dựa trên bằng chứng thu thập được, mỗi checklist sẽ được xác minh ở một trong ba trạng thái: MET, UNMET hoặc CANNOT_ASSESS theo quy tắc tại Mục 5.

Ý nghĩa của các thuộc tính được gán nhãn:

* **Cốt lõi**: Checklist mang tính tất yếu, không được phép thiếu trong bài báo cáo.
* **Bắt buộc**: Checklist mang tính chuẩn cần phải đạt, được phép thiếu hoặc làm sai/không đạt.
* **Không bắt buộc**: Checklist mang tính bổ sung, mở rộng.

Dưới đây là ví dụ về danh sách Checklist được tách ra từ 10 tiêu chí ở mục 2 (ví dụ minh hoạ phân tách thủ công để làm mẫu tham chiếu cho hệ thống).

### Nhóm A

**A1 - User profiles**

- A1.1 [LOCAL] [BẮT BUỘC] Có mô tả 2 loại người dùng: customer và bank officer, phân biệt quyền hạn khác nhau.
- A1.2 [LOCAL] [BẮT BUỘC] Officer có quyền tạo tài khoản cho customer.
- A1.3 [GRAPH] [BẮT BUỘC] Officer có quyền sửa thông tin customer khi có yêu cầu (đối chiếu mô tả quyền hạn officer với luồng "customer yêu cầu sửa").
- A1.4 [LOCAL] [BẮT BUỘC] Customer có thể tự xem/sửa thông tin của mình.
- A1.5 [GRAPH] [BẮT BUỘC] Giao diện thể hiện đúng 2 loại quyền khác nhau cho 2 loại người dùng.

**A2 - Security**

- A2.1 [LOCAL] [BẮT BUỘC] Có màn hình đăng nhập.
- A2.2 [LOCAL] [BẮT BUỘC] Có áp dụng eKYC để định danh người dùng.
- A2.3 [LOCAL] [BẮT BUỘC] Có áp dụng 2FA/OTP cho giao dịch giá trị cao.
- A2.4 [GRAPH] [BẮT BUỘC] Mọi giao dịch mô tả ở A4 đều đi qua bước 2FA/OTP đã mô tả ở đây.

**A3 - Account management**

- A3.1 [LOCAL] [BẮT BUỘC] Có mô tả 3 loại tài khoản: checking, saving, mortgage.
- A3.2 [LOCAL] [BẮT BUỘC] Customer xem được số dư checking/saving.
- A3.3 [LOCAL] [BẮT BUỘC] Customer xem được lãi suất và lợi nhuận hàng tháng của saving.
- A3.4 [LOCAL] [BẮT BUỘC] Officer có quyền chỉnh lãi suất theo chính sách ngân hàng.
- A3.5 [LOCAL] [BẮT BUỘC] Customer xem được số tiền phải trả hàng tháng/2 tuần cho mortgage.
- A3.6 [LOCAL] [BẮT BUỘC] Customer xem được lịch sử giao dịch của tài khoản.
- A3.7 [LOCAL] [BẮT BUỘC] Customer có thể nạp (deposit) hoặc rút (withdraw) tiền.

**A4 - Transaction management**

- A4.1 [GRAPH] [BẮT BUỘC] Giao dịch phải tuân theo yêu cầu bảo mật đã mô tả ở A2 (đối chiếu bước 2FA/OTP).
- A4.2 [LOCAL] [BẮT BUỘC] Hệ thống kiểm tra giao dịch hợp lệ trước khi lưu vào database.
- A4.3 [LOCAL] [BẮT BUỘC] Hỗ trợ chuyển tiền cùng ngân hàng.
- A4.4 [LOCAL] [BẮT BUỘC] Hỗ trợ chuyển tiền khác ngân hàng.
- A4.5 [LOCAL] [BẮT BUỘC] Có tích hợp cổng thanh toán (VNPay hoặc Stripe).

**A5 - Utilities**

- A5.1 [LOCAL] [BẮT BUỘC] Hỗ trợ thanh toán tiền điện.
- A5.2 [LOCAL] [BẮT BUỘC] Hỗ trợ thanh toán tiền nước.
- A5.3 [LOCAL] [BẮT BUỘC] Hỗ trợ nạp tiền điện thoại.
- A5.4 [LOCAL] [BẮT BUỘC] Hỗ trợ mua vé máy bay/phim/khách sạn hoặc thanh toán trên nền tảng thương mại điện tử.

**A6 - Navigation**

- A6.1 [LOCAL] [BẮT BUỘC] Định vị vị trí người dùng trên bản đồ.
- A6.2 [LOCAL] [BẮT BUỘC] Hiển thị vị trí các chi nhánh ngân hàng gần đó.
- A6.3 [LOCAL] [BẮT BUỘC] Gợi ý đường đi ngắn nhất đến chi nhánh gần nhất.

### Nhóm B

**B1 - Phân tích & thiết kế**

- B1.1 [LOCAL] [BẮT BUỘC] Có class diagram.
- B1.2 [LOCAL] [BẮT BUỘC] Có ER diagram (entity-relationship).
- B1.3 [LOCAL] [BẮT BUỘC] Có use-case diagram.
- B1.4 [LOCAL] [BẮT BUỘC] Có solution diagram (kiến trúc/hạ tầng).
- B1.5 [LOCAL] [BẮT BUỘC] Có giải thích nguyên tắc/pattern thiết kế đã áp dụng.
- B1.6 [GRAPH] [BẮT BUỘC] Các sơ đồ nhất quán với nhau (VD: class diagram khớp với ER diagram).

**B2 - Implementation**

- B2.1 [LOCAL] [BẮT BUỘC] Có mô tả cấu trúc code (kiến trúc thư mục, layer...).
- B2.2 [LOCAL] [BẮT BUỘC] Có liệt kê công nghệ/framework sử dụng.
- B2.3 [GRAPH] [BẮT BUỘC] Cách hiện thực khớp với thiết kế đã mô tả ở B1.

**B3 - User Interface**

- B3.1 [LOCAL] [BẮT BUỘC] Có trình bày giao diện cho từng chức năng chính (screenshot hoặc mô tả).
- B3.2 [GRAPH] [BẮT BUỘC] Giao diện thể hiện đúng luồng chức năng đã mô tả ở Nhóm A.

**B4 - Tính nhất quán & đầy đủ tổng thể**

- B4.1 [GRAPH] [BẮT BUỘC] Nghiệp vụ (Nhóm A) khớp với thiết kế (B1).
- B4.2 [GRAPH] [BẮT BUỘC] Thiết kế (B1) khớp với hiện thực (B2).
- B4.3 [GRAPH] [BẮT BUỘC] Hiện thực (B2) khớp với giao diện (B3).
- B4.4 [LOCAL] [BẮT BUỘC] Không thiếu mục bắt buộc nào theo cấu trúc đề yêu cầu (Analysis and Design, Implementation, User Interface).

## 5. Quy tắc gán nhãn checklist (MET / UNMET / CANNOT_ASSESS)

**Gán nhãn checklist** là quá trình **biến kết quả kiểm tra bằng chứng thành 1 giá trị chuẩn hoá** mà hệ thống có thể tính toán được, là bước trung gian bắt buộc giữa việc Kiểm tra bằng chứng trong báo cáo (định tính) và việc tính điểm theo Quy tắc quyết định (định lượng). Kết quả gán nhãn của toàn bộ checklist trong 1 tiêu chí sẽ được **dùng để tính tỉ lệ % MET**, từ đó suy ra mức độ đánh giá và điểm số của tiêu chí đó.

Mỗi checklist trong Tầng 2 cần được gán 1 trong 3 nhãn: **MET**, **UNMET**, hoặc **CANNOT_ASSESS**, thể hiện kết quả kiểm tra checklist đó đối với báo cáo đang được đánh giá.

|                       Trạng thái                       | Điều kiện                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | Ví dụ                                                                                                                                                                                                                |
| :------------------------------------------------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|                **MET<br />(ĐẠT)**                | Tìm thấy **bằng chứng rõ ràng**, **trực tiếp**, **đầy đủ** chứng minh **checklist được đáp ứng**.                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Checklist "Có ER diagram"<br />→ báo cáo có hình ER diagram rõ ràng trong phần Analysis and Design<br />→ MET.                                                                                               |
|           **UNMET<br />(KHÔNG ĐẠT)**           | Có**bằng chứng** cụ thể, rõ ràng cho thấy **checklist KHÔNG được đáp ứng**, bao gồm một trong các trường hợp:<br />- (1) có **làm nhưng không đạt** yêu cầu;<br />- (2) báo cáo nói rõ là **không có/không làm**;<br />- (3) báo cáo hoàn toàn **bỏ trống**, **không đề cập** đến (đối với checklist được gán nhãn thuộc tính **bắt buộc**);<br /> - (4) **mâu thuẫn** giữa các phần trong báo cáo, mâu thuẫn trực tiếp với tài liệu đối chứng có tính chuẩn. | Checklist "Tích hợp cổng thanh toán VNPay/Stripe"<br />→ báo cáo chỉ mô tả chuyển khoản nội bộ, không nhắc cổng thanh toán VNPay/Stripe nào<br />→ UNMET                                          |
| **CANNOT_ASSESS<br />(KHÔNG THỂ ĐÁNH GIÁ**) | Báo cáo**đề cập chung chung/mơ hồ** về khía cạnh liên quan đến checklist, **không có đủ bằng chứng** cụ thể để hệ thống đưa ra kết luận là checklist này được đáp ứng hay không.<br />Báo cáo **hoàn toàn bỏ trống**, **không đề cập đến** (đối với checklist được gán nhãn thuộc tính **không bắt buộc**).                                                                                                                                                                                         | Checklist "Giải thích nguyên tắc/pattern thiết kế"<br />→ báo cáo chỉ nhắc chung chung là "hệ thống có áp dụng thiết kế hiện đại" nhưng không nói rõ là pattern nào<br />→ CANNOT_ASSESS |

**Lưu ý**: ở phiên bản hiện tại, hệ thống chưa có khả năng phân tích nội dung hình ảnh/sơ đồ, nên với các checklist liên quan tới hình vẽ, bằng chứng chỉ giới hạn ở caption/mô tả văn bản liên quan.

## 6. Quy tắc quyết định (Deterministic Decision Rules)

Điểm số của báo cáo được suy ra theo quy trình, không để mô hình ngôn ngữ tự quyết định điểm:Hệ thống chấm từng checklist con của 1 tiêu chí là MET / UNMET / CANNOT_ASSESS dựa trên bằng chứng.

1. Tính tỉ lệ % MET trên tổng số checklist có thể chấm được.
2. Nếu tiêu chí thiếu 1 điều kiện được đánh dấu **bắt buộc/cốt lõi** → tự động xếp mức thấp nhất, bất kể tỉ lệ % còn lại.
3. Nếu tỉ lệ CANNOT_ASSESS trong 1 tiêu chí quá cao (**>=2** hoặc chiếm **>40% tổng số checklist của tiêu chí** đó) → hệ thống KHÔNG tự đưa ra mức độ, mà đánh dấu "cần giảng viên xem lại".
4. Ngược lại, từ tỉ lệ % MET → xác định tiêu chí rơi vào mức nào (theo ngưỡng chia đều theo N mức của rubric đó)
5. Áp dụng **công thức nội suy tuyến tính** để quy đổi từ tỷ lệ **%MET** thực tế thành điểm số cụ thể nằm trong dải điểm của mức độ đã xác định:

$$
S = S_{min} + \frac{\%MET - \%MET_{min}}{\%MET_{max} - \%MET_{min}} \times (S_{max} - S_{min})
$$

Trong đó:	

* **$S$**: Điểm số cụ thể của tiêu chí (làm tròn đến 1 chữ số thập phân).
* **$[S_{min}, S_{max}]$**: Khoảng điểm giới hạn của mức đánh giá hiện tại.
* **$[\%MET_{min}, \%MET_{max}]$**: Ngưỡng tỷ lệ hoàn thành checklist tương ứng của mức đó.

6. Cộng dồn điểm có trọng số của tất cả tiêu chí **$\rightarrow$** điểm tổng của rubric, làm tròn đến 1 chữ số thập phân.

## 7. Xử lý khi 2 người gán nhãn khác nhau (Adjudication)

Khi 2 người gán nhãn độc lập cho cùng 1 checklist trên cùng 1 báo cáo, bất đồng có thể xảy ra ở 2 dạng:

* (1) khác nhãn (VD người A gán MET, người B gán UNMET), hoặc
* (2) cùng nhãn nhưng khác đoạn bằng chứng trích dẫn.

Quy trình xử lý:

1. Sau khi 2 người gán nhãn xong độc lập (không trao đổi trước), tính **tỉ lệ đồng thuận (agreement rate)** trên toàn bộ checklist đã gán.
2. Với từng trường hợp bất đồng, 2 người **đối chiếu lại đúng đoạn bằng chứng** trong báo cáo và thảo luận trực tiếp để thống nhất nhãn cuối cùng.
3. Nếu không tự thống nhất được, chuyển cho **người thứ ba (GVHD)** quyết định nhãn cuối cùng.
4. Ghi lại toàn bộ trường hợp bất đồng - checklist nào, 2 nhãn ban đầu, nhãn cuối cùng, lý do - vào **Adjudication Log** riêng để phục vụ phân tích chất lượng gán nhãn.
5. Nếu bất đồng lặp lại nhiều lần trên cùng 1 dạng checklist (VD tất cả checklist GRAPH liên quan đến "tính nhất quán" đều gây tranh cãi) → xem xét viết lại rõ hơn quy tắc MET/UNMET/CANNOT_ASSESS cho dạng đó ở mục 2 (feedback loop cải thiện guideline).
