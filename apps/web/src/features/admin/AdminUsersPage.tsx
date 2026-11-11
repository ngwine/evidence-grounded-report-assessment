import { useEffect, useMemo, useState } from "react";
import { getAllUsers, setUserAccountStatus } from "../../lib/api";
import { AdminSubNav } from "./AdminSubNav";
import type { AdminUserRow, UserAccountStatus } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { userAccountStatusLabel } from "../../lib/statusMaps";
import "./admin.css";

const STATUS_FILTER_OPTIONS: UserAccountStatus[] = ["ACTIVE", "DISABLED", "DELETED"];

/**
 * Man "Admin / Quan ly tai khoan" (UC-11, FR-AUTH-01-03) -- danh sach TOAN
 * BO user trong he thong + trang thai tai khoan (users.status). Admin co
 * the khoa/mo tai khoan (status ACTIVE <-> DISABLED) -- khong cho xoa
 * (DELETED) tu man nay vi UC-17 (vong doi du lieu) la 1 man rieng, co quy
 * trinh audit khac.
 *
 * SUA LAI 2026-10-29 (Yen yeu cau): bo cot "Vai trò theo lớp" + "Vai trò
 * hệ thống" khoi bang -- 1 tai khoan co the co NHIEU vai tro cung luc
 * (nhieu workspace, nhieu roles/workspace) nen gom chung vao 1-2 cot
 * nhìn sai/thieu ngu canh; se can 1 man "Chi tiet tai khoan" rieng de
 * hien day du (getAllUsers van tra ve workspaceRoles, chi chua dung toi
 * o man nay).
 *
 * Yen yeu cau 2026-10-29, chua co wireframe rieng -- dung lai cau truc
 * "panel + tim kiem/loc + data-table" giong "Lecturer / Class Detail" de
 * dong bo UI giua cac man quan tri.
 */
export function AdminUsersPage() {
  const [rows, setRows] = useState<AdminUserRow[] | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<UserAccountStatus | "">("");
  const [pendingUserId, setPendingUserId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAllUsers().then((data) => {
      if (!cancelled) setRows(data);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return (rows ?? []).filter((row) => {
      const matchesQuery =
        normalizedQuery.length === 0 ||
        row.display_name.toLowerCase().includes(normalizedQuery) ||
        (row.email_normalized ?? "").toLowerCase().includes(normalizedQuery) ||
        (row.student_id ?? "").toLowerCase().includes(normalizedQuery);

      const matchesStatus = statusFilter === "" || row.status === statusFilter;

      return matchesQuery && matchesStatus;
    });
  }, [rows, query, statusFilter]);

  async function handleToggleStatus(row: AdminUserRow) {
    const nextStatus: UserAccountStatus =
      row.status === "DISABLED" ? "ACTIVE" : "DISABLED";

    const confirmMessage =
      nextStatus === "DISABLED"
        ? `Khoá tài khoản "${row.display_name}"? Tài khoản này sẽ không thể đăng nhập cho tới khi được mở khoá lại.`
        : `Mở khoá tài khoản "${row.display_name}"?`;
    if (!window.confirm(confirmMessage)) return;

    setErrorMessage(null);
    setPendingUserId(row._id);
    try {
      await setUserAccountStatus(row._id, nextStatus);
      setRows(
        (prev) =>
          prev?.map((r) => (r._id === row._id ? { ...r, status: nextStatus } : r)) ??
          prev,
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Có lỗi xảy ra.");
    } finally {
      setPendingUserId(null);
    }
  }

  return (
    <section className="panel">
      <AdminSubNav active="users" />

      <div className="panel__header">
        <div>
          <h1 className="panel__title">Quản lý tài khoản</h1>
          <p className="panel__subtitle">
            Toàn bộ tài khoản trong hệ thống — trạng thái hoạt động.
          </p>
        </div>
      </div>

      <div className="admin-users__filters">
        <input
          className="search-input"
          type="search"
          placeholder="Tìm theo tên, email hoặc MSSV"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Tìm theo tên, email hoặc MSSV"
        />
        <select
          className="admin-users__status-select"
          value={statusFilter}
          onChange={(event) =>
            setStatusFilter(event.target.value as UserAccountStatus | "")
          }
          aria-label="Lọc theo trạng thái"
        >
          <option value="">Tất cả trạng thái</option>
          {STATUS_FILTER_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {userAccountStatusLabel[value].label}
            </option>
          ))}
        </select>
      </div>

      {errorMessage && <p className="panel__hint admin-users__error">{errorMessage}</p>}

      {rows === null && <p className="panel__hint">Đang tải...</p>}

      {rows !== null && filteredRows.length === 0 && (
        <p className="panel__hint">
          {rows.length === 0
            ? "Hệ thống chưa có tài khoản nào."
            : "Không tìm thấy tài khoản phù hợp."}
        </p>
      )}

      {filteredRows.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Tài khoản</th>
              <th>Trạng thái</th>
              <th className="admin-users__action-cell"></th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => {
              const status = row.status ?? "ACTIVE";
              const statusChip = userAccountStatusLabel[status];

              return (
                <tr key={row._id}>
                  <td>
                    <span className="admin-users__identity">
                      <span className="admin-users__name">{row.display_name}</span>
                      <span className="admin-users__email">
                        {row.email_normalized ?? "—"}
                        {row.student_id ? ` · MSSV: ${row.student_id}` : ""}
                      </span>
                    </span>
                  </td>
                  <td>
                    <StatusBadge label={statusChip.label} tone={statusChip.tone} />
                  </td>
                  <td className="admin-users__action-cell">
                    {status !== "DELETED" && (
                      <button
                        type="button"
                        className="btn-secondary admin-users__toggle-btn"
                        disabled={pendingUserId === row._id}
                        onClick={() => handleToggleStatus(row)}
                      >
                        {pendingUserId === row._id
                          ? "Đang lưu..."
                          : status === "DISABLED"
                            ? "Mở khoá"
                            : "Khoá tài khoản"}
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
