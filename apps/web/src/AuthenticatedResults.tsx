import type { AnalysisResults, Page, RunEvidence } from './authenticatedApi';
import { documentFileUrl } from './authenticatedApi';

type Props = {
  results: AnalysisResults; evidence: Page<RunEvidence> | null; busy: boolean;
  workspaceId: string; reportVersionId: string; onMoreEvidence: () => Promise<void>;
};

export default function AuthenticatedResults({ results, evidence, busy, workspaceId, reportVersionId, onMoreEvidence }: Props) {
  const similarity = results.similarity;
  const assessment = results.assessment;
  return <div className="auth-analysis-results">
    <p className="notice notice-muted">Đây là kết quả phân tích đề xuất. Coverage khớp nguyên văn không phải tỷ lệ đạo văn; điểm assessment chưa phải điểm chính thức.</p>
    {similarity && <section aria-label="Pipeline 1 kết quả">
      <h4>Pipeline 1 · Similarity</h4>
      <p>Exact-match coverage: <strong>{similarity.exact_match_coverage_percentage?.toFixed(2) ?? '—'}%</strong>. Calibrated similarity: {similarity.calibrated_similarity_percentage == null ? 'chưa có' : `${similarity.calibrated_similarity_percentage}%`}.</p>
      <p>Ứng viên cần review: {similarity.provisional_review_report_chunks ?? 0} đoạn. Ứng viên truy xuất không được tự gán nhãn paraphrase/summary đã xác nhận.</p>
      {(similarity.matches ?? []).slice(0, 50).map((item, index) => <details key={`${item.report_chunk_id}:${item.source_chunk_id}:${index}`}>
        <summary>{item.classification_status} · {item.source_name ?? item.source_document_id}</summary>
        <pre className="auth-evidence-json">{JSON.stringify(item, null, 2)}</pre>
      </details>)}
      {(similarity.matches?.length ?? 0) > 50 && <p>Hiển thị 50 cặp đầu. Export JSON để xem đầy đủ.</p>}
    </section>}
    {assessment && <section aria-label="Pipeline 2 kết quả">
      <h4>Pipeline 2 · Evidence-grounded assessment</h4>
      <p>Điểm đề xuất: <strong>{assessment.proposed_total_score == null ? 'chưa thể tổng hợp' : assessment.proposed_total_score} / {assessment.max_score}</strong>.</p>
      <p>Verifier hiện dùng authored phrase requirements và negation cues; chưa phải semantic/cross-source entailment.</p>
      {(assessment.checklist_results ?? []).map((item) => <details key={item.checklist_id}>
        <summary>{item.checklist_id} · {item.checklist_outcome} · {item.statement}</summary>
        <p>{item.rationale}</p><p>{item.verification_relation} · {item.reason_code}</p>
        {(item.evidence_pack ?? []).map((entry) => <blockquote key={entry.evidence_id}>{entry.excerpt}</blockquote>)}
        <pre className="auth-evidence-json">{JSON.stringify({ matched: item.matched_evidence_spans, negated: item.negated_evidence_spans }, null, 2)}</pre>
      </details>)}
    </section>}
    <section aria-label="Evidence đã lưu">
      <h4>Evidence và provenance đã lưu</h4>
      {evidence === null && <p>Đang tải evidence…</p>}
      {evidence?.items.length === 0 && <p>Không có evidence được lưu cho lượt này. Không suy ra kết luận từ việc thiếu evidence.</p>}
      {evidence?.items.map((item) => {
        const locator = item.evidence.locator as { page_index?: number | null } | undefined;
        const quote = typeof item.evidence.quote_text === 'string' ? item.evidence.quote_text : '';
        return <details key={item.id}>
          <summary>{item.pipeline} · {item.checklist_id ?? 'source candidate'} · {String(item.evidence.verification_state ?? 'INSUFFICIENT')}</summary>
          <blockquote>{quote}</blockquote>
          <p>Version: <code>{item.source_version_id ?? reportVersionId}</code>; trang: {typeof locator?.page_index === 'number' ? locator.page_index + 1 : 'không có page coordinate'}.</p>
          <a href={documentFileUrl(workspaceId, item.source_version_id ?? reportVersionId, locator?.page_index)} target="_blank" rel="noreferrer">Mở file version đối chứng</a>
          <p className="field-help">Liên kết mở trang nếu PDF có page coordinate; đây chưa phải geometric highlight trên PDF. Exact spans và raw–normalized mapping nằm trong evidence.</p>
          <pre className="auth-evidence-json">{JSON.stringify(item.evidence, null, 2)}</pre>
        </details>;
      })}
      {evidence?.page.has_more && <button className="secondary-button" disabled={busy} onClick={() => { void onMoreEvidence(); }}>Tải thêm evidence</button>}
    </section>
    {results.manifest && <details><summary>Run manifest</summary><pre className="auth-evidence-json">{JSON.stringify(results.manifest, null, 2)}</pre></details>}
  </div>;
}
