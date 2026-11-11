import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  addWorkspaceMember,
  getWorkspaceById,
  getWorkspaceMembers,
  setMembershipStatus,
} from "../../lib/api";
import { mockUsers } from "../../lib/mockData";
import { AdminUserCombobox } from "./AdminUserCombobox";
import type {
  AdminMembershipRow,
  MembershipRole,
  MembershipStatus,
  Workspace,
} from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import {
  membershipRoleLabel,
  membershipStatusLabel,
  workspaceStatusLabel,
} from "../../lib/statusMaps";
import "./admin.css";

const ROLE_OPTIONS: MembershipRole[] = [
  "STUDENT",
  "LECTURER",
  "OPERATOR",
  "DATA_APPROVER",
];
const STATUS_FILTER_OPTIONS: MembershipStatus[] = ["ACTIVE", "REVOKED"];

/**
 * Man "Admin / Thanh vien lop" -- con cua "Admin / Quan ly lop"
 * (AdminWorkspacesPage.tsx): xem + gan ai la Giang vien, ai la Sinh vien
 * (hoac Operator/Data Approver) trong 1 workspace cu the, va thu hoi/mo
 * lai 1 thanh vien -- Yen yeu cau 2026-10-29.
 */
export function AdminWorkspaceMembersPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();
  const [workspace, setWorkspace] = useState<Workspace | null | undefined>(undefined);
  const [rows, setRows] = useState<AdminMembershipRow[] | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedRole, setSelectedRole] = useState<MembershipRole>("STUDENT");
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [pendingMembershipId, setPendingMembershipId] = useState<string | null>(null);
  const [memberQuery, setMemberQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<MembershipRole | "">("");
  const [statusFilter, setStatusFilter] = useState<MembershipStatus | "">("");

  // Tim theo ten/email/MSSV cua thanh vien -- Yen yeu cau 2026-10-29, dat
  // ngay tren bang thanh vien. Giang vien van luon dung dau (sort truoc,
  // loc sau) de khong mat vi tri uu tien khi dang go tim kiem. Dat TRUOC
  // early-return "khong tim thay lop" o duoi de khong vi pham
  // rules-of-hooks (hook phai goi theo dung thu tu moi lan render).
    const sortedAndFilteredRows = useMemo(() => {
    const normalizedMemberQuery = memberQuery.trim().toLowerCase();

    return (rows ?? [])
      .filter((row) => {
        const matchesQuery =
          normalizedMemberQuery.length === 0 ||
          row.user.display_name.toLowerCase().includes(normalizedMemberQuery) ||
          (row.user.email_normalized ?? "").toLowerCase().includes(normalizedMemberQuery) ||
          (row.user.student_id ?? "").toLowerCase().includes(normalizedMemberQuery);

        // Loc theo vai tro + trang thai -- Yen yeu cau 2026-10-29, dat canh o tim kiem.
        const matchesRole = roleFilter === "" || row.membership.roles.includes(roleFilter);
        const matchesStatus = statusFilter === "" || row.membership.status === statusFilter;

        return matchesQuery && matchesRole && matchesStatus;
      })
      .sort((a, b) => {
        const aIsLecturer = a.membership.roles.includes("LECTURER") ? 0 : 1;
        const bIsLecturer = b.membership.roles.includes("LECTURER") ? 0 : 1;
        if (aIsLecturer !== bIsLecturer) return aIsLecturer - bIsLecturer;
        // Cung nhom (deu la GV hoac deu la SV) thi sap theo ten -- Yen
        // yeu cau 2026-10-29, de de tim 1 sinh vien trong danh sach dai.
        return a.user.display_name.localeCompare(b.user.display_name, "vi");
      });
  }, [rows, memberQuery, roleFilter, statusFilter]);

  function reloadMembers() {
    if (!workspaceId) return;
    getWorkspaceMembers(workspaceId).then(setRows);
  }

  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;

    getWorkspaceById(workspaceId).then((data) => {
      if (!cancelled) setWorkspace(data ?? null);
    });
    getWorkspaceMembers(workspaceId).then((data) => {
      if (!cancelled) setRows(data);
    });

    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  if (workspace === null) {
    return (
      <section className="panel">
        <p className="panel__hint">Không tìm thấy lớp này.</p>
        <button className="link-button" onClick={() => navigate("/admin/workspaces")}>
          Quay lại danh sách lớp
        </button>
      </section>
    );
  }

  function handleCancelAddMember() {
    setIsFormOpen(false);
    setSelectedUserId("");
    setSelectedRole("STUDENT");
    setErrorMessage(null);
  }

  async function handleAddMember() {
    if (!workspaceId || !selectedUserId) return;

    setIsSaving(true);
    setErrorMessage(null);
    try {
      await addWorkspaceMember(workspaceId, selectedUserId, selectedRole);
      setSelectedUserId("");
      setSelectedRole("STUDENT");
      setIsFormOpen(false);
      reloadMembers();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Có lỗi xảy ra.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleToggleMembership(row: AdminMembershipRow) {
    const nextStatus = row.membership.status === "REVOKED" ? "ACTIVE" : "REVOKED";
    const confirmMessage =
      nextStatus === "REVOKED"
        ? `Thu hồi quyền của "${row.user.display_name}" trong lớp này?`
        : `Khôi phục quyền của "${row.user.display_name}" trong lớp này?`;
    if (!window.confirm(confirmMessage)) return;

    setPendingMembershipId(row.membership._id);
    try {
      await setMembershipStatus(row.membership._id, nextStatus);
      reloadMembers();
    } finally {
      setPendingMembershipId(null);
    }
  }

  const status = workspace ? workspaceStatusLabel[workspace.status] : null;

  return (
    <section className="panel">
      <nav className="breadcrumb" aria-label="breadcrumb">
        <Link to="/admin/workspaces">Quản lý lớp</Link>
        <span aria-hidden="true"> &gt; </span>
        <span>{workspace?.name ?? "..."}</span>
      </nav>

      <div className="panel__header">
        <div>
          <h1 className="panel__title">Thành viên lớp</h1>
          {workspace && status && (
            <p className="panel__subtitle">
              {workspace.workspace_key} · {status.label}
            </p>
          )}
        </div>
        <button type="button" className="btn-primary" onClick={() => setIsFormOpen(true)}>
          + Thêm thành viên
        </button>
      </div>

      {isFormOpen && (
        <div className="modal-overlay" role="presentation">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-member-modal-title"
          >
            <div className="modal__header">
              <h2 id="add-member-modal-title" className="modal__title">
                Thêm thành viên
              </h2>
              <button
                type="button"
                className="modal__close"
                aria-label="Đóng"
                onClick={handleCancelAddMember}
              >
                ×
              </button>
            </div>

            <label className="modal__field">
              <span className="modal__label">Người dùng</span>
              <AdminUserCombobox
                users={mockUsers}
                value={selectedUserId}
                onChange={setSelectedUserId}
              />
            </label>
            <label className="modal__field">
              <span className="modal__label">Vai trò</span>
              <select
                className="modal__select"
                value={selectedRole}
                onChange={(event) => setSelectedRole(event.target.value as MembershipRole)}
              >
                {ROLE_OPTIONS.map((role) => (
                  <option key={role} value={role}>
                    {membershipRoleLabel[role]}
                  </option>
                ))}
              </select>
            </label>

            {errorMessage && <p className="panel__hint admin-users__error">{errorMessage}</p>}

            <div className="admin-workspaces__form-actions">
              <button type="button" className="btn-secondary" onClick={handleCancelAddMember}>
                Huỷ
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={!selectedUserId || isSaving}
                onClick={handleAddMember}
              >
                {isSaving ? "Đang thêm..." : "Thêm thành viên"}
              </button>
            </div>
          </div>
        </div>
      )}

      {rows === null && <p className="panel__hint">Đang tải...</p>}

      {rows !== null && rows.length === 0 && (
        <p className="panel__hint">Lớp này chưa có thành viên nào.</p>
      )}

      {rows !== null && rows.length > 0 && (
        <>
          <div className="admin-users__filters">
            <input
              className="search-input"
              type="search"
              placeholder="Tìm theo tên, email hoặc MSSV"
              value={memberQuery}
              onChange={(event) => setMemberQuery(event.target.value)}
              aria-label="Tìm thành viên theo tên, email hoặc MSSV"
            />
            <select
              className="admin-users__status-select"
              value={roleFilter}
              onChange={(event) => setRoleFilter(event.target.value as MembershipRole | "")}
              aria-label="Lọc theo vai trò"
            >
              <option value="">Tất cả vai trò</option>
              {ROLE_OPTIONS.map((role) => (
                <option key={role} value={role}>
                  {membershipRoleLabel[role]}
                </option>
              ))}
            </select>
            <select
              className="admin-users__status-select"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as MembershipStatus | "")}
              aria-label="Lọc theo trạng thái"
            >
              <option value="">Tất cả trạng thái</option>
              {STATUS_FILTER_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {membershipStatusLabel[status].label}
                </option>
              ))}
            </select>
          </div>

          {sortedAndFilteredRows.length === 0 && (
            <p className="panel__hint">Không tìm thấy thành viên phù hợp.</p>
          )}

          {sortedAndFilteredRows.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Người dùng</th>
              <th>Vai trò</th>
              <th>Trạng thái</th>
              <th className="admin-users__action-cell"></th>
            </tr>
          </thead>
          <tbody>
            {/* Giang vien dung dau danh sach -- Yen yeu cau 2026-10-29, de
                de thay ai la nguoi phu trach lop truoc khi xem tiep danh
                sach sinh vien -- gio nam trong sortedAndFilteredRows (gop
                ca tim kiem, Yen yeu cau them 2026-10-29). */}
            {sortedAndFilteredRows.map((row) => {
              const membershipStatus = membershipStatusLabel[row.membership.status];
              const isLecturer = row.membership.roles.includes("LECTURER");
              return (
                <tr key={row.membership._id}>
                  <td>
                    <span className="admin-users__identity">
                      <span className="admin-users__name">{row.user.display_name}</span>
                      <span className="admin-users__email">
                        {row.user.email_normalized ?? "—"}
                      </span>
                    </span>
                  </td>
                  <td>
                    <span className={isLecturer ? "admin-members__role--lecturer" : undefined}>
                      {row.membership.roles.map((role) => membershipRoleLabel[role]).join(", ")}
                    </span>
                  </td>
                  <td>
                    <StatusBadge label={membershipStatus.label} tone={membershipStatus.tone} />
                  </td>
                  <td className="admin-users__action-cell">
                    <button
                      type="button"
                      className="btn-secondary admin-users__toggle-btn"
                      disabled={pendingMembershipId === row.membership._id}
                      onClick={() => handleToggleMembership(row)}
                    >
                      {pendingMembershipId === row.membership._id
                        ? "Đang lưu..."
                        : row.membership.status === "REVOKED"
                          ? "Khôi phục"
                          : "Thu hồi"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
          )}
        </>
      )}
    </section>
  );
}
