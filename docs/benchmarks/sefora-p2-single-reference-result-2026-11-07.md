# P2 trên 15 bài SEFORA — đánh giá thăm dò ngày 07/11/2026

**Trạng thái: đã hoàn thành 90/90 quyết định và kiểm tra artifact đạt.**

> Cập nhật 08/11: đã [đọc lại 15 mục bất đồng](sefora-p2-disagreement-review-2026-11-08.md)
> theo yêu cầu người phụ trách. Rà soát AI tìm được căn cứ ủng hộ giữ nhãn
> Yến ở 14 mục, còn 1 mục cần thống nhất cách hiểu; đồng thời phát hiện
> đoạn giống feedback lẫn trong ba captured body. Không đổi nhãn hoặc số
> của lượt chạy này; đây không phải bổ sung annotator độc lập.

| Cấu hình | Khớp nhãn tham chiếu | Tỷ lệ | Macro F1 trên MET/UNMET | Lỗi kỹ thuật |
| --- | ---: | ---: | ---: | ---: |
| Một bước | 37/45 | 82,22% | 0,4625 | 0 |
| Hai bước | 32/45 | 71,11% | 0,4211 | 0 |
| Baseline luôn MET | 42/45 | 93,33% | 0,4828 | — |

**Hai bước chưa cải thiện mức khớp nhãn trên bộ này.** Cả hai cấu hình chưa
vượt baseline MET; không diễn giải kết quả thành độ chính xác chấm rubric
toàn diện hoặc hiệu quả hơn giảng viên. Đây là so sánh với nhãn tham chiếu
một người có AI hỗ trợ, có thể vẫn chứa bất đồng về cách đọc rubric.

Đường chạy này đối chiếu cấu hình LLM một bước và hai bước với phiếu Yến:
15 bài × 3 checklist = 45 mục tham chiếu; hai cấu hình tạo 90 quyết định.
Nhãn được một người đọc và trao đổi với Claude tạo ra, trước khi xem dự đoán
P2 theo khai báo trong phiếu. Không tính đồng thuận hai người hoặc gọi đây
là gold đa giám khảo.

## Phương pháp đã khóa trước suy luận

- Model local `qwen3.5:4b-q4_K_M`, digest `d8b0f5e…e38c04`, Ollama 0.40.13.
- Cùng model, seed, parser, source-unit catalog, tối đa ba citations và
  budget mỗi request. Hai bước được phép nhiều request hơn; không cân bằng
  tổng compute và không cô lập tác dụng riêng của auditor.
- Cùng CLM001, EXP001 và QUO001, vận hành hóa từ đúng hướng dẫn người gán.
  Runtime rubric riêng có ánh xạ version rõ; không suy điểm toàn bài.
- Cả 45 evidence pack chứa toàn bộ parsed chunks của bài tương ứng. Điều
  này không chứng nhận PDF gốc/ảnh đầy đủ hoặc tự chứng minh vắng nội dung.
- Nhãn và rationale tham chiếu không được đưa vào verifier. Cấu hình,
  rubric, nguồn và mã dùng suy luận được chụp/hash trước request đầu tiên.
- Mỗi quyết định lưu ngay; không tự retry hoặc đổi phương pháp sau khi xem
  dự đoán. Timeout/schema/proof failure ghi technical abstention, không đổi
  thành CANNOT_ASSESS đúng.

Manifest trước chạy:
`1da0001836751d4612e279610dadda9b0eb5a6c83e7ce00ce4e23e2b2ae832cf`.
Kiểm tra trước chạy: 65 test đạt; kiểm tra adapter tọa độ bổ sung bằng
fixture tự soạn: 8 test đạt. Không dùng các bài thật để sửa các validator này.
Kiểm tra toàn bộ research/backend sau khi hoàn tất: **1.346 test đạt,
21 bỏ qua**; Ruff và `git diff --check` đạt.

## Hồ sơ và kết quả

Mọi dữ liệu riêng nằm dưới
`var/paper/p2-single-reference-eval-2026-11-07/`:

- `inputs/`: protocol, yêu cầu chạy của người phụ trách, rubric runtime và
  môi trường. Đây không phải hồ sơ tự cấp approval GOLD_EVALUATION.
- `prepared-v1/`: toàn bộ nguồn, nhãn, evidence pack/canonical catalog,
  cấu hình và mã nguồn đã khóa; không ghi đè.
- `run-v1/<case>/<method>/`: từng kết quả, trích dẫn, rationale, telemetry
  và assessment report theo contract hiện hành.
- `run-v1/all-methods-predictions.json` và `run-v1/run-summary.json` đã ghi
  đầy đủ 90 quyết định và trạng thái hoàn tất.
- `summarize_run.py`: kiểm checksum, contract và source geometry, rồi xuất
  `evaluation-v1/` gồm bảng nhãn, các mục lệch, thống kê và hồ sơ trích dẫn.

Các đầu ra đã có:

- [Bảng kết quả chi tiết](../../var/paper/p2-single-reference-eval-2026-11-07/evaluation-v1/KET_QUA_P2_THAM_DO.md).
- [Toàn bộ mục đối chiếu](../../var/paper/p2-single-reference-eval-2026-11-07/evaluation-v1/comparison.csv)
  và [các mục lệch nhãn](../../var/paper/p2-single-reference-eval-2026-11-07/evaluation-v1/mismatches.csv).
- [Metrics JSON](../../var/paper/p2-single-reference-eval-2026-11-07/evaluation-v1/metrics.json),
  [kiểm chứng artifact](../../var/paper/p2-single-reference-eval-2026-11-07/evaluation-v1/artifact-verification.json),
  [kiểm tọa độ bằng chứng](../../var/paper/p2-single-reference-eval-2026-11-07/evaluation-v1/evidence-audit.json).

## Kết quả từng checklist

| Checklist | Một bước khớp | Hai bước khớp | Phân bố tham chiếu |
| --- | ---: | ---: | --- |
| CLM001 — Luận điểm trung tâm | 12/15 | 12/15 | 13 MET, 2 UNMET |
| EXP001 — Trải nghiệm cá nhân | 15/15 | 14/15 | 15 MET |
| QUO001 — Hai quotation cùng nguồn chính | 10/15 | 6/15 | 14 MET, 1 UNMET |

Một bước trả 38 MET và 7 CANNOT_ASSESS; hai bước trả 34 MET và 11
CANNOT_ASSESS. **Không cấu hình nào trả UNMET**, trong khi tham chiếu có ba
mục UNMET dạng kiểm toàn văn xác nhận vắng nội dung.

Một bước có 5 mục MET tham chiếu thành CA, 1 UNMET thành MET và 2 UNMET
thành CA. Hai bước có 10 MET thành CA, 2 UNMET thành MET và 1 UNMET thành CA.
CA ở đây là quyết định ngữ nghĩa đã qua contract, không phải lỗi runtime.

Trong 45 cặp, hai cấu hình cùng khớp 30 mục; chỉ một bước khớp 7, chỉ hai
bước khớp 2, cả hai không khớp 6. Đây là thống kê ghép cặp mô tả, không phải
kiểm định ý nghĩa thống kê hoặc chứng minh tác dụng riêng của auditor.

## Điểm nghẽn thấy từ artifact

1. **Selector trả rỗng cho QUO001 ở 7 bài.** Trong đó 6 mục tham chiếu MET,
   1 mục UNMET. Auditor được bỏ qua đúng thiết kế và trả CA. Vì pack ban đầu
   đã có toàn bộ parsed chunks, không thể quy các trường hợp này đơn giản
   thành BM25 không đưa bài vào đầu vào. Không chọn được unit không chứng
   minh bài vắng quotation.
2. **Có chọn unit nhưng chưa đủ điều kiện tổng thể.** Ví dụ `C2-06-ID0040`
   và `C2-13-ID0100` ở QUO001, auditor chỉ thấy đủ căn cứ cho một quotation.
   Với `C2-13-ID0100` ở EXP001, auditor thấy câu nói về sợ bác sĩ nhưng thiếu
   ngữ cảnh trải nghiệm phát triển ý trong các unit đã chọn.
3. **Nhận định về “luận điểm trung tâm” còn bất đồng.** Hai bước trả MET cho
   `C2-07-ID0055` và `C2-08-ID0061` mà Yến chọn UNMET. Các rationale cho thấy
   model dùng sở thích/ý kiến cá nhân làm căn cứ. Chưa có adjudication độc
   lập để coi mọi bất đồng này là lỗi model hoặc sửa nhãn người gán.
4. **Quy tắc UNMET do vắng nội dung chưa được verifier hiện tại biểu diễn
   đầy đủ.** Phiếu có DOCUMENT_ABSENCE sau kiểm toàn văn, còn prompt/model
   yêu cầu phản chứng trực tiếp và không được suy “không chọn được” thành
   CONTRADICTED. Auditor chỉ đọc selected units cũng không đủ phạm vi xác
   nhận vắng trong toàn bài. Không chuyển CA sang UNMET sau chạy cho trùng
   tham chiếu hoặc tạo quote phản chứng giả.

## Bằng chứng và kiểm chứng kỹ thuật

Đã xác minh 30 assessment report theo contract/schema, cùng evidence
pack/catalog giữa hai phương pháp, cùng phiên bản nguồn và checksum mã
đã khóa. Không retry, thay nhãn tham chiếu hoặc đổi phương pháp giữa lượt.

Một bước có **94/94** proof trỏ đúng nguồn; hai bước có **85/85**. Không
phát hiện lỗi tọa độ trong các proof hiện diện. F1 overlap ký tự với các
đoạn người gán chọn lần lượt 0,2545 và 0,2287 trên 42 mục SPAN_SET; ba mục
DOCUMENT_ABSENCE được tách riêng, không tạo span giả. Các tỷ lệ overlap này
không xác minh lập luận đúng/sai: người gán có thể dẫn ngữ cảnh dài hơn và
có nhiều đoạn bằng chứng hợp lệ khác nhau.

Telemetry ghi 45 model calls cho một bước, 83 calls cho hai bước (7 lần
selection rỗng bỏ auditor). Tổng thời gian các lời gọi verification khoảng
887,51 giây và 845,31 giây. Đây là số đo một lượt thực thi với cache/thứ tự
không kiểm soát, không dùng để kết luận hai bước nhanh hơn.

## Cách sử dụng kết quả

Bộ hiện tại không có CANNOT_ASSESS tham chiếu; EXP001 toàn MET. Vì vậy
không suy khả năng nhận diện các lớp/trường hợp đó từ tỷ lệ khớp tổng.
Macro F1 trên các lớp có mẫu thấp hơn baseline ở cả hai cấu hình.

Có thể dùng lượt này làm **phân tích thăm dò và điểm nghẽn** của P2. Chưa
có căn cứ gọi kiến trúc hai bước tốt hơn hoặc công bố hiệu quả chấm rubric
độc lập. Bản thảo bài báo chưa được thêm bảng chất lượng P2 từ lượt này.

Nếu sửa tiếp, ưu tiên đường chọn đủ quotation và gán nguồn, sau đó là cơ
chế kiểm phạm vi toàn văn cho vắng nội dung. Giữ nguyên lượt gốc này; từ
lúc dùng các bất đồng để sửa phương pháp, cohort này phải được xem là DEV
cho các phiên bản tiếp theo, không đổi tên thành đánh giá chưa từng xem.

Trích dẫn đúng tọa độ nguồn và trùng vị trí người gán là hai kiểm tra kỹ
thuật riêng; chúng không tự chứng minh bằng chứng hỗ trợ đúng kết luận.
