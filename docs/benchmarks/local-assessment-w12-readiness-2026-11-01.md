# Kiểm tra LOCAL Assessment cho tuần 12 — 01/11/2026

## Phạm vi và kết luận

Theo [WBS mục 11](../planning/WBS_VA_PHAN_CONG.md#11-recovery-và-reforecast-v17--ưu-tiên-hoàn-thành-hai-pipeline),
tuần 12 của lịch thực thi hiện hành là `W10.1–W10.6`: LOCAL Assessment.
Các task mang mã `W12.1–W12.6` trong baseline về GRAPH/router được thực thi ở
cửa sổ W14. Bản kiểm tra này không đổi baseline, lịch sử hoặc trạng thái DONE.

Đường kỹ thuật rubric → checklist → LOCAL retrieval → Evidence Pack →
verification → scoring/report đã có. Lần kiểm tra này sửa thêm hai lỗ hổng
toàn vẹn bằng chứng. **G-05 vẫn OPEN**: chưa có pilot report–rubric được duyệt,
gán nhãn độc lập hai người, phân xử và đo metric đủ để nghiệm thu. QASPER
retrieval và kết quả LIP đã dùng phát triển không thay thế phần này.

## Đối chiếu từng task

| Task | Mã triển khai và bằng chứng hiện có | Phần còn cần hoàn thành |
|---|---|---|
| `W10.1` Orchestration/API | `research/core_mvp/runner.py`, `assessment.py`; `services/backend/src/kltn_ai/worker/bounded_pipeline.py`, `mongo_analysis_worker.py`; `services/backend/tests/test_mongo_analysis_flow.py` kiểm luồng hai pipeline, version, lưu/xuất và review. | Review/merge, nghiệm thu với rubric và báo cáo phù hợp; không dùng fixture để suy chất lượng chấm. |
| `W10.2` Evidence Pack/validator | `_validated_evidence_pack` giải hit về chunk gốc, kiểm report/version/duplicate/dangling và tọa độ; `contracts.py` kiểm proof liên kết Evidence Pack trước khi lưu/xuất. | Review thay đổi; kiểm trên các định dạng và tập dữ liệu đại diện. |
| `W10.3` Failure/authorization | Các test Mongo analysis kiểm thay đổi quyền trước/trong/sau lượt chạy, stale worker, tamper và idempotency; worker có giới hạn subprocess. `test_core_mvp_evidence_scope.py` có fixture chỉ thị trong report không được thay rubric. | Live Mongo rollback/restart/load acceptance chưa được chạy lại trong lượt này; fixture chỉ thị không phải đánh giá prompt injection đầy đủ hoặc chứng minh chống giả mạo nội dung. |
| `W10.4` Query/retrieval | `_query_for_checklist`, `_rank_local` dùng query, statement và yêu cầu đã biên dịch; BM25, Dense/RRF và reranking tùy cấu hình; output giữ query/method/config. | Đo evidence recall trên checklist thật đã khóa; QASPER dùng câu hỏi gốc chỉ là proxy retrieval. |
| `W10.5` Three-state verifier | `_verify`, `_score_criteria` dùng `SCOPED_PHRASE_CONTEXT_V4`; SUPPORTED/CONTRADICTED/INSUFFICIENT → MET/UNMET/CANNOT_ASSESS; bất kỳ checklist chưa đánh giá được đều giữ điểm criterion và tổng là null. | Đánh giá đúng/sai và abstention trên nhãn độc lập. Đây vẫn là authored phrase/context rules, chưa phải semantic entailment. |
| `W10.6` Pilot/gold | `research/gold_annotation`, `research/gold_evaluation` có workflow gán nhãn, agreement, adjudication, freeze và metric. Bộ chuẩn bị SEFORA có 10 bài/rubric, context/paragraph IDs và hai phiếu trống. | Con người chốt checklist, gán riêng, phân xử cả nhãn/bằng chứng; chuẩn hóa schema, split và hồ sơ pack trước lượt đánh giá. Chưa có kết quả model SEFORA trong bộ này. |

## Hai lỗi toàn vẹn được sửa

1. Source span đúng report/version nhưng nằm ngoài chunk, hoặc bỏ trống phần
   chữ của chunk, trước đây có thể vẫn cho ra `MET`. Validator nay yêu cầu
   tọa độ normalized là số nguyên trong giới hạn và hợp các span phủ mọi ký
   tự không phải khoảng trắng. Khoảng trắng nối các element vẫn được phép.
2. Runtime contract trước đây có thể nhận một kết luận `MET` sau khi xóa
   Evidence Pack và proof, hoặc không kiểm proof còn trỏ đúng pack. `MET` nay
   cần supporting span, `UNMET` cần contradiction span; proof được đối chiếu
   với ID/chunk/report/version và provenance của bằng chứng đã lấy.

`CANNOT_ASSESS` với Evidence Pack rỗng vẫn hợp lệ. Không thay yêu cầu rubric,
thuật toán retrieval, ngưỡng chấm hoặc nhãn tham chiếu để đạt kết quả mong muốn.
Kiểm tra toàn vẹn không chứng minh câu trích thực sự đáp ứng tiêu chí về ngữ nghĩa.

## Nhãn cần người thực hiện

Bộ riêng tại `var/paper/p2-preparation-2026-10-30/sefora/` hiện có 6 dòng
rubric mapping chưa chốt và 60 dòng nhãn trống cho mỗi người. Số item cuối
có thể thay đổi nếu tiêu chí cần tách; chưa dùng 60 dòng tạm làm gold.

1. Q/Y đọc rubric, thống nhất yêu cầu nguyên tử và khả năng kiểm từ phần text;
   cập nhật `rubric-mapping-review.csv`, tạo lại phiếu nếu cần tách tiêu chí.
2. Q điền `labels_quy.csv`, Y điền `labels_yen.csv` riêng trước khi xem phiếu
   nhau, điểm/nhận xét nguồn hoặc dự đoán model. Mỗi item cần nhãn, bằng chứng
   phù hợp hoặc lý do thiếu bằng chứng, và người gán thực tế.
3. Phân xử nhãn và span, chuẩn hóa context/checklist/schema, khóa split và
   hồ sơ pack; sau đó mới đo label metric và evidence recall.

ZIP gửi Y đã được khôi phục và kiểm tra byte giống gói trước: 160.418 byte,
48 file, đủ 10 bài; không có phiếu Q hoặc điểm/nhận xét giảng viên. Hướng dẫn
chi tiết trong `README_BAT_DAU.md` của ZIP và
[runbook QASPER/SEFORA](../demo/huong-dan-kiem-chung-p2-qasper-sefora.md).

## Kiểm tra kỹ thuật đã chạy

Trên working tree hiện tại ngày 01/11, **288 passed, 3 skipped** trong nhóm
kiểm tra dưới đây. Đây là regression/contract tests, không phải 288 nhãn gold
hoặc kết quả chất lượng P2. Các ca live Mongo yêu cầu cấu hình tích hợp không
được chạy trong lượt này. Không tải model hoặc chạy inference trên TEST0.

```bash
.venv-research/bin/python -m pytest -q \
  research/tests/test_core_mvp.py \
  research/tests/test_core_mvp_evidence_scope.py \
  research/tests/test_core_mvp_assessment_regression.py \
  research/tests/test_assessment_context_verification.py \
  research/tests/test_assessment_evidence_status.py \
  research/tests/test_assessment_proof_contract.py \
  research/tests/test_output_contracts.py \
  research/tests/test_json_schema_outputs.py \
  research/tests/test_gold_annotation_workflow.py \
  research/tests/test_gold_evaluation.py \
  services/backend/tests/test_mongo_analysis_flow.py \
  services/backend/tests/test_local_worker.py \
  services/backend/tests/test_rubric_lifecycle.py \
  services/backend/tests/test_semantic_analysis_profile.py
```

Thêm 41 ca regression cho hai lớp bảo vệ: 17 ca bounds/coverage trong
`test_core_mvp_evidence_scope.py` và 24 ca proof contract trong
`test_assessment_proof_contract.py`. Các kiểm tra gồm source span ngoài chunk,
thiếu tọa độ, vùng chữ không có provenance, khoảng trắng ghép element hợp lệ,
xóa proof/pack, đổi nguồn/phiên bản, offset sai, tham chiếu lồng và trường hợp
không đủ bằng chứng hợp lệ. Chưa có commit/review/merge cho thay đổi lần này;
kết quả tests không thay các điều kiện DoD hoặc quyết định G-05.
