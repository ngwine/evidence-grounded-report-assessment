# Cải thiện đầu ra hai pipeline — 29/10/2026

Đợt này sửa và đo đầu ra ứng dụng, tách khỏi thí nghiệm PAN truy xuất nguồn
trong bài báo. Bản chấm đầu tiên được khóa ở commit
`7aa249f87083ced348ec798e64c398f323c2a598` trước khi mở challenge.
[Protocol và quá trình chọn cấu hình](../../research/protocols/output-quality/development-cycle-v1.md)
ghi lại cả các lượt chưa đạt.

## Kết quả trên bộ ca mới

DEV gồm 12 ca P1 và 6 ca P2; challenge gồm 24 ca P1 và 12 ca P2, cả tiếng
Anh và tiếng Việt. Văn bản, nhãn kỳ vọng và vị trí bằng chứng được khóa hash
trước khi chạy. Nhãn do trợ lý soạn; đây là kiểm tra phát triển, **chưa phải
gold do người gán nhãn độc lập**, không phải độ chính xác nghiên cứu.

| Truy xuất P1 | DEV trước → sau | Challenge trước → sau |
|---|---:|---:|
| BM25 | 4 → **10/12** | 8 → **16/24** |
| BM25 + E5 + RRF, không relevance reranker | 1 → **10/12** | 4 → **16/24** |

Hai cấu hình candidate đều nhận đúng 4/4 paraphrase và 4/4 exact ở challenge.
Không ghi nhận nhãn reuse sai trên bất kỳ nguồn nào của 16 ca âm, cũng không
gán reuse cho distractor ở các ca dương. Exact coverage sai bằng 0.
Tám ca còn lại đều abstain: bốn ca số lượng, ba ca tác thể và một ca cùng
chủ đề. Không quy đổi abstain thành nhãn NONE đúng; chưa kết luận độ tương
đương hay độ chính xác tổng quát từ bộ ca nhỏ này.

P2 giữ 6/6 DEV và 11/12 challenge, không có false MET; bốn mục kỳ vọng chưa
đủ bằng chứng vẫn CANNOT_ASSESS. Một ca tiếng Việt có hành động hoàn tất
nhưng đồng thời nói không đổi đối tượng khác vẫn bị giữ điểm do phạm vi phủ
định. Không sửa tiếp thuật toán theo nhãn challenge sau khi đã xem kết quả.

Trong harness RRF, truy xuất P2 cũng dùng RRF và được giữ giống nhau trước/sau.
Hai profile ứng dụng mới giữ P2 ở BM25 để so verifier; không đánh đồng hai
điều kiện này. Kết quả web được ghi riêng bên dưới.

## Những gì đã sửa

**P1:** giữ nguyên đường exact nhưng thay điều kiện thiên về từ dài tiếng Anh
bằng độ đa dạng token chữ, bên cạnh mức tối thiểu ký tự/token cũ. Đoạn nguyên
văn tiếng Việt với nhiều âm tiết ngắn không còn bị loại chỉ vì thiếu từ dài.

Bổ sung bước NLI hai chiều cho các cửa sổ 1–2 câu. Candidate dùng
[mDeBERTa NLI](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli)
revision `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`, mutual entailment 0,65,
rejection 0,85, margin 0,20. Đây là cấu hình **chọn trên DEV**, chưa được
calibration. Giữ lại các lần MiniLM/mDeBERTa ngưỡng 0,85 chưa đạt; không gọi
các lần chọn cấu hình là phép kiểm độc lập.

NLI chỉ đề xuất tương đương cho đúng span được so sánh, không chứng minh
nguồn gốc sao chép. Không cắt ngầm đầu vào model; quá giới hạn hoặc chưa
đủ cơ sở thì abstain. Sai khác số rõ ràng và cùng tập từ nhưng đảo thứ tự/vai
trò chặn positive. Các guard này chưa giải quyết ngữ nghĩa vai trò/số lượng
tổng quát. Semantic match không cộng vào exact coverage; SUMMARY chưa có.

**P2:** V4 phân biệt hoàn tất với kế hoạch, bảng pending và công cụ có sẵn;
đọc phủ định bảo toàn dữ liệu/công khai hạn chế theo yêu cầu được khai báo.
Trên đúng bằng chứng LIP đã lưu, V3 khớp 6/10 → V4 **10/10** ở cả BM25 và
Hybrid, gồm 6 MET / 3 UNMET / 1 CANNOT_ASSESS. Đây là ca đã xem để phát triển.
Rubric, nhãn kỳ vọng, bằng chứng và cách giữ tổng điểm ở `null` không đổi.

## Kiểm tra qua ứng dụng thật

Web/API/Mongo/worker đã được khôi phục bằng container Mongo cũ và launcher
hiện có. Lượt BM25 mới hoàn tất với 6 MET / 3 UNMET / 1 CANNOT_ASSESS,
exact coverage 3,4616%. Lượt NLI CPU v1 chạm giới hạn 180 giây; attempt và
profile v1 được giữ nguyên, không sửa hash của cấu hình đã có run/index.

Profile vận hành v2 giữ model, ngưỡng và cửa sổ so sánh, nâng giới hạn thực thi
và dùng GPU Apple với float32, không tự fallback. Bản tiếp theo
`a2a3d88582b3bebf61379454af2ca596dfd7a0ce` còn sửa numeric guard: chỉ bỏ số
của marker `[n]` khi parser có provenance và liên kết duy nhất tới bibliography.
Đầu vào NLI và span gốc không đổi; liên kết này chưa xác minh tính đúng của
trích dẫn. Kết quả challenge đầu tiên phía trên thuộc `7aa249f`, không phải
phép đo lại cho sửa đổi này. Trên DEV, mọi quyết định cặp
đoạn giống CPU; 480 xác suất có chênh lệch lớn nhất khoảng 1,8×10⁻⁵.
Hai profile `bm25-nli-v2` và `rrf-nli-v2` cần MPS; E5 của RRF vẫn dùng CPU.
Giới hạn wall là 600 giây và CPU là 590 giây, không phải tuyên bố latency.

Ba lượt BOTH trên đúng phiên bản báo cáo/ba nguồn/rubric LIP đã hoàn tất:

| Cấu hình | Run ID | P1 | P2 |
|---|---|---|---|
| BM25 | `6ae2c9f1ed4117ea459183b6` | 2 exact; chưa có semantic verifier | 6 MET / 3 UNMET / 1 CA |
| BM25 + NLI v2 | `6ae2ca0bed4117ea459183c9` | 2 exact + 1 đề xuất paraphrase; 120 abstain | 6 / 3 / 1 |
| BM25 + E5 + RRF + NLI v2 | `6ae2ca95ed4117ea459183dc` | 2 exact + 1 đề xuất paraphrase; 126 abstain | 6 / 3 / 1 |

Cả ba giữ exact coverage **3,4616%** và điểm tổng `null`. Từng mục P2 khớp
10/10 kỳ vọng của ca đã dùng phát triển. Đề xuất paraphrase nằm ở cặp P128–S2;
cặp P131–S2 vẫn chưa đủ cơ sở. Không gán NONE cho các cặp abstain. RRF chưa
tìm thêm cặp paraphrase và có 38 ứng viên provisional được chọn review,
so với 3 ở BM25 + NLI. Đây chưa phải đo false positive hay precision: các
cặp provisional đó chưa được xác nhận tương đương. Với ca demo này, chọn
BM25 + NLI v2 để giảm lượng ứng viên cần kiểm tra.

Core gồm nạp model và hai pipeline mất khoảng 1,18 / 104,74 / 107,32 giây
theo thứ tự bảng; không gồm upload, parse, index và chờ UI, không phải phép
đo latency có đối chứng. Export từ API và ảnh trình duyệt đã được lưu; kết
quả máy của các lượt gốc được kiểm tra không đổi, không sao chép nhãn review
thành dự đoán. Các cặp chưa được chọn review vẫn xem được ở nhóm **Chưa xác
định** hoặc trong JSON, thay vì hiển thị tất cả như ứng viên đáng nghi.

Kiểm tra tích hợp phát hiện trường tổng hợp `hardware.device` của hai lượt
NLI đầu bị ghi sai CPU: code đọc device trực tiếp thay vì device lồng trong
`models.semantic_verifier.scorer`. Thông tin model gốc vẫn ghi MPS. Bản
`9b9721d` sửa cách tổng hợp metadata, giữ nguyên các export cũ; model, ngưỡng,
truy xuất và quyết định không đổi. Lượt BM25 + NLI xác nhận sau sửa
**`6ae2cc1f1d78f107b6b0d9e8`** hoàn tất qua web, ghi đúng thiết bị MPS và
giữ 2 exact / 1 paraphrase / 120 abstain cùng 10/10 nhãn P2 kỳ vọng.
Đã kiểm tra các span so sánh hiển thị, evidence ngữ nghĩa lưu trong Mongo,
hai nhóm review/chưa xác định, tổng điểm `null` và kết quả gốc không đổi.
Các file triển khai của lượt này khớp snapshot sạch
`9b9721d6b0d0eb9069b95b4d937635c2d9e3924e`. Đây là lượt nên mở lại để demo.

## Phép thử riêng cho numeric guard

Bản `a2a3d885` được khóa trước khi mở một cohort mới gồm 16 ca Việt/Anh.
Chạy cùng model MPS, cùng ngưỡng, cùng chuỗi đầu vào, chỉ bật/tắt các hint
loại marker đã liên kết. Kết quả **không cải thiện**: khớp quyết định kỳ vọng
8/16 ở cả hai điều kiện; không nhận được ca nào trong 4 paraphrase có marker.
Không có false equivalence trên 10 ca khác nghĩa; 10/16 ca abstain. Trong
8 ca không có hint đáng tin, 5 ca giữ đúng abstain và 3 ca trả NONE.
Các nhóm có giao nhau, không cộng các mẫu số này.

Đây là kết quả âm cần giữ lại: sửa marker chỉ tháo một điều kiện chặn, không
khắc phục việc model chưa đủ tin cậy để xác nhận tương đương. Không đổi
ngưỡng hoặc nhãn sau khi xem cohort. Phép thử component này chưa kiểm chứng
toàn bộ đường parser → citation resolver → kết quả web và không phải gold độc lập.

## File triển khai và khả năng kiểm tra lại

- [P1 và ánh xạ span](../../research/core_mvp/similarity.py)
- [NLI adapter, policy và giới hạn](../../research/core_mvp/semantic_verification.py)
- [P2 verifier](../../research/core_mvp/assessment.py)
- [Bộ ca DEV và evaluator](../../research/output_quality/README.md)
- [Worker có giới hạn và metadata](../../services/backend/src/kltn_ai/worker/bounded_pipeline.py)
- [Hiển thị nhóm kết quả và đoạn so sánh](../../apps/web/src/AuthenticatedResults.tsx)

Artifact riêng nằm tại `var/quality/output-improvement-2026-10-29/`: source
snapshot trước sửa, `candidate-freeze.json`, hash pack, toàn bộ prediction,
bảng trước/sau cho mỗi profile/split, replay LIP, log và ảnh web.
Không đưa nội dung báo cáo riêng hoặc session đăng nhập vào Git.

Snapshot sạch đầu tiên dùng chấm challenge ghi nhận 784 passed / 21 skipped;
snapshot ops `b4026d4` có 821 passed / 21 skipped; snapshot citation `a2a3d885`
có **861 passed / 21 skipped** ở research/backend. Những suite sạch này không
gồm các test thí nghiệm PAN chưa commit ở workspace chính. Web build thành
công. Snapshot cuối `9b9721d` có **868 passed / 21 skipped**, gồm 32 test
profile/orchestration dùng đúng cấu trúc metadata lồng của wrapper NLI.
DOCX bài báo đã đồng bộ mô tả prototype; 9 bảng dữ liệu khớp số trong Markdown
và giữ 2 hình (chưa kiểm tra phân trang Word). Đây là kiểm tra phần mềm và
tài liệu, không phải độ chính xác của mô hình.

## Phần còn lại

- Xử lý scope phủ định tiếng Việt và gắn số lượng/tác thể với hành động;
  tạo cohort mới trước lần kiểm tra chưa xem tiếp theo.
- Thu thập nhãn do người kiểm độc lập, đối chiếu span và adjudicate trước
  khi báo cáo model accuracy hoặc chấm rubric có tính khái quát.
- Tiếp tục đo candidate/evidence selection thay vì chỉ điểm NLI. Các guard
  và model vẫn có thể sai; không ép hệ thống ra điểm tổng khi thiếu evidence.
- Giữ nguyên bảng PAN DEV0/DEV1. PAN TEST0 chưa mở và không dùng để kiểm
  paraphrase hay rubric vì qrels của nó đo truy xuất tài liệu nguồn.
