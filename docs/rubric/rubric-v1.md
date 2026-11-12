# W2.5 — Rubric Template, Checklist, Quy tắc gán nhãn và Annotation/Adjudication Guideline v1

| Thuộc tính | Giá trị                    |
| ------------ | ---------------------------- |
| Phiên bản  | `1.0.0-rc1`                  |
| Ngày cập nhật | 20/10/2026                |
| WBS          | `W2.5`                     |
| Owner        | Võ Thị Kim Yến (Y)        |
| Reviewer     | Nguyễn Trần Ngọc Quý (Q) |
| Trạng thái | Review candidate; feasibility baseline |

## 1. Mục đích và giới hạn

Tài liệu này trả lời những câu hỏi liên quan đến Rubric và chấm điểm báo cáo theo Rubric:

1. Thiết kế Rubric Template v1;
2. Checklist LOCAL/GRAPH;
3. Quy tắc gán nhãn Checklist;
4. Quy tắc quyết định;
5. Annotation/Adjudication guideline.

*Tài liệu này không bao gồm toàn bộ quy trình Đánh giá báo cáo dựa trên bằng chứng (Pipeline 2).*

## 2. Rubric Template

Rubric template là giao diện nhập liệu dành cho GV khi tạo rubric đánh giá (Tầng 1). GV khai báo tiêu chí, trọng số, mức đánh giá và các checklist nguyên tử kèm yêu cầu bằng chứng. Compiler hiện tại kiểm tra, chuẩn hóa và gán ID ổn định cho dữ liệu đã khai báo; **chưa tự động phân tách tiêu chí tự do thành checklist bằng LLM**. Automatic rubric decomposition là hướng nghiên cứu sau, không thuộc feasibility baseline đang chạy.
Rubric gồm 4 thành phần: **tiêu chí, trọng số, mức độ đánh giá, thang điểm đánh giá.**

| Tiêu chí          | Trọng số | Mức độ 1 | Mức độ 2 | ... | Mức độ 6 |
| ------------------- | :--------: | :---------: | :---------: | :-: | :---------: |
| TC 1: ............. |    ...    |     ...     |     ...     | ... |     ...     |
| TC 2: ............. |    ...    |     ...     |     ...     | ... |     ...     |
| TC 3: ............. |    ...    |     ...     |     ...     | ... |     ...     |

- **Tiêu chí**: do GV tự định nghĩa và phải kèm các checklist nguyên tử, đo lường được. Baseline không tự suy diễn checklist từ một tiêu chí mơ hồ.
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

**Checklist là các điều kiện nguyên tử** (atomic), cụ thể và đo lường được, do người soạn rubric khai báo trong v1. Mục đích là biến một tiêu chí lớn thành các câu kiểm tra rõ ràng để việc đánh giá nhất quán và giải thích được. Compiler chỉ validate/canonicalize checklist đã khai báo; không tự tạo checklist mới.

Mỗi checklist được phân loại thành 1 trong 2 dạng:

- **LOCAL**: Chỉ cần xem 1 đoạn hoặc 1 số đoạn cụ thể trong báo cáo là đủ để kiểm tra được, không cần đối chiếu thêm phần nào khác.
- **GRAPH**: Cần đối chiếu thông tin và các quan hệ tri thức (giữa claim, phương pháp, kết quả, kết luận) thuộc nhiều phần của báo cáo (hoặc nhiều nguồn dữ liệu) mới kết luận được, vì bản chất câu hỏi đòi hỏi tính nhất quán/liên kết giữa các phần. Baseline hiện chỉ dùng graph cấu trúc/từ vựng và Personalized PageRank; chưa phải Evidence Graph claim/entity hoàn chỉnh.

Người soạn rubric gán mode `LOCAL/GRAPH` và mức quan trọng `CORE/REQUIRED/OPTIONAL`; compiler kiểm tra tính hợp lệ nhưng không tự dự đoán các thuộc tính này trong v1. Dựa trên bằng chứng thu thập được, mỗi checklist được xác minh ở một trong ba trạng thái: `MET`, `UNMET` hoặc `CANNOT_ASSESS` theo quy tắc tại Mục 5.

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

## 5. Quan hệ evidence và kết quả checklist

Hệ thống tách hai tầng trạng thái để không đánh đồng việc "không tìm thấy" với việc "đã chứng minh là không đạt":

| Quan hệ claim–evidence | Ý nghĩa |
| ---------------------- | ------- |
| `SUPPORTED` | Evidence span trực tiếp hỗ trợ yêu cầu của checklist. |
| `CONTRADICTED` | Evidence span trực tiếp cho thấy yêu cầu không đạt hoặc mâu thuẫn với điều kiện đã được khai báo. |
| `INSUFFICIENT` | Bằng chứng thiếu, mơ hồ, khác đối tượng/thời điểm/điều kiện, hoặc chưa xác minh được provenance. |

Decision rule ánh xạ quan hệ claim–evidence sang một trong ba kết quả checklist:

| Kết quả checklist | Điều kiện quyết định | Ví dụ |
| ----------------- | -------------------- | ----- |
| `MET` | Tất cả yêu cầu bằng chứng tường minh đều ở trạng thái `SUPPORTED`. | Checklist "Có ER diagram" và báo cáo có caption/mô tả văn bản xác định đúng ER diagram. |
| `UNMET` | Có bằng chứng trực tiếp ở trạng thái `CONTRADICTED` theo rule do người soạn rubric khai báo. | Báo cáo nói rõ chức năng chưa được cài đặt, hoặc kết quả vi phạm một ngưỡng định lượng đã khai báo. |
| `CANNOT_ASSESS` | Có ít nhất một yêu cầu bằng chứng bắt buộc ở trạng thái `INSUFFICIENT`, hoặc còn xung đột chưa phân xử được. | Báo cáo không đề cập, mô tả chung chung, hoặc nguồn đối chứng chưa đủ thẩm quyền để kết luận. |

Không tìm thấy evidence hoặc báo cáo không đề cập **không tự động là `UNMET`**, kể cả với checklist `CORE/REQUIRED`; trường hợp đó là `INSUFFICIENT → CANNOT_ASSESS`. Nếu báo cáo nói A còn tài liệu đối chứng nói B, chỉ gán `CONTRADICTED → UNMET` khi hai phát biểu cùng đối tượng, thời điểm và điều kiện, đồng thời nguồn B đã được duyệt và đủ thẩm quyền. Các trường hợp còn lại giữ `INSUFFICIENT → CANNOT_ASSESS` để giảng viên xem lại.

Baseline hiện dùng các positive/negative patterns do người soạn rubric khai báo để tạo quan hệ bước đầu; đây chưa phải bộ suy luận NLI ngữ nghĩa hoàn chỉnh. Hệ thống cũng chưa phân tích trực tiếp nội dung hình ảnh/sơ đồ, nên chỉ dùng caption hoặc mô tả văn bản; nếu phần chữ không đủ thì kết quả là `CANNOT_ASSESS`.

## 6. Quy tắc quyết định (Deterministic Decision Rules)

Điểm được tính bằng rule xác định và luôn giữ evidence span; mô hình không tự quyết định điểm cuối:

1. Xác minh từng checklist theo Mục 5 và lưu evidence, relation, outcome cùng lý do.
2. Nếu một checklist có kết quả `CANNOT_ASSESS`, điểm của tiêu chí đó và điểm tổng để `null`; hệ thống chỉ hiển thị `assessable_subtotal` như số liệu chẩn đoán và yêu cầu giảng viên review. Ngưỡng số lượng/tỷ lệ `CANNOT_ASSESS` chỉ quyết định lý do và mức ưu tiên review, không cho phép bỏ qua checklist để tính điểm cuối.
3. Nếu checklist `CORE/REQUIRED` có kết quả `UNMET`, điểm tiêu chí được giới hạn bởi `required_unmet_score` đã cấu hình và không vượt quá trọng số tiêu chí.
4. Khi không có `CANNOT_ASSESS` và không rơi vào rule ở bước 3, điểm tiêu chí được tính theo tỷ lệ checklist đã xác minh:

   `criterion_score = criterion_weight × MET / (MET + UNMET)`

   Kết quả được làm tròn đến một chữ số thập phân.
5. Chỉ cộng điểm tổng khi mọi tiêu chí đều có điểm xác định. Mức đánh giá và các dải điểm của rubric dùng để trình bày/đối chiếu; nội suy theo dải mức chưa thuộc feasibility baseline hiện tại.
6. Điểm do hệ thống sinh là đề xuất có thể kiểm toán. Giảng viên phải xem evidence và xác nhận trước khi công bố.

## 7. Xử lý khi 2 người gán nhãn khác nhau (Adjudication)

Khi 2 người gán nhãn độc lập cho cùng 1 checklist trên cùng 1 báo cáo, bất đồng có thể xảy ra ở 2 dạng:

* (1) khác nhãn (VD người A gán MET, người B gán UNMET), hoặc
* (2) cùng nhãn nhưng khác đoạn bằng chứng trích dẫn.

Quy trình xử lý:

1. Khóa cùng phiên bản báo cáo, rubric, nguồn đối chứng và checksum; hai người gán nhãn độc lập, không xem nhãn của nhau và không xem dự đoán của mô hình. Sau khi cả hai hoàn tất mới tính **tỉ lệ đồng thuận (agreement rate)** trên toàn bộ checklist đã gán.
2. Với từng trường hợp bất đồng, giữ nguyên hai phiếu ban đầu, sau đó hai người **đối chiếu lại đúng đoạn bằng chứng** và provenance trong báo cáo/nguồn để thống nhất nhãn cuối cùng.
3. Nếu không tự thống nhất được, chuyển cho **người thứ ba (GVHD)** quyết định nhãn cuối cùng.
4. Ghi lại toàn bộ trường hợp bất đồng - checklist nào, 2 nhãn ban đầu, nhãn cuối cùng, lý do - vào **Adjudication Log** riêng để phục vụ phân tích chất lượng gán nhãn.
5. Nếu bất đồng lặp lại nhiều lần trên cùng 1 dạng checklist (VD tất cả checklist GRAPH liên quan đến "tính nhất quán" đều gây tranh cãi) → xem xét viết lại rõ hơn quy tắc MET/UNMET/CANNOT_ASSESS cho dạng đó ở mục 2 (feedback loop cải thiện guideline).
