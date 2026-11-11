import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getExperimentRuns } from "../../lib/api";
import type { ExperimentRun, ResearchQuestion } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { experimentRunStatusLabel } from "../../lib/statusMaps";
import { formatDateTime } from "../../lib/format";
import "./operator.css";

const RQ_FILTER_OPTIONS: ResearchQuestion[] = ["RQ1", "RQ2", "RQ3"];

/**
 * Man "Experiment Operator / Danh sach run" (UC-12, actor rieng "Experiment
 * Operator" -- xem ghi chu ExperimentRun, lib/types.ts). CHI DOC trong ban
 * demo nay: khong co nut "Chay run moi" vi do la hanh dong goi 1 pipeline
 * thuc nghiem thuc (CLI/notebook), ngoai pham vi 1 form UI web -- GIA DINH
 * DEMO, man nay chi phuc vu xem lai cac run DA chay (FR-EXP-01/02).
 */
export function OperatorRunListPage() {
  const [runs, setRuns] = useState<ExperimentRun[] | null>(null);
  const [rqFilter, setRqFilter] = useState<ResearchQuestion | "">("");

  useEffect(() => {
    getExperimentRuns().then(setRuns);
  }, []);

  const filteredRuns = useMemo(() => {
    if (rqFilter === "") return runs ?? [];
    return (runs ?? []).filter((run) => run.rq === rqFilter);
  }, [runs, rqFilter]);

  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <h1 className="panel__title">Experiment runs</h1>
          <p className="panel__subtitle">
            Danh sách run thực nghiệm theo từng câu hỏi nghiên cứu (RQ1–RQ3).
            Mỗi run lưu đủ commit/dataset/config/model/seed/hardware để tái
            tạo lại (FR-EXP-01).
          </p>
        </div>
      </div>

      <div className="operator-run-list__filters">
        <select
          className="operator-run-list__status-select"
          value={rqFilter}
          onChange={(event) => setRqFilter(event.target.value as ResearchQuestion | "")}
          aria-label="Lọc theo RQ"
        >
          <option value="">Tất cả RQ</option>
          {RQ_FILTER_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </div>

      {runs === null && <p className="panel__hint">Đang tải...</p>}

      {runs !== null && filteredRuns.length === 0 && (
        <p className="panel__hint">
          {runs.length === 0 ? "Chưa có run thực nghiệm nào." : "Không tìm thấy run phù hợp."}
        </p>
      )}

      {filteredRuns.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Run</th>
              <th>RQ</th>
              <th>Model</th>
              <th>Dataset</th>
              <th>Trạng thái</th>
              <th>Bắt đầu</th>
            </tr>
          </thead>
          <tbody>
            {filteredRuns.map((run) => {
              const statusChip = experimentRunStatusLabel[run.status];

              return (
                <tr key={run._id} className="data-table__row--clickable">
                  <td>
                    <Link className="link-cell" to={`/operator/runs/${run._id}`}>
                      {run.runKey}
                    </Link>
                  </td>
                  <td>{run.rq}</td>
                  <td>{run.modelName}</td>
                  <td>
                    <span className="operator-run-list__dataset">
                      <span className="operator-run-list__dataset-key">{run.datasetKey}</span>
                      <span className="operator-run-list__dataset-version">v{run.datasetVersion}</span>
                    </span>
                  </td>
                  <td>
                    <StatusBadge label={statusChip.label} tone={statusChip.tone} />
                  </td>
                  <td>{formatDateTime(run.startedAt)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
