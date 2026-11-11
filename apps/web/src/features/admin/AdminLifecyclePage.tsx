import { useEffect, useState } from "react";
import { AdminSubNav } from "./AdminSubNav";
import {
  archiveDocumentLifecycle,
  getDataLifecycleRows,
  purgeDocumentLifecycle,
  restoreDocumentLifecycle,
} from "../../lib/api";
import type { AdminLifecycleRow } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { dataLifecycleStateLabel } from "../../lib/statusMaps";
import { formatDateTime } from "../../lib/format";
import "./admin.css";

/**
 * Man "Admin / Quan ly vong doi du lieu" (UC-17, actor "Giang vien, Quan
 * tri vien duoc uy quyen") -- ban DEMO theo yeu cau "lam thu xem" cua
 * Yen (2026-10-29).
 *
 * 3 trang thai vong doi (xem DataLifecycleState, lib/types.ts):
 * ACTIVE (dang dung) -> ARCHIVED (luu tru, co the khoi phuc) -> TOMBSTONED
 * (xoa vinh vien, KHONG the hoan tac trong demo nay). Day la mock HOAN
 * TOAN, chua xoa du lieu thuc (document van con trong mockDocuments de
 * khong lam vo cac man khac dang tham chieu toi) -- can Quy xac nhan lai
 * quy trinh thuc (vd co can "giu lai X ngay truoc khi xoa thuc" khong).
 */
export function AdminLifecyclePage() {
  const [rows, setRows] = useState<AdminLifecycleRow[] | null>(null);
  const [pendingDocumentId, setPendingDocumentId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  function reload() {
    getDataLifecycleRows().then(setRows);
  }

  useEffect(() => {
    reload();
  }, []);

  async function handleArchive(row: AdminLifecycleRow) {
    if (!window.confirm(`Lưu trữ báo cáo "${row.documentTitle}" (${row.ownerName})?`)) return;

    setErrorMessage(null);
    setPendingDocumentId(row.documentId);
    try {
      await archiveDocumentLifecycle(row.documentId);
      reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Có lỗi xảy ra.");
    } finally {
      setPendingDocumentId(null);
    }
  }

  async function handleRestore(row: AdminLifecycleRow) {
    setErrorMessage(null);
    setPendingDocumentId(row.documentId);
    try {
      await restoreDocumentLifecycle(row.documentId);
      reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Có lỗi xảy ra.");
    } finally {
      setPendingDocumentId(null);
    }
  }

  async function handlePurge(row: AdminLifecycleRow) {
    if (
      !window.confirm(
        `Xoá VĨNH VIỄN báo cáo "${row.documentTitle}" (${row.ownerName})? Hành động này KHÔNG THỂ hoàn tác.`,
      )
    ) {
      return;
    }

    setErrorMessage(null);
    setPendingDocumentId(row.documentId);
    try {
      await purgeDocumentLifecycle(row.documentId);
      reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Có lỗi xảy ra.");
    } finally {
      setPendingDocumentId(null);
    }
  }

  return (
    <section className="panel">
      <AdminSubNav active="lifecycle" />

      <div className="panel__header">
        <div>
          <h1 className="panel__title">Quản lý vòng đời dữ liệu</h1>
          <p className="panel__subtitle">
            Lưu trữ / khôi phục / xoá vĩnh viễn báo cáo. (Bản demo minh hoạ UI,
            chưa nối backend thật.)
          </p>
        </div>
      </div>

      {errorMessage && <p className="panel__hint admin-users__error">{errorMessage}</p>}

      {rows === null && <p className="panel__hint">Đang tải...</p>}

      {rows !== null && rows.length === 0 && (
        <p className="panel__hint">Hệ thống chưa có báo cáo nào.</p>
      )}

      {rows !== null && rows.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Báo cáo</th>
              <th>Phiên bản</th>
              <th>Lớp</th>
              <th>Trạng thái</th>
              <th>Lưu trữ lúc</th>
              <th className="admin-users__action-cell"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const statusChip = dataLifecycleStateLabel[row.state];
              const isPending = pendingDocumentId === row.documentId;

              return (
                <tr key={row.documentId}>
                  <td>
                    <span className="admin-users__identity">
                      <span className="admin-users__name">{row.documentTitle}</span>
                      {/* Chi hien nguoi nop -- xem giai thich o AdminJobsPage.tsx
                          (document_key la id noi bo, khong can show ra UI). */}
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
                  <td>
                    <StatusBadge label={statusChip.label} tone={statusChip.tone} />
                  </td>
                  <td>{row.archivedAt ? formatDateTime(row.archivedAt) : "—"}</td>
                  <td className="admin-users__action-cell">
                    {row.state === "ACTIVE" && (
                      <button
                        type="button"
                        className="btn-secondary admin-users__toggle-btn"
                        disabled={isPending}
                        onClick={() => handleArchive(row)}
                      >
                        {isPending ? "Đang lưu..." : "Lưu trữ"}
                      </button>
                    )}
                    {row.state === "ARCHIVED" && (
                      <>
                        <button
                          type="button"
                          className="btn-secondary admin-users__toggle-btn"
                          disabled={isPending}
                          onClick={() => handleRestore(row)}
                        >
                          Khôi phục
                        </button>{" "}
                        <button
                          type="button"
                          className="btn-secondary admin-users__toggle-btn admin-lifecycle__purge-btn"
                          disabled={isPending}
                          onClick={() => handlePurge(row)}
                        >
                          Xoá vĩnh viễn
                        </button>
                      </>
                    )}
                    {row.state === "TOMBSTONED" && (
                      <span className="admin-users__email">Đã xoá vĩnh viễn</span>
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
