import { useEffect, useMemo, useState } from "react";
import { AdminSubNav } from "./AdminSubNav";
import { getGovernanceRecords, setGovernanceRecordStatus } from "../../lib/api";
import type { AdminGovernanceRow, GovernanceStatus } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { governanceStatusLabel, rightsBasisLabel } from "../../lib/statusMaps";
import { formatDateTime } from "../../lib/format";
import "./admin.css";

const STATUS_FILTER_OPTIONS: GovernanceStatus[] = [
  "PENDING",
  "APPROVED",
  "REJECTED",
  "REVOKED",
  "EXPIRED",
];

/**
 * Man "Admin / Cau hinh policy" (UC-11, governance_records -- xem ghi
 * chu AdminGovernanceRow, lib/types.ts). Moi dong la 1 "quyen su dung"
 * gan voi 1 resource (bao cao/dataset/model/rubric) -- Admin co the
 * Duyet 1 ban ghi dang Cho duyet, hoac Thu hoi 1 ban ghi dang Da duyet.
 * Tuong tu AdminLifecyclePage/AdminJobsPage: ban DEMO minh hoa UI, chua
 * noi backend thuc -- optimistic concurrency bang revision (xem
 * setGovernanceRecordStatus, lib/api.ts).
 */
export function AdminPolicyPage() {
  const [rows, setRows] = useState<AdminGovernanceRow[] | null>(null);
  const [pendingRecordId, setPendingRecordId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<GovernanceStatus | "">("");

  function reload() {
    getGovernanceRecords().then(setRows);
  }

  useEffect(() => {
    reload();
  }, []);

  const filteredRows = useMemo(() => {
    if (statusFilter === "") return rows ?? [];
    return (rows ?? []).filter((row) => row.status === statusFilter);
  }, [rows, statusFilter]);

  async function handleSetStatus(row: AdminGovernanceRow, status: GovernanceStatus) {
    const actionLabel = status === "APPROVED" ? "Duyệt" : "Thu hồi";
    if (!window.confirm(`${actionLabel} quyền sử dụng cho "${row.resourceLabel}"?`)) return;

    setErrorMessage(null);
    setPendingRecordId(row._id);
    try {
      await setGovernanceRecordStatus(row._id, status, row.revision);
      reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Có lỗi xảy ra.");
    } finally {
      setPendingRecordId(null);
    }
  }

  return (
    <section className="panel">
      <AdminSubNav active="policy" />

      <div className="panel__header">
        <div>
          <h1 className="panel__title">Cấu hình policy sử dụng dữ liệu</h1>
          <p className="panel__subtitle">
            Quản lý cơ sở quyền sử dụng (rights basis) và trạng thái duyệt cho
            từng báo cáo/dataset/model/rubric. (Bản demo minh hoạ UI, chưa nối
            backend thật.)
          </p>
        </div>
      </div>

      <div className="admin-users__filters">
        <select
          className="admin-users__status-select"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as GovernanceStatus | "")}
          aria-label="Lọc theo trạng thái"
        >
          <option value="">Tất cả trạng thái</option>
          {STATUS_FILTER_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {governanceStatusLabel[value].label}
            </option>
          ))}
        </select>
      </div>

      {errorMessage && <p className="panel__hint admin-users__error">{errorMessage}</p>}

      {rows === null && <p className="panel__hint">Đang tải...</p>}

      {rows !== null && filteredRows.length === 0 && (
        <p className="panel__hint">
          {rows.length === 0 ? "Chưa có bản ghi policy nào." : "Không tìm thấy bản ghi phù hợp."}
        </p>
      )}

      {filteredRows.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Resource</th>
              <th>Lớp</th>
              <th>Cơ sở quyền</th>
              <th>Mục đích cho phép</th>
              <th>Trạng thái</th>
              <th>Hiệu lực đến</th>
              <th className="admin-users__action-cell"></th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => {
              const statusChip = governanceStatusLabel[row.status];
              const isPending = pendingRecordId === row._id;

              return (
                <tr key={row._id}>
                  <td>
                    <span className="admin-users__identity">
                      <span className="admin-users__name">{row.resourceLabel}</span>
                      <span className="admin-users__email">{row.resourceType}</span>
                    </span>
                  </td>
                  <td>{row.workspaceName ?? "—"}</td>
                  <td>{rightsBasisLabel[row.rightsBasis]}</td>
                  <td>{row.allowedPurposes.join(", ")}</td>
                  <td>
                    <StatusBadge label={statusChip.label} tone={statusChip.tone} />
                    {row.status === "APPROVED" && row.approverName && (
                      <div className="admin-users__email">bởi {row.approverName}</div>
                    )}
                  </td>
                  <td>{row.validUntil ? formatDateTime(row.validUntil) : "—"}</td>
                  <td className="admin-users__action-cell">
                    {row.status === "PENDING" && (
                      <>
                        <button
                          type="button"
                          className="btn-secondary admin-users__toggle-btn"
                          disabled={isPending}
                          onClick={() => handleSetStatus(row, "APPROVED")}
                        >
                          {isPending ? "Đang xử lý..." : "Duyệt"}
                        </button>{" "}
                        <button
                          type="button"
                          className="btn-secondary admin-users__toggle-btn admin-lifecycle__purge-btn"
                          disabled={isPending}
                          onClick={() => handleSetStatus(row, "REJECTED")}
                        >
                          Từ chối
                        </button>
                      </>
                    )}
                    {row.status === "APPROVED" && (
                      <button
                        type="button"
                        className="btn-secondary admin-users__toggle-btn admin-lifecycle__purge-btn"
                        disabled={isPending}
                        onClick={() => handleSetStatus(row, "REVOKED")}
                      >
                        {isPending ? "Đang thu hồi..." : "Thu hồi"}
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
