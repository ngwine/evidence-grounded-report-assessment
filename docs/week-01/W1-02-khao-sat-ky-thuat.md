# W1-02 — Khảo sát kỹ thuật

**Đề tài:** Hệ thống hỗ trợ đánh giá báo cáo sinh viên bằng AI cục bộ  
**Phiên bản:** 1.0  
**Ngày hoàn thành khảo sát:** 13/08/2026  
**Phạm vi:** phát hiện tương đồng; Rubric-RAG/chấm dựa trên bằng chứng; kiểm chứng tài liệu tham khảo; giới hạn phát hiện văn bản do AI tạo.

## 1. Kết luận điều hành

Khảo sát này chốt các định hướng kỹ thuật sau:

1. **Phát hiện tương đồng dùng pipeline nhiều tầng:** n-gram/BM25 để bắt trùng lặp từ vựng, embedding đa ngôn ngữ để bắt paraphrase/dịch, Reciprocal Rank Fusion (RRF) để hợp nhất thứ hạng, rồi cross-encoder reranker để xếp hạng lại một tập ứng viên nhỏ. BM25 là baseline bắt buộc; BEIR cho thấy đây vẫn là một baseline zero-shot mạnh, còn reranking thường cải thiện chất lượng nhưng tăng chi phí tính toán [S2].
2. **Tỷ lệ tương đồng không phải tỷ lệ đạo văn.** Hệ thống chỉ phát hiện quan hệ văn bản và cung cấp bằng chứng. Kết luận “đạo văn” còn phụ thuộc trích dẫn, quyền sử dụng, ngữ cảnh, chủ ý và quy định học thuật; quyền quyết định thuộc giảng viên.
3. **Rubric-RAG phải truy xuất bằng chứng riêng cho từng tiêu chí.** Mỗi điểm/nhận xét phải liên kết tới `evidence_id`, trang, chương/mục và đoạn trích. Kết quả thiếu bằng chứng hợp lệ phải bị từ chối hoặc chuyển sang trạng thái “không đủ bằng chứng”, không được để mô hình tự suy diễn.
4. **Kiểm chứng tài liệu tham khảo là đối chiếu nhiều tín hiệu**, không phải chỉ thử mở URL: DOI resolution, Crossref/DataCite metadata, khớp tiêu đề–tác giả–năm, trạng thái URL, và tính nhất quán giữa trích dẫn trong nội dung với danh mục cuối tài liệu. Không tìm thấy bản ghi không đồng nghĩa tài liệu giả.
5. **AI-writing detector chỉ là cảnh báo phụ**, không phải bằng chứng gian lận và không được tự động làm thay đổi điểm. Nghiên cứu cho thấy kết quả phụ thuộc detector, dữ liệu, ngôn ngữ, miền và phép biến đổi; paraphrase có thể làm giảm mạnh khả năng phát hiện [S24], [S25]. Các nghiên cứu bias năm 2026 cũng cho kết quả khác nhau giữa bối cảnh tiếng Anh/ELL và tiếng Czech [S29], [S30], nên bắt buộc benchmark riêng cho tiếng Việt trước khi hiển thị tính năng.
6. **Giả định Google Search trong bản đề xuất hiện có rủi ro chặn triển khai.** Tại ngày khảo sát, Gemini Grounding trả lời có nguồn nhưng điều khoản cấm dùng các link của Grounded Results để thu thập link, xây index, hoặc xác định trang đích để crawl/scrape [S10]. Custom Search JSON API đã đóng với khách hàng mới và khách hàng hiện hữu phải chuyển đổi trước 01/01/2027 [S11]. Vì vậy không được triển khai luồng “Gemini Grounding → lấy URL → crawl → index” nếu chưa có quyền bằng văn bản hoặc một dịch vụ tìm kiếm khác cho phép rõ ràng.

## 2. Nguyên tắc và thuật ngữ chung

### 2.1. Phân biệt similarity và plagiarism

| Khái niệm | Hệ thống có thể đo | Hệ thống không được tự kết luận |
|---|---|---|
| **Tương đồng văn bản (similarity/text reuse)** | Mức trùng n-gram, tương đồng ngữ nghĩa, nguồn ứng viên, vùng văn bản tương ứng, độ bao phủ token | Có vi phạm hay không |
| **Trích dẫn hợp lệ** | Có/không marker trích dẫn; marker có map tới bibliography; vị trí và nguồn đối chứng | Quyền sử dụng có hợp lệ trong mọi ngữ cảnh hay không |
| **Đạo văn (plagiarism)** | Cung cấp bằng chứng hỗ trợ giảng viên xem xét | Chủ ý, gian lận, chế tài hoặc kết luận kỷ luật |

Quy ước giao diện:

- Dùng nhãn **“tỷ lệ nội dung tương đồng”**, không dùng “tỷ lệ đạo văn”.
- Hiển thị từng cặp `đoạn báo cáo ↔ đoạn nguồn`, URL/nguồn nội bộ, loại tương đồng, trạng thái trích dẫn và điểm thành phần.
- Cho phép giảng viên đánh dấu `hợp lệ`, `cần xem xét`, `loại khỏi kết quả`, `đã trích dẫn`, `nghi vấn thiếu trích dẫn`.
- Điểm tổng tài liệu là độ bao phủ của **hợp các span token duy nhất**, tránh cộng trùng các đoạn chồng lặp; loại mục lục, bibliography, mẫu biểu, cụm phổ biến và trích dẫn dài hợp lệ theo cấu hình.

### 2.2. Nguyên tắc evidence-first và human-in-the-loop

Mọi module phải giữ được đường dẫn kiểm tra:

```text
kết quả/nhận xét
  -> evidence_id
  -> document_id + page + section + chunk/span
  -> phiên bản parser/index/model/prompt
  -> trạng thái giảng viên duyệt/sửa/từ chối
```

“Có nguồn được trích” chỉ chứng minh khả năng truy nguyên (attribution), chưa tự chứng minh nguồn đúng. Khung AIS yêu cầu phát biểu có thể được xác minh dựa trên nguồn đã chỉ ra [S14]; ALCE tách riêng citation recall và citation precision [S15]. Hai ý này phù hợp để đánh giá bằng chứng của hệ thống.

## 3. Nhóm 1 — Phát hiện nội dung tương đồng

### 3.1. Các họ phương pháp

| Phương pháp | Bắt tốt | Baseline/chỉ số phù hợp | Ưu điểm | Hạn chế | Quyết định cho đề tài |
|---|---|---|---|---|---|
| Exact phrase, character/word n-gram, fingerprint/winnowing | Sao chép nguyên văn; sửa dấu/cách trắng nhẹ; đoạn con dài | Precision/Recall/F1 cấp span hoặc cặp; thời gian | Nhanh, giải thích trực tiếp, dễ chạy local. Winnowing bảo đảm bắt ít nhất một fingerprint cho chuỗi chung đủ dài theo tham số [S1] | Yếu với paraphrase, tóm tắt, dịch; dễ bắt cụm công thức | Dùng như tín hiệu lexical phụ và để highlight span; không thay thế BM25/embedding |
| TF-IDF/cosine hoặc BM25 | Trùng từ/cụm từ, sửa nhẹ, truy vấn chứa từ hiếm | A1; Recall@k, MRR, nDCG@10 | Nhẹ, có inverted index, dễ giải thích; BM25 là baseline mạnh [S2] | Từ đồng nghĩa, paraphrase và xuyên ngôn ngữ có thể bị bỏ sót | **Baseline bắt buộc A1**; BM25 ở mức chunk, bổ sung boost phrase/entity |
| Dense embedding/bi-encoder | Paraphrase, tương đồng ngữ nghĩa, có thể hỗ trợ xuyên ngôn ngữ | A2; Recall@k, MRR, nDCG@10 | Truy xuất vector nhanh sau khi index; SBERT minh họa lợi ích của bi-encoder cho semantic search [S3] | Có false positive cùng chủ đề nhưng không tái sử dụng; chất lượng phụ thuộc model/ngôn ngữ/chunk | **Baseline bắt buộc A2**; benchmark Qwen3-Embedding-0.6B và BGE-M3 trên tiếng Việt |
| Hybrid lexical + dense | Kết hợp exact/rare terms với paraphrase | A3; so với A1/A2 trên cùng corpus | Bù điểm mù giữa lexical và semantic | Cần hợp nhất score/rank; thêm tham số | **Cấu hình chính A3**, ưu tiên RRF để tránh phụ thuộc scale score; vẫn thử weighted convex fusion trên validation |
| Cross-encoder reranker | Phân biệt cặp thật sự liên quan trong top-k | A4; nDCG@10, MRR, pair F1, latency | Đọc đồng thời cặp query–passage nên chính xác hơn bi-encoder; BERT reranking đạt cải thiện lớn trên MS MARCO trong nghiên cứu gốc [S4] | Chậm, tốn RAM/VRAM; không dùng để quét toàn corpus | **A4**, chỉ rerank top 20–100 ứng viên; chọn `k` bằng validation |
| Web candidate discovery | Nguồn nằm ngoài kho nội bộ | A5; source Recall@k, query/report, cost/report, failure rate | Tăng độ phủ nguồn công khai | Phụ thuộc API/index/ToS; web thay đổi; khó tái lập; không phải URL nào cũng được phép tải | Giữ interface provider, nhưng **chưa chốt Google provider** cho đến khi xử lý vấn đề điều khoản tại §3.5 |

RRF hợp nhất các danh sách thứ hạng mà không cần so sánh trực tiếp hai thang điểm khác nhau; công thức gốc là `RRF(d) = Σ 1/(k + rank_i(d))` [S5]. Đây là mặc định hợp lý cho A3, nhưng vẫn cần kiểm thử vì nghiên cứu sau cho thấy lựa chọn hàm fusion/phần tử tham số phụ thuộc miền [S6].

### 3.2. Mô hình local dự kiến

Hai cấu hình cần benchmark thay vì chốt theo leaderboard:

| Thành phần | Ứng viên 1 | Ứng viên 2 | Lý do đưa vào benchmark |
|---|---|---|---|
| Embedding | Qwen3-Embedding-0.6B | BGE-M3 | Cả hai hỗ trợ hơn 100 ngôn ngữ. Qwen3 0.6B có embedding tối đa 1.024 chiều và context 32K [S7]; BGE-M3 hỗ trợ dense, sparse, multi-vector và văn bản đến 8.192 token [S8] |
| Reranker | Qwen3-Reranker-0.6B | BGE-reranker-v2-m3 | Đều có lựa chọn đa ngôn ngữ, đủ nhỏ để thử local; phải đo chất lượng tiếng Việt, RAM và latency thật |
| Lexical | MongoDB Search/$search hoặc BM25 implementation chạy local trên deployment được duyệt | Cùng cấu hình tokenizer khác nhau | Không mặc nhiên coi mọi text score là cùng một cấu hình BM25; A1 phải khóa analyzer/index/scoring và benchmark riêng. Cần đánh giá tokenizer tiếng Việt và tác động bỏ dấu/giữ dấu |

Không dùng điểm công bố của nhà sản xuất để thay cho benchmark nội bộ. Quyết định cuối cùng dựa trên Pareto `Recall/nDCG – latency – peak RAM` trên phần validation tiếng Việt/Anh của đề tài.

### 3.3. Pipeline đề xuất

```text
parse PDF/DOCX
  -> chunk theo cấu trúc, giữ page/section/span
  -> chuẩn hóa Unicode, khoảng trắng; giữ bản gốc để hiển thị
  -> chọn đoạn đặc trưng
  -> BM25 + dense retrieval
  -> RRF/score fusion
  -> rerank top-k
  -> phân loại loại tương đồng + căn chỉnh span
  -> kiểm tra marker trích dẫn
  -> khử trùng nguồn/span
  -> evidence report cho giảng viên
```

Điểm tổng hợp ở cấp cặp có thể được hiệu chỉnh trên validation:

```text
pair_score = alpha * lexical_score_norm
           + beta  * semantic_score_norm
           + gamma * rerank_score_norm
```

Các trọng số và ngưỡng phải được khóa trước khi chạy test. `pair_score` là điểm xếp hạng/độ tin cậy kỹ thuật, **không phải xác suất đạo văn**.

Tỷ lệ bao phủ tài liệu:

```text
similarity_coverage = số token hợp lệ thuộc hợp các span được chấp nhận
                      / tổng số token hợp lệ của báo cáo
```

Phải báo cáo thêm phân bố theo nguồn và loại (`verbatim`, `light_edit`, `paraphrase`, `summary`, `cross_language`), vì một con số tổng không đủ cho quyết định học thuật.

### 3.4. Dataset và chỉ số

Theo đề cương, tạo 500–1.000 cặp có nhãn, gồm sao chép nguyên văn, sửa nhẹ, paraphrase, tóm tắt, dịch Việt–Anh/Anh–Việt và negative cùng chủ đề/không liên quan.

Yêu cầu thiết kế dữ liệu:

- Chia train/validation/test theo **tài liệu nguồn**, không chia ngẫu nhiên theo cặp; mọi biến thể của một đoạn gốc chỉ nằm trong một split để tránh leakage.
- Có hard negative cùng chủ đề, cùng thuật ngữ nhưng không có quan hệ tái sử dụng.
- Gán `source_id`, `source_span`, `suspicious_span`, loại biến đổi, ngôn ngữ, trạng thái trích dẫn.
- Hai người gán nhãn một phần dữ liệu; báo cáo đồng thuận và quy trình adjudication.
- Với web, ghi thời điểm truy vấn, provider, query, rank và lỗi; chỉ lưu nội dung/ảnh chụp khi giấy phép và điều khoản provider/website cho phép.

| Tầng đánh giá | Chỉ số chính | Cách đọc |
|---|---|---|
| Truy xuất nguồn | Recall@5, Recall@10 | Nguồn đúng có xuất hiện trong top-k hay không; ưu tiên cao vì bỏ sót nguồn thì reranker không cứu được |
| Xếp hạng | MRR, nDCG@10 | Nguồn đúng nằm sớm đến đâu; nDCG dùng được khi có nhiều mức liên quan |
| Xác định cặp | Precision, Recall, F1 | Đúng/sai ở cặp đoạn–nguồn |
| Loại tương đồng | Macro-F1 và F1 từng lớp | Tránh lớp nhiều mẫu che lớp paraphrase/dịch ít mẫu |
| Span/coverage | Token- hoặc character-level Precision/Recall/F1; sai số coverage | Đo chất lượng highlight và tỷ lệ tổng |
| Vận hành | p50/p95 latency, peak RAM/VRAM, số query/report, chi phí/report, API failure rate | Đo tính khả thi local và chi phí web |

PAN 2026 dùng các thước đo retrieval chuẩn như nDCG@10, Recall@10 và Recall@100 [S9], phù hợp để tham chiếu thêm cho A5.

### 3.5. Vấn đề Google Search phải xử lý trước khi code A5

Tình trạng tại **13/08/2026**:

- Gemini Grounding with Google Search tự quyết định một hoặc nhiều truy vấn và trả câu trả lời kèm citation [S10a]. Với Gemini 3, mỗi search query thực thi là một lượt tính phí; một prompt có thể sinh nhiều lượt [S10a]. Giá/quota có thể thay đổi nên phải đọc lại trang pricing ngay trước thí nghiệm [S10b].
- Điều khoản Gemini có hiệu lực 23/03/2026 cấm dùng Grounded Results/Search Suggestions/Links để thu thập link, xây index, hoặc xác định trang đích cho crawling/scraping; prompt, context và output Grounding được Google lưu 30 ngày cho mục đích vận hành được nêu trong điều khoản [S10]. Điều này xung đột trực tiếp với pipeline trong đề cương “Grounding lấy URL → tải nội dung → index/đối chiếu local”.
- Custom Search JSON API đã đóng với khách hàng mới; khách hàng cũ phải chuyển đổi trước 01/01/2027 [S11]. Nó không phải lựa chọn bền vững cho khóa luận kết thúc năm 2027 nếu tài khoản chưa có quyền cũ.

**Quyết định kỹ thuật:**

1. Tạo abstraction `SearchProvider`, không gắn domain model với Google:

   ```text
   search(query, budget, locale) -> [candidate_url, title, snippet, rank, provider_meta]
   ```

2. Chỉ cài provider cho phép rõ ràng việc lấy URL ứng viên và xử lý nội dung theo mục đích nghiên cứu. Từng website vẫn cần tuân thủ robots, giấy phép và điều khoản truy cập.
3. Có thể dùng Gemini Grounding như một luồng **hiển thị grounded response cho chính người gửi prompt**, theo đúng điều khoản, nhưng không dùng output đó làm nguồn thu thập cho index nội bộ.
4. Nếu chưa có web-search provider hợp lệ, chạy A1–A4 trên kho nội bộ/static corpus; chạy A5 trên corpus web được cấp phép hoặc hoãn A5. Không giả lập kết quả Google.
5. Không gửi toàn báo cáo hoặc thông tin nhận diện lên dịch vụ ngoài. Mọi snippet gửi ra ngoài cần quy trình đồng ý/ẩn danh và đánh giá dữ liệu; “local-first” không có nghĩa “không có dữ liệu rời máy” khi bật web provider.
6. Đưa vấn đề này vào W1-03 để chỉnh RQ2/phạm vi trước khi cam kết triển khai.

## 4. Nhóm 2 — Rubric-RAG và chấm dựa trên bằng chứng

### 4.1. Từ RAG tới Rubric-RAG

RAG kết hợp bộ nhớ tham số của mô hình với kho tri thức ngoài có thể truy xuất [S12]. Trong đề tài, đơn vị truy xuất không phải “mọi đoạn liên quan chung chung” mà là bằng chứng phục vụ **một tiêu chí rubric cụ thể**.

Quy trình đề xuất:

1. Phiên bản hóa rubric; tách thành tiêu chí độc lập có `criterion_id`, trọng số, thang điểm, mô tả từng mức và loại bằng chứng cần có.
2. Sinh truy vấn theo tiêu chí; truy xuất lexical + semantic trong báo cáo, rồi rerank top-k.
3. Đưa vào prompt chỉ tiêu chí đang chấm, thang điểm, evidence đã chọn và quy tắc không suy diễn ngoài evidence.
4. Local LLM trả JSON theo schema cố định.
5. Validator kiểm tra schema, phạm vi điểm, tổng trọng số, sự tồn tại của `evidence_id`, page/span, và mức hỗ trợ của evidence.
6. Nếu evidence rỗng/yếu hoặc mâu thuẫn: trả `insufficient_evidence`/giảm confidence, không bịa nhận xét.
7. Giảng viên sửa/duyệt/từ chối; lưu cả kết quả gốc và quyết định cuối.

Ollama hỗ trợ ràng buộc đầu ra theo JSON Schema và khuyến nghị validate lại bằng Pydantic/Zod [S16]. Structured output chỉ bảo đảm **hình dạng dữ liệu**, không bảo đảm nội dung hoặc evidence đúng; validator nghiệp vụ vẫn bắt buộc.

Schema tối thiểu:

```json
{
  "criterion_id": "LOGIC_RESULT_CONCLUSION",
  "proposed_score": 7.0,
  "max_score": 10.0,
  "confidence": 0.78,
  "evidence": [
    {
      "evidence_id": "c_431",
      "page": 31,
      "section": "4.2",
      "quote": "..."
    }
  ],
  "issues": [],
  "recommendations": [],
  "status": "pending_human_review"
}
```

### 4.2. So sánh cấu hình

| Cấu hình | Mô tả/baseline | Ưu điểm | Hạn chế/rủi ro | Kỳ vọng cần kiểm chứng |
|---|---|---|---|---|
| LLM đọc trực tiếp | B1; đọc context chung, không rubric có cấu trúc | Đơn giản, rẻ công triển khai | Điểm khó giải thích; trộn tiêu chí; dễ bỏ sót hoặc suy diễn | Baseline thấp nhất, không dùng production |
| LLM + rubric | B2; có tiêu chí/thang điểm, không retrieval riêng | Nhất quán hơn B1; dễ version rubric | Context dài; evidence không có ID; vẫn có thể trích sai | Kiểm tra đóng góp của rubric |
| Rubric-RAG | B3; retrieval evidence cho từng tiêu chí | Context tập trung, truy nguyên được | Nếu retriever bỏ sót thì điểm sai; tăng latency | Cải thiện evidence support và chấp nhận của giảng viên |
| Rubric-RAG + validation | B4; B3 + schema/rule/evidence validation/confidence | Chặn output hỏng và citation không tồn tại; dễ audit | Rule chỉ bắt lỗi hình thức; validation quá cứng có thể tăng abstention | **Cấu hình mục tiêu**, phải đo cả accuracy và coverage/abstention |

Các nghiên cứu AES cho thấy LLM không nên mặc định thay thế người chấm: một đánh giá trên ASAP ghi nhận độ lệch điểm và tương quan chưa tốt trong một số cấu hình [S17]; nghiên cứu CEFR cũng cho thấy calibration example có ích nhưng agreement thay đổi theo L1 [S18]. Vì vậy baseline giảng viên và human-in-the-loop là thành phần của thiết kế, không phải bước giao diện tùy chọn.

### 4.3. Chỉ số và thiết kế đánh giá

Theo đề cương, dùng 20–30 báo cáo/chương báo cáo có điểm và nhận xét theo rubric. Tối thiểu một giảng viên chấm tất cả; nên có hai giảng viên chấm một tập con và adjudicate.

| Khía cạnh | Chỉ số | Lưu ý |
|---|---|---|
| Sai số điểm | MAE theo tiêu chí và tổng | Báo cáo macro theo tiêu chí; không chỉ một điểm tổng |
| Thứ hạng | Spearman rho | Đo khả năng giữ thứ tự chất lượng bài |
| Đồng thuận ordinal | Quadratic Weighted Kappa (QWK) | Phù hợp thang điểm rời rạc; báo cáo human–human trước human–AI |
| Retrieval evidence | Evidence Recall@k, nDCG@k | Gold evidence cần được giảng viên/span annotator gán |
| Attribution | Evidence/citation precision, recall; tỷ lệ claim được evidence hỗ trợ | Đánh giá thủ công một mẫu; tham khảo AIS/RAGAS [S13], [S14] |
| Validation | JSON-valid rate, valid-`evidence_id` rate, unsupported-claim rate, abstention rate | Không xem schema-valid là evidence-valid |
| Giá trị sử dụng | Tỷ lệ nhận xét chấp nhận nguyên trạng/chấp nhận sau sửa/bị loại; thời gian giảng viên tiết kiệm | So sánh với quy trình chấm không có AI |
| Ổn định | Độ lệch giữa các lần chạy; bias theo độ dài/ngôn ngữ/tiêu chí | Khóa model, quantization, prompt, seed/temperature nếu hỗ trợ |
| Vận hành | p50/p95 latency, peak RAM/VRAM, token/context | Đo trên phần cứng đích |

Không chọn model/prompt bằng test set. Mỗi lần chạy phải log `model_hash`, quantization, prompt/rubric version, retriever/reranker version, top-k, nhiệt độ, schema version và hardware.

## 5. Nhóm 3 — Kiểm chứng tài liệu tham khảo

### 5.1. Mục tiêu và pipeline

Mục tiêu là phát hiện **bất nhất có thể kiểm tra**, không tuyên bố một nguồn “giả” chỉ vì API không tìm thấy.

```text
parse bibliography + in-text citations
  -> chuẩn hóa DOI/URL/author/title/year
  -> nếu có DOI: resolve + lấy metadata từ RA
  -> nếu không có DOI: bibliographic search và xếp hạng ứng viên
  -> so khớp field có trọng số
  -> kiểm tra URL/status/redirect (khi được phép)
  -> kiểm tra in-text <-> bibliography
  -> status + evidence + confidence + human review
```

GROBID có thể trích xuất full text và bibliographic references [S19]. Crossref REST API trả metadata do thành viên/trusted sources gửi và cho phép lookup DOI/search metadata [S20]; `query.bibliographic` phù hợp tra cứu citation theo title/author/year [S21]. DataCite Public API là fallback cho DOI do DataCite quản lý và không yêu cầu xác thực khi đọc metadata Findable [S22]. DOI resolution xác nhận identifier có bản ghi đích, nhưng không tự xác nhận metadata mà sinh viên ghi là đúng [S23].

### 5.2. Phương pháp, baseline và quyết định

| Phương pháp | Baseline/chỉ số | Ưu điểm | Hạn chế | Quyết định |
|---|---|---|---|---|
| Regex/normalization DOI + `doi.org` resolve | Exact DOI match; DOI resolution accuracy | Chính xác, rẻ, dễ audit | DOI đúng có thể trỏ tới tác phẩm khác với entry | Bước đầu bắt buộc; luôn kiểm metadata sau resolve |
| Crossref/DataCite lookup theo DOI | Field accuracy, mismatch F1, API failure | Metadata có cấu trúc, nguồn đăng ký chính thức | Metadata có thể thiếu/lỗi/cập nhật chậm; coverage khác nhau | Crossref trước, DataCite/RA phù hợp fallback; cache theo chính sách |
| Bibliographic search khi thiếu DOI | Top-1 accuracy, MRR/Recall@k | Tìm DOI ứng viên từ title/author/year | Nhiều tác phẩm gần tên; dễ gán nhầm | Chỉ tự match khi vượt ngưỡng và cách biệt đủ lớn; còn lại `AMBIGUOUS` |
| Weighted/fuzzy field matching | Precision/Recall/F1 từng loại lỗi | Chịu lỗi chính tả/dấu/thứ tự tên | Ngưỡng phụ thuộc ngôn ngữ; tiêu đề gần nhau | Trọng số ưu tiên DOI/title, rồi author/year; tune trên validation |
| URL health/redirect | URL status accuracy, failure rate | Phát hiện link hỏng/chuyển hướng | Link hỏng không có nghĩa nguồn sai; HEAD có thể bị chặn | Tín hiệu riêng, không gộp thành “fake reference” |
| In-text citation ↔ bibliography | F1 cho missing/orphan citation | Phát hiện cite thiếu entry và entry không được cite | Nhiều citation style, OCR/parser error | MVP bắt buộc với style hỗ trợ; hiển thị parser confidence |

Trạng thái đầu ra đề xuất:

| Status | Ý nghĩa |
|---|---|
| `VERIFIED` | Identifier/ứng viên đủ chắc và metadata khớp trong dung sai |
| `METADATA_MISMATCH` | Tìm thấy bản ghi nhưng title/author/year không khớp |
| `DOI_NOT_FOUND` | DOI không resolve/không có trong RA đã hỏi; cần kiểm tra thủ công |
| `AMBIGUOUS` | Có nhiều ứng viên, không đủ khoảng cách để chọn |
| `URL_UNREACHABLE` | URL lỗi/timeout/redirect bất thường; không đồng nghĩa tài liệu không tồn tại |
| `MISSING_BIB_ENTRY` | Citation trong nội dung không map tới bibliography |
| `UNCITED_REFERENCE` | Entry bibliography không tìm thấy citation trong nội dung |
| `UNVERIFIED` | Thiếu metadata/nguồn không thuộc coverage; không được tự gán là sai |

### 5.3. Dataset và metrics

Theo đề cương: 300–500 entry, ít nhất 100 trường hợp lỗi có chủ đích (`DOI giả`, `DOI của bài khác`, sai tiêu đề, tác giả, năm, URL hỏng, citation thiếu).

- Tách train/validation/test theo **tác phẩm**, không để bản đúng ở train và bản gây lỗi của cùng tác phẩm ở test.
- Có tài liệu tiếng Việt không DOI, luận văn, sách, tiêu chuẩn và web page để đo coverage thực tế.
- Báo cáo Precision/Recall/F1 cho từng nhóm lỗi và macro-F1; top-1 accuracy/MRR cho DOI matching; field accuracy; API failure/timeout; latency.
- Tách kết quả `có DOI`, `không DOI nhưng có metadata`, `chỉ URL`, `không đủ thông tin`.
- Confusion matrix phải giữ riêng `UNVERIFIED` và `ERROR`; không ép mọi thất bại API thành “invalid”.

## 6. Nhóm 4 — Giới hạn phát hiện văn bản AI

### 6.1. Các họ phương pháp

| Họ phương pháp | Tín hiệu | Ưu điểm | Giới hạn chính | Vai trò trong đề tài |
|---|---|---|---|---|
| Perplexity/burstiness/stylometry | Độ dự đoán được, phân bố câu/từ, đặc trưng phong cách | Chạy local, giải thích được một phần | Phụ thuộc model/ngôn ngữ/miền; dễ nhầm văn phong công thức hoặc người học ngôn ngữ | Chỉ tạo tín hiệu bất thường, không nhãn kết luận |
| Supervised classifier | Biểu diễn học từ human/AI corpus | Có thể tốt trong-domain | Distribution shift khi model/prompt/domain thay đổi; dễ học shortcut | Chỉ thử nghiệm nếu có dataset tiếng Việt đúng miền |
| Zero-shot likelihood/curvature | Xác suất token dưới proxy model; DetectGPT là ví dụ [S26] | Không cần tập train detector riêng | Cần log-prob/model phù hợp; tốn tính toán; không ổn định với model lạ/chỉnh sửa | Ngoài MVP hoặc baseline nghiên cứu nhỏ |
| Watermark | Tín hiệu được cài lúc sinh | Có thể có kiểm định thống kê khi biết scheme/model | Chỉ áp dụng output của generator tham gia; chỉnh sửa/paraphrase và spoofing là threat model | Không phù hợp để quét báo cáo không rõ generator |
| Retrieval/provenance/process evidence | So với log output đã biết, lịch sử phiên bản, bản nháp, nguồn và vấn đáp | Có bằng chứng quy trình mạnh hơn chỉ phong cách | Cần quyền truy cập, chính sách và dữ liệu trước đó | Ưu tiên cho review của giảng viên; không coi là detector phổ quát |

### 6.2. Bằng chứng về giới hạn và fairness

- Sadasivan et al. cho thấy detector thuộc nhiều họ có thể bị làm suy giảm bởi recursive paraphrasing và còn phân tích giới hạn lý thuyết khi phân phối văn bản người/máy gần nhau [S24].
- Krishna et al. cho thấy paraphrase làm giảm mạnh nhiều detector; retrieval chỉ là biện pháp tốt khi nhà cung cấp có database output đã sinh, không phải giải pháp tổng quát cho trường học [S25].
- OpenAI đã rút classifier năm 2023 vì độ chính xác thấp và từng cảnh báo không dùng làm công cụ quyết định chính [S27]. Turnitin hiện cũng nói kết quả có thể nhầm human/AI/paraphrased và không được dùng làm căn cứ duy nhất cho hành động bất lợi [S28].
- Nghiên cứu Liang et al. ghi nhận bias với người viết tiếng Anh không bản ngữ trong các detector được thử năm 2023 [S31]. Tuy nhiên, kết quả mới không đồng nhất: Stowe et al. (ACL 2026) thấy một số detector có chênh lệch theo ELL/nhóm giao cắt trong dữ liệu tiếng Anh [S29], còn Al Ali et al. (EACL 2026) không thấy systematic bias với người viết Czech không bản ngữ ở ba họ detector [S30]. Kết luận đúng là **fairness phụ thuộc hệ thống, ngôn ngữ và dữ liệu**, không phải mọi detector luôn bias theo cùng cách.
- Đã có nghiên cứu/dataset phát hiện văn bản AI tiếng Việt [S32], nhưng nó không chứng minh khả năng tổng quát lên báo cáo khóa luận, model mới, văn bản đã biên tập hoặc text kết hợp người–AI.

### 6.3. Chính sách sản phẩm bắt buộc

1. Không hiển thị “X% do AI viết” như một sự thật. Dùng `AI-writing anomaly warning` hoặc “đoạn có đặc trưng cần rà soát”.
2. Không tự động trừ điểm, khóa bài, gắn nhãn gian lận hoặc chuyển kỷ luật.
3. Cảnh báo phải kèm: span, loại tín hiệu, model/version, ngưỡng, mức bất định và lưu ý “không phải bằng chứng kết luận”.
4. Giảng viên xem thêm bản nháp/version history, nguồn, mức nhất quán nội dung và hỏi vấn đáp; quyết định cuối theo quy định nhà trường.
5. Nếu chưa có benchmark tiếng Việt đúng miền đạt yêu cầu FPR/fairness đã chốt, **không phát hành detector trong MVP**. Có thể chỉ giữ module nghiên cứu tắt mặc định.

### 6.4. Nếu thực nghiệm detector phụ

Dataset phải có tối thiểu các nhóm:

- người viết hoàn toàn;
- AI sinh hoàn toàn từ nhiều model/prompt;
- AI sinh rồi người sửa;
- người viết rồi AI sửa ngữ pháp/paraphrase;
- paraphrase nhiều vòng;
- dịch qua lại;
- ngắn/dài, các ngành và mức năng lực viết khác nhau.

Chia test theo **tác giả và generator**; có test model chưa xuất hiện trong train. Báo cáo AUROC/AUPRC, Precision/Recall/F1, **FPR ở ngưỡng triển khai**, calibration (Brier/ECE), kết quả theo ngôn ngữ/độ dài/nhóm, và robustness sau paraphrase. Accuracy cân bằng không đủ cho bài toán có chi phí false positive cao.

## 7. Thiết kế thí nghiệm đã chốt

### 7.1. Thí nghiệm A — Truy xuất nguồn tương đồng (RQ1/RQ2)

| ID | Cấu hình | Vai trò | Điều kiện kiểm soát |
|---|---|---|---|
| **A1** | Keyword/BM25 | Baseline từ vựng | Cùng chunk, corpus và top-k với A2–A4 |
| **A2** | Dense embedding | Baseline semantic | Cùng chunk/corpus; model được khóa sau validation |
| **A3** | Hybrid BM25 + embedding bằng RRF/fusion | Đo bổ sung của hybrid | Không reranker; fusion parameter khóa trên validation |
| **A4** | Hybrid + cross-encoder reranker | Đo bổ sung của reranking | Rerank cùng top-N candidate từ A3 |
| **A5** | Web candidate provider + pipeline A4 đối chiếu local | Đo độ phủ, chi phí và latency end-to-end | Provider/ToS hợp lệ; log query/cost/failure; không coi đây là ablation thuần với A4 |

Chỉ số bắt buộc: Recall@5/10, MRR, nDCG@10; pair Precision/Recall/F1; macro-F1 loại tương đồng; span F1/coverage error; p50/p95 latency; peak RAM/VRAM; số query và chi phí/report.

**Lưu ý thiết kế:** A1–A4 phải chạy trên cùng candidate universe để so sánh công bằng. A5 thay đổi cả phạm vi nguồn nên là đánh giá end-to-end/coverage–cost riêng, không được diễn giải toàn bộ chênh lệch A5–A4 là đóng góp của “Google”.

### 7.2. Thí nghiệm B — Đánh giá theo rubric (RQ3)

| ID | Cấu hình | Thành phần được thêm |
|---|---|---|
| **B1** | LLM trực tiếp | Không rubric có cấu trúc, không evidence retrieval |
| **B2** | LLM + rubric | Rubric/tiêu chí, chưa retrieval riêng |
| **B3** | Rubric-RAG | Retrieval + rerank evidence theo tiêu chí |
| **B4** | Rubric-RAG + validation | JSON Schema, rule kiểm `evidence_id`, range/weight/confidence, abstention |

Chỉ số bắt buộc: MAE, Spearman, QWK; evidence Recall@k/precision/recall; unsupported-claim rate; valid-output rate; tỷ lệ nhận xét được chấp nhận; abstention rate; thời gian xử lý và thời gian giảng viên review.

Điều kiện khóa: cùng tập báo cáo, rubric, model/quantization và budget context khi có thể. Nếu B1 dùng toàn báo cáo còn B3 chỉ dùng evidence, phải ghi token/context thực tế để tránh kết luận sai do khác ngân sách đầu vào.

### 7.3. Thí nghiệm C — Tài liệu tham khảo (RQ4)

- Precision/Recall/F1 từng loại lỗi và macro-F1.
- DOI match top-1 accuracy/MRR; accuracy từng field title/author/year.
- Tỷ lệ `UNVERIFIED`, API failure, timeout và latency.
- Phân tích riêng có DOI/không DOI/chỉ URL và lỗi parser so với lỗi verifier.

### 7.4. AI-writing là module phụ, không phải RQ5 hiện tại

Trong đề cương hiện hành, **RQ5 là đánh giá chất lượng câu hỏi vấn đáp được sinh**, không phải phát hiện văn bản AI. Vì vậy không được đổi nghĩa RQ5 trong W1-02. AI-writing chỉ là module cảnh báo mở rộng, nằm ngoài hai đóng góp/thí nghiệm chính A và B; nếu thực hiện thì dùng thiết kế phụ ở §6.4 và không tuyên bố “xác định AI”. Thí nghiệm câu hỏi vấn đáp của RQ5 cần được đặc tả riêng theo thiết kế D trong đề cương.

### 7.5. Quy tắc thực nghiệm chung

- Khóa test set; chỉ tune ngưỡng/trọng số/top-k trên validation.
- Ghi version code, dataset, parser, model, embedding, reranker, prompt/rubric/schema, seed và hardware.
- Chạy lặp các cấu hình có tính ngẫu nhiên; báo cáo mean, độ lệch chuẩn và bootstrap confidence interval 95% khi phù hợp.
- Báo cả quality và cost/latency/RAM; không chọn cấu hình chỉ vì điểm cao nhất.
- Phân tích sai số theo ngôn ngữ, loại biến đổi, độ dài, ngành, loại nguồn và parser quality.
- Không dùng dữ liệu thật chưa ẩn danh/chưa được phép; kiểm soát dữ liệu gửi dịch vụ ngoài.

## 8. Khuyến nghị triển khai và thứ tự ưu tiên

| Ưu tiên | Việc cần làm | Đầu ra/tiêu chí hoàn tất |
|---|---|---|
| P0 | Chốt định nghĩa label và annotation guide similarity | Có ví dụ positive/negative/hard-negative, loại biến đổi, trạng thái citation |
| P0 | Chốt rubric và gold evidence với giảng viên | Rubric version 1; mỗi tiêu chí có descriptor và evidence requirement |
| P0 | Xử lý pháp lý/kỹ thuật cho web provider | Có văn bản điều khoản cho phép workflow hoặc chính thức thu hẹp/đổi RQ2/A5 |
| P0 | Dựng A1/B1/B2 baseline trước | Có script benchmark tái lập và log version |
| P1 | Benchmark embedding/reranker local | Bảng Pareto quality–latency–RAM, chọn model trên validation |
| P1 | Dựng reference gold set và status taxonomy | 300–500 entry theo kế hoạch, không trộn `UNVERIFIED` với invalid |
| P1 | Dựng B3/B4 và evidence validator | Không nhận output có `evidence_id` không tồn tại; hỗ trợ abstention |
| P2 | AI-writing research prototype | Chỉ bật nếu có benchmark tiếng Việt, threshold/FPR/fairness được duyệt |

## 9. Điểm chưa chắc chắn cần xác nhận

1. Phần cứng đích (RAM/VRAM/CPU/GPU) chưa có trong tài liệu nên chưa thể chốt Qwen3 hay BGE-M3, quantization và top-k/rerank-k.
2. Chưa có sample báo cáo thật và rubric đã được giảng viên duyệt; chất lượng B3/B4 phụ thuộc trực tiếp hai nguồn này.
3. Chưa biết trường/tài khoản có quyền dùng một web-search API cho phép lấy URL và đối chiếu local hay không. Gemini Grounding và Custom Search JSON API hiện không đáp ứng workflow như mô tả.
4. Chưa chốt quy định xử lý dữ liệu sinh viên khi gửi snippet ra ngoài; Gemini Grounding có lưu dữ liệu 30 ngày theo điều khoản hiện hành [S10].
5. Chưa chốt citation style cần hỗ trợ (IEEE/APA/Vancouver/tự do), ảnh hưởng parser và mapping in-text.
6. Chưa có ngưỡng chấp nhận cho Recall/FPR/latency/cost; phải được định nghĩa trước benchmark, không chọn sau khi thấy test result.
7. Chưa có gold label đủ để tuyên bố fairness/hiệu quả AI detector tiếng Việt; mặc định tính năng ngoài MVP và tắt.

## 10. Nguồn sơ cấp và tài liệu chính thức

**Tất cả URL dưới đây được truy cập ngày 13/08/2026.** Các nguồn dùng để đưa ra kết luận là paper gốc, trang tác giả/ACL Anthology, model card của nhóm phát hành hoặc tài liệu chính thức của nhà cung cấp.

### Phát hiện tương đồng và retrieval

- [S1 — Schleimer, Wilkerson & Aiken, *Winnowing: Local Algorithms for Document Fingerprinting* (paper gốc)](https://theory.stanford.edu/~aiken/publications/papers/sigmod03.pdf)
- [S2 — Thakur et al., *BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models*](https://arxiv.org/abs/2104.08663)
- [S3 — Reimers & Gurevych, *Sentence-BERT*](https://arxiv.org/abs/1908.10084)
- [S4 — Nogueira & Cho, *Passage Re-ranking with BERT*](https://arxiv.org/abs/1901.04085)
- [S5 — Cormack, Clarke & Büttcher, *Reciprocal Rank Fusion...* (bản tác giả)](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf)
- [S6 — Bruch, Gai & Ingber, *An Analysis of Fusion Functions for Hybrid Retrieval*](https://arxiv.org/abs/2210.11934)
- [S7 — Qwen Team, Qwen3 Embedding/Reranking — model card chính thức](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- [S8 — Chen et al., *BGE M3-Embedding*](https://arxiv.org/abs/2402.03216)
- [S9 — PAN at CLEF 2026, Generated Plagiarism Detection — task/evaluation chính thức](https://pan.webis.de/clef26/pan26-web/generated-plagiarism-detection.html)

### Google Search/Grounding

- [S10a — Google AI for Developers, Grounding with Google Search](https://ai.google.dev/gemini-api/docs/google-search)
- [S10b — Google AI for Developers, Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [S10 — Google AI for Developers, Gemini API Additional Terms of Service (hiệu lực 23/03/2026)](https://ai.google.dev/gemini-api/terms)
- [S11 — Google for Developers, Custom Search JSON API: availability/deprecation](https://developers.google.com/custom-search/v1/overview)

### RAG, evidence và chấm rubric

- [S12 — Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*](https://arxiv.org/abs/2005.11401)
- [S13 — Es et al., *RAGAS: Automated Evaluation of Retrieval Augmented Generation*](https://arxiv.org/abs/2309.15217)
- [S14 — Rashkin et al., *Measuring Attribution in Natural Language Generation Models (AIS)*](https://aclanthology.org/2023.cl-4.2/)
- [S15 — Gao et al., *Enabling Large Language Models to Generate Text with Citations (ALCE)*](https://aclanthology.org/2023.emnlp-main.398/)
- [S16 — Ollama, Structured Outputs — tài liệu chính thức](https://docs.ollama.com/capabilities/structured-outputs)
- [S17 — Kundu & Barbosa, *Are Large Language Models Good Essay Graders?*](https://arxiv.org/abs/2409.13120)
- [S18 — Yancey et al., *Rating Short L2 Essays on the CEFR Scale with GPT-4*](https://aclanthology.org/2023.bea-1.49/)

### Kiểm chứng tài liệu tham khảo

- [S19 — GROBID, Introduction/full-text and bibliographic extraction — tài liệu chính thức](https://grobid.readthedocs.io/en/latest/Introduction/)
- [S20 — Crossref REST API — tài liệu chính thức](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
- [S21 — Crossref REST API repository, `query.bibliographic` — tài liệu chính thức](https://github.com/CrossRef/rest-api-doc)
- [S22 — DataCite REST API — tài liệu chính thức](https://support.datacite.org/docs/api)
- [S23 — DOI Foundation, DOI Handbook](https://www.doi.org/doi-handbook/html/)

### Phát hiện văn bản AI và giới hạn

- [S24 — Sadasivan et al., *Can AI-Generated Text be Reliably Detected?*](https://arxiv.org/abs/2303.11156)
- [S25 — Krishna et al., *Paraphrasing Evades Detectors of AI-Generated Text, but Retrieval Is an Effective Defense*](https://arxiv.org/abs/2303.13408)
- [S26 — Mitchell et al., *DetectGPT*](https://arxiv.org/abs/2301.11305)
- [S27 — OpenAI, AI classifier retirement and documented limitations — thông báo chính thức](https://openai.com/index/new-ai-classifier-for-indicating-ai-written-text/)
- [S28 — Turnitin, Using the AI Writing Report — hướng dẫn/giới hạn chính thức](https://guides.turnitin.com/hc/en-us/articles/22774058814093-Using-the-AI-Writing-Report)
- [S29 — Stowe et al., *Identifying Bias in Machine-generated Text Detection*, ACL 2026](https://aclanthology.org/2026.acl-long.109/)
- [S30 — Al Ali, Helcl & Libovický, *Different Time, Different Language...*, EACL 2026](https://aclanthology.org/2026.eacl-srw.20/)
- [S31 — Liang et al., *GPT Detectors Are Biased against Non-Native English Writers*](https://arxiv.org/abs/2304.02819)
- [S32 — Nguyen-Son et al., *Vietnamese AI Generated Text Detection*](https://arxiv.org/abs/2405.03206)

## 11. Definition of Done cho W1-02

- [x] Bao phủ đủ bốn nhóm kỹ thuật.
- [x] Có baseline, metrics, ưu/nhược điểm và khuyến nghị.
- [x] Phân biệt similarity với plagiarism; AI detector chỉ là cảnh báo.
- [x] Khớp thiết kế A1–A5 và B1–B4 trong tài liệu khóa luận.
- [x] Nêu dataset, kiểm soát leakage, log tái lập và human-in-the-loop.
- [x] Nguồn là paper gốc/tài liệu chính thức, có link trực tiếp và ngày truy cập.
- [x] Ghi rõ rủi ro Google API/điều khoản cần đưa sang W1-03.
