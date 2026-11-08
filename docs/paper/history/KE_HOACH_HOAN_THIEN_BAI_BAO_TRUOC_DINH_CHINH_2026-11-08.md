> Bản lưu lịch sử trước khi đính chính kế hoạch ngày 08/11/2026.
> Các đề xuất thu hẹp bài vào P1 hoặc hoãn GRAPH/câu hỏi trong bản này đã
> được thay thế. Xem [kế hoạch hiện hành](../KE_HOACH_HOAN_THIEN_BAI_BAO.md).

# Ưu tiên hoàn thiện bài báo để nộp khoa

Kế hoạch thực hiện chi tiết theo năm nhận xét phản biện nằm tại
[Kế hoạch xử lý phản biện](../KE_HOACH_XU_LY_PHAN_BIEN.md). Ưu tiên hoàn thành
bản sửa bằng output hiện có, rồi bổ sung baseline/cohort/đối chứng mới theo
protocol riêng. Các đoạn ngày trước bên dưới giữ lịch sử quyết định.

Cập nhật 03/11/2026. Đầu ra trước mắt là bản bài báo hoàn chỉnh gửi khoa/GVHD.
Dùng bản tiếng Anh và mẫu LNCS hiện có; không cần chờ xác định hội nghị hay
tạp chí mới tiếp tục. Tài liệu này không đặt ngày hạn mới.

**Cập nhật 07/11:** đã hoàn thành
[P2 trên 15 bài/45 mục tham chiếu của Yến](../../benchmarks/sefora-p2-single-reference-result-2026-11-07.md).
Một bước khớp 37/45, hai bước 32/45, baseline luôn MET 42/45; không có lỗi
kỹ thuật. Bộ nhãn do một người có Claude hỗ trợ tạo, theo lựa chọn của
người phụ trách. Kết quả dùng cho phân tích thăm dò/điểm nghẽn, chưa chứng
minh hai bước cải thiện chất lượng; chưa bổ sung thành bảng hiệu quả P2
trong bản thảo. Không cần chờ phiếu thứ hai cho thiết kế hiện tại.

## Hướng làm

Giữ câu chuyện chính của bản thảo: **truy xuất nguồn và phân tích ảnh hưởng
của reranking trong Pipeline 1**, đặt trong kiến trúc hệ thống hai pipeline.
Pipeline 2 được mô tả là prototype đã chạy được, kèm đúng giới hạn hiện tại.
Không chờ hoàn thành semantic classifier, semantic assessment và Evidence
Graph mới hoàn tất bản bài báo.

Thực nghiệm QASPER đã được bổ sung vào bản thảo gửi khoa ở §4.6 và
§5.6/Table 10 như một phép đo **truy xuất đoạn bằng chứng trong cùng paper**,
tách khỏi các bảng PAN. Lượt xác nhận từ code sạch `9b9721d` tái hiện metrics
cũ trên 646/1.005 câu DEV, với 359 câu loại theo quy tắc ánh xạ paragraph.
[Báo cáo QASPER](../../benchmarks/qasper-v03-local-evidence-dev-result.md) giữ
provenance, định nghĩa metric và giới hạn. Runner chỉ gọi các retriever dùng
chung với P2; không gọi đầy đủ LOCAL assessment, verifier hay scoring.

Ngày 02/11 đã [nhận và đối chiếu hai phiếu SEFORA](../../benchmarks/sefora-p2-return-review-2026-11-02.md),
mỗi phiếu 60 mục theo 6 tiêu chí rộng của 10 bài cùng rubric. Có 35 mục cùng
nhãn khi cả hai đã quyết định và 25 UNSURE ở phiếu Yến; mapping và phân xử
bằng chứng còn mở. Phiếu Quý ghi AI-assisted review; người dùng xác nhận hai
người chưa xem nhãn nhau hoặc dự đoán P2 trước khi lưu phiếu riêng. Những
quyết định do AI bổ sung phải được ghi riêng, không tự trở thành quyết định
cuối của Quý/Yến hoặc gold độc lập. Chưa có kết quả chấm SEFORA bằng model
được bổ sung vào bài. Giữ bộ hiện có để rà soát theo tiêu chí gốc; chỉ đổi
sang checklist con khi phạm vi và nhãn tương ứng được thống nhất.

Đợt [cải thiện đầu ra ứng dụng ngày 29/10](../../benchmarks/output-quality-development-2026-10-29.md)
đã bổ sung P1 NLI theo span và P2 V4. Các ca do trợ lý soạn chỉ phục vụ phát
triển, chưa có nhãn độc lập; không đưa số liệu này vào các bảng PAN của bài.
Giữ riêng challenge đầu tiên ở `7aa249f` với cohort citation sau ở `a2a3d885`:
cohort sau vẫn khớp 8/16 trước và sau sửa guard, chưa có cải thiện.

Bản hiện có đã đủ tám phần, các bảng DEV0 và phân tích sai số. Việc cần làm
trước là sửa các phát biểu lỗi thời, kiểm lại số liệu và đóng thành bản đọc
được từ đầu đến cuối. Thực nghiệm mới làm song song để bổ sung bằng chứng,
không để bản thảo tiếp tục nằm chờ vì mở rộng phạm vi.

## Nếu bổ sung verifier LLM cho P2

Ngày 03/11 đã triển khai
[chế độ verifier LLM local](../../architecture/p2-local-llm-verifier.md) với
profile Qwen3.5 4B riêng và đã chạy smoke kỹ thuật bằng model thật. Chưa có
thực nghiệm chất lượng P2 trên reference/gold độc lập. Các ca tổng hợp mới
không được thêm thành bảng độ chính xác SEFORA. Bản thảo chính mô tả đúng
snapshot V4 và các component experiment đã chạy; khi bổ sung methods/results
mới, dùng đúng mức chứng cứ hiện có và giữ nguyên số liệu PAN/QASPER.

| Phần bản thảo | Cách sửa khi có implementation và kết quả tương ứng |
|---|---|
| §3.3 Pipeline 2 | Giữ V4 làm baseline; mô tả biến thể verifier LLM đọc yêu cầu và Evidence Pack, xuất ba trạng thái cùng evidence ID/giải thích, kiểm schema/provenance và giữ scoring bằng code. |
| §4.7 mới — thiết kế đánh giá P2 | Khóa phiên bản rubric, nhãn tham chiếu, model/prompt/config và dữ liệu trước khi xem dự đoán. So trên cùng yêu cầu và cùng evidence để tách ảnh hưởng verifier khỏi retrieval. Chỉ so baseline trên những yêu cầu mà nó biểu diễn được; nếu không hỗ trợ thì báo đúng giới hạn, không dựng phrase đơn giản để đại diện cho chất lượng lập luận. |
| §5.7 mới — kết quả P2 | Bảng riêng cho nhãn, lỗi MET khi thiếu căn cứ, evidence, khả năng từ chối, lỗi output/schema và thời gian/tài nguyên. Mỗi số phải truy về output thực; chưa có run thì chưa điền bảng. |
| Abstract/Introduction/RQs | Chỉ bổ sung câu hỏi và đóng góp về P2 khi đã có đánh giá đúng phạm vi. Giữ các RQ và đóng góp PAN/QASPER hiện tại; tên model mới không tự tạo đóng góp. |
| Discussion/Limitations/Conclusion | Diễn giải đúng mức cải thiện hoặc kết quả âm; nêu giới hạn của rubric, ảnh/bài nguồn thiếu và bộ tham chiếu có AI hỗ trợ. |
| Related Work/References/hình | Bổ sung nguồn model và semantic verification đã thực sự dùng; đồng bộ sơ đồ, Markdown và DOCX sau khi phương pháp được chốt. |

Giữ nguyên các bảng PAN DEV0/DEV1 và QASPER, checkpoint và artifact của chúng.
Thử embedding mới cho P1 là thí nghiệm riêng; nếu thực hiện thì chạy lại và
thêm bảng đối chứng mới, không thay tên model trên số cũ.

Với SEFORA hiện tại, 60 dòng là 6 tiêu chí rộng trên **10 bài**, không phải
60 quan sát độc lập hay gold checklist nguyên tử. Nếu dùng tham chiếu do AI
phân xử chưa được người xác nhận thì báo như một diagnostic thăm dò có AI
hỗ trợ; không dùng để khẳng định chất lượng chấm rubric theo người. Một kết
quả P2 mạnh hơn cần bộ nhãn cuối có nguồn gốc rõ, được người kiểm xác nhận
trước dự đoán của model đang đánh giá. Không dùng chính model được kiểm để
sinh đáp án rồi coi phép so đó là kiểm chứng độc lập.

## Thứ tự thực hiện

| Ưu tiên | Phụ trách đề xuất | Đầu ra cụ thể | Kết quả cần đạt |
|---|---|---|---|
| 1 — làm trước | Q + Y | Một đoạn mô tả vấn đề, phạm vi, RQs và đóng góp thống nhất với số liệu đang có | Người đọc biết nghiên cứu chính kiểm tra source retrieval/reranking, còn QASPER kiểm truy xuất đoạn trong cùng paper; phân biệt phần hệ thống đã chạy và phần được đánh giá thực nghiệm. Giữ kết quả âm của Cross-Encoder đúng như artifact. |
| 2 — ra bản hoàn chỉnh sớm | Y sửa nội dung; Q đối chiếu code | Bản Markdown đã sửa abstract, framework, compiler, scoring và conclusion | P2 được mô tả đúng là prototype; checklist do người soạn khai báo; mọi mục chưa đánh giá được giữ điểm liên quan và tổng ở null. Title–abstract–method–results–conclusion cùng một phạm vi. |
| 3 — song song với viết | Q kiểm số; Y kiểm bảng/diễn giải | Bảng claim → artifact, các bảng/hình tái tạo từ metrics/predictions, audit cập nhật | DEV0 giữ nguyên; 30 parent/320 windows không bị tính thành 320 quan sát độc lập. Mỗi con số có nguồn và checksum; timing có suspended interval không dùng làm latency end-to-end. |
| 4 — tăng độ chắc của kết quả | Q chuẩn bị runner/dữ liệu; Y kiểm chéo, người phụ trách xác nhận pack | DEV1/TEST0 tái tạo từ code sạch, manifest và protocol một thí nghiệm bổ sung nhỏ | Hai pack v2 đã tái tạo, kiểm không trùng dữ liệu và được Quý duyệt cho mục đích nội bộ; pack cũ giữ nguyên. DEV1 đã chạy và qua audit; TEST0 giữ kín tới khi khóa cấu hình cuối. |
| 5 — đã có đối chứng đầu tiên | Q chạy; Y kiểm bảng và phân tích | Bảng A5/A6 trên DEV1, uncertainty và audit đầu vào thực chấm | Đã chạy chính sách đầu vào ngắn trên cùng candidate pool/checkpoint/rerank budget/aggregation, không dùng gold để chọn đoạn. Truncation bổ sung giảm về 0 nhưng chưa cải thiện Recall@10; giữ kết quả âm trong bài. Cần đọc chéo trước khi chốt đánh giá TEST0. |
| 6 — đóng bản gửi khoa | Y định dạng; Q tái lập và kiểm kỹ thuật; cả hai đọc chéo | Markdown nguồn, DOCX, PDF, hình/bảng/references đồng bộ và ghi chú kết quả còn thiếu | Bản đọc liền mạch, số liệu nhất quán, hình/bảng không vỡ, ký hiệu/thuật ngữ thống nhất; có bản đầy đủ để khoa/GVHD góp ý. Nếu thực nghiệm bổ sung chưa xong, ghi đúng mức diagnostic hiện có, không tự nâng claim. |

Phân công này là đề xuất theo thế mạnh hiện tại: Quý tập trung số liệu,
runner và khả năng tái lập; Yến tập trung mạch bài, related work, diễn giải,
references và định dạng. Cả hai kiểm chéo, cùng đọc bản hoàn chỉnh.

## Bản làm việc đã cập nhật

Trong lượt rà ngày 28/10, đã sửa các mô tả lỗi thời về prototype P2, compiler,
MongoDB, review và cách xử lý điểm chưa xác định trong bản Markdown; đồng bộ
sơ đồ kiến trúc. Sau khi DEV1 hoàn tất, đã thêm phương pháp/kết quả và cập nhật
abstract, discussion, limitations, conclusion; các bảng số liệu DEV0 và references
vẫn được giữ nguyên. DOCX đã sinh lại với 9 bảng số liệu/nội dung, 3 bảng bố trí
phương trình và 2 hình; kiểm tra cấu trúc và con số khớp Markdown. Audit cũng
đã cập nhật theo hiện trạng.

Ngày 01/11 bổ sung phương pháp QASPER §4.6, kết quả §5.6/Table 10 và đồng bộ
phạm vi ở abstract, introduction, discussion và conclusion. Các giá trị dùng
đúng aggregate đã tái hiện; không chạy thêm hoặc thay số liệu PAN. Bản Word
đã sinh lại và đối chiếu khớp 10 bảng nội dung, 3 bảng bố trí phương trình và
hai hình. Toàn bộ 18 ô metric QASPER khớp artifact gốc; kiểm tra phân trang
vẫn cần Word/Pages hoặc một trình render tương đương.

Việc tiếp theo là Q/Y đọc chéo bản đầy đủ đã bổ sung QASPER, xác nhận cách kể
contribution, kiểm references và xem kết quả DEV1 đã hoàn tất theo protocol/pack
đã khóa. Hồ sơ QASPER vẫn ghi `team_dataset_approval=NOT_RECORDED`; việc thêm
bảng vào bản thảo góp ý không tự tạo approval hoặc đóng gate đánh giá P2.
Bản DOCX chưa được kiểm tra phân trang trong Word/Pages hoặc xuất PDF ở lượt
này. Đây là bản để đọc và góp ý trước khi chốt bản nộp, chưa phải xác nhận đã
hoàn tất mọi kiểm chứng nghiên cứu và định dạng.

## Tiến độ thí nghiệm bổ sung

Đã thêm biến thể A6, config và protocol; giữ A5 làm đối chứng và khóa code
thí nghiệm vào commit riêng `2a8c073`. DEV1/TEST0 mới đã tái tạo, kiểm checksum,
kiểm không trùng nhóm dữ liệu và ghi quyết định xử lý pack. DEV1 đã hoàn tất
bằng mô hình thật và qua audit đối chứng/checksum. Recall@10 theo parent:
A5 77,29%, A6 73,84%; chênh lệch -3,46 điểm phần trăm, khoảng 95% từ -10,28
đến +3,69. A6 hết truncation bổ sung ở mô hình nhưng chưa cho thấy truy xuất
tốt hơn; không thay A5 bằng A6 như một cải tiến đã được chứng minh.
Đã thêm phương pháp §4.5, kết quả §5.5/Table 9 và cập nhật diễn giải trong bài;
TEST0 còn giữ kín. Xem [kết quả đối chứng](../../benchmarks/pan-pc-11-short-evidence-dev1-result.md)
và [biên bản chuẩn bị](../../benchmarks/pan-pc-11-short-evidence-dev1-readiness-2026-10-28.md).

## Những chỗ sửa ngay trong bản thảo

- **Abstract và Introduction:** P2 hiện đã có prototype backend/web; sửa câu
  chỉ có design specification. Giữ rõ nghiên cứu chính tập trung P1, bổ sung
  QASPER cho truy xuất đoạn bằng chứng; chưa tuyên bố hiệu quả chấm rubric P2.
- **Framework:** MongoDB/persistence đã có implementation. Compiler kiểm tra
  và chuẩn hóa authored checklist, chưa tự tách mọi rubric tự do.
- **Verification và scoring:** V4 vẫn là phrase/context rule, chưa phải mô
  hình suy luận ngữ nghĩa. Bất kỳ checklist `CANNOT_ASSESS` nào đều giữ điểm
  tiêu chí liên quan và tổng ở `null`, không chỉ khi quá ngưỡng số lượng.
- **Results và Discussion:** DEV0 là positive-only, oracle suspicious-span
  diagnostic. Giữ parent-balanced metrics, paired bootstrap và ba cơ chế lỗi
  như các giả thuyết cần kiểm soát, chưa gọi là kết luận nhân quả. QASPER giữ
  riêng denominator/metric và giới hạn DEV; không so trực tiếp tỷ lệ QASPER
  với PAN hoặc gọi 87,15% là độ chính xác đánh giá rubric.
- **Conclusion:** trả lời đúng ba RQ chính và mục tiêu truy xuất bằng chứng
  bổ sung trên QASPER; không dùng kết quả truy xuất để tuyên bố độ chính xác
  phát hiện đạo văn hoặc chấm rubric toàn hệ thống.
- **EXPERIMENT_AUDIT:** cập nhật trạng thái tích hợp và các pilot đã thử;
  tách prototype, diagnostic và thực nghiệm đủ điều kiện đưa số vào bài.

## Thực nghiệm bổ sung nên gọn đến mức nào?

Ưu tiên **một thay đổi có thể kiểm tra rõ**. DEV0 cho thấy 97,5% cặp chấm bằng
Cross-Encoder bị truncation, nên có cơ sở thử cách xây đầu vào evidence ngắn
hơn. Trên DEV1, giữ các baseline A1–A5 và chỉ thêm một biến thể của A5 để kiểm
tra giả thuyết này. Chốt trước cách chọn đoạn, ngân sách token/pair và metric.

Metric chính: **parent-balanced Recall@10**. Metric phụ: MRR@10, nDCG@10,
Recall@100, tỷ lệ truncation, paired bootstrap theo parent và tài nguyên đo
trong điều kiện cố định. DEV0 dùng chẩn đoán; không tiếp tục chọn tham số trên đó.

Nếu thay candidate gate hoặc số support passages, phải tách thành đối chứng
riêng. `quota_union` trong app hiện chưa phải tính năng sẵn có của offline
source-document runner dùng cho bài. Không coi chỉ đổi config app là đã có
một phép ablation paper tái lập được.

Với phạm vi truy xuất nguồn từ truy vấn có source đã biết, có thể ghi rõ
positive-only. Chỉ cần thêm negative/no-source cohort khi mở claim sang
precision, false positives hoặc rejection. Không mở task mới chỉ để làm bài
trông bao quát hơn.

## Những việc tạm xếp sau bài báo

- Chỉnh màu/nút và mở rộng giao diện demo.
- Docker hóa toàn bộ stack, đổi database hoặc vector engine.
- Hoàn thiện toàn bộ semantic classifier, P2 semantic verifier, graph claim/
  entity, OCR, highlight PDF và sinh câu hỏi trong cùng đợt viết bài.
- Chạy nhiều checkpoint, tuning tiếp DEV0 hoặc cố làm Hybrid luôn thắng.

Vẫn sửa lỗi thực sự chặn chạy, mất dữ liệu hoặc tính đúng của artifact.
Phần mềm demo và thay đổi hiện có được giữ lại; ưu tiên mới tập trung vào
những việc trực tiếp tạo bản bài báo và bằng chứng cho các claim của bài.

## Bản gửi khoa cần có

- Bản tiếng Anh đủ abstract, introduction, related work, method, experiment,
  results/discussion, limitations, conclusion và references.
- Bảng/hình có nguồn dữ liệu và diễn giải khớp con số; phân biệt chất lượng
  truy xuất, phân loại và đánh giá rubric.
- DOCX và PDF đọc được, theo mẫu hiện có; quy trình sinh bản Word được ghi lại.
- Ghi chú ngắn để khoa/GVHD góp ý vào contribution, phạm vi thực nghiệm và
  những giới hạn cần bổ sung.

Bộ LIP V3 khớp 6/10; V4 khớp 10/10 trên cùng bằng chứng đã lưu, với tổng
điểm vẫn ở `null`. Đây là case phát triển đã dùng để chẩn đoán và sửa rule;
không đưa các tỷ lệ đó thành độ chính xác nghiên cứu trong bảng kết quả chính.
QASPER nay được báo cáo như thực nghiệm thành phần truy xuất với phạm vi và
giới hạn nêu trên. MMDocIR vẫn là lượt exploratory chưa đưa vào Results;
LIP và các ca tự soạn cũng chưa được nâng thành bằng chứng hiệu quả chấm
rubric trên nhãn người độc lập.

## File làm việc

Cập nhật 05/11 trong lúc chờ hai phiếu 15 bài mới: đã chuẩn bị
[nhận Excel, evidence vắng mặt và đối chứng P2](../../benchmarks/p2-readiness-2026-11-05.md).
Phần phương pháp P2 trong Markdown/Word đã đồng bộ với verifier local hiện
có; phần thiết kế/kết quả thực nghiệm vẫn giữ nguyên. Đây là chuẩn bị công
cụ và mô tả triển khai, chưa đóng phần đánh giá chất lượng P2 trên nhãn mới.

- [Bản Markdown nguồn](../BaiBao_523H0087_52200229_EN.md)
- [Bản DOCX hiện có](../BaiBao_523H0087_52200229_EN_LNCS.docx)
- [Audit số liệu và giới hạn claim](../EXPERIMENT_AUDIT.md)
- [Script sinh Word](../../../scripts/generate_lncs_paper.py)
- [Ghi chú template](../TEMPLATE_NOTES.md)
- [DEV0 A1–A5](../../benchmarks/pan-pc-11-cross-encoder-ablation-dev0-result.md)
- [Bootstrap theo parent](../../benchmarks/pan-pc-11-parent-bootstrap-dev0-result.md)
- [Readiness DEV1/TEST0](../../../research/protocols/rq1-similarity/pan-pc-11-split-readiness.md)
