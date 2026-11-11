import { useEffect, useRef, useState } from "react";
import { submitReportVersion } from "../../lib/api";
import { formatFileSize } from "../../lib/format";
import type { ReportDocumentWithVersions } from "../../lib/types";
import { FileTypeBadge } from "../../components/FileTypeBadge";
import "./UploadReportModal.css";

interface UploadReportModalProps {
  workspaceId: string;
  /** Các báo cáo đã có của chính user trong workspace này -- để chọn "nộp thêm phiên bản" */
  documents: ReportDocumentWithVersions[];
  onClose: () => void;
  /** Gọi khi nộp thành công, kèm document (đã có version mới) để parent cập nhật lại bảng */
  onSubmitted: (document: ReportDocumentWithVersions) => void;
}

const NEW_REPORT_VALUE = "__new__";

type FileStatus = "idle" | "uploading" | "success" | "error";

/**
 * Popup "Nộp báo cáo" (Student / Upload Popup, wireframe W2.4).
 * Thêm so với wireframe gốc: bước chọn "Nộp cho báo cáo nào?" ở đầu --
 * nộp báo cáo mới (tạo document mới) hay nộp thêm phiên bản cho 1 báo cáo
 * đã có sẵn (thêm document_version mới) -- theo đúng quyết định đã bàn.
 */
export function UploadReportModal({
  workspaceId,
  documents,
  onClose,
  onSubmitted,
}: UploadReportModalProps) {
  const hasExistingDocuments = documents.length > 0;
  const [target, setTarget] = useState<string>(
    hasExistingDocuments ? NEW_REPORT_VALUE : NEW_REPORT_VALUE,
  );
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<FileStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isNewMode = target === NEW_REPORT_VALUE;
  const selectedDocument = !isNewMode
    ? documents.find((d) => d._id === target)
    : undefined;

  function resetFile() {
    setFile(null);
    setStatus("idle");
    setErrorMessage(null);
  }

  function handleFileChosen(chosen: File | undefined) {
    if (!chosen) return;
    setFile(chosen);
    setStatus("idle");
    setErrorMessage(null);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDraggingOver(false);
    if (status === "uploading") return;
    handleFileChosen(e.dataTransfer.files[0]);
  }

  async function handleUpload() {
    if (!file) return;
    if (!isNewMode && !selectedDocument) return;

    setStatus("uploading");
    setErrorMessage(null);

    const result = await submitReportVersion({
      workspaceId,
      mode: isNewMode ? "NEW" : "EXISTING",
      documentId: isNewMode ? undefined : selectedDocument!._id,
      title: isNewMode ? title : undefined,
      file,
    });

    if (result.ok && result.document) {
      setStatus("success");
      onSubmitted(result.document);
    } else {
      setStatus("error");
      setErrorMessage(result.error ?? "Có lỗi xảy ra, vui lòng thử lại.");
    }
  }

  const canUpload =
    !!file &&
    status !== "uploading" &&
    status !== "success" &&
    (isNewMode ? true : !!selectedDocument);

  const isBusy = status === "uploading";

  // Esc để đóng (trừ lúc đang tải lên, tránh thoát giữa chừng)
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && !isBusy) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isBusy, onClose]);

  return (
    <div className="modal-overlay" role="presentation">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-modal-title"
      >
        <div className="modal__header">
          <h2 id="upload-modal-title" className="modal__title">
            Nộp báo cáo
          </h2>
          <button
            type="button"
            className="modal__close"
            aria-label="Đóng"
            onClick={onClose}
            disabled={isBusy}
          >
            ×
          </button>
        </div>

        {hasExistingDocuments && status !== "success" && (
          <label className="modal__field">
            <span className="modal__label">Nộp cho báo cáo nào?</span>
            <select
              className="modal__select"
              value={target}
              disabled={isBusy}
              onChange={(e) => setTarget(e.target.value)}
            >
              <option value={NEW_REPORT_VALUE}>+ Báo cáo mới</option>
              {documents.map((doc) => (
                <option key={doc._id} value={doc._id}>
                  {doc.versions[0]?.original_filename ?? doc.title}
                </option>
              ))}
            </select>
          </label>
        )}

        {!isNewMode && selectedDocument && status !== "success" && (
          <p className="modal__hint">
            Phiên bản mới sẽ được thêm vào báo cáo "
            {selectedDocument.versions[0]?.original_filename ?? selectedDocument.title}
            ".
          </p>
        )}

        {status !== "success" && (
          <div
            className={`modal__dropzone${isDraggingOver ? " modal__dropzone--active" : ""}${
              file ? " modal__dropzone--has-file" : ""
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              if (!isBusy) setIsDraggingOver(true);
            }}
            onDragLeave={() => setIsDraggingOver(false)}
            onDrop={handleDrop}
          >
            {!file && (
              <>
                <span className="modal__dropzone-icon" aria-hidden="true">
                  ↓
                </span>
                <p className="modal__dropzone-text">
                  Kéo thả file vào đây hoặc{" "}
                  <button
                    type="button"
                    className="modal__dropzone-browse"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    chọn từ máy
                  </button>
                </p>
                <p className="modal__dropzone-hint">PDF, DOCX — tối đa 100MB</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx"
                  className="modal__file-input"
                  onChange={(e) => handleFileChosen(e.target.files?.[0])}
                />
              </>
            )}

            {file && (
              <div className="modal__file-row">
                <div className="modal__file-info">
                  <span className="modal__file-name">
                    <FileTypeBadge filename={file.name} />
                    {file.name}
                  </span>
                  <span
                    className={`modal__file-status modal__file-status--${status}`}
                  >
                    {status === "idle" && formatFileSize(file.size)}
                    {status === "uploading" && "⏳ Đang tải..."}
                    {status === "error" && `⚠ ${errorMessage}`}
                  </span>
                </div>
                {status !== "uploading" && (
                  <button
                    type="button"
                    className="modal__file-remove"
                    aria-label="Xoá file"
                    onClick={resetFile}
                  >
                    ⊗
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {status === "success" && file && (
          <div className="modal__dropzone modal__dropzone--has-file">
            <div className="modal__file-row">
              <div className="modal__file-info">
                <span className="modal__file-name">
                  <FileTypeBadge filename={file.name} />
                  {file.name}
                </span>
                <span className="modal__file-status modal__file-status--success">
                  ✓ Đã nộp · {formatFileSize(file.size)}
                </span>
              </div>
            </div>
          </div>
        )}

        {isNewMode && (
          <label className="modal__field">
            <span className="modal__label">Tiêu đề báo cáo</span>
            <input
              type="text"
              className="modal__input"
              placeholder="Nhập tiêu đề báo cáo"
              value={title}
              disabled={isBusy || status === "success"}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
        )}

        <div className="modal__actions">
          {status === "success" ? (
            <button type="button" className="btn-primary" onClick={onClose}>
              Đóng
            </button>
          ) : (
            <>
              <button
                type="button"
                className="btn-secondary"
                onClick={onClose}
                disabled={isBusy}
              >
                Hủy
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={handleUpload}
                disabled={!canUpload}
              >
                Tải lên
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
