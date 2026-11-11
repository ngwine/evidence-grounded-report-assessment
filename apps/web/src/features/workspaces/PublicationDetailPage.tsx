import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getPublicationDetail } from "../../lib/api";
import type {
  EvidenceItem,
  PublicationDetail,
  RubricCriterionScore,
  SimilarityMatch,
} from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime, truncateText } from "../../lib/format";
import { evidenceVerificationStateLabel, rubricChecklistOutcomeLabel } from "../../lib/statusMaps";
import "../review/review.css";

/**
 * Man "Xem publication" (`UC-09` trong bo-use-case.md, CORE, actor Sinh
 * vien) -- Yen yeu cau 2026-10-28, sau khi audit tai lieu ky thuat phat
 * hien SV chua co man nao de xem ket qua da cong bo (chi thay badge "Đã
 * có kết quả" o DocumentVersionsTable, khong bam vao dau duoc).
 *
 * Theo UC-09 muc 7.8: "chỉ cho sinh viên được cấp quyền xem publication,
 * KHONG hien thi proposal hoặc review history nội bộ" -- vi vay trang
 * nay CHI hien GIA TRI CUOI CUNG (diem, ket qua checklist, similarity
 * report), KHONG co nut Accept/Edit/Reject hay lich su quyet dinh cua
 * GV (khac voi LecturerReportDetailPage.tsx). Dung lai cac class CSS o
 * review.css (bundle chung toan app, xem ghi chu trong review.css) de
 * giao dien giong voi man GV xem, khong phai viet CSS rieng.
 */
export function PublicationDetailPage() {
  const { workspaceId, documentId } = useParams<{
    workspaceId: string;
    documentId: string;
  }>();
  const [detail, setDetail] = useState<PublicationDetail | null | undefined>(undefined);
  const [selectedMatch, setSelectedMatch] = useState<SimilarityMatch | null>(null);
  const [expandedCriteria, setExpandedCriteria] = useState<Set<string>>(new Set());
  // Popup "Chi tiet bang chung" -- them 2026-11-08, thay the link
  // placeholder "Xem bằng chứng" cu (xem ghi chu tren EvidenceDetailModal,
  // features/review/LecturerReportDetailPage.tsx -- ban SV nay chi doc,
  // khong co Accept/Edit/Reject).
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem[] | null>(null);

  useEffect(() => {
    if (!documentId) return;
    let cancelled = false;

    getPublicationDetail(documentId).then((data) => {
      if (!cancelled) setDetail(data ?? null);
    });

    return () => {
      cancelled = true;
    };
  }, [documentId]);

  function toggleCriterion(criterionId: string) {
    setExpandedCriteria((prev) => {
      const next = new Set(prev);
      if (next.has(criterionId)) next.delete(criterionId);
      else next.add(criterionId);
      return next;
    });
  }

  if (detail === null) {
    return (
      <section className="panel">
        <p className="panel__hint">
          Báo cáo này chưa được công bố kết quả, hoặc bạn không có quyền xem.
        </p>
        {workspaceId && (
          <Link className="link-button" to={`/workspaces/${workspaceId}`}>
            Quay lại lớp
          </Link>
        )}
      </section>
    );
  }

  if (detail === undefined) {
    return (
      <section className="panel">
        <p className="panel__hint">Đang tải...</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <nav className="breadcrumb" aria-label="breadcrumb">
        <Link to="/workspaces">Các lớp</Link>
        <span aria-hidden="true"> &gt; </span>
        <Link to={`/workspaces/${detail.workspaceId}`}>{detail.workspaceName}</Link>
        <span aria-hidden="true"> &gt; </span>
        <span>{detail.documentTitle}</span>
      </nav>

      <div className="panel__header">
        <div>
          <h1 className="panel__title">{detail.documentTitle}</h1>
          <p className="panel__subtitle">
            Phiên bản v{detail.versionNo} · Công bố {formatDateTime(detail.publishedAt)}
          </p>
        </div>
        <StatusBadge label="Đã công bố" tone="success" />
      </div>

      <h2 className="panel__section-title">Kết quả chấm điểm</h2>
      {detail.rubricScore ? (
        <>
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
                {detail.rubricScore.criteria.map((criterion) => (
                  <PublicationCriterionRow
                    key={criterion._id}
                    criterion={criterion}
                    isOpen={expandedCriteria.has(criterion._id)}
                    onToggle={() => toggleCriterion(criterion._id)}
                    onViewEvidence={setSelectedEvidence}
                  />
                ))}
                <tr className="rubric-score-table__total-row">
                  <td colSpan={4}>Tổng điểm đề xuất</td>
                  <td>
                    <strong>{detail.rubricScore.totalScore}</strong>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="panel__hint report-detail__rubric-score-footnote">
            Điểm được chấm chỉ mang tính đề xuất.
          </p>
        </>
      ) : (
        <p className="panel__hint">Chưa có kết quả chấm điểm cho báo cáo này.</p>
      )}

      <h2 className="panel__section-title">Similarity</h2>
      <PublicationSimilarityResults
        matches={detail.similarityMatches}
        onSelectMatch={setSelectedMatch}
      />

      {selectedMatch && (
        <PublicationSimilarityModal
          match={selectedMatch}
          documentTitle={detail.documentTitle}
          versionNo={detail.versionNo}
          onClose={() => setSelectedMatch(null)}
        />
      )}

      {selectedEvidence && (
        <PublicationEvidenceModal
          evidence={selectedEvidence}
          onClose={() => setSelectedEvidence(null)}
        />
      )}
    </section>
  );
}

/** Giong RubricCriterionRow o LecturerReportDetailPage.tsx nhung KHONG co nut sua/duyet -- chi doc. */
function PublicationCriterionRow({
  criterion,
  isOpen,
  onToggle,
  onViewEvidence,
}: {
  criterion: RubricCriterionScore;
  isOpen: boolean;
  onToggle: () => void;
  onViewEvidence: (evidence: EvidenceItem[]) => void;
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
                    onClick={() => onViewEvidence(checklist.evidence!)}
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

/** Giong SimilarityResults o LecturerReportDetailPage.tsx nhung KHONG co nut "Chay lai" -- chi doc, SV khong duoc chay lai phan tich. */
function PublicationSimilarityResults({
  matches,
  onSelectMatch,
}: {
  matches: SimilarityMatch[];
  onSelectMatch: (match: SimilarityMatch) => void;
}) {
  if (matches.length === 0) {
    return (
      <p className="panel__hint report-detail__similarity-empty">
        Không phát hiện đoạn nào trùng khớp với các nguồn đã duyệt.
      </p>
    );
  }

  const sorted = [...matches].sort((a, b) => b.similarityPercent - a.similarityPercent);

  // KHONG co cot "Nguồn tương đồng" o day (khac bang GV xem) -- nguon bi
  // so khop co the la bao cao cua SV khac, coi la "evidence bi han che"
  // theo bo-use-case.md (bang actor, dong 68): SV duoc xem doan nghi van
  // CUA CHINH MINH nhung khong duoc xem nguon cu the la gi.
  return (
    <div className="report-detail__similarity-results">
      <div className="report-detail__similarity-table-wrap">
        <table className="report-detail__similarity-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Đoạn trong báo cáo</th>
              <th>Vị trí</th>
              <th>Độ tương đồng</th>
              <th>Loại tương đồng</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((match, index) => (
              <tr key={match._id}>
                <td>{index + 1}</td>
                <td>
                  <button
                    type="button"
                    className="link-button report-detail__similarity-excerpt"
                    onClick={() => onSelectMatch(match)}
                  >
                    {truncateText(match.excerpt, 100)}
                  </button>
                </td>
                <td>{match.location}</td>
                <td>
                  <StatusBadge
                    label={`${match.similarityPercent}%`}
                    tone={
                      match.similarityPercent >= 70
                        ? "danger"
                        : match.similarityPercent >= 40
                          ? "warning"
                          : "success"
                    }
                  />
                </td>
                <td>{match.matchType ?? "—"}</td>
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

/** Giong SimilarityMatchModal o LecturerReportDetailPage.tsx -- chi doc, dung chung CSS (.modal--wide, .similarity-modal__*). */
function PublicationSimilarityModal({
  match,
  documentTitle,
  versionNo,
  onClose,
}: {
  match: SimilarityMatch;
  documentTitle: string;
  versionNo: number;
  onClose: () => void;
}) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const context = match.context ?? match.excerpt;
  const highlightIndex = match.highlightText ? context.indexOf(match.highlightText) : -1;

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
        aria-labelledby="publication-similarity-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal__header">
          <h2 id="publication-similarity-modal-title" className="modal__title">
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

          {/* KHONG hien ten/link nguon bi so khop cho SV -- bo-use-case.md
              dong 68 (bang actor): SV "Không xem... evidence bị hạn chế
              hoặc báo cáo người khác". Nguon similarity co the la bao
              cao cua SV khac, nen coi la evidence bi han che, chi GV moi
              xem duoc ten/link nguon (khac LecturerReportDetailPage.tsx
              -- Yen yeu cau 2026-10-28, sau khi ban thao cach doc UC-09). */}
          <div className="similarity-modal__meta-box">
            <span>
              Độ tương đồng:{" "}
              <StatusBadge
                label={`${match.similarityPercent}%`}
                tone={
                  match.similarityPercent >= 70
                    ? "danger"
                    : match.similarityPercent >= 40
                      ? "warning"
                      : "success"
                }
              />
            </span>
            <span>Loại trích dẫn: {match.matchType ?? "—"}</span>
          </div>
        </div>

        <p className="similarity-modal__footnote">
          Tỷ lệ tương đồng không đồng nghĩa với đạo văn.
        </p>
      </div>
    </div>
  );
}

/**
 * Popup "Chi tiet bang chung" ban SV -- them 2026-11-08, chi doc (giong
 * EvidenceDetailModal o features/review/LecturerReportDetailPage.tsx,
 * KHONG co nut thao tac gi vi SV chi xem KET QUA CUOI CUNG theo UC-09).
 */
function PublicationEvidenceModal({
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
        aria-labelledby="publication-evidence-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal__header">
          <h2 id="publication-evidence-modal-title" className="modal__title">
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
                  <span className="similarity-modal__col-subtitle">{item.locatorLabel}</span>
                  <blockquote className="evidence-modal__quote">{item.quoteText}</blockquote>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
