# Chương 1. Giới thiệu đề tài

**Bản nháp để review — 22/10/2026.** Biên tập từ `Chương 1.docx` của nhóm
và phạm vi trong SRS/WBS hiện hành. Chưa ghi nhận GVHD duyệt nội dung này.

## 1.1. Bối cảnh và vấn đề nghiên cứu

Báo cáo học phần, tiểu luận và khóa luận thường được nộp dưới dạng PDF hoặc
DOCX. Khi xem một báo cáo, giảng viên cần vừa kiểm tra mức độ đáp ứng yêu cầu
môn học, vừa đối chiếu các nội dung có thể đã sử dụng lại từ tài liệu khác.
Hai công việc này liên quan đến cùng một tài liệu nhưng sử dụng căn cứ khác
nhau: kiểm tra tương đồng cần đoạn đối chứng, còn đánh giá cần rubric và bằng
chứng cho từng tiêu chí.

Một kết quả chỉ gồm điểm số hoặc tỷ lệ tương đồng chưa cho biết kết luận đến
từ đâu. Giảng viên cần mở được đoạn báo cáo, vị trí trang/mục, nguồn đối chứng
và phiên bản dữ liệu đã dùng. Với nội dung diễn giải lại, sự liên quan về chủ
đề cũng chưa đủ để khẳng định quan hệ sử dụng lại văn bản. Với chấm rubric,
không truy xuất được evidence chưa đủ để kết luận báo cáo không đạt tiêu chí.
Do đó, hệ thống cần lưu provenance và thể hiện sự chưa chắc chắn ngay trong
quy trình xử lý.

Các nghiên cứu liên quan cho thấy những thành phần có thể kế thừa. QASPER
xây dựng bài toán hỏi đáp trên bài báo có evidence hỗ trợ, phù hợp để tham
khảo cách đánh giá truy xuất bằng chứng trong tài liệu dài [1]. RMTS kết hợp
rationale theo từng trait với essay scoring, gợi ý cách tách nhận xét theo
rubric thay vì chỉ đưa ra một điểm tổng [2]. RAGChecker cung cấp các metric
chẩn đoán retrieval và generation riêng, phù hợp với yêu cầu xác định lỗi ở
từng bước của hệ thống [3]. Các công trình này chưa tự chứng minh chất lượng
của hệ thống đề xuất trên báo cáo sinh viên; việc đó cần dữ liệu và thực nghiệm
riêng của đề tài.

Từ nhu cầu trên, đề tài “Xây dựng hệ thống hỗ trợ kiểm tra đạo văn và đánh giá
báo cáo sinh viên dựa trên bằng chứng” tập trung xây dựng hai pipeline dùng
chung xử lý tài liệu và provenance. Kết quả được trình bày như đề xuất để
giảng viên kiểm tra, chỉnh sửa và quyết định.

## 1.2. Mục tiêu nghiên cứu

Mục tiêu tổng quát là xây dựng và đánh giá một hệ thống có thể truy xuất nội
dung đối chứng, phân tích báo cáo theo rubric và trình bày căn cứ cho từng
kết quả. Hệ thống ưu tiên chạy cục bộ, tái lập được các lượt thực nghiệm và
giữ quyền quyết định ở giảng viên.

Các mục tiêu cụ thể gồm:

1. Xử lý PDF/DOCX, bóc tách cấu trúc và tạo chunk có định danh ổn định, giữ
   raw–normalized mapping, trang/mục và span chính xác.
2. Kết hợp BM25 và Dense Retrieval để tạo tập nguồn ứng viên; thử nghiệm RRF
   và Cross-Encoder; đối chiếu passage và tổng hợp Similarity Report.
3. Biên dịch rubric thành checklist nguyên tử; truy xuất evidence theo từng
   checklist, xác minh mức đáp ứng và tổng hợp rationale/điểm theo rule rõ ràng.
4. Xây dựng Evidence Graph có version và provenance để thử nghiệm những tiêu
   chí cần kết nối nhiều phần của báo cáo.
5. Đánh giá chất lượng theo từng thành phần và end-to-end, gồm chất lượng
   truy xuất, nhãn tương đồng, evidence, kết quả rubric và chi phí xử lý.

## 1.3. Đối tượng, phạm vi và giới hạn

Đối tượng nghiên cứu là báo cáo sinh viên, rubric và kho tài liệu đối chứng
được cho phép sử dụng, cùng các phương pháp truy xuất thông tin, xử lý ngôn
ngữ và đánh giá có bằng chứng. Định dạng chính là PDF có lớp văn bản và DOCX,
với nội dung tiếng Việt hoặc tiếng Anh.

Pipeline 1 thực hiện truy xuất nguồn và phân tích tương đồng. Bốn nhãn mục
tiêu là `VERBATIM`, `PARAPHRASE`, `SUMMARY`, `NONE`. Retrieval score không được
dùng trực tiếp làm xác suất của bốn nhãn. Classifier/ngưỡng chỉ được chốt sau
khi có nhãn độc lập và đánh giá trên split phù hợp. Tỷ lệ tương đồng phản ánh
coverage theo công thức công bố, không đồng nghĩa với tỷ lệ đạo văn.

Pipeline 2 đánh giá theo rubric có version, với `MET`, `UNMET` và
`CANNOT_ASSESS`. Mỗi kết quả cần evidence và rationale truy vết được. Khi còn
tiêu chí không đủ căn cứ, hệ thống chuyển sang review và áp dụng rule xử lý
điểm đã khóa; không tự suy ra điểm tối đa từ các tiêu chí còn lại.

Kho nguồn ban đầu được nạp có kiểm soát. Web crawling, kiểm chứng DOI/tài liệu
tham khảo độc lập và AI-writing detector không thuộc baseline triển khai.
OCR/multimodal không phải điều kiện hoàn thành phiên bản đầu. Targeted
Questions là phần bổ sung có điều kiện sau khi hai pipeline chính đạt gate.
Giới hạn về quyền dữ liệu, quy mô gold data, ngôn ngữ và tài nguyên phần cứng
được ghi riêng trong báo cáo thực nghiệm.

## 1.4. Câu hỏi nghiên cứu

| Câu hỏi | Nội dung đánh giá | Bằng chứng cần thu thập |
|---|---|---|
| RQ1 | Hybrid retrieval, chunking và reranking hỗ trợ tìm nguồn/đoạn tương đồng đến mức nào so với baseline lexical/dense? | Recall@K, MRR/nDCG; ablation; span/class F1 khi đủ gold; latency/RAM |
| RQ2 | Quy trình rubric–checklist–evidence hỗ trợ đánh giá báo cáo với căn cứ kiểm tra được đến mức nào? | Evidence precision/recall; three-state agreement; score agreement; rationale support và abstention |
| RQ3 — bổ sung | Câu hỏi tạo từ evidence/issues có hữu ích cho giảng viên kiểm tra nội dung báo cáo không? | Grounding, relevance, answerability và lecturer review |

Mỗi RQ được đánh giá bằng protocol có split và cấu hình khóa trước evaluation.
Việc sử dụng kết hợp các kỹ thuật hiện có chưa đủ để khẳng định tính mới hoặc
hiệu quả; đóng góp cần được xác định từ thiết kế cụ thể và kết quả kiểm chứng.

## 1.5. Phương pháp nghiên cứu và đánh giá

Đề tài kết hợp khảo sát tài liệu, xây dựng hệ thống và thực nghiệm có kiểm
soát. Khảo sát xác định baseline và metric; thiết kế hệ thống xác định data
contract/provenance; các thử nghiệm nhỏ dùng để phát hiện lỗi trước khi khóa
cấu hình cho evaluation độc lập.

PAN-PC-11/PAN13 được tổ chức cho P1 retrieval/alignment. MMDocIR, HoVer và
HARMOGEN-R hỗ trợ kiểm tra các thành phần P2 theo nhiệm vụ của từng dataset.
Đánh giá toàn bộ P2 cần report–rubric in-domain. Mỗi frozen pack phải ghi
version, split, checksum, mục đích sử dụng và quyết định quyền dữ liệu.

Gold pilot được hai người gán nhãn riêng, sau đó xử lý bất đồng có evidence
cuối và người/ngày quyết định. Split được nhóm theo report/source để hạn chế
leakage; DEV0 dùng cho chẩn đoán, còn holdout giữ kín đến khi khóa phương pháp.
Các run lưu commit, config, seed, model revision, hardware và timing. Kết quả
âm hoặc trường hợp baseline tốt hơn phương pháp kết hợp vẫn được giữ lại.

## 1.6. Đóng góp dự kiến và ý nghĩa

Đầu ra dự kiến gồm một hệ thống tích hợp hai pipeline, cơ chế provenance dùng
chung, bộ protocol/dữ liệu gán nhãn được phép dùng và các thực nghiệm giúp
xác định lựa chọn kỹ thuật phù hợp. Đóng góp học thuật được đánh giá qua khả
năng truy xuất và hỗ trợ kết luận có căn cứ, đồng thời phân tích giới hạn của
hybrid/reranking/graph trên dữ liệu đã chọn.

Về ứng dụng, hệ thống cung cấp luồng kiểm tra từ kết quả trở về đúng đoạn
báo cáo và nguồn. Ý nghĩa này cần được kiểm tra bằng bài toán thực tế và
review của giảng viên; hiện chưa kết luận hệ thống đã giảm thời gian chấm
hoặc đạt độ chính xác đủ cho công bố điểm.

## 1.7. Bố cục luận văn dự kiến

Chương 1 giới thiệu vấn đề và phạm vi. Chương 2 trình bày cơ sở lý thuyết và
nghiên cứu liên quan. Chương 3 mô tả phương pháp, kiến trúc và hai pipeline.
Chương 4 trình bày triển khai, dữ liệu, protocol và kết quả thực nghiệm.
Chương 5 tổng kết đóng góp, hạn chế và hướng phát triển.

## Tài liệu tham khảo trong chương

1. Dasigi et al. (2021). [A Dataset of Information-Seeking Questions and Answers Anchored in Research Papers](https://aclanthology.org/2021.naacl-main.365/).
2. Chu et al. (2025). [Rationale Behind Essay Scores: Enhancing S-LLM’s Multi-Trait Essay Scoring with Rationale Generated by LLMs](https://aclanthology.org/2025.findings-naacl.322/).
3. Ru et al. (2024). [RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation](https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract.html).
