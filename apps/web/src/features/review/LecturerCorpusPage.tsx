import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  createCorpusSource,
  getCorpusSourcesInWorkspace,
  getWorkspaceById,
  setCorpusSourceStatus,
} from "../../lib/api";
import type { CorpusSource, CorpusSourceStatus, CorpusSourceType, Workspace } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { corpusSourceStatusLabel, corpusSourceTypeLabel } from "../../lib/statusMaps";
import { formatDateTime } from "../../lib/format";
import "./review.css";

const TYPE_OPTIONS: { value: CorpusSourceType; label: string }[] = [
  { value: "INTERNAL_REPORT", label: corpusSourceTypeLabel.INTERNAL_REPORT },
  { value: "EXTERNAL_DOC", label: corpusSourceTypeLabel.EXTERNAL_DOC },
  { value: "WEB", label: corpusSourceTypeLabel.WEB },
];

const STATUS_FILTER_OPTIONS: CorpusSourceStatus[] = ["PENDING", "APPROVED", "REJECTED"];

/**
 * Man "Lecturer / Nguồn đối chiếu của lớp" (UC-15) -- SUA LAI 2026-10-29
 * (Yen phat hien): bo-use-case.md muc 7.9 ghi ro actor UC-15 la "Giang
 * vien" ("...dang ky source, version, checksum, license/consent,
 * purpose, retention va approver. Chi source APPROVED moi duoc index
 * hoac dung cho run."), KHONG phai Quan tri vien -- ban dau da lam sai o
 * man Admin (/admin/corpus), nay chuyen ve day va gan theo workspace_id.
 *
 * "Approver" trong tai lieu khop voi role DATA_APPROVER da co san trong
 * Membership.roles (data-dictionary.md muc 5.3, 1 vai tro THEO LOP) --
 * GIA DINH (demo): vi mock chi co 1 tai khoan Giang vien duy nhat, man
 * nay cho phep CHINH GV dang nhap vua dang ky vua duyet luon, thuc te
 * nen la 1 nguoi khac mang role DATA_APPROVER trong lop duyet, can Quy
 * xac nhan lai truoc khi lam API that.
 */
export function LecturerCorpusPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();
  const [workspace, setWorkspace] = useState<Workspace | null | undefined>(undefined);
  const [rows, setRows] = useState<CorpusSource[] | null>(null);
  const [statusFilter, setStatusFilter] = useState<CorpusSourceStatus | "">("");
  const [pendingSourceId, setPendingSourceId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState<CorpusSourceType>("INTERNAL_REPORT");
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function reload() {
    if (!workspaceId) return;
    getCorpusSourcesInWorkspace(workspaceId).then(setRows);
  }

  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;

    getWorkspaceById(workspaceId).then((data) => {
      if (!cancelled) setWorkspace(data ?? null);
    });
    getCorpusSourcesInWorkspace(workspaceId).then((data) => {
      if (!cancelled) setRows(data);
    });

    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const filteredRows = useMemo(() => {
    return (rows ?? []).filter((row) => statusFilter === "" || row.status === statusFilter);
  }, [rows, statusFilter]);

  function resetForm() {
    setTitle("");
    setSourceType("INTERNAL_REPORT");
    setFormError(null);
  }

  function handleCancelCreate() {
    setIsFormOpen(false);
    resetForm();
  }

  const canSubmit = useMemo(() => title.trim().length > 0, [title]);

  async function handleCreate() {
    if (!canSubmit || !workspaceId) return;

    setIsSaving(true);
    setFormError(null);
    try {
      await createCorpusSource({ workspace_id: workspaceId, title: title.trim(), sourceType });
      resetForm();
      setIsFormOpen(false);
      reload();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Có lỗi xảy ra.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDecide(row: CorpusSource, status: CorpusSourceStatus) {
    const confirmMessage =
      status === "APPROVED"
        ? `Duyệt nguồn "${row.title}" để dùng trong đối chiếu Similarity?`
        : `Từ chối nguồn "${row.title}"?`;
    if (!window.confirm(confirmMessage)) return;

    setErrorMessage(null);
    setPendingSourceId(row._id);
    try {
      await setCorpusSourceStatus(row._id, status);
      reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Có lỗi xảy ra.");
    } finally {
      setPendingSourceId(null);
    }
  }

  if (workspace === null) {
    return (
      <section className="panel">
        <p className="panel__hint">Không tìm thấy lớp này, hoặc bạn không có quyền xem.</p>
        <button className="link-button" onClick={() => navigate("/lecturer/workspaces")}>
          Quay lại danh sách lớp
        </button>
      </section>
    );
  }

  return (
    <section className="panel">
      <nav className="breadcrumb" aria-label="breadcrumb">
        <Link to="/lecturer/workspaces">Các lớp</Link>
        <span aria-hidden="true"> &gt; </span>
        <Link to={`/lecturer/workspaces/${workspaceId}`}>Chi tiết lớp</Link>
        <span aria-hidden="true"> &gt; </span>
        <span>Nguồn đối chiếu</span>
      </nav>

      <div className="panel__header">
        <div>
          <h1 className="panel__title">Nguồn đối chiếu của lớp</h1>
          <p className="panel__subtitle">
            Tài liệu dùng làm nguồn so khớp ở chặng Similarity — chỉ nguồn{" "}
            <strong>Đã duyệt</strong> mới được dùng khi phân tích.
          </p>
        </div>
        <button type="button" className="btn-primary" onClick={() => setIsFormOpen(true)}>
          + Thêm nguồn
        </button>
      </div>

      {isFormOpen && (
        <div className="modal-overlay" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="create-corpus-modal-title">
            <div className="modal__header">
              <h2 id="create-corpus-modal-title" className="modal__title">
                Thêm nguồn đối chiếu
              </h2>
              <button type="button" className="modal__close" aria-label="Đóng" onClick={handleCancelCreate}>
                ×
              </button>
            </div>

            <label className="modal__field">
              <span className="modal__label">Tên tài liệu / nguồn</span>
              <input
                className="modal__select"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="VD: Báo cáo KLTN khoá 2024"
              />
            </label>
            <label className="modal__field">
              <span className="modal__label">Loại nguồn</span>
              <select
                className="modal__select"
                value={sourceType}
                onChange={(event) => setSourceType(event.target.value as CorpusSourceType)}
              >
                {TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            {formError && <p className="panel__hint corpus-list__error">{formError}</p>}

            <div className="corpus-list__form-actions">
              <button type="button" className="btn-secondary" onClick={handleCancelCreate}>
                Huỷ
              </button>
              <button type="button" className="btn-primary" disabled={!canSubmit || isSaving} onClick={handleCreate}>
                {isSaving ? "Đang lưu..." : "Thêm nguồn"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="corpus-list__filters">
        <select
          className="corpus-list__status-select"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as CorpusSourceStatus | "")}
          aria-label="Lọc theo trạng thái"
        >
          <option value="">Tất cả trạng thái</option>
          {STATUS_FILTER_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {corpusSourceStatusLabel[value].label}
            </option>
          ))}
        </select>
      </div>

      {errorMessage && <p className="panel__hint corpus-list__error">{errorMessage}</p>}

      {rows === null && <p className="panel__hint">Đang tải...</p>}

      {rows !== null && filteredRows.length === 0 && (
        <p className="panel__hint">
          {rows.length === 0 ? "Lớp này chưa có nguồn đối chiếu nào." : "Không có nguồn phù hợp."}
        </p>
      )}

      {filteredRows.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Nguồn</th>
              <th>Loại</th>
              <th>Người đăng ký</th>
              <th>Ngày đăng ký</th>
              <th>Trạng thái</th>
              <th className="corpus-list__action-cell"></th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => {
              const statusChip = corpusSourceStatusLabel[row.status];
              const isPending = pendingSourceId === row._id;

              return (
                <tr key={row._id}>
                  <td>{row.title}</td>
                  <td>{corpusSourceTypeLabel[row.sourceType]}</td>
                  <td>{row.submittedByName}</td>
                  <td>{formatDateTime(row.submittedAt)}</td>
                  <td>
                    <StatusBadge label={statusChip.label} tone={statusChip.tone} />
                  </td>
                  <td className="corpus-list__action-cell">
                    {row.status === "PENDING" && (
                      <>
                        <button
                          type="button"
                          className="btn-secondary corpus-list__action-btn"
                          disabled={isPending}
                          onClick={() => handleDecide(row, "REJECTED")}
                        >
                          Từ chối
                        </button>{" "}
                        <button
                          type="button"
                          className="btn-primary corpus-list__action-btn"
                          disabled={isPending}
                          onClick={() => handleDecide(row, "APPROVED")}
                        >
                          Duyệt
                        </button>
                      </>
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
