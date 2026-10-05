# Assessment datasets

## Pack bắt buộc: in-domain report–rubric

Kết quả end-to-end của RQ2 phải dùng report–rubric trong miền đã được duyệt,
không suy ra từ benchmark QA/fact verification công khai. Một version pilot cần
khóa tối thiểu:

- report ID/version/hash và bản đã ẩn danh;
- rubric ID/version cùng criterion/checklist/weight/level/decision rule;
- checklist nguyên tử và routing `LOCAL` hoặc `GRAPH`;
- nhãn `MET`, `UNMET` hoặc `CANNOT_ASSESS`;
- quan hệ claim–evidence `SUPPORTED`, `CONTRADICTED` hoặc `INSUFFICIENT`;
- exact evidence span cùng document/version provenance;
- annotator vòng 1, cross-review, adjudicator và lý do đổi nhãn;
- consent/authority, allowed purpose, retention, approver/date và split theo
  report/source group để chống leakage.

Không commit report sinh viên, PII hay annotation nhạy cảm. Raw/derived data ở
`var/datasets/`; repository chỉ giữ schema, manifest và dữ liệu synthetic.

## Component benchmark bổ sung

| Dataset | Vai trò giới hạn | Không được dùng để tuyên bố |
| --- | --- | --- |
| MMDocIR | Long-document evidence retrieval | Chất lượng chấm report–rubric end-to-end |
| HoVer | Multi-hop/GRAPH verification | Mức phù hợp điểm với giảng viên |
| HARMOGEN-R | Rubric grading và human agreement | Evidence retrieval trên báo cáo của nhóm |

Mỗi nguồn vẫn cần data card riêng về license/access, checksum, official split,
allowed purpose và version trước khi index hoặc chạy experiment.
