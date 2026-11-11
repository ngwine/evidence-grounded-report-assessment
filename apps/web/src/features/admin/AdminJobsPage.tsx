import { useEffect, useMemo, useState } from "react";
import { AdminSubNav } from "./AdminSubNav";
import { cancelJob, getJobs, retryJob } from "../../lib/api";
import type { AdminJobRow, JobStageKey, JobStatus } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { jobStageLabel, jobStatusLabel } from "../../lib/statusMaps";
import { formatDateTime } from "../../lib/format";
import "./admin.css";

const POLL_INTERVAL_MS = 1000;

// Chi 3 chang la job xu ly NEN thuc su -- REVIEW/PUBLISH la hanh dong
// cua giang vien, khong phai job co the ket/retry. Xem ghi chu JobStageKey
// (lib/types.ts). Yen phat hien 2026-10-24.
const STAGE_FILTER_OPTIONS: JobStageKey[] = ["PROCESSING", "SIMILARITY", "RUBRIC"];
const STATUS_FILTER_OPTIONS: JobStatus[] = ["QUEUED", "RUNNING", "DONE", "ERROR", "CANCELLED"];

/**
 * Man "Admin / Giam sat hang doi xu ly" (UC-14, actor "Giang vien, Quan
 * tri vien" theo bo-use-case.md) -- ban DEMO theo yeu cau "làm thử xem"
 * cua Yen (2026-10-29), de hinh dung UI truoc khi co backend thuc.
 *
 * Goc nhin TONG QUAN toan he thong: moi dong la 1 "job" = 1 chang xu ly
 * cua 1 bao cao (xem JobRecord/AdminJobRow). Admin co the Huy 1 job dang
 * chay, hoac Chay lai 1 job loi/da huy. Du lieu + hanh dong deu la MOCK,
 * GIA DINH toan bo cach mo hinh hoa "hang doi" nay (data-dictionary.md
 * chua co bang rieng cho job/queue) -- can Quy xac nhan lai khi lam API
 * that.
 */
export function AdminJobsPage() {
  const [rows, setRows] = useState<AdminJobRow[] | null>(null);
  const [pendingJobId, setPendingJobId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [stageFilter, setStageFilter] = useState<JobStageKey | "">("");
  const [statusFilter, setStatusFilter] = useState<JobStatus | "">("");

  function reload() {
    getJobs().then(setRows);
  }

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return (rows ?? []).filter((row) => {
      const matchesQuery =
        normalizedQuery.length === 0 ||
        row.documentTitle.toLowerCase().includes(normalizedQuery) ||
        row.documentKey.toLowerCase().includes(normalizedQuery) ||
        row.ownerName.toLowerCase().includes(normalizedQuery) ||
        row.workspaceName.toLowerCase().includes(normalizedQuery) ||
        row.workspaceKey.toLowerCase().includes(normalizedQuery);

      const matchesStage = stageFilter === "" || row.stage === stageFilter;
      const matchesStatus = statusFilter === "" || row.status === statusFilter;

      return matchesQuery && matchesStage && matchesStatus;
    });
  }, [rows, query, stageFilter, statusFilter]);

  useEffect(() => {
    reload();
  }, []);

  // Poll nhe de thay job "Chay lai" tu RUNNING chuyen sang DONE (gia lap
  // qua setTimeout o lib/api.ts, giong co che o LecturerReportDetailPage).
  useEffect(() => {
    const hasRunningJob = rows?.some((row) => row.status === "RUNNING") ?? false;
    if (!hasRunningJob) return;

    const timer = window.setInterval(reload, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [rows]);

  async function handleCancel(row: AdminJobRow) {
    if (!window.confirm(`Huỷ job "${jobStageLabel[row.stage]}" của "${row.documentTitle}" (${row.ownerName})?`)) {
      return;
    }

    setErrorMessage(null);
    setPendingJobId(row._id);
    try {
      await cancelJob(row._id);
      reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Có lỗi xảy ra.");
    } finally {
      setPendingJobId(null);
    }
  }

  async function handleRetry(row: AdminJobRow) {
    setErrorMessage(null);
    setPendingJobId(row._id);
    try {
      await retryJob(row._id);
      reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Có lỗi xảy ra.");
    } finally {
      setPendingJobId(null);
    }
  }

  return (
    <section className="panel">
      <AdminSubNav active="jobs" />

      <div className="panel__header">
        <div>
          <h1 className="panel__title">Giám sát hàng đợi xử lý</h1>
          <p className="panel__subtitle">
            Toàn bộ job đang chạy/đã chạy trên hệ thống — huỷ job đang chạy,
            chạy lại job lỗi. (Bản demo minh hoạ UI, chưa nối backend thật.)
          </p>
        </div>
      </div>

      <div className="admin-users__filters">
        <input
          className="search-input"
          type="search"
          placeholder="Tìm theo báo cáo, lớp hoặc người nộp"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Tìm theo báo cáo, lớp hoặc người nộp"
        />
        <select
          className="admin-users__status-select"
          value={stageFilter}
          onChange={(event) => setStageFilter(event.target.value as JobStageKey | "")}
          aria-label="Lọc theo chặng"
        >
          <option value="">Tất cả chặng</option>
          {STAGE_FILTER_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {jobStageLabel[value] ?? value}
            </option>
          ))}
        </select>
        <select
          className="admin-users__status-select"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as JobStatus | "")}
          aria-label="Lọc theo trạng thái"
        >
          <option value="">Tất cả trạng thái</option>
          {STATUS_FILTER_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {jobStatusLabel[value].label}
            </option>
          ))}
        </select>
      </div>

      {errorMessage && <p className="panel__hint admin-users__error">{errorMessage}</p>}

      {rows === null && <p className="panel__hint">Đang tải...</p>}

      {rows !== null && filteredRows.length === 0 && (
        <p className="panel__hint">
          {rows.length === 0 ? "Chưa có job nào trong hàng đợi." : "Không tìm thấy job phù hợp."}
        </p>
      )}

      {filteredRows.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Báo cáo</th>
              <th>Phiên bản</th>
              <th>Lớp</th>
              <th>Chặng</th>
              <th>Trạng thái</th>
              <th>Bắt đầu</th>
              <th>Số lần chạy lại</th>
              <th className="admin-users__action-cell"></th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => {
              const statusChip = jobStatusLabel[row.status];
              const isPending = pendingJobId === row._id;

              return (
                <tr key={row._id}>
                  <td>
                    <span className="admin-users__identity">
                      <span className="admin-users__name">{row.documentTitle}</span>
                      {/* Chi hien nguoi nop -- document_key la id noi bo de
                          backend dam bao khong trung trong workspace (xem
                          data-dictionary.md Sec 6.1 "Stable trong workspace"),
                          khong phai ma chinh thuc nguoi dung tu dat nhu
                          workspace_key ("ma lop") nen khong can show ra UI.
                          Yen yeu cau bo 2026-10-24. */}
                      <span className="admin-users__email">{row.ownerName}</span>
                    </span>
                  </td>
                  <td>v{row.versionNo}</td>
                  <td>
                    <span className="admin-users__identity">
                      <span className="admin-users__name">{row.workspaceName}</span>
                      <span className="admin-users__email">{row.workspaceKey}</span>
                    </span>
                  </td>
                  <td>{jobStageLabel[row.stage] ?? row.stage}</td>
                  <td>
                    <StatusBadge label={statusChip.label} tone={statusChip.tone} />
                  </td>
                  <td>{formatDateTime(row.startedAt)}</td>
                  <td>{row.retryCount}</td>
                  <td className="admin-users__action-cell">
                    {row.status === "RUNNING" && (
                      <button
                        type="button"
                        className="btn-secondary admin-users__toggle-btn"
                        disabled={isPending}
                        onClick={() => handleCancel(row)}
                      >
                        {isPending ? "Đang huỷ..." : "Huỷ"}
                      </button>
                    )}
                    {(row.status === "ERROR" || row.status === "CANCELLED") && (
                      <button
                        type="button"
                        className="btn-secondary admin-users__toggle-btn"
                        disabled={isPending}
                        onClick={() => handleRetry(row)}
                      >
                        {isPending ? "Đang chạy lại..." : "Chạy lại"}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
