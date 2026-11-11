import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getAssessmentProposal,
  getReportPipelineDetail,
  publishReportReview,
  ReviewConflictError,
  startPipelineStage,
  submitProposalReview,
} from "../../lib/api";
import { RQ3_ENABLED } from "../../lib/mockData";
import type {
  AssessmentProposalReview,
  EvidenceItem,
  PipelineStageKey,
  PipelineStageStatus,
  ReportPipelineDetail,
  ReviewDecision,
  RubricCriterionScore,
} from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { pipelineStageStatusTone, reviewDecisionLabel } from "../../lib/statusMaps";
import { SimilarityResults, SimilarityMatchModal } from "../similarity/SimilarityPanel";
import { RubricScoreTable, EvidenceDetailModal } from "../rubrics/RubricScoreDisplay";
import "./review.css";

/** Polling: khi co chang nao dang RUNNING, goi lai getReportPipelineDetail theo chu ky nay de thay tien do (setTimeout o lib/api.ts chay ngam, UI khong tu biet neu khong hoi lai). */
const POLL_INTERVAL_MS = 1000;

// Chang PUBLISH (Cong bo) KHONG con hien rieng o day nua -- Yen yeu cau
// 2026-10-28: "gộp vô duyệt rồi", nut "Công bố" nam ngay trong panel
// Duyet (xem ReviewPanel) va publish LUON ca 2 chang khi bam. `PUBLISH`
// van con trong PipelineStageKey/STAGE_SEQUENCE o lib/api.ts (backend
// state), chi khong co accordion rieng o UI nay.
const STAGE_ORDER: Array<{ key: PipelineStageKey; title: string }> = [
  { key: "PROCESSING", title: "Tiến trình xử lý" },
  { key: "SIMILARITY", title: "Similarity" },
  { key: "RUBRIC", title: "Rubric" },
  { key: "REVIEW", title: "Duyệt" },
];

/**
 * Man "Lecturer / Report" (wireframe gui 2026-10-18, chi tham khao UI) --
 * giang vien bam vao 1 bao cao (document) da nop trong "Lecturer / Class
 * Detail" (xem StudentReportsTable) se den day. Trang gom 5 CHANG xu ly
 * dang accordion -- co the mo NHIEU chang CUNG LUC (theo yeu cau cua Yen
 * 2026-10-24, khong con gioi han chi 1 chang tai 1 thoi diem nua), xem
 * PipelineStageKey + ReportPipelineDetail trong lib/types.ts cho cach gop
 * du lieu (GIA DINH, can Quy xac nhan lai khi co API that).
 *
 * "Tien trinh xu ly" va "Similarity" da co UI chi tiet dang danh sach
 * buoc nho (xem StepListContent, dung chung) -- rieng Tien trinh xu ly co
 * them nut Huy tien trinh. 3 chang con lai (Rubric, Duyet, Cong bo) moi
 * dung lam KHUNG accordion + badge trang thai -- noi dung chi tiet se
 * lam o cac luot sau khi Yen yeu cau cu the tung chang (giong cach
 * rubrics/review da tach feature rieng truoc do).
 */
export function LecturerReportDetailPage() {
  const { workspaceId, documentId } = useParams<{
    workspaceId: string;
    documentId: string;
  }>();
  const [detail, setDetail] = useState<ReportPipelineDetail | null | undefined>(undefined);
  // Co the mo nhieu chang CUNG LUC -- Set cac key dang mo, khong phai 1
  // key duy nhat nhu accordion kieu cu.
  const [openStages, setOpenStages] = useState<Set<PipelineStageKey>>(new Set());
  const [selectedVersionId, setSelectedVersionId] = useState<string>("");
  // Co dang goi startPipelineStage cho 1 chang khong -- disable nut trong
  // luc cho phan hoi, tranh GV bam lien tuc.
  const [startingStage, setStartingStage] = useState<PipelineStageKey | null>(null);
  // Dang mo popup "Chi tiet doan nghi van" cho match nao (null = dong) --
  // Yen yeu cau 2026-10-27, bam vao chu xanh o cot "Doan trong bao cao".
  // Luu MATCH ID (khong luu nguyen object SimilarityMatch) -- SUA LAI
  // 2026-11-08: tu khi popup nay co them Accept/Edit/Reject (UC-05), can
  // luon lay LAI match MOI NHAT tu `detail` (sau moi lan refetch) de thay
  // dung quyet dinh/revision vua duyet, thay vi giu 1 snapshot cu bi "dong
  // bang" luc mo popup.
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  // Dang mo popup "Chi tiet bang chung" cho checklist nao (null = dong) --
  // them 2026-11-08, thay the link placeholder "Xem bằng chứng" cu.
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem[] | null>(null);

  // Tai LAI du lieu cho dung VERSION dang chon o dropdown (selectedVersionId)
  // -- SUA LAI 2026-10-24 (Yen phat hien): moi version gio co pipeline
  // rieng (xem ghi chu getReportPipelineDetail, lib/api.ts), nen doi
  // version o dropdown phai goi lai API voi dung _id cua version do, moi
  // hien dung ket qua cua version do (truoc day xem version nao cung ra
  // y het tien do cua version moi nhat).
  const refetch = useCallback(() => {
    if (!documentId) return;
    getReportPipelineDetail(documentId, selectedVersionId || undefined).then((data) => {
      setDetail(data ?? null);
    });
  }, [documentId, selectedVersionId]);

  // Lan dau vao trang (hoac doi sang bao cao khac) -- nap version MOI
  // NHAT lam mac dinh + tu mo chang can GV xu ly. TACH RIENG voi refetch
  // o tren de khong bi reset lua chon version/chang dang mo moi lan
  // polling hoac moi lan GV tu doi version o dropdown.
  useEffect(() => {
    if (!documentId) return;
    let cancelled = false;
    getReportPipelineDetail(documentId).then((data) => {
      if (cancelled) return;
      setDetail(data ?? null);
      if (data) {
        setSelectedVersionId(data.currentVersion._id);
        // Mac dinh mo chang dang chay (RUNNING) hoac can GV xu ly truoc --
        // neu khong co chang nao dang chay (vd da cong bo het) thi khong mo san.
        const running = STAGE_ORDER.find((s) => data.stages[s.key].status === "RUNNING");
        const errored = STAGE_ORDER.find((s) => data.stages[s.key].status === "ERROR");
        const defaultOpen = (errored ?? running)?.key;
        setOpenStages(defaultOpen ? new Set([defaultOpen]) : new Set());
      }
    });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  // Khi con chang nao dang RUNNING, hoi lai dinh ky de thay tien do backend
  // (setTimeout o lib/api.ts chay ngam doc lap voi component nay) -- dung
  // cach nay thay WebSocket/polling that sau nay chi can sua lai refetch.
  const isAnyStageRunning = detail
    ? STAGE_ORDER.some((s) => detail.stages[s.key].status === "RUNNING")
    : false;

  useEffect(() => {
    if (!isAnyStageRunning) return;
    const interval = setInterval(refetch, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [isAnyStageRunning, refetch]);

  function handleStartStage(key: PipelineStageKey, allowRerunFromDone = false) {
    // Chi duoc bam tren VERSION MOI NHAT -- version cu da dong bang, nut
    // nay bi an o UI (xem isLatestSelected) nhung chan lai o day cho chac.
    if (!documentId || !detail || startingStage) return;
    setStartingStage(key);
    startPipelineStage(detail.currentVersion._id, key, allowRerunFromDone)
      .then(refetch)
      .finally(() => setStartingStage(null));
  }

  if (detail === null) {
    return (
      <section className="panel">
        <p className="panel__hint">Không tìm thấy báo cáo này, hoặc bạn không có quyền xem.</p>
        {workspaceId && (
          <Link className="link-button" to={`/lecturer/workspaces/${workspaceId}`}>
            Quay lại chi tiết lớp
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

  function toggleStage(key: PipelineStageKey) {
    setOpenStages((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const isLatestSelected = selectedVersionId === detail.currentVersion._id;

  return (
    <section className="panel">
      <nav className="breadcrumb" aria-label="breadcrumb">
        <Link to="/lecturer/workspaces">Các lớp</Link>
        <span aria-hidden="true"> &gt; </span>
        <Link to={`/lecturer/workspaces/${detail.workspaceId}`}>{detail.workspaceName}</Link>
        <span aria-hidden="true"> &gt; </span>
        <span>{detail.documentTitle}</span>
      </nav>

      <div className="panel__header">
        <div>
          <h1 className="panel__title">{detail.documentTitle}</h1>
          <p className="panel__subtitle">
            {detail.studentName} · {detail.studentId}
          </p>
        </div>

        <div className="report-detail__header-actions">
          {/* Feedback Log (FR-REV-04, MUST) -- them 2026-11-08, luon hien
              (khong gate nhu Targeted Questions) vi moi bao cao deu co
              the co quyet dinh Accept/Edit/Reject can xem lai. */}
          {workspaceId && documentId && (
            <Link
              className="btn-secondary"
              to={`/lecturer/workspaces/${workspaceId}/documents/${documentId}/feedback-log`}
            >
              Feedback Log
            </Link>
          )}

          {/* UC-08 (CONDITIONAL, chi khi RQ3_ENABLED -- xem lib/mockData.ts)
              -- them 2026-11-08, dat canh selector phien ban vi khong gan
              voi 1 chang nao trong pipeline 5 chang. */}
          {RQ3_ENABLED && workspaceId && documentId && (
            <Link
              className="btn-secondary"
              to={`/lecturer/workspaces/${workspaceId}/documents/${documentId}/questions`}
            >
              Targeted Questions
            </Link>
          )}

          <select
            className="class-detail__status-select"
            value={selectedVersionId}
            onChange={(event) => setSelectedVersionId(event.target.value)}
            aria-label="Chọn phiên bản"
          >
            {detail.versions.map((version) => (
              <option key={version._id} value={version._id}>
                v{version.version_no}
                {version._id === detail.currentVersion._id ? " (mới nhất)" : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      {!isLatestSelected && (
        <p className="panel__hint report-detail__old-version-hint">
          Đang xem phiên bản cũ hơn — đây là kết quả xử lý RIÊNG của phiên bản này (đã đóng băng, không thể chạy lại). Chỉ phiên bản mới nhất mới thao tác được.
        </p>
      )}

      <div className="report-detail__stage-list">
        {STAGE_ORDER.map(({ key, title }) => {
          const stage = detail.stages[key];
          const isOpen = openStages.has(key);

          return (
            <div className="report-detail__stage" key={key}>
              <button
                type="button"
                className="report-detail__stage-header"
                onClick={() => toggleStage(key)}
                aria-expanded={isOpen}
              >
                <span className="report-detail__stage-title">{title}</span>
                <StatusBadge label={stage.statusLabel} tone={pipelineStageStatusTone[stage.status]} />
                <span
                  className={`doc-row__chevron report-detail__stage-chevron${
                    isOpen ? " report-detail__stage-chevron--open" : ""
                  }`}
                  aria-hidden="true"
                >
                  ▶
                </span>
              </button>

              {isOpen && (
                <div className="report-detail__stage-body">
                  {key === "REVIEW" ? (
                    // Duyet KHONG co "Bat dau"/tien trinh chay nhu 4 chang
                    // kia -- WAITING van khoa binh thuong, con lai (chua
                    // duyet/dang duyet/da duyet) deu mo truc tiep bang
                    // "Duyet" de GV thao tac tung dong (Yen yeu cau
                    // 2026-10-28).
                    stage.status === "WAITING" ? (
                      <p className="panel__hint report-detail__placeholder">
                        Đang chờ các bước trước hoàn tất.
                      </p>
                    ) : isLatestSelected ? (
                      <ReviewPanel
                        documentId={detail.documentId}
                        isPublished={stage.status === "DONE"}
                        allSimilarityDecided={
                          (detail.stages.SIMILARITY.similarityMatches ?? []).every(
                            (m) => !!m.decision,
                          )
                        }
                        onPublished={refetch}
                        onViewEvidence={setSelectedEvidence}
                      />
                    ) : (
                      // Phien ban cu -- chi hien trang thai tinh (DONE/
                      // ERROR cua chinh version do), khong cho thao tac
                      // Duyet (proposal/ReviewPanel luon gan voi version
                      // moi nhat, xem getOrInitAssessmentProposal trong
                      // lib/api.ts).
                      <p className="panel__hint report-detail__placeholder">
                        {stage.status === "DONE" ? "Đã duyệt xong." : "Chỉ xem được, không thao tác trên phiên bản cũ."}
                      </p>
                    )
                  ) : stage.steps ? (
                    <StepListContent
                      steps={stage.steps}
                      status={stage.status}
                      showCancelButton={key === "PROCESSING"}
                      onStart={() => handleStartStage(key)}
                      starting={startingStage === key}
                      readOnly={!isLatestSelected}
                    />
                  ) : (
                    <PlaceholderStageContent
                      status={stage.status}
                      onStart={() => handleStartStage(key)}
                      starting={startingStage === key}
                      readOnly={!isLatestSelected}
                    />
                  )}

                  {/* Chang Similarity, khi DONE: them nut "Chay lai" + ket
                      qua so khop (bang hoac Empty) -- Yen yeu cau
                      2026-10-27, theo wireframe gui kem. Nut "Chay lai"
                      chi hien tren version MOI NHAT -- version cu da dong
                      bang, khong the chay lai (Yen phat hien 2026-10-24). */}
                  {key === "SIMILARITY" && stage.status === "DONE" && (
                    <>
                      {isLatestSelected && (
                        <button
                          type="button"
                          className="btn-secondary report-detail__rerun-btn"
                          onClick={() => handleStartStage(key, true)}
                          disabled={startingStage === key}
                        >
                          {startingStage === key ? "Đang chạy lại..." : "Chạy lại"}
                        </button>
                      )}

                      <SimilarityResults
                        matches={stage.similarityMatches ?? []}
                        onSelectMatch={(match) => setSelectedMatchId(match._id)}
                      />
                    </>
                  )}

                  {/* Chang Rubric, khi DONE: them nut "Chay lai" + bang
                      "Ket qua cham diem" -- Yen yeu cau 2026-10-28, theo
                      wireframe gui kem (giong cach lam Similarity). Nut
                      "Chay lai" chi hien tren version MOI NHAT (giong
                      Similarity) -- Yen phat hien 2026-10-24. */}
                  {key === "RUBRIC" && stage.status === "DONE" && (
                    <>
                      {isLatestSelected && (
                        <button
                          type="button"
                          className="btn-secondary report-detail__rerun-btn"
                          onClick={() => handleStartStage(key, true)}
                          disabled={startingStage === key}
                        >
                          {startingStage === key ? "Đang chạy lại..." : "Chạy lại"}
                        </button>
                      )}

                      {stage.rubricScore && (
                        <RubricScoreTable
                          result={stage.rubricScore}
                          onViewEvidence={setSelectedEvidence}
                        />
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {selectedMatchId &&
        (() => {
          // Luon lay LAI tu `detail` hien tai (khong giu snapshot cu) -- de
          // popup thay dung quyet dinh/revision MOI NHAT sau khi GV
          // Accept/Edit/Reject (xem ghi chu tren selectedMatchId o tren).
          const match = detail.stages.SIMILARITY.similarityMatches?.find(
            (m) => m._id === selectedMatchId,
          );
          if (!match) return null;
          return (
            <SimilarityMatchModal
              match={match}
              documentTitle={detail.documentTitle}
              versionNo={detail.currentVersion.version_no}
              // Chi cho duyet tren VERSION MOI NHAT -- cung quy uoc voi
              // cac nut "Bắt đầu"/"Chạy lại" khac (phien ban cu da dong
              // bang, xem isLatestSelected).
              readOnly={!isLatestSelected}
              onReviewed={refetch}
              onClose={() => setSelectedMatchId(null)}
            />
          );
        })()}

      {selectedEvidence && (
        <EvidenceDetailModal evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)} />
      )}
    </section>
  );
}

/**
 * Danh sach buoc nho dung chung cho MOI chang co `steps` (hien la "Tien
 * trinh xu ly" 4 buoc + "Similarity" 2 buoc -- xem lib/api.ts
 * deriveStages). `showCancelButton` chi bat cho chang nao thuc su huy
 * duoc (hien chi Tien trinh xu ly).
 */
function StepListContent({
  steps,
  status,
  showCancelButton,
  onStart,
  starting,
  readOnly,
}: {
  steps: NonNullable<ReportPipelineDetail["stages"][PipelineStageKey]["steps"]>;
  status: PipelineStageStatus;
  showCancelButton: boolean;
  onStart: () => void;
  starting: boolean;
  /** Dang xem 1 phien ban CU (khong phai moi nhat) -- an het nut thao tac, chi con xem. */
  readOnly: boolean;
}) {
  return (
    <>
      <ul className="report-detail__step-list">
        {steps.map((step, index) => (
          <li className="report-detail__step" key={step.key}>
            <span className="report-detail__step-icon-col">
              <span
                className={`report-detail__step-icon report-detail__step-icon--${step.status.toLowerCase()}`}
                aria-hidden="true"
              >
                {step.status === "DONE" ? "✓" : step.status === "RUNNING" ? "" : ""}
              </span>
              {/* Duong noi giua 2 buoc -- to mau khi buoc HIEN TAI da
                  DONE (giong anh mau Yen gui 2026-10-28), xam khi chua
                  xong. Buoc cuoi khong co duong noi. */}
              {index < steps.length - 1 && (
                <span
                  className={`report-detail__step-connector${
                    step.status === "DONE" ? " report-detail__step-connector--done" : ""
                  }`}
                  aria-hidden="true"
                />
              )}
            </span>
            <span className="report-detail__step-text">
              <span className="report-detail__step-label">{step.label}</span>
              {step.timeLabel && (
                <span className="report-detail__step-time">{step.timeLabel}</span>
              )}
            </span>
          </li>
        ))}
      </ul>

      {!readOnly && status === "NOT_STARTED" && (
        <button
          type="button"
          className="btn-primary report-detail__start-btn"
          onClick={onStart}
          disabled={starting}
        >
          {starting ? "Đang bắt đầu..." : "Bắt đầu"}
        </button>
      )}

      {status === "WAITING" && (
        <p className="panel__hint report-detail__placeholder">Đang chờ bước trước hoàn tất.</p>
      )}

      {!readOnly && showCancelButton && status === "RUNNING" && (
        <button type="button" className="btn-secondary report-detail__cancel-btn">
          Hủy tiến trình
        </button>
      )}
    </>
  );
}

function PlaceholderStageContent({
  status,
  onStart,
  starting,
  readOnly,
}: {
  status: PipelineStageStatus;
  onStart: () => void;
  starting: boolean;
  /** Dang xem 1 phien ban CU (khong phai moi nhat) -- an nut "Bắt đầu", chi con xem trang thai tinh. */
  readOnly: boolean;
}) {
  if (status === "NOT_STARTED") {
    return (
      <div className="report-detail__not-started">
        <p className="panel__hint report-detail__placeholder">
          Chưa bắt đầu — bấm để giảng viên tiến hành bước này.
        </p>
        {!readOnly && (
          <button
            type="button"
            className="btn-primary report-detail__start-btn"
            onClick={onStart}
            disabled={starting}
          >
            {starting ? "Đang bắt đầu..." : "Bắt đầu"}
          </button>
        )}
      </div>
    );
  }

  const text =
    status === "WAITING"
      ? "Đang chờ bước trước hoàn tất."
      : status === "DONE"
        ? "Đã hoàn tất."
        : status === "RUNNING"
          ? "Đang xử lý..."
          : "Có lỗi xảy ra ở bước này.";

  return <p className="panel__hint report-detail__placeholder">{text}</p>;
}

/**
 * Man "Duyet" (chang REVIEW) -- 1 PROPOSAL DUY NHAT cho ca bao cao (sua
 * lai 2026-10-28 cho dung data-dictionary.md muc 10.3-10.4 +
 * W1-03-dac-ta-yeu-cau-v1.md FR-REV-01/02, sau khi Yen hoi "co trong tai
 * lieu ky thuat khong" -- truoc do mình lam MOI dong/tieu chi 1
 * Accept/Edit/Reject rieng, khong dung voi tai lieu). GV xem toan bo ket
 * qua cham rubric de xuat (dung lai RubricScoreTable de hien thi), roi
 * Accept/Edit/Reject NGUYEN proposal 1 lan, cuoi cung bam "Công bố"
 * rieng (Yen xac nhan 2026-10-28: bam la publish luon).
 *
 * SUA LAI 2026-11-08: dong cuoi cu ("Similarity KHONG nam trong man nay
 * nua") da BO vi SAI -- xem ghi chu tren SimilarityMatch/ReviewDecision
 * o lib/types.ts (UC-05 THUC RA co Accept/Edit/Reject rieng tung match).
 * GV van duyet Similarity o CHANG Similarity (SimilarityMatchModal), KHONG
 * phai o day -- nhung nut "Công bố" o day gio PHAI cho het ca 2: proposal
 * Rubric DA duyet VA moi match Similarity DA duyet (tham so
 * `allSimilarityDecided` truyen tu component cha, vi UC-10 "sau" ca
 * UC-05 lan UC-06" theo bo-use-case.md muc 6.1).
 */
function ReviewPanel({
  documentId,
  isPublished,
  allSimilarityDecided,
  onPublished,
  onViewEvidence,
}: {
  documentId: string;
  isPublished: boolean;
  /** true = khong co match nao (Empty) hoac moi match deu da duyet -- xem tinh toan o LecturerReportDetailPage. */
  allSimilarityDecided: boolean;
  onPublished: () => void;
  onViewEvidence: (evidence: EvidenceItem[]) => void;
}) {
  const [proposal, setProposal] = useState<AssessmentProposalReview | null | undefined>(undefined);
  const [formOpen, setFormOpen] = useState<"EDIT" | "REJECT" | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [publishing, setPublishing] = useState(false);

  const load = useCallback(() => {
    getAssessmentProposal(documentId).then((data) => setProposal(data ?? null));
  }, [documentId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleDecision(
    decision: ReviewDecision,
    extra?: { reasonText?: string; editedNote?: string; editedCriterionScores?: Record<string, number> },
  ) {
    if (!proposal) return;
    setSubmitting(true);
    setConflict(false);
    try {
      await submitProposalReview({
        documentId,
        decision,
        expectedRevision: proposal.revision,
        ...extra,
      });
      setFormOpen(null);
      load();
    } catch (err) {
      if (err instanceof ReviewConflictError) {
        setConflict(true);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePublish() {
    setPublishing(true);
    await publishReportReview(documentId);
    setPublishing(false);
    onPublished();
  }

  if (isPublished) {
    return (
      <p className="panel__hint report-detail__placeholder">Báo cáo này đã được duyệt và công bố.</p>
    );
  }

  if (proposal === undefined) {
    return <p className="panel__hint report-detail__placeholder">Đang tải...</p>;
  }

  if (proposal === null) {
    return <p className="panel__hint report-detail__placeholder">Chưa có đề xuất nào để duyệt.</p>;
  }

  return (
    <div className="report-detail__review">
      <RubricScoreTable
        result={{ criteria: proposal.criteria, totalScore: proposal.totalScore }}
        onViewEvidence={onViewEvidence}
      />

      <div className="review-decision">
        {proposal.decision && (
          <StatusBadge
            label={reviewDecisionLabel[proposal.decision].label}
            tone={reviewDecisionLabel[proposal.decision].tone}
          />
        )}

        {/* Accept la hanh dong CHINH (dong y nguyen trang) -- dam/filled,
            Edit la hanh dong phu -- vien nhat, Reject la hanh dong canh
            bao -- vien do, de phan biet ro muc do thay vi 3 nut giong
            het nhau nhu Yen phan anh 2026-10-28 ("nhìn kì quá"). */}
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

        {submitting && <p className="panel__hint review-decision__loading">Đang submit review...</p>}

        {conflict && (
          <div className="review-list__conflict">
            <p>Dữ liệu đã thay đổi, tải lại.</p>
            <button type="button" className="btn-secondary" onClick={load}>
              Tải lại
            </button>
          </div>
        )}

        {formOpen && (
          <ReviewDecisionForm
            criteria={proposal.criteria}
            decision={formOpen}
            submitting={submitting}
            onCancel={() => setFormOpen(null)}
            onSubmit={(extra) => handleDecision(formOpen, extra)}
          />
        )}

        {proposal.reasonText && !formOpen && (
          <p className="review-list__reason panel__hint">Lý do: {proposal.reasonText}</p>
        )}
      </div>

      <button
        type="button"
        className="btn-primary report-detail__publish-btn"
        disabled={!proposal.decision || !allSimilarityDecided || publishing}
        onClick={handlePublish}
      >
        {publishing ? "Đang công bố..." : "Công bố"}
      </button>
      {!proposal.decision && (
        <p className="panel__hint">Cần duyệt (Accept/Edit/Reject) proposal trước khi công bố.</p>
      )}
      {proposal.decision && !allSimilarityDecided && (
        <p className="panel__hint">
          Cần duyệt (Accept/Edit/Reject) hết các đoạn trùng khớp ở chặng Similarity trước khi công bố
          (UC-05).
        </p>
      )}
    </div>
  );
}

/** Form mo rong tai cho khi GV bam Edit/Reject -- "Lý do" bat buoc ca 2 truong hop, khi Edit them 1 o diem cho MOI tieu chi (prefill diem AI de xuat) + "Nhận xét" chung (Yen yeu cau 2026-10-28). */
function ReviewDecisionForm({
  criteria,
  decision,
  submitting,
  onCancel,
  onSubmit,
}: {
  criteria: RubricCriterionScore[];
  decision: "EDIT" | "REJECT";
  submitting: boolean;
  onCancel: () => void;
  onSubmit: (extra: {
    reasonText: string;
    editedNote?: string;
    editedCriterionScores?: Record<string, number>;
  }) => void;
}) {
  const [reasonText, setReasonText] = useState("");
  const [editedNote, setEditedNote] = useState("");
  const [scores, setScores] = useState<Record<string, string>>(() =>
    Object.fromEntries(criteria.map((c) => [c._id, String(c.score)])),
  );
  const reasonValid = reasonText.trim().length > 0;

  function handleSubmit() {
    if (!reasonValid) return;
    const editedCriterionScores: Record<string, number> = {};
    criteria.forEach((c) => {
      const raw = scores[c._id];
      if (raw !== undefined && raw.trim() !== "") editedCriterionScores[c._id] = Number(raw);
    });
    onSubmit({
      reasonText: reasonText.trim(),
      editedNote: decision === "EDIT" ? editedNote.trim() || undefined : undefined,
      editedCriterionScores: decision === "EDIT" ? editedCriterionScores : undefined,
    });
  }

  return (
    <div className="review-list__form">
      {decision === "EDIT" && (
        <div className="review-list__form-scores">
          {criteria.map((c) => (
            <label className="review-list__form-field" key={c._id}>
              {c.title}
              <input
                type="number"
                value={scores[c._id] ?? ""}
                onChange={(event) =>
                  setScores((prev) => ({ ...prev, [c._id]: event.target.value }))
                }
              />
            </label>
          ))}
        </div>
      )}

      {decision === "EDIT" && (
        <label className="review-list__form-field">
          Nhận xét
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
