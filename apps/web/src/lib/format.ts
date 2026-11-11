/** Helper hien thi dung chung cho ca UploadReportModal va DocumentVersionsTable. */

export function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Hien thi 1 ISO datetime (vd submitted_at) dang "dd/mm/yyyy · HH:mm:ss"
 * (gio theo may nguoi dung) -- dung chung cho moi noi can hien gio phut
 * giay cua version/tien trinh (StudentReportsTable, lib/api.ts
 * buildSubSteps). Neu chuoi dau vao khong parse duoc thanh ngay hop le
 * (vd du lieu cu chi co "yyyy-mm-dd" khong gio), tra lai nguyen chuoi goc
 * de khong hien "Invalid Date".
 */
export function formatDateTime(isoString: string): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;

  const pad = (n: number) => n.toString().padStart(2, "0");
  const datePart = `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`;
  const timePart = `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;

  return `${datePart} ${timePart}`;
}

/**
 * Cat ngan 1 doan text, them "..." neu vuot qua maxLength -- dung cho cot
 * "Đoạn trong báo cáo" o bang "Ket qua so khop" (Similarity), GV xac
 * nhan 2026-10-27 gioi han toi da 100 ky tu. Trim truoc/sau de khong cat
 * ngay giua khoang trang thua.
 */
export function truncateText(text: string, maxLength: number): string {
  const trimmed = text.trim();
  if (trimmed.length <= maxLength) return trimmed;
  return `${trimmed.slice(0, maxLength).trimEnd()}...`;
}
