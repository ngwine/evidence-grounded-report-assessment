import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getMyWorkspaces } from "../../lib/api";
import type { MyWorkspaceRow } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { workspaceStatusLabel } from "../../lib/statusMaps";
import "./workspaces.css";

/**
 * Man "Student / Class" theo wireframe W2.4 (chi tham khao UI) -- ve mat
 * ky thuat day la danh sach Workspace (kind=COURSE) cua sinh vien, route
 * va API deu dung "workspace" theo data-dictionary.md.
 */
export function WorkspaceListPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<MyWorkspaceRow[] | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    getMyWorkspaces().then((data) => {
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
            ? "Bạn chưa có lớp nào."
            : "Không tìm thấy lớp phù hợp."}
        </p>
      )}

      {filteredRows.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Mã lớp</th>
              <th>Tên lớp</th>
              <th>Giảng viên</th>
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
                  onClick={() => navigate(`/workspaces/${row._id}`)}
                >
                  <td>
                    <a
                      href={`/workspaces/${row._id}`}
                      onClick={(event) => event.preventDefault()}
                      className="link-cell"
                    >
                      {row.workspace_key}
                    </a>
                  </td>
                  <td>{row.name}</td>
                  <td>{row.lecturer_name}</td>
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
