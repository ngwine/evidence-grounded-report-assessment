import { useEffect, useMemo, useState } from "react";
import { AdminSubNav } from "./AdminSubNav";
import { getAuditEvents } from "../../lib/api";
import type { AuditEventRow } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { auditOutcomeLabel } from "../../lib/statusMaps";
import { formatDateTime } from "../../lib/format";
import "./admin.css";

/**
 * Man "Admin / Audit log" (UC-11, audit_events muc 11.3 -- xem ghi chu
 * AuditEventRow, lib/types.ts). APPEND-ONLY: man nay CHI DOC, khong co
 * hanh dong sua/xoa nao (dung quy uoc cua chinh audit log). Chi co tim
 * kiem (theo nguoi thuc hien/action/resource) + loc theo ket qua, KHONG
 * co filter theo lop vi 1 audit event co the khong gan workspace nao
 * (xem workspaceName optional tren AuditEventRow).
 */
export function AdminAuditLogPage() {
  const [rows, setRows] = useState<AuditEventRow[] | null>(null);
  const [query, setQuery] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState<"" | "SUCCESS" | "FAILURE">("");

  useEffect(() => {
    getAuditEvents().then(setRows);
  }, []);

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return (rows ?? []).filter((row) => {
      const matchesQuery =
        normalizedQuery.length === 0 ||
        row.actorName.toLowerCase().includes(normalizedQuery) ||
        row.action.toLowerCase().includes(normalizedQuery) ||
        row.resourceLabel.toLowerCase().includes(normalizedQuery) ||
        (row.workspaceName ?? "").toLowerCase().includes(normalizedQuery);

      const matchesOutcome = outcomeFilter === "" || row.outcome === outcomeFilter;

      return matchesQuery && matchesOutcome;
    });
  }, [rows, query, outcomeFilter]);

  return (
    <section className="panel">
      <AdminSubNav active="audit-log" />

      <div className="panel__header">
        <div>
          <h1 className="panel__title">Audit log</h1>
          <p className="panel__subtitle">
            Nhật ký hành động trên hệ thống (append-only, chỉ đọc). Không lưu
            nội dung thô/token/mật khẩu — xem data-dictionary.md mục 11.3.
          </p>
        </div>
      </div>

      <div className="admin-users__filters">
        <input
          className="search-input"
          type="search"
          placeholder="Tìm theo người thực hiện, hành động hoặc resource"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Tìm theo người thực hiện, hành động hoặc resource"
        />
        <select
          className="admin-users__status-select"
          value={outcomeFilter}
          onChange={(event) => setOutcomeFilter(event.target.value as "" | "SUCCESS" | "FAILURE")}
          aria-label="Lọc theo kết quả"
        >
          <option value="">Tất cả kết quả</option>
          <option value="SUCCESS">{auditOutcomeLabel.SUCCESS.label}</option>
          <option value="FAILURE">{auditOutcomeLabel.FAILURE.label}</option>
        </select>
      </div>

      {rows === null && <p className="panel__hint">Đang tải...</p>}

      {rows !== null && filteredRows.length === 0 && (
        <p className="panel__hint">
          {rows.length === 0 ? "Chưa có audit event nào." : "Không tìm thấy event phù hợp."}
        </p>
      )}

      {filteredRows.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Thời điểm</th>
              <th>Người/hệ thống thực hiện</th>
              <th>Hành động</th>
              <th>Resource</th>
              <th>Lớp</th>
              <th>Kết quả</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => {
              const outcomeChip = auditOutcomeLabel[row.outcome];

              return (
                <tr key={row._id}>
                  <td>{formatDateTime(row.occurredAt)}</td>
                  <td>
                    <span className="admin-users__identity">
                      <span className="admin-users__name">{row.actorName}</span>
                      <span className="admin-users__email">
                        {row.actorType === "SYSTEM" ? "Hệ thống" : "Người dùng"}
                      </span>
                    </span>
                  </td>
                  <td>{row.action}</td>
                  <td>
                    <span className="admin-users__identity">
                      <span className="admin-users__name">{row.resourceLabel}</span>
                      <span className="admin-users__email">{row.resourceType}</span>
                    </span>
                  </td>
                  <td>{row.workspaceName ?? "—"}</td>
                  <td>
                    <StatusBadge label={outcomeChip.label} tone={outcomeChip.tone} />
                    {row.outcome === "FAILURE" && row.reasonCode && (
                      <div className="admin-users__email">{row.reasonCode}</div>
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
