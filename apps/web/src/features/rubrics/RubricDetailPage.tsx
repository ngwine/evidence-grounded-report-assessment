import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getRubricDetail, type RubricDetail } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { StatusBadge } from "../../components/StatusBadge";
import { checklistImportanceLabel, rubricVersionStatusLabel } from "../../lib/statusMaps";
import "./rubrics.css";

/**
 * Man "Xem chi tiet rubric" -- giang vien xem lai 1 rubric da tao (sau khi
 * bam "Xac nhan hoan tat" o RubricCreatePage, hoac tu danh sach rubric o
 * LecturerClassDetailPage) -- Yen yeu cau 2026-10-25: "neu tao xong rubric
 * roi thi duoc phep xem rubric, checklist". Hien CHI DOC -- CHUA co nut
 * sua/clone o day (data-dictionary.md muc 8.2: "Published version la
 * immutable. Sua rubric da dung phai clone version" -- sua that se la 1
 * luong rieng, chua lam UI, xem ghi chu o getRubricDetail trong lib/api.ts).
 *
 * Bo cuc: 1 bang ma tran to (tieu chi x muc do) cho toan bo rubric, giong
 * dang 1 "rubric" chuan thay vi tach rieng tung khung nho/tieu chi nhu
 * truoc -- Yen yeu cau 2026-10-26 ("sao ta ko hien thi 1 cai rubric to
 * luon"). Checklist van de rieng ben duoi, nhom theo tieu chi, vi so
 * luong/cac truong (mode, importance) cua checklist khong nhet vao 1 o
 * ma tran duoc. KHONG hien LOCAL/GRAPH o day (Yen yeu cau 2026-10-26: "ko
 * hien thi local/graph o ui", vi do la chi tiet he thong tu phan loai,
 * GV khong can/khong sua duoc -- xem ghi chu o RubricCreatePage.tsx).
 */
export function RubricDetailPage() {
  const { workspaceId, rubricId } = useParams<{ workspaceId: string; rubricId: string }>();
  const [detail, setDetail] = useState<RubricDetail | null | undefined>(undefined);

  useEffect(() => {
    if (!rubricId) return;
    let cancelled = false;

    getRubricDetail(rubricId).then((data) => {
      if (!cancelled) setDetail(data ?? null);
    });

    return () => {
      cancelled = true;
    };
  }, [rubricId]);

  if (detail === null) {
    return (
      <section className="panel">
        <p className="panel__hint">Không tìm thấy rubric này, hoặc bạn không có quyền xem.</p>
        {workspaceId && (
          <Link className="link-button" to={`/lecturer/workspaces/${workspaceId}`}>
            Quay lại chi tiết lớp
          </Link>
        )}
      </section>
    );
  }

  if (detail === undefined) {
    return (
      <section className="panel">
        <p className="panel__hint">Đang tải...</p>
      </section>
    );
  }

  const { rubric, version } = detail;
  const status = rubricVersionStatusLabel[version.status];

  return (
    <section className="panel">
      <nav className="breadcrumb" aria-label="breadcrumb">
        <Link to="/lecturer/workspaces">Các lớp</Link>
        <span aria-hidden="true"> &gt; </span>
        <Link to={`/lecturer/workspaces/${rubric.workspace_id}`}>Chi tiết lớp</Link>
        <span aria-hidden="true"> &gt; </span>
        <span>{rubric.title}</span>
      </nav>

      <div className="panel__header">
        <div>
          <h1 className="panel__title">{rubric.title}</h1>
          <p className="panel__subtitle">
            Phiên bản {version.version_no} · {version.level_names.join(" / ")} · Tạo lúc{" "}
            {formatDateTime(rubric.created_at)}
            {rubric.updated_at !== rubric.created_at && (
              <> · Sửa lúc {formatDateTime(rubric.updated_at)}</>
            )}
          </p>
        </div>
        <div className="rubric-detail__header-actions">
          <StatusBadge label={status.label} tone={status.tone} />
          {/* Chi cho sua khi con DRAFT -- published thi immutable, phai
              clone de tao version moi (chua lam UI) -- Yen yeu cau
              2026-10-27. */}
          {version.status === "DRAFT" && (
            <Link
              className="btn-secondary"
              to={`/lecturer/workspaces/${rubric.workspace_id}/rubrics/${rubric._id}/edit`}
            >
              Sửa
            </Link>
          )}
        </div>
      </div>

      <div className="rubric-review-table-wrap">
        <table className="rubric-review-table rubric-review-table--even">
          <thead>
            <tr>
              <th>Tiêu chí</th>
              <th>Trọng số</th>
              {version.level_names.map((name, levelIndex) => (
                <th key={levelIndex}>{name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {version.criteria.map((criterion, index) => (
              <tr key={criterion._id}>
                <td className="rubric-review-table__criterion-name">
                  {index + 1}. {criterion.title}
                </td>
                <td>{criterion.weight}</td>
                {criterion.levels.map((level, levelIndex) => (
                  <td key={levelIndex}>
                    {level.min} – {level.max}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="panel__section-title">Checklist</h2>

      {version.criteria.map((criterion, index) => (
        <div className="rubric-criterion-card" key={criterion._id}>
          <div className="rubric-criterion-card__header">
            <strong>
              {index + 1}. {criterion.title}
            </strong>
          </div>

          {criterion.checklists.map((checklist, checklistIndex) => {
            const importance = checklistImportanceLabel[checklist.importance];
            return (
              <div className="rubric-checklist-row rubric-checklist-row--readonly" key={checklist._id}>
                <span className="rubric-checklist-row__index">{checklistIndex + 1}.</span>
                <span className="rubric-checklist-row__condition">
                  {checklist.condition.trim() || (
                    <span className="panel__hint">(chưa nhập nội dung)</span>
                  )}
                </span>
                <StatusBadge label={importance.label} tone={importance.tone} />
              </div>
            );
          })}
        </div>
      ))}
    </section>
  );
}
