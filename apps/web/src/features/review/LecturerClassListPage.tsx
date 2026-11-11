import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getMyLecturerWorkspaces } from "../../lib/api";
import type { LecturerWorkspaceRow } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { workspaceStatusLabel } from "../../lib/statusMaps";

/**
 * Man "Lecturer / Class" theo wireframe gui ngay 2026-10-16 (chi tham
 * khao UI) -- ve mat ky thuat day la danh sach Workspace (kind=COURSE)
 * ma giang vien hien tai co membership ACTIVE voi role LECTURER, kem so
 * bao cao dang cho duyet (assessment_proposals.status = READY_FOR_REVIEW)
 * trong tung workspace -- dung "workspace" xuyen suot theo data-dictionary.md,
 * giong cach man Student da lam (xem features/workspaces).
 *
 * Bam vao 1 dong se qua man "Lecturer / Class Detail" (xem
 * features/review/LecturerClassDetailPage.tsx).
 */
export function LecturerClassListPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<LecturerWorkspaceRow[] | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    getMyLecturerWorkspaces().then((data) => {
      if (!cancelled) setRows(data);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredRows = (rows ?? []).filter((row) =>
    row.name.toLowerCase().includes(query.trim().toLowerCase()),
  );

  return (
    <section className="panel">
      <h1 className="panel__title">Các lớp của bạn</h1>

      <input
        className="search-input"
        type="search"
        placeholder="Tìm lớp"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-label="Tìm lớp"
      />

      {rows === null && <p className="panel__hint">Đang tải danh sách lớp...</p>}

      {rows !== null && filteredRows.length === 0 && (
        <p className="panel__hint">
          {rows.length === 0
            ? "Bạn chưa quản lý lớp nào."
            : "Không tìm thấy lớp phù hợp."}
        </p>
      )}

      {filteredRows.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Mã lớp</th>
              <th>Tên lớp</th>
              <th>Chờ duyệt</th>
              <th>Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => {
              const status = workspaceStatusLabel[row.status];
              return (
                <tr
                  key={row._id}
                  className="data-table__row--clickable"
                  onClick={() => navigate(`/lecturer/workspaces/${row._id}`)}
                >
                  <td>{row.workspace_key}</td>
                  <td>
                    <a
                      href={`/lecturer/workspaces/${row._id}`}
                      onClick={(event) => event.preventDefault()}
                      className="link-cell"
                    >
                      {row.name}
                    </a>
                  </td>
                  <td>{row.pending_review_count}</td>
                  <td>
                    <StatusBadge label={status.label} tone={status.tone} />
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
