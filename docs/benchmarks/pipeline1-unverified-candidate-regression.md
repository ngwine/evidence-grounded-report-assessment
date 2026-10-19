# Pipeline 1 — tách ứng viên retrieval khỏi kết luận semantic

Ngày kiểm tra: 19/10/2026.

## Vấn đề được sửa

Trước đây, `_classify` dùng điểm Dense/Cross-Encoder cùng tín hiệu từ vựng để
gợi ý `PARAPHRASE`, và chuyển thành `SUMMARY` khi đoạn report ngắn hơn nguồn.
Những tín hiệu này chỉ cho thấy mức liên quan, không xác minh quan hệ diễn
đạt lại hoặc tóm tắt. Trên report thử nghiệm, một chunk chứa caption Sudoku
và phân công thành viên cũng bị gợi ý `SUMMARY` của đoạn sách giải thích CSP.

Policy mới: `EXACT_EVIDENCE_OR_UNVERIFIED_RETRIEVAL_V1`.

- Ứng viên semantic có `similarity_type = null`,
  `provisional_similarity_type = null`, `semantic_verification_status = NOT_RUN`.
- Giữ trạng thái `PROVISIONAL_REVIEW_REQUIRED` và các cặp được chọn để review;
  không coi `null` là nhãn âm hoặc kết luận không có tương đồng.
- Không suy ra summary từ tỷ lệ độ dài. `summary_length_ratio` vẫn được đọc
  để tương thích config cũ nhưng không còn tham gia quyết định.
- Giữ logic VERBATIM dựa trên exact span. Những exact overlap chưa đạt mức
  bằng chứng tối thiểu vẫn có thể là provisional VERBATIM, không vào coverage
  đã xác nhận.
- `review_source_groups` gom các cặp cùng source chunk và giữ đủ report spans.
  Nhiều ứng viên cùng trỏ vào một đoạn nguồn có cảnh báo để rà soát từng cặp;
  không giới hạn số lần sử dụng nguồn hoặc loại bỏ chép thật lặp ở nhiều chỗ.
- Giao diện ghi rõ tỷ lệ token của các chunk cần review là khối lượng cần
  kiểm tra, không phải tỷ lệ tương đồng. Trường legacy
  `provisional_review_passage_coverage_percentage` được giữ để tương thích.

## Đối chiếu bằng lượt chạy lại

Cùng report PDF, ba PDF nguồn, rubric, config, model revisions và seed của
lượt chạy 18/10. Chạy lại cả hai pipeline, không sửa dữ liệu đầu vào hoặc
ngưỡng retrieval. Lượt mới hoàn tất trong **203,00 giây**; đây không phải
benchmark so sánh tốc độ.

| Nội dung | Trước | Sau |
|---|---|---|
| Report/source chunks | 24 / 5.372 | 24 / 5.372 |
| Cặp ứng viên trong output | 72 | 72; giữ nguyên rank, score, features và alignment |
| Đoạn được chọn để review | 8 | 8 |
| Nhãn semantic của 8 đoạn | 5 PARAPHRASE, 3 SUMMARY | 8 chưa xác minh, cả hai trường nhãn đều null |
| Nhóm theo source chunk | Chưa hiển thị nhóm | 2 nhóm: 7 và 1 report chunks |
| Coverage token của chunk cần review | 32,0028% | 32,0028%; chỉ là review workload |
| Exact-match coverage | 0% | 0%; không đồng nghĩa report không có reuse |
| Pipeline 2 | 9 MET, 1 CANNOT_ASSESS; điểm tổng null | Toàn bộ Assessment Report JSON giữ nguyên |

Đã so sánh chính xác metadata/checksum đầu vào, cấu hình và toàn bộ 72 cặp.
Không có thay đổi ngoài dự kiến về retrieval hoặc Pipeline 2. Checksum các
output mới khớp run manifest. Kết quả cũ và ZIP nộp trước đó không bị ghi đè.

Artifacts local (không đưa nội dung report/nguồn lên Git):

- Trước: `var/results/core-mvp/desktop-real-report-weekly-20261018/`.
- Sau: `var/results/core-mvp/desktop-real-report-20261019-verification-boundary-v1/`.

## Kiểm thử

- 6 test regression mới: same-topic/contribution text có score cao không được
  suy thành semantic label; thay đổi tỷ lệ độ dài không sinh SUMMARY; gom nhóm
  ổn định, không bỏ cặp; exact reuse ở nhiều chỗ vẫn giữ nguyên coverage.
- Phiếu annotation hỗ trợ cả artifact cũ có provisional label và bản mới null;
  không lộ dự đoán trong phiếu gán nhãn độc lập.
- Tại thời điểm lập artifact: `research/tests` **145 passed**, API/worker
  **5 passed**. Sau khi tích hợp thêm contract/golden/upload tests ngày
  19/10/2026, clean working-tree verification đạt **163 research passed** và
  **26 backend passed, 1 skipped**; xem
  [`W1-W11_STATUS_2026-10-19.md`](../planning/W1-W11_STATUS_2026-10-19.md).
- TypeScript/Vite build đạt; kiểm tra render giữ đủ 12 đoạn trong một nhóm,
  hỗ trợ artifact cũ và giữ nhãn exact VERBATIM.

## Giới hạn còn lại

Đây là sửa lỗi gán nhãn thiếu cơ sở, **chưa phải cải thiện chất lượng retrieval
hay hoàn thành semantic classifier**. 7 đoạn vẫn được truy xuất về cùng đoạn
Sudoku và vẫn cần review; số ứng viên và score không bị thay đổi để tạo kết quả
đẹp hơn. Chưa có phép đo precision/recall/F1 cho paraphrase hoặc summary.

Bước tiếp theo là dùng các cặp gán nhãn độc lập, có same-topic hard negatives,
caption/phân công và ví dụ reuse thật, để đánh giá bộ xác minh cặp. Cần kiểm
tra trên tập tách biệt trước khi cho semantic label đóng góp vào Similarity
Report. Mẫu report này chỉ phục vụ regression, không dùng thay bộ đánh giá
độc lập hoặc điều chỉnh ngưỡng lặp lại trên cùng dữ liệu.
