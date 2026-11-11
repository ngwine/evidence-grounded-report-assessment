import "./FileTypeBadge.css";

type DetectedFileType = "PDF" | "DOCX" | null;

function detectFileType(filename: string): DetectedFileType {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".pdf")) return "PDF";
  if (lower.endsWith(".docx")) return "DOCX";
  return null;
}

interface FileTypeBadgeProps {
  /** Ten file (vd: original_filename cua document_version) -- loai file suy ra tu duoi file */
  filename: string;
}

/**
 * Badge nho hien loai file (PDF/DOCX) suy ra tu duoi file trong filename --
 * khong can them field rieng trong data model, khong can icon anh/thu vien
 * ngoai. Khong hien gi neu khong nhan dien duoc (vd file loai khac).
 */
export function FileTypeBadge({ filename }: FileTypeBadgeProps) {
  const type = detectFileType(filename);
  if (!type) return null;

  return (
    <span className={`file-type-badge file-type-badge--${type.toLowerCase()}`}>
      {type}
    </span>
  );
}
