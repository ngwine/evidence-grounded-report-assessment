import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import type { ReportDocumentWithVersions } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { documentStatusLabel } from "../../lib/statusMaps";
import { formatDateTime } from "../../lib/format";

interface DocumentVersionsTableProps {
  workspaceId: string;
  documents: ReportDocumentWithVersions[];
}

/**
 * Bang "Bao cao da nop", moi document la 1 dong co the mo rong de xem lai
 * cac phien ban (document_versions) da nop truoc do cua chinh document do.
 * Dong cha hien THONG TIN CUA PHIEN BAN MOI NHAT (versions[0], da sap xep
 * giam dan tu api.ts) tren TAT CA cac cot, ke ca ten hien thi -- khong
 * dung document.title (chi la field luu luc tao, khong dam bao phan anh
 * dung noi dung file hien tai) vi dong cha khong phai la "dai dien" rieng
 * cho document, no chi la 1 cach gon de xem phien ban moi nhat, mo rong ra
 * moi thay cac phien ban cu.
 */
export function DocumentVersionsTable({ workspaceId, documents }: DocumentVersionsTableProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  function toggle(documentId: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(documentId)) next.delete(documentId);
      else next.add(documentId);
      return next;
    });
  }

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Tiêu đề</th>
          <th>Ngày nộp</th>
          <th>Phiên bản</th>
          <th>Trạng thái</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {documents.map((doc) => {
          const latest = doc.versions[0];
          const isExpanded = expandedIds.has(doc._id);
          const canExpand = doc.versions.length > 1;
          const latestStatus = latest
            ? documentStatusLabel[latest.display_status]
            : null;

          return (
            <Fragment key={doc._id}>
              <tr
                key={doc._id}
                className={canExpand ? "data-table__row--clickable" : undefined}
                onClick={canExpand ? () => toggle(doc._id) : undefined}
              >
                <td>
                  <span className="doc-row__title">
                    {canExpand && (
                      <span className="doc-row__chevron" aria-hidden="true">
                        {isExpanded ? "▼" : "▶"}
                      </span>
                    )}
                    {!canExpand && <span className="doc-row__chevron-spacer" />}
                    {latest?.original_filename ?? doc.title}
                    {canExpand && (
                      <span className="doc-row__count">
                        ({doc.versions.length} phiên bản)
                      </span>
                    )}
                  </span>
                </td>
                <td>{latest ? formatDateTime(latest.submitted_at) : "-"}</td>
                <td>{latest?.version_no ?? "-"}</td>
                <td>
                  {latestStatus && (
                    <StatusBadge label={latestStatus.label} tone={latestStatus.tone} />
                  )}
                </td>
                <td onClick={(event) => event.stopPropagation()}>
                  {/* "Xem kết quả" -- man "Xem publication" (UC-09, CORE,
                      Sinh vien), chi hien khi phien ban MOI NHAT da cong
                      bo (DA_CO_KET_QUA) -- Yen yeu cau 2026-10-28. */}
                  {latest?.display_status === "DA_CO_KET_QUA" && (
                    <Link
                      className="link-button"
                      to={`/workspaces/${workspaceId}/documents/${doc._id}/publication`}
                    >
                      Xem kết quả
                    </Link>
                  )}
                </td>
              </tr>

              {isExpanded &&
                doc.versions.map((version) => {
                  const status = documentStatusLabel[version.display_status];
                  return (
                    <tr key={version._id} className="doc-row__version-row">
                      <td className="doc-row__version-title">
                        {version.original_filename}
                      </td>
                      <td>{formatDateTime(version.submitted_at)}</td>
                      <td>{version.version_no}</td>
                      <td>
                        <StatusBadge label={status.label} tone={status.tone} />
                      </td>
                      <td></td>
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
