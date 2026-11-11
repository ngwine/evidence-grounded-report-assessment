import { Fragment, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { ReportListStatus, StudentReportsRow } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { reportListStatusLabel } from "../../lib/statusMaps";
import { getListStatus, getListStatusChip } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import "./review.css";

interface StudentReportsTableProps {
  rows: StudentReportsRow[];
}

const COUNT_COLUMNS: ReportListStatus[] = [
  "SUBMITTED",
  "PROCESSING",
  "PUBLISHED",
  "ERROR",
];

/** Dem so bao cao cua 1 sinh vien theo tung trang thai (lay trang thai cua VERSION MOI NHAT trong moi document -- 1 document tinh 1 lan, khong tinh lich su cac version cu). Trang thai lay tu getListStatus (lib/api.ts), duoc suy ra tu pipeline progress thuc te, khong con doc field tinh san. */
function countByStatus(row: StudentReportsRow): Record<ReportListStatus, number> {
  const counts: Record<ReportListStatus, number> = {
    SUBMITTED: 0,
    PROCESSING: 0,
    PUBLISHED: 0,
    ERROR: 0,
  };
  for (const document of row.documents) {
    const version = document.versions[0];
    if (version) counts[getListStatus(version)] += 1;
  }
  return counts;
}

/**
 * Bang "Bao cao cua lop" trong man Lecturer / Class Detail -- moi dong la
 * 1 SINH VIEN (khac man Student: moi dong la 1 bao cao). Dong cha hien
 * SO LUONG bao cao theo tung trang thai (khong chon 1 bao cao "dai dien"
 * -- 1 sinh vien co the co nhieu bao cao KHAC NHAU, khong co tieu chi hop
 * ly nao de chon cai nao dai dien cho ca sinh vien do). Mo rong ra moi
 * thay danh sach tung bao cao cu the ho da nop.
 */
export function StudentReportsTable({ rows }: StudentReportsTableProps) {
  const navigate = useNavigate();
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  function toggle(studentId: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(studentId)) next.delete(studentId);
      else next.add(studentId);
      return next;
    });
  }

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Sinh viên</th>
          {COUNT_COLUMNS.map((status) => (
            <th key={status} className="student-row__count-header">
              {reportListStatusLabel[status].label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const studentId = row.student._id;
          const isExpanded = expandedIds.has(studentId);
          const canExpand = row.documents.length > 0;
          const counts = countByStatus(row);

          return (
            <Fragment key={studentId}>
              <tr
                className={canExpand ? "data-table__row--clickable" : undefined}
                onClick={canExpand ? () => toggle(studentId) : undefined}
              >
                <td>
                  <span className="student-row__name-cell">
                    {canExpand && (
                      <span className="doc-row__chevron" aria-hidden="true">
                        {isExpanded ? "▼" : "▶"}
                      </span>
                    )}
                    {!canExpand && <span className="doc-row__chevron-spacer" />}
                    <span className="student-row__identity">
                      <span className="student-row__name">
                        {row.student.display_name}{" "}
                        <span className="doc-row__count">
                          ({row.documents.length} báo cáo)
                        </span>
                      </span>
                      <span className="student-row__student-id">
                        MSSV: {row.student.student_id ?? "—"}
                      </span>
                    </span>
                  </span>
                </td>
                {COUNT_COLUMNS.map((status) => (
                  <td key={status} className="student-row__count-cell">
                    {counts[status] > 0 ? counts[status] : <span className="student-row__count-zero">–</span>}
                  </td>
                ))}
              </tr>

              {isExpanded &&
                row.documents.map((document) => {
                  const version = document.versions[0];
                  // Chip phu thuoc vao man "Lecturer / Report" (pipeline) --
                  // xem getListStatusChip trong lib/api.ts, khong doc thang
                  // lecturer_display_status nua.
                  const status = version ? getListStatusChip(version) : null;
                  const reportPath = `/lecturer/workspaces/${document.workspace_id}/documents/${document._id}`;
                  return (
                    <tr
                      key={document._id}
                      className="doc-row__version-row data-table__row--clickable"
                      onClick={() => navigate(reportPath)}
                    >
                      <td colSpan={COUNT_COLUMNS.length + 1} className="doc-row__version-title">
                        <span className="student-row__version-content">
                          <span className="student-row__status-slot">
                            {status && <StatusBadge label={status.label} tone={status.tone} />}
                          </span>
                          <Link
                            className="link-cell student-row__report-title"
                            to={reportPath}
                            onClick={(event) => event.stopPropagation()}
                          >
                            {/* Ten FILE thuc te (original_filename cua version MOI NHAT),
                                KHONG dung document.title -- Yen phat hien 2026-10-24:
                                title chi la field luu luc TAO document (vd "baocao_cuoiky"),
                                khong theo kip ten file SV doi khi nop lai (vd
                                "BaoCao_CuoiKy_v3_sua_loi.docx") -- dung chung 1 cach hien thi
                                voi man Sinh vien tu xem (xem DocumentVersionsTable.tsx). */}
                            {version?.original_filename ?? document.title}
                          </Link>
                          {version && (
                            <span className="student-row__report-meta">
                              v{version.version_no} · {formatDateTime(version.submitted_at)}
                            </span>
                          )}
                        </span>
                      </td>
                    </tr>
                  );
                })}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}
