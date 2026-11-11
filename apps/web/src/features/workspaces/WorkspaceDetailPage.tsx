import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getMyDocumentsInWorkspace, getWorkspaceById } from "../../lib/api";
import type { ReportDocumentWithVersions, Workspace } from "../../lib/types";
import { workspaceStatusLabel } from "../../lib/statusMaps";
import { DocumentVersionsTable } from "./DocumentVersionsTable";
import { UploadReportModal } from "./UploadReportModal";
import "./workspaces.css";

/**
 * Man "Student / Class Detail" theo wireframe W2.4 (chi tham khao UI) --
 * ve mat ky thuat day la chi tiet 1 Workspace + danh sach Document
 * (kind=REPORT) cua chinh sinh vien dang dang nhap, theo dung route/API
 * "workspace" trong data-dictionary.md.
 *
 * Nut "Nop bao cao" mo UploadReportModal (man 1 - Upload, wireframe
 * W2.4) -- nop bao cao moi (document moi) hoac nop them phien ban cho
 * 1 bao cao da co (document_version moi).
 */
export function WorkspaceDetailPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();
  const [workspace, setWorkspace] = useState<Workspace | null | undefined>(
    undefined,
  );
  const [documents, setDocuments] = useState<
    ReportDocumentWithVersions[] | null
  >(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;

    getWorkspaceById(workspaceId).then((data) => {
      if (!cancelled) setWorkspace(data ?? null);
    });
    getMyDocumentsInWorkspace(workspaceId).then((data) => {
      if (!cancelled) setDocuments(data);
    });

    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  if (workspace === null) {
    return (
      <section className="panel">
        <p className="panel__hint">
          Không tìm thấy lớp này, hoặc bạn không có quyền xem.
        </p>
        <button className="link-button" onClick={() => navigate("/workspaces")}>
          Quay lại danh sách lớp
        </button>
      </section>
    );
  }

  const status = workspace ? workspaceStatusLabel[workspace.status] : null;

  return (
    <section className="panel">
      <nav className="breadcrumb" aria-label="breadcrumb">
        <Link to="/workspaces">Các lớp</Link>
        <span aria-hidden="true"> &gt; </span>
        <span>{workspace?.name ?? "..."}</span>
      </nav>

      <div className="panel__header">
        <div>
          <h1 className="panel__title">{workspace?.name ?? "Đang tải..."}</h1>
          {workspace && status && (
            <p className="panel__subtitle">
              {workspace.workspace_key} · {status.label}
            </p>
          )}
        </div>
        <button
          className="btn-primary"
          type="button"
          onClick={() => setIsUploadOpen(true)}
        >
          Nộp báo cáo
        </button>
      </div>

      <h2 className="panel__section-title">Báo cáo đã nộp</h2>

      {documents === null && <p className="panel__hint">Đang tải...</p>}

      {documents !== null && documents.length === 0 && (
        <p className="panel__hint">Bạn chưa nộp báo cáo nào trong lớp này.</p>
      )}

      {documents !== null && documents.length > 0 && workspaceId && (
        <DocumentVersionsTable workspaceId={workspaceId} documents={documents} />
      )}

      {isUploadOpen && workspaceId && (
        <UploadReportModal
          workspaceId={workspaceId}
          documents={documents ?? []}
          onClose={() => setIsUploadOpen(false)}
          onSubmitted={() => {
            // Nop xong -- lam moi lai danh sach bao cao tu "API" de dong bo
            getMyDocumentsInWorkspace(workspaceId).then(setDocuments);
          }}
        />
      )}
    </section>
  );
}
