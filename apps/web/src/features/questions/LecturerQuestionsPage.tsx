import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  exportTargetedQuestionsJson,
  getTargetedQuestions,
  submitTargetedQuestionReview,
  ReviewConflictError,
} from "../../lib/api";
import type { ReviewDecision, TargetedQuestion } from "../../lib/types";
import { targetedQuestionTypeLabel, reviewDecisionLabel } from "../../lib/statusMaps";
import { StatusBadge } from "../../components/StatusBadge";
import "./questions.css";

/**
 * Man "Lecturer / Targeted Questions" (UC-08, CONDITIONAL chi khi gate
 * RQ3=ENABLED -- xem RQ3_ENABLED trong lib/mockData.ts, demo coi gate
 * nay LUON BAT). GV review tung cau hoi do he thong goi y (Accept/Edit/
 * Reject, FR-QST-02) TRUOC KHI export ra file JSON (chi export cau da
 * Accept/Edit, REJECT thi khong export).
 *
 * Tach FEATURE RIENG "questions" (khong nhet vao features/review) theo
 * dung README.md ("moi use-case lon nen co feature folder rieng") --
 * sua lai 2026-11-08 cung dip tach similarity/rubrics ra khoi "review".
 */
export function LecturerQuestionsPage() {
  const { workspaceId, documentId } = useParams<{
    workspaceId: string;
    documentId: string;
  }>();

  const [questions, setQuestions] = useState<TargetedQuestion[] | null>(null);
  const [activeDecisionFor, setActiveDecisionFor] = useState<{
    questionId: string;
    decision: "EDIT" | "REJECT";
  } | null>(null);
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [conflictId, setConflictId] = useState<string | null>(null);
  const [exportedJson, setExportedJson] = useState<string | null>(null);

  const reload = useCallback(() => {
    if (!documentId) return;
    getTargetedQuestions(documentId).then(setQuestions);
  }, [documentId]);

  useEffect(() => {
    reload();
  }, [reload]);

  async function handleDecision(
    question: TargetedQuestion,
    decision: ReviewDecision,
    extra?: { reasonText?: string; editedQuestionText?: string },
  ) {
    setSubmittingId(question._id);
    setConflictId(null);
    try {
      await submitTargetedQuestionReview({
        questionId: question._id,
        decision,
        expectedRevision: question.revision,
        reasonText: extra?.reasonText,
        editedQuestionText: extra?.editedQuestionText,
      });
      setActiveDecisionFor(null);
      reload();
    } catch (error) {
      if (error instanceof ReviewConflictError) {
        setConflictId(question._id);
      }
    } finally {
      setSubmittingId(null);
    }
  }

  async function handleExport() {
    if (!documentId) return;
    const json = await exportTargetedQuestionsJson(documentId);
    setExportedJson(json);

    // Tao file download ngay tren client (GIA DINH DEMO -- chua co
    // endpoint file thuc, xem ghi chu exportTargetedQuestionsJson, lib/api.ts).
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `targeted-questions-${documentId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (questions === null) {
    return (
      <section className="panel">
        <p className="panel__hint">Đang tải...</p>
      </section>
    );
  }

  const exportableCount = questions.filter(
    (q) => q.decision === "ACCEPT" || q.decision === "EDIT",
  ).length;

  return (
    <section className="panel">
      {workspaceId && documentId && (
        <nav className="breadcrumb" aria-label="breadcrumb">
          <Link to="/lecturer/workspaces">Các lớp</Link>
          <span aria-hidden="true"> &gt; </span>
          <Link to={`/lecturer/workspaces/${workspaceId}`}>Chi tiết lớp</Link>
          <span aria-hidden="true"> &gt; </span>
          <Link to={`/lecturer/workspaces/${workspaceId}/documents/${documentId}`}>
            Báo cáo
          </Link>
          <span aria-hidden="true"> &gt; </span>
          <span>Targeted Questions</span>
        </nav>
      )}

      <div className="panel__header">
        <div>
          <h1 className="panel__title">Targeted Questions</h1>
          <p className="panel__subtitle">
            Review từng câu hỏi hệ thống gợi ý trước khi xuất — câu đã Reject
            sẽ không có trong file xuất.
          </p>
        </div>

        <button
          type="button"
          className="btn-primary"
          disabled={exportableCount === 0}
          onClick={handleExport}
        >
          Xuất JSON ({exportableCount})
        </button>
      </div>

      {questions.length === 0 && (
        <p className="panel__hint">Báo cáo này chưa có câu hỏi gợi ý nào.</p>
      )}

      <ul className="tq-list">
        {questions.map((question) => {
          const typeLabel = targetedQuestionTypeLabel[question.type];
          const isSubmitting = submittingId === question._id;
          const hasConflict = conflictId === question._id;
          const isFormOpen = activeDecisionFor?.questionId === question._id;

          return (
            <li key={question._id} className="tq-list__item">
              <div className="tq-list__item-header">
                <span className="tq-list__type">{typeLabel}</span>
                {question.decision && (
                  <StatusBadge
                    label={reviewDecisionLabel[question.decision].label}
                    tone={reviewDecisionLabel[question.decision].tone}
                  />
                )}
              </div>

              <p className="tq-list__question">
                {question.decision === "EDIT" && question.editedQuestionText
                  ? question.editedQuestionText
                  : question.questionText}
              </p>

              <p className="tq-list__linked">Liên kết: {question.linkedTo}</p>

              {question.decision === "EDIT" && question.reasonText && (
                <p className="review-list__reason">Lý do chỉnh sửa: {question.reasonText}</p>
              )}
              {question.decision === "REJECT" && question.reasonText && (
                <p className="review-list__reason">Lý do từ chối: {question.reasonText}</p>
              )}

              {hasConflict && (
                <div className="review-list__conflict">
                  <p>Câu hỏi này vừa được cập nhật bởi người khác. Tải lại để xem.</p>
                  <button type="button" className="btn-secondary" onClick={reload}>
                    Tải lại
                  </button>
                </div>
              )}

              {!question.decision && !hasConflict && (
                <div className="review-decision__row">
                  <button
                    type="button"
                    className="btn-secondary review-decision__accept-btn"
                    disabled={isSubmitting}
                    onClick={() => handleDecision(question, "ACCEPT")}
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    className="btn-secondary review-decision__edit-btn"
                    disabled={isSubmitting}
                    onClick={() => setActiveDecisionFor({ questionId: question._id, decision: "EDIT" })}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="btn-secondary report-detail__reject-btn"
                    disabled={isSubmitting}
                    onClick={() => setActiveDecisionFor({ questionId: question._id, decision: "REJECT" })}
                  >
                    Reject
                  </button>
                </div>
              )}

              {isFormOpen && (
                <TargetedQuestionDecisionForm
                  decision={activeDecisionFor.decision}
                  initialQuestionText={question.questionText}
                  submitting={isSubmitting}
                  onCancel={() => setActiveDecisionFor(null)}
                  onSubmit={(extra) => handleDecision(question, activeDecisionFor.decision, extra)}
                />
              )}
            </li>
          );
        })}
      </ul>

      {exportedJson && (
        <p className="panel__hint">
          Đã xuất {exportableCount} câu hỏi (file JSON đã tải xuống).
        </p>
      )}
    </section>
  );
}

function TargetedQuestionDecisionForm({
  decision,
  initialQuestionText,
  submitting,
  onCancel,
  onSubmit,
}: {
  decision: "EDIT" | "REJECT";
  initialQuestionText: string;
  submitting: boolean;
  onCancel: () => void;
  onSubmit: (extra: { reasonText: string; editedQuestionText?: string }) => void;
}) {
  const [reasonText, setReasonText] = useState("");
  const [editedQuestionText, setEditedQuestionText] = useState(initialQuestionText);
  const reasonValid = reasonText.trim().length > 0;

  function handleSubmit() {
    if (!reasonValid) return;
    onSubmit({
      reasonText: reasonText.trim(),
      editedQuestionText: decision === "EDIT" ? editedQuestionText.trim() : undefined,
    });
  }

  return (
    <div className="review-list__form">
      {decision === "EDIT" && (
        <label className="review-list__form-field">
          Nội dung câu hỏi sau khi sửa
          <textarea
            rows={2}
            value={editedQuestionText}
            onChange={(event) => setEditedQuestionText(event.target.value)}
          />
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
