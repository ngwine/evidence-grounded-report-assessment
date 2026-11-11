import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AdminSubNav } from "./AdminSubNav";
import { createWorkspace, getAllWorkspacesAdmin, setWorkspaceStatus } from "../../lib/api";
import type {
  AdminWorkspaceRow,
  WorkspaceKind,
  WorkspaceStatus,
} from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { workspaceStatusLabel } from "../../lib/statusMaps";
import "./admin.css";

const KIND_OPTIONS: { value: WorkspaceKind; label: string }[] = [
  { value: "COURSE", label: "Lớp học phần (COURSE)" },
  { value: "RESEARCH", label: "Nhóm nghiên cứu (RESEARCH)" },
];

/**
 * Man "Admin / Quan ly lop" -- danh sach TOAN BO workspace trong he thong
 * (khac "Lecturer / Class": man do chi hien workspace ma CHINH giang vien
 * dang dang nhap co membership) + tao lop moi + dong/mo lai 1 lop.
 *
 * Yen yeu cau 2026-10-29: "quan ly danh sach lop/workspace" nen la man
 * dau tien cua Admin, truoc ca "Quan ly tai khoan" -- chua co UC/FR nao
 * ghi ro ai tao workspace (xem ghi chu GIA DINH tren AdminWorkspaceRow,
 * lib/types.ts), tam gan cho Admin theo UC-11.
 */
export function AdminWorkspacesPage() {
  const [rows, setRows] = useState<AdminWorkspaceRow[] | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [workspaceKey, setWorkspaceKey] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState<WorkspaceKind>("COURSE");
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [pendingWorkspaceId, setPendingWorkspaceId] = useState<string | null>(null);

  function reload() {
    getAllWorkspacesAdmin().then(setRows);
  }

  useEffect(() => {
    reload();
  }, []);

  const canSubmit = useMemo(
    () => workspaceKey.trim().length > 0 && name.trim().length > 0,
    [workspaceKey, name],
  );

  function resetForm() {
    setWorkspaceKey("");
    setName("");
    setKind("COURSE");
    setErrorMessage(null);
  }

  function handleCancelCreate() {
    setIsFormOpen(false);
    resetForm();
  }

  async function handleCreate() {
    if (!canSubmit) return;

    setIsSaving(true);
    setErrorMessage(null);
    try {
      await createWorkspace({ workspace_key: workspaceKey.trim(), name: name.trim(), kind });
      resetForm();
      setIsFormOpen(false);
      reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Có lỗi xảy ra.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleToggleWorkspaceStatus(row: AdminWorkspaceRow) {
    const nextStatus: WorkspaceStatus = row.status === "ARCHIVED" ? "ACTIVE" : "ARCHIVED";
    const confirmMessage =
      nextStatus === "ARCHIVED"
        ? `Đóng lớp "${row.name}"? Giảng viên/sinh viên trong lớp này sẽ không nộp/chấm báo cáo mới được nữa.`
        : `Mở lại lớp "${row.name}"?`;
    if (!window.confirm(confirmMessage)) return;

    setPendingWorkspaceId(row._id);
    try {
      await setWorkspaceStatus(row._id, nextStatus);
      reload();
    } finally {
      setPendingWorkspaceId(null);
    }
  }

  return (
    <section className="panel">
      <AdminSubNav active="workspaces" />

      <div className="panel__header">
        <div>
          <h1 className="panel__title">Quản lý lớp</h1>
          <p className="panel__subtitle">
            Toàn bộ lớp (workspace) trong hệ thống — tạo lớp mới, đóng/mở lại,
            và gán ai là giảng viên, ai là sinh viên trong từng lớp.
          </p>
        </div>
        <button type="button" className="btn-primary" onClick={() => setIsFormOpen(true)}>
          + Tạo lớp
        </button>
      </div>

      {isFormOpen && (
        <div className="modal-overlay" role="presentation">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-workspace-modal-title"
          >
            <div className="modal__header">
              <h2 id="create-workspace-modal-title" className="modal__title">
                Tạo lớp mới
              </h2>
              <button
                type="button"
                className="modal__close"
                aria-label="Đóng"
                onClick={handleCancelCreate}
              >
                ×
              </button>
            </div>

            <label className="modal__field">
              <span className="modal__label">Mã lớp</span>
              <input
                className="modal__select"
                value={workspaceKey}
                onChange={(event) => setWorkspaceKey(event.target.value)}
                placeholder="VD: MAD-2026-2027"
              />
            </label>
            <label className="modal__field">
              <span className="modal__label">Tên lớp</span>
              <input
                className="modal__select"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="VD: Mobile Apps Development"
              />
            </label>
            <label className="modal__field">
              <span className="modal__label">Loại</span>
              <select
                className="modal__select"
                value={kind}
                onChange={(event) => setKind(event.target.value as WorkspaceKind)}
              >
                {KIND_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            {errorMessage && <p className="panel__hint admin-users__error">{errorMessage}</p>}

            <div className="admin-workspaces__form-actions">
              <button type="button" className="btn-secondary" onClick={handleCancelCreate}>
                Huỷ
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={!canSubmit || isSaving}
                onClick={handleCreate}
              >
                {isSaving ? "Đang tạo..." : "Tạo lớp"}
              </button>
            </div>
          </div>
        </div>
      )}

      {rows === null && <p className="panel__hint">Đang tải...</p>}

      {rows !== null && rows.length === 0 && (
        <p className="panel__hint">Hệ thống chưa có lớp nào.</p>
      )}

      {rows !== null && rows.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Lớp</th>
              <th>Loại</th>
              <th>Thành viên</th>
              <th>Trạng thái</th>
              <th className="admin-users__action-cell"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const status = workspaceStatusLabel[row.status];
              return (
                <tr key={row._id}>
                  <td>
                    <Link className="link-button" to={`/admin/workspaces/${row._id}`}>
                      {row.name}
                    </Link>
                    <div className="admin-users__email">{row.workspace_key}</div>
                  </td>
                  <td>{row.kind === "COURSE" ? "Lớp học phần" : "Nhóm nghiên cứu"}</td>
                  <td>{row.memberCount}</td>
                  <td>
                    <StatusBadge label={status.label} tone={status.tone} />
                  </td>
                  <td className="admin-users__action-cell">
                    <button
                      type="button"
                      className="btn-secondary admin-users__toggle-btn"
                      disabled={pendingWorkspaceId === row._id}
                      onClick={() => handleToggleWorkspaceStatus(row)}
                    >
                      {pendingWorkspaceId === row._id
                        ? "Đang lưu..."
                        : row.status === "ARCHIVED"
                          ? "Mở lại"
                          : "Đóng lớp"}
                    </button>
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
