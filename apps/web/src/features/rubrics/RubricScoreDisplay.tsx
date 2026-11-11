import { useEffect, useState } from "react";
import type { EvidenceItem, RubricCriterionScore, RubricScoreResult } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { evidenceVerificationStateLabel, rubricChecklistOutcomeLabel } from "../../lib/statusMaps";
import "./rubrics.css";

/**
 * Hien thi "Ket qua cham diem" + "Chi tiet bang chung" cho 1 bao cao da
 * cham Rubric -- tach ra khoi features/review/LecturerReportDetailPage.tsx
 * theo dung features/README.md (sua lai 2026-11-08, Rilakkuma yeu cau
 * "dọn code"). Dung lai o CA chang Rubric (xem LecturerReportDetailPage)
 * VA chang Duyet (ReviewPanel hien proposal dang cham cung cau truc).
 * Di chuyen NGUYEN VEN -- KHONG doi logic/UI, chi doi cho o so voi
 * RubricCreatePage.tsx/RubricDetailPage.tsx (2 file nay lo rieng viec
 * tao/xem RUBRIC MAU, khac voi file nay lo hien thi KET QUA CHAM 1
 * BAO CAO cu the).
 */

/**
 * Bang "Ket qua cham diem" khi chang Rubric DONE -- moi tieu chi la 1
 * hang CHA (mo rong duoc de xem checklist con cua no), trong so tieu
 * chi de RIENG 1 cot (Yen yeu cau 2026-10-28, tach khoi ten tieu chi so
 * voi wireframe goc). Hang cuoi "Tổng điểm đề xuất" cong don diem tung
 * tieu chi -- GIA DINH DEMO, chua phai cach tinh that cua he thong cham.
 */
export function RubricScoreTable({
  result,
  onViewEvidence,
}: {
  result: RubricScoreResult;
  /**
   * Mo popup "Chi tiet bang chung" -- optional vi RubricScoreTable con
   * dung lai o ReviewPanel/noi chi doc khac KHONG can xem bang chung chi
   * tiet. Thieu prop nay thi cot "Bằng chứng" chi hien dang text, khong
   * bam duoc.
   */
  onViewEvidence?: (evidence: EvidenceItem[]) => void;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggle(criterionId: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(criterionId)) next.delete(criterionId);
      else next.add(criterionId);
      return next;
    });
  }

  return (
    <div className="report-detail__rubric-score">
      <h3 className="report-detail__rubric-score-title">Kết quả chấm điểm</h3>
      <p className="panel__hint">Ghi chú về các trạng thái chấm điểm</p>

      <div className="rubric-score-table-wrap">
        <table className="rubric-score-table">
          <thead>
            <tr>
              <th>Tiêu chí</th>
              <th>Trọng số</th>
              <th>Kết quả</th>
              <th>Bằng chứng</th>
              <th>Điểm</th>
            </tr>
          </thead>
          <tbody>
            {result.criteria.map((criterion) => (
              <RubricCriterionRow
                key={criterion._id}
                criterion={criterion}
                isOpen={expanded.has(criterion._id)}
                onToggle={() => toggle(criterion._id)}
                onViewEvidence={onViewEvidence}
              />
            ))}
            <tr className="rubric-score-table__total-row">
              <td colSpan={4}>Tổng điểm đề xuất</td>
              <td>
                <strong>{result.totalScore}</strong>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p className="panel__hint report-detail__rubric-score-footnote">
        Điểm được chấm chỉ mang tính đề xuất.
      </p>
    </div>
  );
}

function RubricCriterionRow({
  criterion,
  isOpen,
  onToggle,
  onViewEvidence,
}: {
  criterion: RubricCriterionScore;
  isOpen: boolean;
  onToggle: () => void;
  onViewEvidence?: (evidence: EvidenceItem[]) => void;
}) {
  return (
    <>
      <tr className="rubric-score-table__criterion-row">
        <td>
          <button
            type="button"
            className="rubric-score-table__toggle-btn"
            onClick={onToggle}
            aria-expanded={isOpen}
          >
            <span className="doc-row__chevron" aria-hidden="true">
              {isOpen ? "▼" : "▶"}
            </span>
            {criterion.title}
          </button>
        </td>
        <td>{criterion.weight}</td>
        <td>{criterion.resultSummary}</td>
        <td></td>
        <td>{criterion.score}</td>
      </tr>

      {isOpen &&
        criterion.checklists.map((checklist) => {
          const outcome = rubricChecklistOutcomeLabel[checklist.outcome];
          return (
            <tr className="rubric-score-table__checklist-row" key={checklist._id}>
              <td className="rubric-score-table__checklist-condition">{checklist.condition}</td>
              <td></td>
              <td>
                <StatusBadge label={outcome.label} tone={outcome.tone} />
              </td>
              <td>
                {checklist.evidence && checklist.evidence.length > 0 ? (
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => onViewEvidence?.(checklist.evidence!)}
                  >
                    Xem bằng chứng{checklist.evidence.length > 1 ? ` (${checklist.evidence.length})` : ""}
                  </button>
                ) : (
                  <span className="panel__hint">Không có bằng chứng</span>
                )}
              </td>
              <td></td>
            </tr>
          );
        })}
    </>
  );
}

/**
 * Popup "Chi tiet bang chung" -- thay the link placeholder "Xem bằng
 * chứng" cu. Hien DANH SACH evidence_item (data-dictionary.md muc 10.2)
 * ho tro cho 1 checklist -- co the nhieu hon 1 (vd 1 evidence SUPPORTED
 * + 1 evidence khac INSUFFICIENT cho cung dieu kien). Dung chung bo
 * khung .modal-overlay/.modal (khong can ".modal--wide" vi chi 1 cot,
 * khong phai 2 cot nhu SimilarityMatchModal o features/similarity).
 */
export function EvidenceDetailModal({
  evidence,
  onClose,
}: {
  evidence: EvidenceItem[];
  onClose: () => void;
}) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal__header">
          <h2 id="evidence-modal-title" className="modal__title">
            Chi tiết bằng chứng
          </h2>
          <button type="button" className="modal__close" aria-label="Đóng" onClick={onClose}>
            ×
          </button>
        </div>

        {evidence.length === 0 ? (
          <p className="panel__hint">Không có bằng chứng.</p>
        ) : (
          <div className="evidence-modal__list">
            {evidence.map((item) => {
              const state = evidenceVerificationStateLabel[item.verificationState];
              return (
                <div className="evidence-modal__item" key={item._id}>
                  <div className="evidence-modal__item-header">
                    <strong>{item.sourceLabel}</strong>
                    <StatusBadge label={state.label} tone={state.tone} />
                  </div>
                  <span className="rubric-score-evidence__subtitle">{item.locatorLabel}</span>
                  <blockquote className="evidence-modal__quote">{item.quoteText}</blockquote>
                  {item.verificationReasonCode && (
                    <span className="panel__hint">Mã lý do: {item.verificationReasonCode}</span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
