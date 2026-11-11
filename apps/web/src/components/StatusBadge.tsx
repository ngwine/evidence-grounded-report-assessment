import "./StatusBadge.css";

export type BadgeTone = "success" | "warning" | "danger" | "neutral" | "info";

interface StatusBadgeProps {
  label: string;
  tone: BadgeTone;
}

/**
 * Pill trang thai dung chung cho moi man hinh (Class, Document, Checklist...).
 * Khong chua logic nghiep vu rieng cua feature nao -- feature tu quyet dinh
 * label/tone phu hop (xem lib/statusMaps.ts).
 */
export function StatusBadge({ label, tone }: StatusBadgeProps) {
  return <span className={`status-badge status-badge--${tone}`}>{label}</span>;
}
