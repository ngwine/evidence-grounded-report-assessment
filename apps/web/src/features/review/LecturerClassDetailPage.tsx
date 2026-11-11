import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  getListStatus,
  getRubricsInWorkspace,
  getStudentReportsInWorkspace,
  getWorkspaceById,
} from "../../lib/api";
import type {
  ReportListStatus,
  Rubric,
  StudentReportsRow,
  Workspace,
} from "../../lib/types";
import { formatDateTime } from "../../lib/format";
import { reportListStatusLabel, workspaceStatusLabel } from "../../lib/statusMaps";
import { StudentReportsTable } from "./StudentReportsTable";
import "./review.css";

const STATUS_FILTER_OPTIONS: ReportListStatus[] = [
  "SUBMITTED",
  "PROCESSING",
  "PUBLISHED",
  "ERROR",
];

/**
 * Man "Lecturer / Class Detail" theo wireframe gui ngay 2026-10-16 (chi
 * tham khao UI) -- ve mat ky thuat day la danh sach sinh vien
 * (membership role=STUDENT) trong 1 Workspace, kem toan bo bao cao cua
 * tung sinh vien -- xem features/review/StudentReportsTable.tsx.
 *
 * Khac man Student (mo rong 1 bao cao -> thay cac phien ban), man nay
 * mo rong 1 SINH VIEN -> thay danh sach cac bao cao (document) khac nhau
 * ma sinh vien do da nop trong lop.
 *
 * Nut "+ Tao rubric": `rubrics` co field `workspace_id` tu dau
 * (data-dictionary.md muc 8.1) nen 1 rubric von gan theo 1 lop -- dung
 * de giang vien dinh nghia rubric cham diem cho lop nay. Dan toi man tao
 * rubric rieng (features/rubrics/RubricCreatePage.tsx).
 */
export function LecturerClassDetailPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();
  const [workspace, setWorkspace] = useState<Workspace | null | undefined>(undefined);
  const [rows, setRows] = useState<StudentReportsRow[] | null>(null);
  // Danh sach rubric da tao cho lop nay -- Yen phan anh 2026-10-25 la bam
  // "Xac nhan hoan tat" o man Tao rubric xong khong thay gi khac tren man
  // hinh, tuong nhu chua luu; them khu vuc nay de GV xac nhan truc quan.
  const [rubrics, setRubrics] = useState<Rubric[] | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<ReportListStatus | "">("");

  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;

    getWorkspaceById(workspaceId).then((data) => {
      if (!cancelled) setWorkspace(data ?? null);
    });
    getStudentReportsInWorkspace(workspaceId).then((data) => {
      if (!cancelled) setRows(data);
    });
    getRubricsInWorkspace(workspaceId).then((data) => {
      if (!cancelled) setRubrics(data);
    });

    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return (rows ?? []).filter((row) => {
      const matchesQuery =
        normalizedQuery.length === 0 ||
        row.student.display_name.toLowerCase().includes(normalizedQuery) ||
        (row.student.student_id ?? "").toLowerCase().includes(normalizedQuery);

      // "Co bao cao nao dang o trang thai nay khong" -- khong con khai niem
      // "trang thai dai dien" cho ca sinh vien nua (xem StudentReportsTable)
      const matchesStatus =
        statusFilter === "" ||
        row.documents.some((document) => {
          const version = document.versions[0];
          return version ? getListStatus(version) === statusFilter : false;
        });

      return matchesQuery && matchesStatus;
    });
  }, [rows, query, statusFilter]);

  if (workspace === null) {
    return (
      <section className="panel">
        <p className="panel__hint">
          Không tìm thấy lớp này, hoặc bạn không có quyền xem.
        </p>
        <button className="link-button" onClick={() => navigate("/lecturer/workspaces")}>
          Quay lại danh sách lớp
        </button>
      </section>
    );
  }

  const status = workspace ? workspaceStatusLabel[workspace.status] : null;

  return (
    <section className="panel">
      <nav className="breadcrumb" aria-label="breadcrumb">
        <Link to="/lecturer/workspaces">Các lớp</Link>
        <span aria-hidden="true"> &gt; </span>
        <span>{workspace?.name ?? "..."}</span>
      </nav>

      <div className="panel__header">
        <div>
          <h1 className="panel__title">Chi tiết lớp</h1>
          {workspace && status && (
            <p className="panel__subtitle">
              {workspace.workspace_key} · {status.label}
            </p>
          )}
        </div>
        {/* UC-15 "Quan ly nguon doi chieu" -- SUA LAI 2026-10-29: chuyen
            tu Admin ve day, vi actor dung theo bo-use-case.md la Giang
            vien (xem ghi chu CorpusSource, lib/types.ts). */}
        <button
          type="button"
          className="btn-secondary"
          onClick={() => navigate(`/lecturer/workspaces/${workspaceId}/corpus`)}
        >
          Nguồn đối chiếu
        </button>
      </div>

      {/* Nut "+ Tao rubric" doi vao ngay canh tieu de "Rubric cua lop" (thay
          vi o tren cung) -- Yen yeu cau 2026-10-26, vi no la hanh dong lien
          quan truc tiep toi muc rubric, de o panel__header de GV de nham
          lien quan toi bang bao cao ben duoi. */}
      <div className="panel__section-header">
        <h2 className="panel__section-title">Rubric của lớp</h2>
        <button
          type="button"
          className="btn-primary"
          onClick={() => navigate(`/lecturer/workspaces/${workspaceId}/rubrics/new`)}
        >
          + Tạo rubric
        </button>
      </div>

      {rubrics === null && <p className="panel__hint">Đang tải...</p>}

      {rubrics !== null && rubrics.length === 0 && (
        <div className="rubric-list__item rubric-list__item--empty">
          Chưa có rubric
        </div>
      )}

      {rubrics !== null && rubrics.length > 0 && (
        <ul className="rubric-list">
          {rubrics.map((rubric) => (
            <li className="rubric-list__item" key={rubric._id}>
              <Link
                className="rubric-list__link"
                to={`/lecturer/workspaces/${workspaceId}/rubrics/${rubric._id}`}
              >
                {rubric.title}
              </Link>
              <span className="rubric-list__created-at">
                Tạo lúc {formatDateTime(rubric.created_at)}
              </span>
            </li>
          ))}
        </ul>
      )}

      <h2 className="panel__section-title">Báo cáo của lớp</h2>

      {/* Tim SV + loc trang thai -- doi xuong ngay tren bang danh sach bao
          cao, vi 2 o nay chi loc du lieu bang nay, de o tren cung (canh nut
          "+ Tao rubric") de GV hieu lam la lien quan toi rubric -- Yen
          phan anh 2026-10-26. */}
      <div className="class-detail__filters">
        <input
          className="search-input"
          type="search"
          placeholder="Tìm theo tên hoặc MSSV"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Tìm theo tên hoặc MSSV"
        />
        <select
          className="class-detail__status-select"
          value={statusFilter}
          onChange={(event) =>
            setStatusFilter(event.target.value as ReportListStatus | "")
          }
          aria-label="Lọc theo trạng thái"
        >
          <option value="">Tất cả trạng thái</option>
          {STATUS_FILTER_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {reportListStatusLabel[value].label}
            </option>
          ))}
        </select>
      </div>

      {rows === null && <p className="panel__hint">Đang tải...</p>}

      {rows !== null && filteredRows.length === 0 && (
        <p className="panel__hint">
          {rows.length === 0
            ? "Lớp này chưa có sinh viên nào."
            : "Không tìm thấy sinh viên/báo cáo phù hợp."}
        </p>
      )}

      {filteredRows.length > 0 && <StudentReportsTable rows={filteredRows} />}
    </section>
  );
}
