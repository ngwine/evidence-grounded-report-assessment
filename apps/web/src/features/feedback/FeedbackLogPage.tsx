import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { exportFeedbackLogJson, getFeedbackLog } from "../../lib/api";
import type { FeedbackLogEntry } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { feedbackLogSourceLabel, reviewDecisionLabel } from "../../lib/statusMaps";
import { formatDateTime } from "../../lib/format";
import "./feedback.css";

/**
 * Man "Lecturer / Feedback Log" (FR-REV-04, MUST: "Feedback Log bất biến
 * và xuất được cho error analysis đúng quyền") -- them 2026-11-08. Hien
 * TOAN BO quyet dinh Accept/Edit/Reject GV da lam cho 1 bao cao (Similarity
 * UC-05 + Rubric proposal UC-06 + Targeted Questions UC-08), gop CHUNG 1
 * dong thoi gian -- xem appendFeedbackLogEntry trong lib/api.ts (noi GHI
 * duy nhat). Trang nay CHI DOC + xuat JSON, KHONG co nut sua/xoa dong nao
 * (dung quy uoc "bất biến" cua FR-REV-04).
 *
 * Khac voi "Audit log" (Admin, toan he thong) -- Feedback Log gan theo 1
 * BAO CAO cu the, phuc vu GV xem lai lich su quyet dinh cua chinh bao cao
 * do + xuat cho error analysis, khong phai nhat ky he thong chung.
 */
export function FeedbackLogPage() {
  const { workspaceId, documentId } = useParams<{
    workspaceId: string;
    documentId: string;
  }>();

  const [entries, setEntries] = useState<FeedbackLogEntry[] | null>(null);

  useEffect(() => {
    if (!documentId) return;
    getFeedbackLog(documentId).then(setEntries);
  }, [documentId]);

  async function handleExport() {
    if (!documentId) return;
    const json = await exportFeedbackLogJson(documentId);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `feedback-log-${documentId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (entries === null) {
    return (
      <section className="panel">
        <p className="panel__hint">Đang tải...</p>
      </section>
    );
  }

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
          <span>Feedback Log</span>
        </nav>
      )}

      <div className="panel__header">
        <div>
          <h1 className="panel__title">Feedback Log</h1>
          <p className="panel__subtitle">
            Lịch sử các quyết định Accept/Edit/Reject đã thực hiện cho báo cáo này
            (bất biến, chỉ đọc). Dùng nút "Xuất JSON" để lấy dữ liệu cho error
            analysis.
          </p>
        </div>

        <button
          type="button"
          className="btn-primary"
          disabled={entries.length === 0}
          onClick={handleExport}
        >
          Xuất JSON ({entries.length})
        </button>
      </div>

      {entries.length === 0 && (
        <p className="panel__hint">Báo cáo này chưa có quyết định nào được ghi lại.</p>
      )}

      {entries.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Thời điểm</th>
              <th>Nguồn</th>
              <th>Nội dung</th>
              <th>Quyết định</th>
              <th>Người thực hiện</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const decisionChip = reviewDecisionLabel[entry.decision];
              return (
                <tr key={entry._id}>
                  <td>{formatDateTime(entry.occurredAt)}</td>
                  <td>{feedbackLogSourceLabel[entry.source]}</td>
                  <td>
                    <span className="feedback-log__item-label">{entry.itemLabel}</span>
                    {entry.reasonText && (
                      <div className="feedback-log__reason">Lý do: {entry.reasonText}</div>
                    )}
                  </td>
                  <td>
                    <StatusBadge label={decisionChip.label} tone={decisionChip.tone} />
                  </td>
                  <td>{entry.actorName}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
