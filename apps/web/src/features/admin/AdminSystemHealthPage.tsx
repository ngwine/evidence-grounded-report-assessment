import { useEffect, useState } from "react";
import { AdminSubNav } from "./AdminSubNav";
import { getSystemHealthSummary } from "../../lib/api";
import type { SystemHealthSummary } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { jobStageLabel } from "../../lib/statusMaps";
import { formatDateTime } from "../../lib/format";
import "./admin.css";

const POLL_INTERVAL_MS = 5000;

/**
 * Man "Admin / System health" (UC-11) -- KHONG co bang rieng trong
 * data-dictionary.md, tinh GIA DINH DEMO tu `jobs` (xem ghi chu
 * SystemHealthSummary, lib/types.ts + getSystemHealthSummary, lib/api.ts).
 * Goc nhin TONG QUAN (so voi AdminJobsPage la danh sach tung job): dem
 * theo chang + canh bao job "nghi ngo ket" (RUNNING qua lau). Tu lam moi
 * nhe (polling) de so lieu khong qua cu khi Admin de man mo lau.
 */
export function AdminSystemHealthPage() {
  const [summary, setSummary] = useState<SystemHealthSummary | null>(null);

  function reload() {
    getSystemHealthSummary().then(setSummary);
  }

  useEffect(() => {
    reload();
    const timer = window.setInterval(reload, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <section className="panel">
      <AdminSubNav active="system-health" />

      <div className="panel__header">
        <div>
          <h1 className="panel__title">System health</h1>
          <p className="panel__subtitle">
            Tổng quan tình trạng hàng đợi xử lý theo từng chặng. (Bản demo
            minh hoạ UI, số liệu tính từ hàng đợi job — chưa có cơ chế
            heartbeat/lease thật.)
          </p>
        </div>
      </div>

      {summary === null && <p className="panel__hint">Đang tải...</p>}

      {summary !== null && (
        <>
          <div className="system-health__overview">
            <div className="system-health__metric">
              <span className="system-health__metric-value">{summary.totalJobs}</span>
              <span className="system-health__metric-label">Tổng số job</span>
            </div>
            <div className="system-health__metric">
              <span className="system-health__metric-value">{summary.totalError}</span>
              <span className="system-health__metric-label">Job lỗi</span>
            </div>
            <div className="system-health__metric">
              <span className="system-health__metric-value">{summary.totalStale}</span>
              <span className="system-health__metric-label">Job nghi ngờ kẹt</span>
            </div>
          </div>

          {summary.totalStale > 0 && (
            <p className="panel__hint admin-users__error">
              Có {summary.totalStale} job đang RUNNING quá lâu (nghi ngờ kẹt/lease hết
              hạn) — xem chi tiết ở màn "Giám sát hàng đợi".
            </p>
          )}

          <h2 className="panel__section-title">Theo từng chặng xử lý</h2>

          <table className="data-table">
            <thead>
              <tr>
                <th>Chặng</th>
                <th>Trong hàng đợi</th>
                <th>Đang xử lý</th>
                <th>Lỗi</th>
                <th>Nghi ngờ kẹt</th>
              </tr>
            </thead>
            <tbody>
              {summary.stages.map((stage) => (
                <tr key={stage.stage}>
                  <td>{jobStageLabel[stage.stage] ?? stage.stage}</td>
                  <td>{stage.queued}</td>
                  <td>{stage.running}</td>
                  <td>
                    {stage.error > 0 ? (
                      <StatusBadge label={String(stage.error)} tone="danger" />
                    ) : (
                      stage.error
                    )}
                  </td>
                  <td>
                    {stage.stale > 0 ? (
                      <StatusBadge label={String(stage.stale)} tone="warning" />
                    ) : (
                      stage.stale
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <p className="panel__hint">Cập nhật lúc {formatDateTime(summary.checkedAt)}</p>
        </>
      )}
    </section>
  );
}
