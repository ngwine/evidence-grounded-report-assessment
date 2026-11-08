# Verifier LLM local cho Pipeline 2

## Bổ sung nghiên cứu 08/11 — context bundles

Policy opt-in `source_unit_policy: context_bundles_v1` trong
[`context-one-step-v1.json`](../../research/configs/p2-comparison/context-one-step-v1.json)
giữ unit trong một source span liên tục thay vì chia theo dấu chấm/câu.
Giới hạn 1.800 ký tự/unit; đoạn dài hoặc đoạn đã bị chunker chia vẫn có thể
có nhiều unit. Không ghép source spans khác nhau thành quote giả, không mất
non-whitespace text; overlap ownership mơ hồ/vượt budget thì giữ kết luận.
Prompt riêng yêu cầu giữ attribution, phân biệt tác giả với người được trích,
kiểm số quotation và nguồn theo đúng rubric. Đây là hướng sửa cần đo bằng
model thật và người kiểm, không bảo đảm suy luận đúng từ proof provenance.

Prompt/policy hashes và catalog mới được khóa trong runner nghiên cứu
[`retrieval_study`](../../research/p2_comparison/README.md).
Mode legacy giữ nguyên khi không khai setting; profile app v1/v2 bên dưới
vẫn dùng cấu hình của chúng. Nhánh mới hiện là cấu hình nghiên cứu riêng,
chưa được đăng ký thành profile web hoặc dùng kết quả DEV làm chứng nhận grading.

## Bản v2 — đọc báo cáo ngắn và chọn đoạn nguồn

Profile `bm25-p2-llm-v2` thêm chế độ **LLM · đọc đủ báo cáo ngắn**. Với
checklist LOCAL, nếu tổng các chunk đã parse không quá 14.000 ký tự,
20.000 UTF-8 bytes và 32 chunk, verifier đọc tất cả theo thứ tự đầu vào.
Nếu vượt một giới hạn, giữ bộ truy xuất có xếp hạng và ghi lý do fallback.
Đọc hết các chunk không chứng minh parser đã giữ mọi nội dung tài liệu gốc;
ảnh, nguồn ngoài và nội dung vắng khỏi parser vẫn không tự được xác minh.

Code chia evidence thành các đoạn nguồn có ID và tọa độ cố định. Model chỉ
chọn `unit_id`, tối đa ba đoạn mỗi yêu cầu ở chế độ hai bước; code tự giải
ID bằng chứng gốc.
Grammar giới hạn các ID có thật, code kiểm lại rồi tự lấy nguyên văn và
giải offset/source spans. Câu lặp vẫn phân biệt được bằng ID và vị trí, không cần đoán model
muốn dẫn lần nào. Không dùng fuzzy matching hay tự sửa quote model tạo.

Profile v2 bật `citation_audit`: lượt đầu chỉ chọn các unit, không kết luận
hoặc sinh giải thích. Lượt xác minh thứ hai chỉ thấy requirement và text của
các unit đã chọn; không nhận toàn bài hoặc nhận xét ban đầu để dựa theo.
Nó chỉ được dùng một phần các unit đã chọn, không truy tìm lại đoạn khác.
Yêu cầu không chọn được unit nào giữ INSUFFICIENT; các yêu cầu còn lại vẫn
được kiểm riêng. Mỗi checklist dùng tối đa hai lượt model và không tự retry.

Hai lượt có prompt/schema, request/response hash, telemetry và kiểm digest
riêng; lỗi của một bước đều giữ điểm chưa xác định. Đây vẫn là phán đoán
của model cần đánh giá độc lập, không phải chứng minh ngữ nghĩa bằng code.

Prompt/schema v2 có phiên bản/hash riêng. Prompt yêu cầu bám điều kiện thực
sự có trong rubric; không tự thêm yêu cầu tên người/trường, số ví dụ hoặc
phép đo ngoài đặc tả. Giới hạn rationale 400 ký tự và generation 768 token
giảm phần phải sinh; timeout mỗi yêu cầu 120 giây, context 32.768 token,
byte-budget đầu vào cuối cùng vẫn được kiểm trước inference. Cấu hình cũ
v1, prompt/schema exact-quote mặc định và phép tính điểm được giữ riêng.

Thay đổi này kết hợp context, citation, prompt và tài nguyên, nên so kết quả
trước/sau là một vòng sửa phần mềm, không phải ablation một yếu tố. Lượt
SEFORA CRIT001 đã dùng tìm lỗi là tập phát triển, không được gọi holdout
hoặc kết quả chấm độc lập. Các ca có phản chứng, thiếu thông tin, chỉ có
kế hoạch và chỉ thị nhúng vẫn cần kiểm tra để tránh thưởng MET quá mức.

CLI v2:

```sh
.venv-research/bin/python -m research.core_mvp \
  --report path/to/report.docx --rubric path/to/authored-rubric.json \
  --config services/backend/configs/bm25-p2-llm-v2.json \
  --output-dir var/results/core-mvp/p2-llm-v2-new-run --pipeline assessment
```

Migration `009-local-llm-assessment-profile-v2` mở thêm enum cho profile,
không sửa migration 001–008. Phần sau ghi lại triển khai/lượt đo v1 ngày
03/11, không phải mô tả mặc định của v2.

Cập nhật 03/11/2026. Chế độ mới là **opt-in**; cấu hình V4, các profile cũ
và số liệu PAN/QASPER lịch sử được giữ nguyên.

## Cách dùng trên máy demo

Model và runtime riêng đã được cài trong `var/` của checkout này:

```bash
.venv-research/bin/python scripts/dev_p2_llm.py start
.venv-research/bin/python scripts/dev_p2_llm.py status
.venv-research/bin/python scripts/dev_app.py start
```

Mở `http://127.0.0.1:5173`, vào phần phân tích, mở **Cấu hình phân tích**,
chọn **BM25 + đánh giá rubric bằng LLM** (`bm25-p2-llm-v1`). Chọn chạy đánh
giá rubric hoặc cả hai pipeline, chọn báo cáo/rubric rồi chạy như luồng hiện
có. P1 trong profile này dùng BM25; verifier LLM chỉ được gọi cho P2.

CLI offline dùng cùng profile:

```bash
.venv-research/bin/python -m research.core_mvp \
  --report path/to/report.docx \
  --rubric path/to/authored-rubric.json \
  --config services/backend/configs/bm25-p2-llm-v1.json \
  --output-dir var/results/core-mvp/p2-llm-new-run \
  --pipeline assessment
```

Output phải dùng thư mục mới. Rubric vẫn theo hợp đồng authored checklist;
phiên bản này không tự chuyển mọi rubric tự do hoặc hai CSV SEFORA thành
checklist/gold.

## Model và runtime

- Model: `qwen3.5:4b-q4_K_M`, GGUF Q4_K_M, khoảng 3,32 GB.
- Digest model: `sha256:d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.
- Ollama riêng: `0.40.13`, tại `var/runtime/ollama-v0.40.13/`.
- Endpoint: `http://127.0.0.1:11435`; model ở `var/models/ollama-p2/`.
- Launcher dùng launchd của phiên đăng nhập macOS, một model được nạp và
  một yêu cầu song song, tắt cloud. Host prompt cache của llama-server được
  tắt bằng `LLAMA_ARG_CACHE_RAM=0`, hàng đợi giới hạn 1 để tránh tích cache
  ngoài phần bộ nhớ model trên máy 16 GB. Model tự nhả khỏi RAM sau thời gian
  keep-alive; file trọng số vẫn giữ trên đĩa.
- Ollama có sẵn ở cổng 11434 không bị nâng cấp hoặc thay thế. Bản 0.17.6
  cũ không tải được tag Qwen3.5 hiện tại, nên dùng runtime riêng.

Để dừng riêng model service:

```bash
.venv-research/bin/python scripts/dev_p2_llm.py stop
```

Trên checkout mới, tải runtime từ
[release Ollama 0.40.13](https://github.com/ollama/ollama/releases/tag/v0.40.13),
kiểm SHA-256 của `ollama-darwin.tgz` là
`bae29252232b9e1358cf5801a7d65a07442af18fb5467cb68c7fc3711f59c511`
trước khi giải nén vào `var/runtime/ollama-v0.40.13/`. Launcher kiểm thêm
hash binary đã khóa. Sau khi `start`, tải model bằng runtime riêng:

```bash
OLLAMA_HOST=127.0.0.1:11435 \
  var/runtime/ollama-v0.40.13/ollama pull qwen3.5:4b-q4_K_M
```

Model tag có thể thay đổi theo registry; verifier chỉ nhận đúng digest
trong profile. Thay checkpoint cần profile/đối chứng mới và kiểm tra lại.

## Luồng và ranh giới quyết định

```text
Authored rubric → Compiler → LOCAL/GRAPH retrieval → Validated Evidence Pack
→ Local LLM proposes a relation for each requirement + exact quotations
→ JSON/ID/version/quote/proof validation
→ Code maps relations to MET / UNMET / CANNOT_ASSESS
→ Existing deterministic scoring → Lecturer review
```

LLM đọc ý nghĩa của statement/requirement; `any_of` mô tả các cách diễn đạt
nội dung được chấp nhận. Cho phép paraphrase tương đương nhưng phải giữ
đúng đối tượng, số liệu, phiên bản và điều kiện; trùng từ không tự chứng
minh yêu cầu đạt. Các mẫu phản chứng là gợi ý tùy chọn, không phải danh sách
đầy đủ để giới hạn khả năng nhận ra phản chứng trực tiếp. Verifier không nhận
điểm số từ model. Code kiểm toàn bộ requirement ID xuất hiện đúng một lần
và tự tổng hợp: phản chứng trực tiếp → UNMET; mọi yêu cầu được hỗ trợ → MET;
còn thiếu/bất định → CANNOT_ASSESS. Những yêu cầu khác nhau có thể được đạt
và không đạt; mâu thuẫn chưa phân xử trong cùng yêu cầu phải giữ insufficient.

Mỗi kết luận hỗ trợ/phản bác cần trích nguyên văn xuất hiện duy nhất trong
chunk của Evidence Pack. Offset và source span được giải từ chunk gốc bằng
code, không nhận tọa độ model tự tạo. Các proof được kiểm lại ở runtime
contract, cùng requirement counts, phép tổng hợp nhãn, điểm và cờ review.

Rubric/report không được cấp quyền thay system prompt. Chỉ gọi endpoint
loopback đã cho phép; không proxy, redirect, model cloud hoặc tự tải model.
Digest được kiểm trước/sau inference; prompt, schema, policy, request và
response có hash/provenance. Metadata không chứa nguyên văn prompt riêng tư.

JSON sai, thiếu requirement, quote sai/lặp, digest đổi, model thiếu, timeout
hoặc vượt context/output budget đều trả CANNOT_ASSESS có mã lý do. Không
tự chuyển về V4 sau một lần gọi LLM lỗi. Budget đầu vào dùng UTF-8 bytes
bảo thủ cộng phần dự phòng template/generation; không cắt passage ngầm để
đưa vừa context. Token telemetry của runtime được lưu và kiểm thêm.

Mọi CANNOT_ASSESS vẫn giữ điểm tiêu chí liên quan và tổng ở `null`. Khi đủ
căn cứ, code có thể tạo điểm đề xuất theo rule cũ; trạng thái review của
ứng dụng vẫn cần giảng viên quyết định trước công bố. Kiểm được quote/offset
không chứng minh model đã suy luận đúng ý nghĩa.

## Tích hợp và kiểm tra đã thực hiện

- Module `research/core_mvp/llm_assessment.py`; core runner và Mongo bounded
  worker chỉ load khi chạy P2 và bật chính sách LLM.
- API/index config registry, OpenAPI và web có profile mới riêng.
- Migration `008-local-llm-assessment-profile-v1` chỉ thêm enum profile,
  từ commit sạch `bdf3f95ae17eb4a3cfa46e7c705deeb21d686f3d`; không sửa
  checksum của migration 001–007.
- Bộ tests research/backend: **1.093 passed, 21 skipped** trong lượt
  03/11. Các ca cần hạ tầng tích hợp riêng không được coi là đã chạy.
- Smoke đầu tiên bằng Qwen thật: cả năm ca tổng hợp đáp ứng kỳ vọng. Ca
  diễn đạt khác phrase chuyển V4 CANNOT_ASSESS → LLM MET có quote hợp lệ;
  phản chứng trực tiếp → UNMET; thiếu nội dung và chỉ có kế hoạch →
  CANNOT_ASSESS; ca nhúng chỉ thị trong report không được thưởng MET.
- Khi lặp lại đã ghi nhận timeout, áp lực swap và mặc định host prompt cache
  tối đa 8 GiB của runtime. Sau khi restart riêng service và tắt cache này,
  lượt `smoke-v4` có 6/6 phản hồi model qua kiểm tra schema/proof, khoảng
  6–18 giây/mục trong lượt đo đó. Không suy thời gian này thành latency
  trung bình của báo cáo thật hoặc kết luận nhân quả về cache.
- Lượt cuối khớp kỳ vọng nhãn ở **5/6 ca tự soạn**. Ca yêu cầu TLS 1.3 nhưng
  báo cáo chỉ dùng TLS 1.2 vẫn bị model trả CANNOT_ASSESS, thay vì UNMET kỳ
  vọng. Giữ đây là lỗi từ chối quá thận trọng; script trả exit code 1 cho
  lượt này, không sửa nhãn hoặc che thất bại để báo toàn bộ đã đạt.
- Đã chạy browser thật qua upload/rubric/worker/export; lượt
  `6ae9b5389aad691de5f26ec8` có MET, proof hợp lệ và điểm đề xuất 10/10 trên
  báo cáo tổng hợp tự viết, trạng thái giảng viên vẫn UNREVIEWED. Đã sửa và
  kiểm lại phần diễn giải UI để nhãn LLM không đi cùng thông báo thiếu
  bằng chứng của V4; build và 6 browser contract tests đạt.

Lượt chạy và so V4/LLM tại
`var/quality/p2-llm-2026-11-03/smoke-v1/` đến `smoke-v4/`, có input, cấu
hình, output, manifest và summary; các lượt timeout/không khớp cũng giữ
nguyên. Case phiên bản được làm rõ statement/description ở lượt v3, nên
không so v2/v3 như một ablation chỉ thay runtime. Prompt/schema mới được
ghi bằng phiên bản và checksum riêng. Browser artifacts nằm trong
`var/quality/p2-llm-2026-11-03/web-v1/`. Tái lập trên thư mục mới:

```bash
.venv-research/bin/python scripts/smoke_p2_llm.py \
  --output-dir var/quality/p2-llm-2026-11-03/smoke-new-run
```

Đây là ca kỹ thuật do tác giả soạn, chưa phải gold người gán độc lập, độ
chính xác chấm SEFORA hoặc thực nghiệm chất lượng P2 cho bài báo. Lượt này
không mở PAN TEST0 và không thay số liệu lịch sử. Bước đo tiếp theo cần
khóa reference, cấu hình và phạm vi rubric phù hợp trước khi so sánh.
