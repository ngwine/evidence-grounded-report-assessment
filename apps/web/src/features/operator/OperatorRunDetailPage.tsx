import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getExperimentRun } from "../../lib/api";
import type { ExperimentRun } from "../../lib/types";
import { StatusBadge } from "../../components/StatusBadge";
import { experimentRunStatusLabel } from "../../lib/statusMaps";
import { formatDateTime } from "../../lib/format";
import "./operator.css";

/**
 * Man "Experiment Operator / Chi tiet run" (UC-12) -- hien day du run
 * manifest (commit/dataset/split/model/seed/hardware/timing, FR-EXP-01)
 * + bang metric. Nhan manh `splitSpec` de nguoi xem thay ro test split
 * khong dung de chon model/threshold (FR-EXP-03) -- ghi chu truc tiep
 * trong du lieu mock (xem mockExperimentRuns, lib/mockData.ts).
 */
export function OperatorRunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<ExperimentRun | null | undefined>(undefined);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;

    getExperimentRun(runId).then((data) => {
      if (!cancelled) setRun(data ?? null);
    });

    return () => {
      cancelled = true;
    };
  }, [runId]);

  if (run === null) {
    return (
      <section className="panel">
        <p className="panel__hint">Không tìm thấy run này.</p>
        <Link className="link-button" to="/operator/runs">
          Quay lại danh sách run
        </Link>
      </section>
    );
  }

  if (run === undefined) {
    return (
      <section className="panel">
        <p className="panel__hint">Đang tải...</p>
      </section>
    );
  }

  const statusChip = experimentRunStatusLabel[run.status];

  return (
    <section className="panel">
      <p className="breadcrumb">
        <Link to="/operator/runs">Experiment runs</Link> / {run.runKey}
      </p>

      <div className="panel__header">
        <div>
          <h1 className="panel__title">{run.runKey}</h1>
          <p className="panel__subtitle">
            {run.rq} · <StatusBadge label={statusChip.label} tone={statusChip.tone} />
          </p>
        </div>
      </div>

      <h2 className="panel__section-title">Run manifest</h2>
      <dl className="operator-run-detail__manifest">
        <div className="operator-run-detail__field">
          <dt>Commit</dt>
          <dd>{run.commitHash}</dd>
        </div>
        <div className="operator-run-detail__field">
          <dt>Dataset</dt>
          <dd>
            {run.datasetKey} (v{run.datasetVersion})
          </dd>
        </div>
        <div className="operator-run-detail__field">
          <dt>Split</dt>
          <dd>{run.splitSpec}</dd>
        </div>
        <div className="operator-run-detail__field">
          <dt>Model</dt>
          <dd>{run.modelName}</dd>
        </div>
        <div className="operator-run-detail__field">
          <dt>Seed</dt>
          <dd>{run.seed}</dd>
        </div>
        <div className="operator-run-detail__field">
          <dt>Hardware</dt>
          <dd>{run.hardware}</dd>
        </div>
        <div className="operator-run-detail__field">
          <dt>Bắt đầu</dt>
          <dd>{formatDateTime(run.startedAt)}</dd>
        </div>
        <div className="operator-run-detail__field">
          <dt>Kết thúc</dt>
          <dd>{run.finishedAt ? formatDateTime(run.finishedAt) : "—"}</dd>
        </div>
      </dl>

      <h2 className="panel__section-title">Metrics</h2>
      {run.metrics.length === 0 ? (
        <p className="panel__hint">
          {run.status === "RUNNING"
            ? "Run đang chạy, chưa có metric."
            : "Run này chưa ghi nhận metric nào."}
        </p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Giá trị</th>
            </tr>
          </thead>
          <tbody>
            {run.metrics.map((metric) => (
              <tr key={metric.name}>
                <td>{metric.name}</td>
                <td>
                  {metric.value}
                  {metric.unit ? ` ${metric.unit}` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
