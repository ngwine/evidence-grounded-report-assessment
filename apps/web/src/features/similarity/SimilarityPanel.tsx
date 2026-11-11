import { useEffect, useRef, useState } from "react";
import { ReviewConflictError, submitSimilarityMatchReview } from "../../lib/api";
import type { ReviewDecision, SimilarityMatch } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { truncateText } from "../../lib/format";
import { reviewDecisionLabel } from "../../lib/statusMaps";
import "./similarity.css";

/**
 * Feature "similarity" (UC-05, chang Similarity) -- tach ra khoi
 * features/review/LecturerReportDetailPage.tsx theo dung
 * features/README.md (sua lai 2026-11-08, Rilakkuma yeu cau "dọn code").
 * Di chuyen NGUYEN VEN SimilarityResults/SimilarityMatchModal/
 * SimilarityDecisionForm/similarityTone -- KHONG doi logic/UI, chi doi
 * cho o (xem lai ghi chu goc trong git history/review.css cho bo-y-tuong
 * gan voi UC-05).
 */

function similarityTone(percent: number): "danger" | "warning" | "success" {
  if (percent >= 70) return "danger";
  if (percent >= 40) return "warning";
  return "success";
}

/**
 * Ket qua "Similarity" khi chang DONE -- rong = "Empty" (khong phat hien
 * doan nao trung khop), co phan tu = bang "Ket qua so khop", sap xep
 * giam dan theo do tuong dong (wireframe gui kem 2026-10-27). Mau badge
 * % chi mang tinh truc quan GIA DINH (cao/trung/thap), KHONG phai nguong
 * "dao van" chinh thuc -- vi vay luon kem dong ghi chu cuoi bang.
 */
export function SimilarityResults({
  matches,
  onSelectMatch,
}: {
  matches: SimilarityMatch[];
  onSelectMatch: (match: SimilarityMatch) => void;
}) {
  if (matches.length === 0) {
    return (
      <div className="report-detail__similarity-results">
        <span className="modal__label">Kết quả so khớp</span>
        <p className="panel__hint report-detail__similarity-empty">
          Không phát hiện đoạn nào trùng khớp với các nguồn đã duyệt.
        </p>
      </div>
    );
  }

  const sorted = [...matches].sort((a, b) => b.similarityPercent - a.similarityPercent);

  return (
    <div className="report-detail__similarity-results">
      <span className="modal__label">Kết quả so khớp ({sorted.length})</span>
      <p className="panel__hint">
        Ghi chú về mức cao thấp của độ tương đồng. Bấm vào đoạn để xem chi tiết và duyệt
        (Accept/Edit/Reject) từng đoạn — theo UC-05.
      </p>

      <div className="report-detail__similarity-table-wrap">
        <table className="report-detail__similarity-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Đoạn trong báo cáo</th>
              <th>Vị trí</th>
              <th>Nguồn tương đồng</th>
              <th>Độ tương đồng</th>
              <th>Loại tương đồng</th>
              <th>Quyết định</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((match, index) => (
              <tr key={match._id}>
                <td>{index + 1}</td>
                <td>
                  {/* Bam vao doan de mo popup "Chi tiet doan nghi van" --
                      Yen yeu cau 2026-10-27, to xanh de GV biet bam duoc.
                      SUA LAI 2026-11-08: popup nay gio CUNG la noi GV
                      Accept/Edit/Reject match (UC-05), xem
                      SimilarityMatchModal. */}
                  <button
                    type="button"
                    className="link-button report-detail__similarity-excerpt"
                    onClick={() => onSelectMatch(match)}
                  >
                    {truncateText(match.excerpt, 100)}
                  </button>
                </td>
                <td>{match.location}</td>
                <td>{match.sourceLabel}</td>
                <td>
                  <StatusBadge
                    label={`${match.similarityPercent}%`}
                    tone={similarityTone(match.similarityPercent)}
                  />
                </td>
                <td>{match.matchType ?? "—"}</td>
                <td>
                  {match.decision ? (
                    <StatusBadge
                      label={reviewDecisionLabel[match.decision].label}
                      tone={reviewDecisionLabel[match.decision].tone}
                    />
                  ) : (
                    <span className="panel__hint">Chưa duyệt</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="panel__hint report-detail__similarity-footnote">
        Tỷ lệ tương đồng không đồng nghĩa với đạo văn.
      </p>
    </div>
  );
}

/**
 * Popup "Chi tiet doan nghi van" -- bam vao 1 dong trong bang "Ket qua so
 * khop" se mo popup nay, hien ca 2 ben: doan van trong bao cao cua SV
 * (co highlight phan trung) va doan van tuong ung tu nguon, kem thong
 * tin do tuong dong/loai trich dan -- Yen yeu cau 2026-10-27, theo
 * wireframe gui kem. Dung chung bo khung .modal-overlay/.modal voi
 * UploadReportModal.tsx (xem UploadReportModal.css), them modifier
 * ".modal--wide" vi popup nay can 2 cot nen rong hon modal mac dinh.
 *
 * SUA LAI 2026-11-08: them khu vuc Accept/Edit/Reject (UC-05) ngay trong
 * popup nay -- vi GV da bam vao match de xem chi tiet roi, tien the
 * quyet dinh LUON tai day thay vi phai dong popup roi lam o 1 cho khac.
 * `readOnly` = true khi dang xem phien ban CU hon (an het nut thao tac,
 * cung quy uoc voi StepListContent/ReviewPanel trong features/review).
 */
export function SimilarityMatchModal({
  match,
  documentTitle,
  versionNo,
  readOnly,
  onReviewed,
  onClose,
}: {
  match: SimilarityMatch;
  documentTitle: string;
  versionNo: number;
  readOnly: boolean;
  /** Goi lai sau khi duyet thanh cong -- de component cha refetch, cap nhat badge trong bang + nut "Công bố". */
  onReviewed: () => void;
  onClose: () => void;
}) {
  const [formOpen, setFormOpen] = useState<"EDIT" | "REJECT" | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [conflict, setConflict] = useState(false);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  async function handleDecision(decision: ReviewDecision, extra?: { reasonText?: string; editedNote?: string }) {
    setSubmitting(true);
    setConflict(false);
    try {
      await submitSimilarityMatchReview({
        matchId: match._id,
        decision,
        expectedRevision: match.revision,
        ...extra,
      });
      setFormOpen(null);
      onReviewed();
    } catch (err) {
      if (err instanceof ReviewConflictError) {
        setConflict(true);
      }
    } finally {
      setSubmitting(false);
    }
  }

  const context = match.context ?? match.excerpt;
  const highlightIndex = match.highlightText ? context.indexOf(match.highlightText) : -1;

  // 2 khung (doan trong bao cao + doan trich nguon) cuon rieng duoc, vi
  // doan van xung quanh co the rat dai hoac co nhieu doan nghi van gan
  // nhau -- Yen yeu cau 2026-10-27: "du dinh se hien thi dung cho cua vi
  // tri do luon, roi 2 ben se duoc cuon". Mo popup len thi TU DONG cuon
  // toi dung vi tri doan highlight (scrollIntoView, block: "center") thay
  // vi luon nam tren cung khung.
  const highlightRef = useRef<HTMLElement>(null);
  useEffect(() => {
    highlightRef.current?.scrollIntoView({ block: "center" });
  }, [match]);

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal modal--wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="similarity-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal__header">
          <h2 id="similarity-modal-title" className="modal__title">
            Chi tiết đoạn nghi vấn
          </h2>
          <button type="button" className="modal__close" aria-label="Đóng" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="similarity-modal__stack">
          <div className="similarity-modal__col-header">
            <strong className="similarity-modal__col-title">
              {documentTitle} — phiên bản v{versionNo}
            </strong>
            <span className="similarity-modal__col-subtitle">{match.location}</span>
          </div>
          <div className="similarity-modal__context-box">
            {highlightIndex >= 0 && match.highlightText ? (
              <>
                {context.slice(0, highlightIndex)}
                <mark className="similarity-modal__highlight" ref={highlightRef}>
                  {match.highlightText}
                </mark>
                {context.slice(highlightIndex + match.highlightText.length)}
              </>
            ) : (
              context
            )}
          </div>

          <div className="similarity-modal__col-header similarity-modal__col-header--source">
            <strong className="similarity-modal__col-title">Nguồn tương đồng</strong>
          </div>
          {/* CHI hien ten/ID tai lieu nguon -- KHONG bia doan trich
              nguyen van ben nguon, vi theo evidence_items
              (data-dictionary.md muc 10.2) chi chac chan co
              source_document_version_id (biet trung tai lieu nao), chua
              chac co quote_text rieng cho phia nguon. Yen quyet dinh
              2026-10-27: "lam theo noi dung dang co", cho den khi xac
              nhan lai voi Quy thi doi sau. */}
          <div className="similarity-modal__source-box">
            {match.sourceUrl ? (
              <a href={match.sourceUrl} target="_blank" rel="noreferrer">
                {match.sourceLabel}
              </a>
            ) : (
              match.sourceLabel
            )}
          </div>
          <div className="similarity-modal__meta-box">
            <span>
              Độ tương đồng:{" "}
              <StatusBadge
                label={`${match.similarityPercent}%`}
                tone={similarityTone(match.similarityPercent)}
              />
            </span>
            <span>Loại trích dẫn: {match.matchType ?? "—"}</span>
          </div>
        </div>

        <p className="similarity-modal__footnote">
          Tỷ lệ tương đồng không đồng nghĩa với đạo văn.
        </p>

        {/* UC-05: "Match được Accept/Edit/Reject" -- an het khi readOnly
            (phien ban cu), chi con xem badge quyet dinh (neu co). */}
        <div className="review-decision review-decision--similarity">
          {match.decision && (
            <StatusBadge
              label={reviewDecisionLabel[match.decision].label}
              tone={reviewDecisionLabel[match.decision].tone}
            />
          )}

          {!readOnly && (
            <div className="review-decision__row">
              <button
                type="button"
                className="btn-secondary review-decision__accept-btn"
                disabled={submitting}
                onClick={() => handleDecision("ACCEPT")}
              >
                Accept
              </button>
              <button
                type="button"
                className="btn-secondary review-decision__edit-btn"
                disabled={submitting}
                onClick={() => setFormOpen("EDIT")}
              >
                Edit
              </button>
              <button
                type="button"
                className="btn-secondary report-detail__reject-btn"
                disabled={submitting}
                onClick={() => setFormOpen("REJECT")}
              >
                Reject
              </button>
            </div>
          )}

          {submitting && <p className="panel__hint review-decision__loading">Đang submit review...</p>}

          {conflict && (
            <div className="review-list__conflict">
              <p>Dữ liệu đã thay đổi, tải lại.</p>
              <button type="button" className="btn-secondary" onClick={onReviewed}>
                Tải lại
              </button>
            </div>
          )}

          {formOpen && (
            <SimilarityDecisionForm
              decision={formOpen}
              submitting={submitting}
              onCancel={() => setFormOpen(null)}
              onSubmit={(extra) => handleDecision(formOpen, extra)}
            />
          )}

          {match.reasonText && !formOpen && (
            <p className="review-list__reason panel__hint">Lý do: {match.reasonText}</p>
          )}
          {match.editedNote && !formOpen && (
            <p className="review-list__reason panel__hint">Ghi chú chỉnh sửa: {match.editedNote}</p>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Form mo rong khi GV bam Edit/Reject cho 1 SimilarityMatch -- giong
 * ReviewDecisionForm (dung chung cho proposal Rubric, xem
 * features/review/LecturerReportDetailPage.tsx) nhung BO phan diem
 * (Similarity khong cham diem) -- chi con "Lý do" bat buoc + "Ghi chú"
 * rieng khi Edit.
 */
function SimilarityDecisionForm({
  decision,
  submitting,
  onCancel,
  onSubmit,
}: {
  decision: "EDIT" | "REJECT";
  submitting: boolean;
  onCancel: () => void;
  onSubmit: (extra: { reasonText: string; editedNote?: string }) => void;
}) {
  const [reasonText, setReasonText] = useState("");
  const [editedNote, setEditedNote] = useState("");
  const reasonValid = reasonText.trim().length > 0;

  function handleSubmit() {
    if (!reasonValid) return;
    onSubmit({
      reasonText: reasonText.trim(),
      editedNote: decision === "EDIT" ? editedNote.trim() || undefined : undefined,
    });
  }

  return (
    <div className="review-list__form">
      {decision === "EDIT" && (
        <label className="review-list__form-field">
          Ghi chú
          <textarea rows={2} value={editedNote} onChange={(event) => setEditedNote(event.target.value)} />
        </label>
      )}

      <label className="review-list__form-field">
        Lý do <span className="review-list__required">*</span>
        <textarea rows={2} value={reasonText} onChange={(event) => setReasonText(event.target.value)} />
      </label>

      <div className="review-list__form-actions">
        <button
          type="button"
          className="btn-primary"
          disabled={submitting || !reasonValid}
          onClick={handleSubmit}
        >
          {submitting ? "Đang gửi..." : "Xác nhận"}
        </button>
        <button type="button" className="btn-secondary" onClick={onCancel} disabled={submitting}>
          Huỷ
        </button>
      </div>
    </div>
  );
}
