# Rà soát bất đồng P2 với phiếu Yến — 08/11/2026

Đã đọc toàn bộ captured body của 11 bài liên quan đến 21 bất đồng của hai
cấu hình. Gộp các bất đồng trùng item còn **15 mục duy nhất**. Đây là rà
soát AI **sau khi đã xem nhãn tham chiếu và dự đoán**, không phải phiếu độc
lập của Quý, không thay thế quyết định của người gán và không tạo gold mới.

## Kết quả rà soát

| Nhóm | Số mục | Đề xuất |
| --- | ---: | --- |
| Có căn cứ ủng hộ giữ nhãn Yến | 14 | 12 MET, 2 UNMET; vẫn có các caveat mức chắc vừa |
| Cần thống nhất cách hiểu | 1 | C2-08-ID0061 · CLM001, chưa tự đổi UNMET |

Độ chắc của các đề xuất: 11 cao, 4 vừa. Đã kiểm **36 trích đoạn** khớp
đúng paragraph và offset Unicode trong nguồn đã khóa. Đây là kiểm chính
xác chuỗi/vị trí, không chứng nhận mọi đề xuất ngữ nghĩa đều đúng.

**C2-08-ID0061 · CLM001** là mục cần xem lại trước: P0006 có nhận định nhân
quả riêng về danh tiếng cheerleading và an toàn, P0007 chủ trương đào tạo
huấn luyện viên. Lý do “chỉ là đề xuất” không tự loại một quan điểm khỏi
rubric. Tuy nhiên mức độ các ý này tạo thành luận điểm *trung tâm* còn cần
người phụ trách thống nhất. Đề xuất rà soát là UNSURE; nhãn gốc vẫn UNMET.
Hai bước trả MET nhưng bằng chứng về ý Bowyer chưa tự chứng minh lập trường
của người viết, nên không xem nhãn MET của model là lời phân xử.

Các điểm khác:

- QUO001: 9 mục có căn cứ MET và 1 mục UNMET theo phạm vi đếm hai quotation
  cùng nguồn chính. Có bài đủ quotation nhưng selector rỗng hoặc chỉ chọn
  một lượt. Không cần đổi nhãn người chỉ vì máy không chọn được.
- C2-07-ID0055 · CLM001: model hai bước dùng mong muốn/tên gọi của Tank Dell
  như lập trường của tác giả bài. Nghiêng giữ UNMET của Yến; đề xuất mức
  chắc vừa vì việc xác nhận vắng phải xét toàn văn.
- C2-13-ID0100 · EXP001: P0005–P0006 có trải nghiệm cá nhân và ngữ cảnh
  liên hệ trải nghiệm với ý của bài. Có căn cứ giữ MET; hai bước chọn thiếu
  ngữ cảnh cần thiết.
- C2-10-ID0076 · QUO001 có tên Nathan/Robinson không nhất quán; C2-15-ID0148
  có hai quotation gắn Parrington nhưng nhan đề resource chưa rõ. Nghiêng
  giữ MET với ghi chú, mức chắc vừa; không tự thêm điều kiện bắt buộc ghi
  nhan đề mà guideline không có.
- Có các trường hợp model khớp MET nhưng proof chưa đủ hoặc rationale sai:
  trộn hai nguồn Bowyer/Edmondson, cắt câu ở “FBI Director J.”, đếm thuật
  ngữ/title hay mảnh “C.S.” thành quotation. Các quan sát này chỉ thuộc
  các mục đã đọc, không phải tỷ lệ lỗi semantic của toàn bộ 90 quyết định.

## Dấu hiệu feedback lẫn trong body

Ít nhất C2-08-ID0061/P0005, C2-09-ID0064/P0009 và C2-12-ID0086/P0009 có
đoạn giống góp ý trực tiếp cho tác giả về lập luận/hình ảnh. Không dùng
những câu này làm căn cứ ủng hộ nhãn trong rà soát. Không thể suy người gán
đã xem feedback riêng hoặc cố ý khai sai từ việc bộ nguồn đã chứa chúng.

Giữ nguyên bản nguồn đã chạy. Nếu làm sạch cần version mới và đối chiếu
lại; không xoá âm thầm rồi giữ nguyên mô tả đầu vào cũ. Dấu hiệu này cần
được bổ sung vào giới hạn của pilot trước khi báo cáo như dữ liệu bài viết
thuần túy, chưa lẫn nhận xét người chấm.

## Hồ sơ và giới hạn sử dụng

- [Rà soát đủ 15 mục, kèm trích đoạn](../../var/paper/sefora-p2-disagreement-review-2026-11-08/v1/RA_SOAT_15_MUC.md).
- [Bảng CSV đối chiếu](../../var/paper/sefora-p2-disagreement-review-2026-11-08/v1/DOI_CHIEU_15_MUC.csv):
  cột đề xuất AI tách riêng; các cột quyết định cuối của con người để trống.
- [Record rà soát](../../var/paper/sefora-p2-disagreement-review-2026-11-08/v1/combined-review.json)
  và [kiểm chứng](../../var/paper/sefora-p2-disagreement-review-2026-11-08/v1/verification.json).

Không chạy model lại, không đổi phiếu Yến hoặc sửa nhãn cho khớp dự đoán.
Kết quả gốc vẫn 37/45 và 32/45. Không dùng các đề xuất này tính accuracy
mới hoặc tính đồng thuận hai người. Nếu Quý đọc báo cáo này trước khi gán,
phiếu sau đó phải ghi đúng đã xem nhãn/dự đoán ở các mục được nêu.
