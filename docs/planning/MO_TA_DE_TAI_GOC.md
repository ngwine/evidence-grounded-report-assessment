# Mô tả đề tài gốc do người phụ trách cung cấp

Nguồn: tệp mô tả được người phụ trách gửi lại ngày 08/11/2026, kèm chỉ đạo
**giữ nguyên phạm vi đã đăng ký và triển khai cho đủ phạm vi**. Phần nội dung
bên dưới giữ nguyên nội dung, chỉ bỏ khoảng trắng cuối dòng khi lưu Git;
không tự điền hai ô tên đề tài đang để trống.
Tên hệ thống trong các tài liệu hiện có không được tự đổi theo một phạm vi hẹp hơn.

Tài liệu đối chiếu và thứ tự thực hiện:
[Kế hoạch hoàn thành đúng phạm vi đề tài](KE_HOACH_HOAN_THANH_PHAM_VI_DE_TAI.md).

---

Tên đề tài VN
Tên đề tài EN
Mô tả chi tiết đề tài
1. Bối cảnh và lý do chọn đề tài
Trong bối cảnh giáo dục đại học hiện nay, việc kiểm tra đạo văn và đánh giá chất lượng báo cáo học thuật đòi hỏi giảng viên phải xem xét đồng thời nhiều khía cạnh phức tạp: từ mức độ sao chép nguyên văn hay diễn giải tinh vi từ các nguồn tài liệu có sẵn, cho đến tính logic, sự nhất quán trong cấu trúc lập luận và mức độ đáp ứng mục tiêu đề tài của sinh viên. Khi khối lượng báo cáo và cơ sở dữ liệu đối chứng ngày càng lớn, việc tìm kiếm nguồn, đối chiếu nội dung và trích xuất bằng chứng để minh bạch hóa các nhận xét đánh giá thường tiêu tốn rất nhiều thời gian nếu thực hiện thủ công. Thêm vào đó, các công cụ kiểm tra đạo văn truyền thống hiện nay thường chỉ dừng lại ở việc báo cáo tỷ lệ trùng lặp mà thiếu đi sự hỗ trợ chuyên sâu về mặt ngữ nghĩa và đánh giá logic học thuật.

Xuất phát từ thực tế đó, đề tài "Xây dựng hệ thống hỗ trợ kiểm tra tính tương đồng và đánh giá báo cáo học thuật dựa trên bằng chứng" được thực hiện nhằm xây dựng một giải pháp toàn diện. Hệ thống kết hợp giữa các kỹ thuật truy xuất thông tin hiện đại (Information Retrieval), mô hình ngôn ngữ cục bộ (Local AI) và biểu diễn tri thức dạng đồ thị để tự động tìm kiếm nguồn đối chứng, phân rã tiêu chí đánh giá và cung cấp hệ thống bằng chứng xác thực (evidence-grounded rationale). Đặc biệt, hệ thống được thiết kế theo nguyên lý Human-in-the-loop, trong đó AI đóng vai trò là trợ lý phân tích, đề xuất và minh chứng, còn giảng viên luôn giữ vai trò trung tâm trong việc xem xét và đưa ra quyết định đánh giá cuối cùng.

2. Mục tiêu đề tài
Hệ thống hỗ trợ xử lý báo cáo tiếng Việt và tiếng Anh ở định dạng PDF hoặc DOCX, tự động bóc tách cấu trúc và tổ chức nội dung theo chương, mục, đoạn văn và vị trí trong tài liệu để phục vụ truy xuất, đối chứng và đánh giá.

Trên dữ liệu đã xử lý, hệ thống tập trung vào hai nhiệm vụ chính:

Kiểm tra nội dung tương đồng: truy xuất các tài liệu và đoạn văn có khả năng liên quan, kết hợp tìm kiếm từ vựng và ngữ nghĩa, xếp hạng lại các nguồn ứng viên và xác định các trường hợp tương đồng như sao chép gần nguyên văn, diễn giải lại hoặc tóm tắt.
Phân tích và đánh giá báo cáo dựa trên bằng chứng: sử dụng rubric của giảng viên kết hợp bằng chứng được truy xuất từ báo cáo, kho tài liệu nguồn và các quan hệ tri thức để xác định mức độ đáp ứng từng tiêu chí, phát hiện những vấn đề cần kiểm tra và đề xuất rationale cùng mức đánh giá phù hợp.
Trong quá trình phân tích, hệ thống có thể bổ sung các cảnh báo như dấu hiệu nội dung được tạo bởi AI, sự bất thường về phong cách viết, nội dung thiếu bằng chứng hoặc chưa nhất quán. Các cảnh báo này chỉ là thông tin hỗ trợ và không được sử dụng độc lập để kết luận hành vi gian lận hoặc tự động quyết định điểm số.

Từ những vấn đề và bằng chứng đã phát hiện, hệ thống có thể sinh các câu hỏi có mục tiêu nhằm hỗ trợ giảng viên kiểm tra mức độ hiểu và khả năng bảo vệ nội dung của sinh viên.

3. Chức năng chính
Các chức năng của hệ thống được tổ chức thành bốn nhóm chính:

3.1 Xử lý và quản lý báo cáo
Quản lý người dùng, báo cáo và kho tài liệu nguồn.
Upload và xử lý báo cáo PDF/DOCX.
Nhận diện chương, mục, đoạn văn, trích dẫn và vị trí nội dung trong tài liệu.
Chuẩn hóa nội dung và lập chỉ mục phục vụ tìm kiếm từ khóa và tìm kiếm ngữ nghĩa.
Lưu trữ thông tin vị trí của từng đoạn để kết quả phân tích có thể truy vết trở lại báo cáo gốc.
3.2 Kiểm tra nội dung tương đồng
Truy xuất các tài liệu và đoạn nguồn có khả năng tương đồng bằng phương pháp tìm kiếm từ vựng và ngữ nghĩa.
Kết hợp và xếp hạng các nguồn ứng viên.
Phân tích chi tiết các ứng viên có độ liên quan cao.
Phân biệt các trường hợp sao chép gần nguyên văn, diễn giải lại, tóm tắt hoặc không có mức tương đồng đáng kể.
Tổng hợp kết quả từ cấp đoạn lên cấp tài liệu.
Hiển thị Similarity Report gồm tỷ lệ tương đồng, đoạn nghi vấn, vị trí, loại tương đồng và tài liệu nguồn để giảng viên kiểm tra.
3.3 Phân tích và đánh giá báo cáo dựa trên rubric và bằng chứng
Cho phép giảng viên định nghĩa rubric theo mẫu chuẩn gồm tiêu chí, checklist, trọng số, mức đánh giá và quy tắc quyết định.
Chuyển rubric thành cấu trúc có thể sử dụng trong quá trình truy xuất và kiểm chứng.
Phân loại checklist thành các tiêu chí có thể đánh giá cục bộ và các tiêu chí cần đối chiếu nhiều phần.
Truy xuất bằng chứng liên quan từ báo cáo và kho dữ liệu.
Phân tích các quan hệ giữa claim, concept, phương pháp, kết quả, kết luận và evidence đối với các tiêu chí cần suy luận liên kết.
Xác minh từng checklist ở một trong ba trạng thái MET, UNMET hoặc CANNOT_ASSESS.
Sinh rationale giải thích kết quả và liên kết rationale với bằng chứng cụ thể.
Đề xuất điểm dựa trên các quy tắc của rubric thay vì để mô hình ngôn ngữ trực tiếp quyết định điểm.
Cảnh báo các trường hợp thiếu bằng chứng, nội dung không nhất quán hoặc cần giảng viên kiểm tra thêm.
Có thể bổ sung cảnh báo về dấu hiệu nội dung được tạo bởi AI như một tín hiệu hỗ trợ.
3.4 Hỗ trợ giảng viên kiểm tra và tổng hợp kết quả
Sinh câu hỏi vấn đáp dựa trên vấn đề, evidence và tiêu chí rubric liên quan.
Cho phép giảng viên chấp nhận, chỉnh sửa hoặc loại bỏ các nhận xét và điểm số đề xuất.
Ghi nhận các điều chỉnh của giảng viên dưới dạng Feedback Log phục vụ phân tích sai số, đánh giá thực nghiệm và xây dựng dữ liệu cải tiến hệ thống về sau.
Tổng hợp kết quả thành báo cáo hỗ trợ đánh giá.
4. Kiến trúc xử lý
Mỗi báo cáo sau khi được tải lên sẽ trải qua pipeline xử lý tổng quát:

Upload Report
→ Document Parsing
→ Structure-aware Chunking
→ Indexing
→ Retrieval & Analysis
→ Evidence Verification
→ Lecturer Review
→ Final Report

Trong đó, giai đoạn Document Parsing và Structure-aware Chunking chịu trách nhiệm bóc tách tài liệu thành các đơn vị có thể truy xuất như chương, mục, đoạn văn và câu, đồng thời duy trì thông tin vị trí trong tài liệu gốc. Nội dung sau đó được lập chỉ mục phục vụ cả tìm kiếm từ khóa và tìm kiếm ngữ nghĩa.

Trên nền dữ liệu chung này, hệ thống triển khai hai pipeline phân tích chính.

4.1 Pipeline 1 – Phát hiện và truy xuất nội dung tương đồng
Pipeline sử dụng chiến lược Hybrid Retrieval, kết hợp tìm kiếm từ vựng và tìm kiếm ngữ nghĩa ngay từ bước truy xuất ứng viên:

Report Passage
→ BM25 Retrieval + Dense Vector Retrieval
→ Reciprocal Rank Fusion (RRF)
→ Top-K Candidates
→ Cross-Encoder Re-ranking
→ Similarity / Plagiarism Classification
→ Document-level Aggregation
→ Similarity Report

BM25 được sử dụng để tìm các đoạn có mức độ trùng khớp từ vựng cao, phù hợp với những trường hợp sao chép gần nguyên văn. Song song đó, Dense Vector Retrieval sử dụng embedding để bổ sung khả năng tìm kiếm các đoạn có nội dung gần nhau về mặt ngữ nghĩa nhưng ít trùng khớp từ vựng.

Kết quả từ hai luồng retrieval được hợp nhất bằng Reciprocal Rank Fusion (RRF) nhằm tạo tập ứng viên chung. Các ứng viên sau đó được xếp hạng lại bằng Cross-Encoder hoặc mô hình reranker tương đương để tăng chất lượng xếp hạng trước khi thực hiện phân tích chi tiết.

Trên tập ứng viên có độ liên quan cao, hệ thống xác định các dạng tương đồng:

Sao chép gần nguyên văn;
Diễn giải lại;
Tóm tắt;
Không có mức tương đồng đáng kể.
Các đoạn tương đồng sau đó được tổng hợp ở cấp tài liệu để tạo Similarity Report gồm tỷ lệ tương đồng, vị trí đoạn liên quan, loại tương đồng và nguồn đối chứng.

Tỷ lệ tương đồng không được xem đồng nghĩa với tỷ lệ đạo văn. Hệ thống cung cấp bằng chứng và nguồn đối chứng để giảng viên đưa ra kết luận.

4.2 Pipeline 2 – Phân tích và đánh giá báo cáo dựa trên bằng chứng
Pipeline đánh giá bắt đầu bằng Template-based Rubric Definition nhằm chuẩn hóa đầu vào rubric trước khi thực hiện phân tích:

Template-based Rubric Definition

→ Rubric Compiler
→ Checklist Classification: LOCAL / GRAPH
→ Evidence Retrieval
→ Evidence Verification
→ MET / UNMET / CANNOT_ASSESS
→ Evidence-grounded Rationale
→ Deterministic Decision Rules
→ Proposed Score
→ Lecturer Review
→ Feedback Log

Rubric được chuẩn hóa theo cấu trúc gồm tiêu chí, checklist, yêu cầu bằng chứng, mức đánh giá, trọng số và quy tắc quyết định. Rubric Compiler chuyển các thông tin này thành các checklist có thể truy xuất và kiểm chứng.

Mỗi checklist được xác định thuộc một trong hai nhóm:

LOCAL: có thể đánh giá dựa trên một hoặc một số đoạn nội dung cụ thể.
GRAPH: cần đối chiếu thông tin và quan hệ giữa nhiều phần của báo cáo hoặc nhiều nguồn dữ liệu.
Đối với checklist LOCAL, hệ thống sử dụng Hybrid Retrieval kết hợp BM25, embedding và reranker để tìm các đoạn bằng chứng phù hợp.

Đối với checklist GRAPH, hệ thống biểu diễn các claim, concept, entity và quan hệ liên quan dưới dạng Evidence Graph. Phương pháp graph-based retrieval theo hướng HippoRAG-style được sử dụng để truy xuất các bằng chứng có quan hệ nhiều bước.

Các dạng quan hệ cần kiểm tra có thể bao gồm:

Mục tiêu có được giải quyết trong báo cáo hay không;
Phương pháp được mô tả có được áp dụng trong thực nghiệm hay không;
Kết quả có trả lời mục tiêu hoặc câu hỏi nghiên cứu hay không;
Kết luận có được hỗ trợ bởi kết quả hay không;
Các phát biểu quan trọng có phù hợp với dữ liệu hoặc tài liệu đối chứng hay không.
Trên tập evidence thu được, mô hình AI hỗ trợ xác minh checklist và tạo rationale. Mỗi checklist có một trong ba trạng thái:

MET: có đủ bằng chứng cho thấy yêu cầu được đáp ứng;
UNMET: bằng chứng cho thấy yêu cầu chưa được đáp ứng;
CANNOT_ASSESS: không có đủ bằng chứng để hệ thống đưa ra đánh giá đáng tin cậy.
Điểm đề xuất được suy ra bằng các decision rules được định nghĩa trong rubric thay vì để mô hình ngôn ngữ trực tiếp quyết định điểm. Nếu không đủ bằng chứng, hệ thống chuyển trường hợp tương ứng cho giảng viên đánh giá thủ công.

Mọi thay đổi của giảng viên đối với kết quả hệ thống được lưu trong Feedback Log để phục vụ phân tích sai số, đánh giá thực nghiệm và xây dựng dữ liệu cải tiến hệ thống trong các giai đoạn sau.

5. Trọng tâm nghiên cứu
Đề tài gồm hai hướng nghiên cứu chính và một hướng nghiên cứu bổ sung có quan hệ hỗ trợ lẫn nhau.

5.1 Hướng nghiên cứu chính 1 – Phát hiện và truy xuất nội dung tương đồng
Nghiên cứu kiến trúc phát hiện nội dung tương đồng nhiều tầng, trong đó Hybrid Retrieval được sử dụng để tăng khả năng tìm kiếm cả các trường hợp trùng khớp từ vựng và tương đồng ngữ nghĩa.

Các thành phần được khảo sát gồm:

  BM25 Retrieval;
 Dense Vector Retrieval;
Reciprocal Rank Fusion;
 Semantic Re-ranking;
Mô hình phân loại các dạng tương đồng;
Phương pháp tổng hợp similarity từ cấp đoạn lên cấp tài liệu.
Nhóm tiến hành đánh giá ảnh hưởng của từng tầng retrieval và re-ranking đến khả năng tìm đúng nguồn và phát hiện các trường hợp sao chép gần nguyên văn, diễn giải lại và tóm tắt.

Kết quả của hướng nghiên cứu này đồng thời có thể cung cấp thêm evidence cho quá trình đánh giá báo cáo ở hướng nghiên cứu thứ hai.

5.2 Hướng nghiên cứu chính 2 – Đánh giá báo cáo dựa trên bằng chứng và quan hệ tri thức
Nghiên cứu phương pháp chuyển rubric thành các checklist có thể kiểm chứng và lựa chọn chiến lược truy xuất evidence phù hợp với từng loại checklist.

Hai chiến lược retrieval được khảo sát:

 Local Evidence Retrieval: sử dụng Hybrid Retrieval và reranker cho các vấn đề có bằng chứng cục bộ.
Graph-based Evidence Retrieval: sử dụng đồ thị biểu diễn claim, concept, entity và relation để truy xuất các bằng chứng có quan hệ nhiều bước.
Trên tập evidence thu được, hệ thống nghiên cứu phương pháp:

Xác minh claim và evidence;
Phát hiện nội dung thiếu bằng chứng;
Phát hiện sự không nhất quán giữa mục tiêu, phương pháp, kết quả và kết luận;
Xác định checklist ở trạng thái MET, UNMET hoặc CANNOT_ASSESS;
Tạo rationale bám sát evidence;
Suy ra mức đánh giá bằng các decision rules của rubric.
Các kết quả từ kiểm tra tương đồng và các cảnh báo hỗ trợ khác có thể được sử dụng như nguồn thông tin bổ sung cho quá trình đánh giá khi phù hợp với tiêu chí rubric.

5.3 Hướng nghiên cứu bổ sung – Sinh câu hỏi có mục tiêu dựa trên vấn đề được phát hiện
Hướng nghiên cứu này sử dụng đầu ra từ hai hướng nghiên cứu chính, bao gồm vấn đề được phát hiện, evidence, đoạn có mức độ tương đồng đáng chú ý và tiêu chí rubric liên quan để tạo các câu hỏi tập trung vào nội dung cần giảng viên kiểm tra thêm.

Câu hỏi có thể hướng đến:

Claim chưa có bằng chứng;
Kết luận chưa được hỗ trợ đầy đủ;
Lựa chọn phương pháp chưa được giải thích;
Nội dung có mức độ tương đồng cao;
Sự không nhất quán giữa các phần của báo cáo;
Các nội dung trọng tâm cần sinh viên giải thích hoặc bảo vệ.
Mỗi câu hỏi được liên kết với vấn đề hoặc evidence cụ thể để giảng viên có thể xem xét và chỉnh sửa trước khi sử dụng.

6. Đánh giá thực nghiệm
Đề tài sử dụng kết hợp benchmark công khai và dataset trong miền do nhóm xây dựng nhằm vừa so sánh với các nghiên cứu trước, vừa đánh giá khả năng hoạt động của hệ thống trên báo cáo sinh viên thực tế.

6.1. Phát hiện nội dung tương đồng
Các cấu hình được so sánh gồm:

BM25;
Dense Retrieval;
BM25 + Dense Retrieval + RRF;
BM25 + Dense Retrieval + RRF + Semantic Re-ranking;
Pipeline nhiều tầng hoàn chỉnh.
Các chỉ số đánh giá dự kiến gồm:

Recall@K;
MRR hoặc nDCG;
Precision;
Recall;
F1-score;
F1 theo từng loại tương đồng;
Thời gian truy xuất và xử lý.
Dataset trong miền dự kiến bao gồm các cặp đoạn văn được gán nhãn theo các nhóm như verbatim, paraphrase, summary và không tương đồng đáng kể.

6.2. Đánh giá báo cáo dựa trên bằng chứng
Dataset thực nghiệm được xây dựng từ báo cáo và rubric, trong đó các checklist được gán nhãn:

MET;
UNMET;
CANNOT_ASSESS;
kèm theo các đoạn evidence tương ứng khi có thể xác định.

Các cấu hình được so sánh gồm:

Mô hình ngôn ngữ không sử dụng retrieval;
Local Evidence Retrieval;
Kết hợp có chọn lọc Local và Graph-based Retrieval.
Các chỉ số đánh giá dự kiến gồm:

Evidence Recall@K;
Evidence Precision;
Độ chính xác của MET / UNMET / CANNOT_ASSESS;
Mức độ phù hợp giữa điểm đề xuất và đánh giá của giảng viên;
Tỷ lệ rationale được evidence hỗ trợ;
Tỷ lệ trường hợp không đủ bằng chứng được nhận biết chính xác.
Feedback Log của giảng viên được sử dụng cho phân tích sai số và đánh giá mức độ khác biệt giữa kết quả hệ thống và đánh giá thực tế.

6.3. Sinh câu hỏi

Câu hỏi được đánh giá theo:

Mức độ liên quan đến vấn đề cần kiểm tra;
Mức độ bám sát evidence;
Khả năng trả lời dựa trên báo cáo;
Mức độ hữu ích đối với giảng viên.
Trong quá trình thực nghiệm, các thông tin về môi trường triển khai như phần cứng, mô hình, phiên bản phần mềm, tham số retrieval, Top-K và cấu hình inference được ghi nhận để bảo đảm khả năng tái lập kết quả.

7.Sản phẩm dự kiến
Sản phẩm của đề tài là một ứng dụng Web hỗ trợ giảng viên kiểm tra tính tương đồng và đánh giá báo cáo sinh viên dựa trên bằng chứng, trong đó các kết quả do AI tạo ra đều có khả năng truy vết và được giảng viên xem xét trước khi sử dụng.
Các thành phần sản phẩm được tổ chức theo các lớp:
Document Processing Layer: xử lý PDF/DOCX, nhận diện cấu trúc, phân đoạn và lập chỉ mục nội dung.
Similarity Analysis Layer: Hybrid Retrieval, RRF, semantic re-ranking, phân loại dạng tương đồng và Similarity Report.
Evidence-based Assessment Layer: Template-based Rubric, Rubric Compiler, Local/Graph Evidence Retrieval, checklist verification, evidence-grounded rationale và deterministic scoring.
Lecturer Support Layer: cảnh báo hỗ trợ, sinh câu hỏi có mục tiêu, Lecturer Review, Feedback Log và báo cáo tổng hợp.
Experimental Artifacts: dataset trong miền, benchmark, cấu hình thực nghiệm và báo cáo phân tích kết quả.
