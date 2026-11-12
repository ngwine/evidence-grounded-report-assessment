# SCRIPT THUYẾT TRÌNH BÁO CÁO TIẾN ĐỘ TUẦN

**Thời gian báo cáo:** 05/09/2026 – 11/09/2026
**Thời lượng mục tiêu:** 8–10 phút
**Đề tài:** Xây dựng hệ thống hỗ trợ kiểm tra đạo văn và đánh giá báo cáo sinh viên dựa trên bằng chứng
**Thành viên:** Nguyễn Trần Ngọc Quý — 523H0087; Võ Thị Kim Yến — 52200229

> Script này bám theo 8 trang của file `BaoCaoTienDoTuan_KLTN_523H0087_52200229.docx`. Phần trong ngoặc vuông là chỉ dẫn khi trình bày, không cần đọc thành lời.

## Phân chia nếu cả hai cùng trình bày

- **Quý:** trang 1–2 và 5–8.
- **Yến:** trang 3–4 về dataset và kế hoạch đánh giá.
- Nếu chỉ có một người tham gia, đọc liên tục theo script; các câu chuyển trang đã được viết để không phụ thuộc người trình bày.

---

## Trang 1 — Mở đầu

**Thời lượng:** khoảng 35 giây

Dạ, nhóm xin báo cáo tiến độ trong tuần từ ngày 5 đến ngày 11 tháng 9.

Đề tài của nhóm là xây dựng hệ thống hỗ trợ kiểm tra đạo văn và đánh giá báo cáo sinh viên dựa trên bằng chứng. Trong tuần này, nhóm tập trung vào ba phần: khảo sát dữ liệu thực nghiệm ở mức chi tiết hơn, hoàn thiện thiết kế kiến trúc và provenance, và xây dựng API Contract để chuẩn bị triển khai backend.

Trong phần trình bày, nhóm sẽ nói rõ nội dung nào đã chạy được bằng code, nội dung nào hiện mới là thiết kế, và bước tiếp theo sẽ triển khai như thế nào.

**Chuyển:** Tiếp theo là phần tổng quan kết quả của tuần.

---

## Trang 2 — Tổng quan tiến độ

**Thời lượng:** khoảng 1 phút

[Chỉ lần lượt vào bốn con số, không đọc toàn bộ phần chữ nhỏ.]

Tuần này nhóm đã khảo sát bảy nguồn dữ liệu, gồm năm benchmark công khai và hai báo cáo in-domain. Nhóm cũng xác định mười trust boundary trong luồng xử lý, mô tả Data Dictionary gồm 26 MongoDB collections, và xây dựng OpenAPI draft với 29 API paths, 33 operations và 59 schemas.

Bốn con số này thể hiện khối lượng khảo sát và thiết kế, không có nghĩa là toàn bộ hệ thống đã được lập trình. Phần đang chạy được hiện nay vẫn là PDF/DOCX parser và section-aware chunker. MongoDB runtime, API endpoints, worker và index chưa được nối thành pipeline hoàn chỉnh.

Kết quả quan trọng nhất là các phần đã bắt đầu khớp với nhau: mỗi dataset đã có vai trò trong kế hoạch đánh giá; kiến trúc đã xác định nơi dữ liệu được phép đi qua; còn provenance và API Contract quy định cách truy ngược một kết quả về đúng nguồn và đúng phiên bản.

**Chuyển:** Trước hết, nhóm trình bày cách lựa chọn dataset.

---

## Trang 3 — Khảo sát và lựa chọn dataset

**Thời lượng:** khoảng 1 phút 40 giây

Kết luận sau khi khảo sát là không có một dataset duy nhất bao phủ toàn bộ đề tài. Tìm tài liệu nguồn, căn chỉnh đoạn tương đồng, tìm evidence trong tài liệu dài, kiểm chứng nhiều bước và chấm theo rubric cần những loại ground truth khác nhau. Vì vậy, nhóm chọn benchmark theo từng năng lực thay vì cố dùng một bộ dữ liệu cho mọi thí nghiệm.

[Chỉ theo từng dòng trong bảng.]

PAN-PC-11 được dùng để đánh giá **source retrieval**, tức là hệ thống có tìm đúng tài liệu nguồn hay không. PAN13 được dùng cho **text alignment**, nghĩa là sau khi đã có nguồn, hệ thống phải chỉ đúng đoạn nghi vấn tương ứng với đoạn nào trong nguồn. PAN13 hiện có mức sẵn sàng kỹ thuật cao nhất vì nhóm đã mở hai archive chính thức, đọc trực tiếp span annotation và đối chiếu local MD5 thành công.

MMDocIR được dùng để đánh giá **evidence retrieval trong tài liệu dài**. Dataset này có 313 PDF cùng annotation đến cấp trang, bounding box và modality, nên phù hợp để kiểm tra trường hợp evidence nằm trong văn bản, bảng hoặc hình.

HoVer dành cho **multi-hop verification**, tức là một claim cần nối evidence qua hai đến bốn bước. Dataset này sẽ giúp kiểm tra graph retrieval có thật sự tốt hơn local retrieval hay không; graph chỉ được giữ nếu kết quả thực nghiệm chứng minh được lợi ích.

HARMOGEN-R được dùng ở cấp module cho **rubric-based grading** và human–AI agreement. Do dữ liệu gốc là bài tập lập trình, nhóm không xem đây là benchmark end-to-end cho báo cáo sinh viên dài.

Đến hiện tại, nhóm đã đọc dữ liệu mẫu, format và annotation, kiểm tra một số offset, label và checksum. Nhóm chưa chạy benchmark nên chưa có số liệu Precision, Recall, PlagDet hay QWK để công bố.

**Chuyển:** Các benchmark công khai sẽ được kết hợp với dữ liệu in-domain, nhưng hai loại dữ liệu có vai trò khác nhau.

---

## Trang 4 — Dữ liệu in-domain và kế hoạch đánh giá

**Thời lượng:** khoảng 1 phút 10 giây

Nhóm đã khảo sát hai báo cáo sinh viên thật. Báo cáo thứ nhất là DOCX dài 28 trang, có heading nhiều cấp, bảng merge và trường hợp mục lục không khớp hoàn toàn với heading. Báo cáo thứ hai có cả PDF và DOCX, dài 112 trang, nhiều bảng, hình và cấu trúc lặp. Những trường hợp này sát với dữ liệu thực tế hơn các fixture nhỏ hiện có.

Tuy nhiên, hai báo cáo này hiện mới là **test case in-domain cho parser và chunker**, chưa được xem là corpus đánh giá. Trước khi dùng chính thức, nhóm phải có consent, ẩn danh tên, MSSV, metadata và tên file; sau đó mới xây dựng annotation guide và ground truth có review chéo.

[Chỉ vào bảng “Cách sử dụng dataset trong thực nghiệm”.]

Mỗi benchmark đã được gắn với một thiết kế so sánh và metric tương ứng. Chẳng hạn source retrieval sẽ so BM25, Dense và Hybrid bằng Recall@K, MRR, nDCG@K; text alignment dùng Precision, Recall và PlagDet; rubric grading dùng QWK, MAE và correlation. Sau cùng, corpus in-domain đã được duyệt mới dùng để đánh giá end-to-end, gồm độ đúng của evidence, điểm theo rubric, tỷ lệ giảng viên chấp nhận hoặc chỉnh sửa và latency.

Điều kiện chặn trước khi chạy experiment là phải đủ thông tin về license hoặc consent, purpose, retention, checksum, split và approver. Dataset chưa đạt điều kiện này sẽ không được index và không được đưa vào kết quả nghiên cứu.

**Chuyển:** Từ yêu cầu dữ liệu đó, nhóm thiết kế kiến trúc và luồng provenance như sau.

---

## Trang 5 — Kiến trúc, lưu trữ và provenance

**Thời lượng:** khoảng 1 phút 45 giây

C4 model, data flow và threat model được làm trước backend để trả lời ba câu hỏi: dữ liệu đi qua thành phần nào, thành phần nào chịu trách nhiệm, và tại đâu hệ thống phải kiểm tra quyền hoặc dừng xử lý.

Nhóm đã xác định mười trust boundary, từ browser, API, upload và parser cho tới worker, database, index, local AI, log và export. Các nguyên tắc chính gồm: browser chỉ giao tiếp với API; file và model output đều là dữ liệu không tin cậy; quyền truy cập phải được lọc trước retrieval; và dữ liệu thiếu quyền sử dụng hoặc thiếu provenance phải bị chặn theo nguyên tắc fail closed.

Về lưu trữ, phương án được chọn cho môi trường phát triển là MongoDB Community chạy single-node replica set bằng Docker Compose. Cấu hình này phù hợp máy 16 GB và vẫn hỗ trợ transaction, nhưng không phải kiến trúc high availability hay phương án production.

File PDF và DOCX gốc được lưu trên persistent volume. MongoDB là source of truth cho metadata, checksum, version, trạng thái và audit. Lexical, vector hoặc graph index chỉ là dữ liệu dẫn xuất, có version riêng và phải rebuild được từ nguồn chuẩn.

[Chỉ theo chuỗi provenance trên trang.]

Một evidence phải truy ngược được theo chuỗi: **file → version → element → chunk → index → analysis run → evidence → review**. Nếu parser, cách chunk, index hoặc model thay đổi, lần chạy mới phải mang đúng version mới. Khi dữ liệu bị thu hồi, tombstone phải chặn retrieval và job mới ngay; cleanup vật lý sau đó phải lan tới các artifact liên quan.

Data Dictionary hiện mô tả 26 collections để khóa các đối tượng và quan hệ trước khi viết persistence layer. Đây vẫn là thiết kế, chưa phải 26 collections đã được dựng và có dữ liệu thật.

**Chuyển:** Trên data model đó, nhóm xây dựng API Contract và quy tắc xử lý evidence.

---

## Trang 6 — API Contract và Evidence Verification

**Thời lượng:** khoảng 1 phút 35 giây

API Contract được dùng để thống nhất trước cách frontend, API và worker trao đổi dữ liệu, tránh việc mỗi phần tự đặt field, trạng thái hoặc error format khác nhau. OpenAPI draft hiện có 29 paths, 33 operations và 59 schemas, bao phủ authentication và RBAC, upload và version, job, rubric, analysis run, evidence, review, publication và deletion request.

File YAML đã được kiểm tra cú pháp, internal reference và operation ID. Tuy nhiên, đây là **đặc tả API**, chưa phải 29 API endpoints đã được implement.

Ở Evidence Verification, nhóm tách hai tầng trạng thái. Quan hệ giữa claim và evidence gồm `SUPPORTED`, `CONTRADICTED` và `INSUFFICIENT`. Kết quả checklist sau khi áp decision rule của rubric gồm `MET`, `UNMET` và `CANNOT_ASSESS`.

Ví dụ, báo cáo nói A còn tài liệu đối chứng nói B. Chỉ khi tài liệu B đã được duyệt cho đúng mục đích, đủ thẩm quyền, và A với B nói về cùng đối tượng, thời điểm và điều kiện thì quan hệ mới là `CONTRADICTED`; rubric khi đó có thể ánh xạ thành `UNMET`. Nếu chưa đủ căn cứ thì phải trả `INSUFFICIENT` và `CANNOT_ASSESS`, đồng thời giữ cả hai evidence span để giảng viên review.

Cách tách này ngăn hệ thống biến “không tìm thấy bằng chứng” thành “nội dung sai”. AI chỉ tạo proposal và rationale; giảng viên mới là người Accept, Edit hoặc Reject trước khi publish.

**Chuyển:** Cuối cùng là phần đã kiểm thử, những điểm review phát hiện và công việc tiếp theo.

---

## Trang 7 — Review, kiểm thử và kế hoạch tiếp theo

**Thời lượng:** khoảng 1 phút 25 giây

Review chéo trong tuần đã phát hiện bốn điểm cụ thể: cần bổ sung safe rendering trước khi hiển thị evidence; một số sơ đồ còn quá dày chữ; sơ đồ dữ liệu thiếu cạnh trực tiếp từ document element tới chunk dù schema đã có `element_ids`; và thuật ngữ evidence từng bị trộn với kết quả checklist. Phần thuật ngữ đã được sửa; các điểm còn lại được đưa vào công việc trước khi triển khai backend.

Về code đang chạy, PDF parser đã trích xuất element và suy luận heading hoặc paragraph cơ bản. DOCX parser đọc được heading, paragraph, caption và table theo thứ tự. Section-aware chunker giữ `section_path` và `source_refs` để tạo provenance ban đầu.

Khi chạy lại test suite, hai fixture PDF và DOCX đạt; một smoke test dùng báo cáo thật bị skip vì file local chưa có trong thư mục test. Demo hiện cho kết quả PDF tám elements thành ba chunks và DOCX mười một elements thành năm chunks. Vì vậy, parser và chunker được dùng làm baseline để nối thử backend, chưa được xem là ổn định trên mọi layout, bảng merge hoặc caption phức tạp.

Phần tiếp theo là một vertical slice tối thiểu: **upload → parse → persist → xem lại chunk đúng file version và provenance**. Quý phụ trách FastAPI, MongoDB replica set, migration, index initialization và contract test. Yến hoàn tất hồ sơ dataset, split, evaluation protocol và fixture đã ẩn danh. Cả hai cùng review data model, API Contract và xây dựng golden corpus nhỏ có expected output.

**Chuyển:** Nhóm xin kết luận ngắn gọn ở trang cuối.

---

## Trang 8 — Kết luận

**Thời lượng:** khoảng 40 giây

Tóm lại, tuần này nhóm đã đi từ danh sách dataset và mô tả pipeline ban đầu sang ba đầu ra cụ thể hơn: kế hoạch đánh giá theo từng năng lực, data model có thể truy vết evidence, và API Contract đủ rõ để bắt đầu triển khai backend.

Phần code chạy được hiện vẫn là parser và chunker. C4, threat model, MongoDB/provenance design và API Contract là nền triển khai, không phải tính mới khoa học. Phần cần chứng minh bằng thực nghiệm nằm ở việc kết hợp retrieval, Evidence Verification, provenance và rubric-based assessment có giảng viên kiểm soát.

Mục tiêu gần nhất là hoàn thành vertical slice upload, parse, lưu trữ và truy xuất lại chunk đúng phiên bản. Sau đó nhóm mới khóa evaluation protocol và bắt đầu chạy benchmark.

Dạ, phần báo cáo tiến độ của nhóm đến đây là hết.

---

# GHI CHÚ DỰ PHÒNG KHI THẦY HỎI

## 1. Cái gì thực sự chạy được?

PDF/DOCX parser và section-aware chunker đang chạy được trên fixture. Test hiện tại là **2 passed, 1 skipped**; bài bị skip cần file báo cáo thật ở máy local. MongoDB, API, worker, index và AI chưa chạy end-to-end.

**Lệnh kiểm tra:**

```bash
./.venv/bin/python -m pytest services/backend/tests/test_pdf_docx_parsing.py -v
./.venv/bin/python services/backend/tests/demo_parsing_chunking.py
```

**File đối chiếu:**

- `services/backend/src/kltn_ai/integrations/parsing/`
- `services/backend/src/kltn_ai/integrations/indexing/chunking.py`
- `services/backend/tests/test_pdf_docx_parsing.py`
- `services/backend/tests/demo_parsing_chunking.py`
- `services/backend/tests/demo_output/`

## 2. Tại sao phải làm C4, trust boundary và threat model trước?

Để khóa trách nhiệm và đường đi của dữ liệu trước khi code. Nếu làm backend trước, nhóm dễ để browser truy cập sai thành phần, lọc quyền quá muộn, đưa dataset chưa được duyệt vào index hoặc làm mất provenance giữa các bước. Threat model hiện là danh sách rủi ro, control và test cần triển khai; chưa phải bằng chứng hệ thống đã an toàn.

**File đối chiếu:**

- `docs/architecture/c4.md`
- `docs/architecture/data-flow.md`
- `docs/threat-model/threat-model-v1.md`

## 3. Tại sao chọn MongoDB?

Dữ liệu của hệ thống có cấu trúc tài liệu, version, trạng thái, evidence và audit; schema sẽ còn tiến hóa trong giai đoạn nghiên cứu. MongoDB phù hợp cho metadata dạng document, còn file gốc để ngoài database. Single-node replica set được chọn cho dev/demo để có transaction và oplog trong giới hạn máy 16 GB, không được xem là production architecture.

**File đối chiếu:**

- `docs/adr/ADR-001-mongodb-provenance-storage.md`
- `docs/architecture/data-dictionary.md`

## 4. Provenance dùng để làm gì?

Để một evidence không chỉ là đoạn text do hệ thống trả ra. Nó phải chỉ được file nào, version nào, vị trí nào, chunk nào, index generation và cấu hình analysis run nào đã tạo ra kết quả. Nhờ đó giảng viên có thể mở lại nguồn; nhóm có thể tái lập thí nghiệm; và kết quả cũ bị đánh dấu stale khi parser, chunker, index hoặc model thay đổi.

## 5. API Contract là gì và chứng minh ở đâu?

Đó là đặc tả giao tiếp trước khi implement: endpoint nào tồn tại, request/response có field gì, trạng thái và error format ra sao. Nó giúp frontend, backend và worker dùng cùng một ngôn ngữ dữ liệu, đồng thời tạo cơ sở viết contract test. File hiện tại là draft thiết kế, chưa phải API runtime.

**File đối chiếu:**

- `docs/api/API_CONTRACT_V1.md`
- `docs/api/openapi-v1.yaml`

**Lệnh kiểm tra số lượng và cú pháp YAML:**

```bash
ruby -ryaml -e 'd=YAML.load_file(ARGV[0]); v=%w[get post put patch delete options head trace]; o=d["paths"].values.sum{|p| p.keys.count{|k| v.include?(k)}}; puts "#{d["paths"].size} paths, #{o} operations, #{d.dig("components","schemas").size} schemas"' docs/api/openapi-v1.yaml
```

Kết quả mong đợi: `29 paths, 33 operations, 59 schemas`.

## 6. Tại sao không dùng một dataset duy nhất?

Vì source retrieval, span alignment, long-document evidence retrieval, multi-hop verification và rubric grading cần các loại ground truth khác nhau. Tách benchmark theo năng lực giúp xác định module nào thực sự cải thiện hoặc gây lỗi; sau đó mới đánh giá end-to-end trên corpus in-domain.

## 7. Dataset nào sẵn sàng nhất?

PAN13 sẵn sàng nhất về mặt kỹ thuật vì có official archive, span annotation rõ và local MD5 đã PASS. Tuy nhiên, nhóm vẫn phải hoàn tất hồ sơ quyền sử dụng và approver trước khi chạy experiment chính thức.

## 8. Hai báo cáo sinh viên đã là dataset đánh giá chưa?

Chưa. Hiện chúng là test case in-domain để khảo sát parser và chunker. Chỉ sau khi có consent, bản ẩn danh, annotation guide, ground truth và review chéo thì mới gọi là corpus đánh giá.

## 9. Nếu báo cáo nói A, tài liệu đối chứng nói B thì xử lý thế nào?

Trước hết kiểm tra B có được duyệt, đủ thẩm quyền và cùng ngữ cảnh với A hay không. Nếu có, quan hệ claim–evidence là `CONTRADICTED`; decision rule của rubric có thể trả `UNMET`. Nếu chưa đủ căn cứ, trả `INSUFFICIENT` và `CANNOT_ASSESS`. Cả hai evidence span đều được giữ để giảng viên quyết định.

## 10. Tính mới của hướng nghiên cứu nằm ở đâu?

Không nằm ở việc dùng C4, MongoDB hay RAG riêng lẻ. Hướng cần kiểm chứng là một workflow evidence-first cho báo cáo sinh viên dài: kết hợp kiểm tra tương đồng, retrieval, kiểm chứng claim, chấm theo rubric, provenance, khả năng abstain khi thiếu bằng chứng và review của giảng viên. Đây mới là giả thuyết nghiên cứu; chỉ được xem là đóng góp nếu benchmark, ablation và human evaluation cho thấy lợi ích rõ ràng.

## 11. Nếu thầy hỏi “tuần tới phải demo được gì?”

Demo tối thiểu là: upload một PDF hoặc DOCX, parser tạo elements, chunker tạo chunks, metadata và provenance được lưu vào MongoDB, sau đó gọi API để xem lại đúng chunks của đúng file version. Demo này chưa cần chạy AI; mục tiêu là chứng minh backbone dữ liệu hoạt động đúng trước.

---

# CHECKLIST 2 PHÚT TRƯỚC KHI TRÌNH BÀY

- Mở sẵn báo cáo ở chế độ toàn màn hình và kiểm tra đủ 8 trang.
- Mở terminal tại root repo; chạy pytest trước buổi báo cáo.
- Mở sẵn `demo_output` để có thể cho thầy xem JSON khi được hỏi.
- Mở sẵn ba file: `c4.md`, `ADR-001-mongodb-provenance-storage.md`, `openapi-v1.yaml`.
- Không nói các benchmark đã chạy; chỉ nói đã khảo sát, mapping và kiểm tra sample/checksum.
- Không nói 29 endpoints đã implement; nói OpenAPI draft có 29 paths.
- Không nói hệ thống đã an toàn; nói threat model đã xác định rủi ro, control và test cần có.
