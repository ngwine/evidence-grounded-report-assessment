import { useState } from 'react';
import type { AnalysisResults, Page, RunEvidence } from './authenticatedApi';
import { documentFileUrl } from './authenticatedApi';
import './results.css';

type Props = {
  results: AnalysisResults; evidence: Page<RunEvidence> | null; busy: boolean;
  workspaceId: string; reportVersionId: string; onMoreEvidence: () => Promise<void>;
  sourceNames?: Record<string, string>;
};

export default function AuthenticatedResults({ results, evidence, busy, workspaceId, reportVersionId, onMoreEvidence, sourceNames = {} }: Props) {
  const similarity = results.similarity;
  const assessment = results.assessment;
  const [tab, setTab] = useState<'similarity' | 'assessment' | 'evidence'>(similarity ? 'similarity' : 'assessment');
  const exactMatches = (similarity?.matches ?? []).filter((item) => item.classification_status === 'EVIDENCE_BACKED_EXACT_MATCH');
  const reviewMatches = (similarity?.matches ?? []).filter((item) => item.classification_status !== 'EVIDENCE_BACKED_EXACT_MATCH');
  const [matchFilter, setMatchFilter] = useState<'exact' | 'review'>(exactMatches.length ? 'exact' : 'review');
  const [visibleMatches, setVisibleMatches] = useState(6);
  const filteredMatches = matchFilter === 'exact' ? exactMatches : reviewMatches;
  const outcomes = assessment?.checklist_outcome_counts ?? {};
  const outcomeName = (value: string) => value === 'MET' ? 'Đạt' : value === 'UNMET' ? 'Chưa đạt' : 'Chưa đủ bằng chứng';
  const pageOf = (spans?: Array<{ locator?: { page_index?: number | null } }>) => spans?.find((span) => typeof span.locator?.page_index === 'number')?.locator?.page_index;
  return <div className="auth-analysis-results">
    <div className="result-summary-cards">
      <div><span>KHỚP NGUYÊN VĂN</span><strong>{similarity?.exact_match_coverage_percentage == null ? '—' : `${similarity.exact_match_coverage_percentage.toFixed(1)}%`}</strong><small>Coverage, không phải tỷ lệ đạo văn</small></div>
      <div><span>CHECKLIST ĐẠT</span><strong>{assessment ? `${outcomes.MET ?? 0} / ${assessment.checklist_results?.length ?? 0}` : '—'}</strong><small>{assessment ? `${outcomes.CANNOT_ASSESS ?? 0} mục cần thêm bằng chứng` : 'Không chạy assessment'}</small></div>
      <div><span>ĐIỂM ĐỀ XUẤT</span><strong>{assessment?.proposed_total_score == null ? 'Chưa đủ cơ sở' : `${assessment.proposed_total_score} / ${assessment.max_score}`}</strong><small>Cần giảng viên review</small></div>
    </div>
    <div className="report-result-tabs" role="tablist" aria-label="Kết quả hai pipeline">
      {similarity && <button role="tab" id="tab-similarity" aria-controls="panel-similarity" aria-selected={tab === 'similarity'} onClick={() => setTab('similarity')}>Đối chiếu nguồn</button>}
      {assessment && <button role="tab" id="tab-assessment" aria-controls="panel-assessment" aria-selected={tab === 'assessment'} onClick={() => setTab('assessment')}>Đánh giá rubric</button>}
      <button role="tab" id="tab-evidence" aria-controls="panel-evidence" aria-selected={tab === 'evidence'} onClick={() => setTab('evidence')}>Bằng chứng đã lưu</button>
    </div>
    {similarity && <section aria-label="Pipeline 1 kết quả" id="panel-similarity" hidden={tab !== 'similarity'}>
      <div className="result-section-copy"><h3>Nội dung đối chiếu</h3><p>Đoạn khớp nguyên văn được tách khỏi ứng viên chưa xác minh. Không tự suy ra paraphrase hoặc kết luận đạo văn.</p></div>
      <div className="match-filter"><button aria-pressed={matchFilter === 'exact'} onClick={() => { setMatchFilter('exact'); setVisibleMatches(6); }}>Khớp nguyên văn <span>{exactMatches.length}</span></button><button aria-pressed={matchFilter === 'review'} onClick={() => { setMatchFilter('review'); setVisibleMatches(6); }}>Ứng viên cần review <span>{reviewMatches.length}</span></button></div>
      {(similarity.matches?.length ?? 0) === 0 && <div className="result-empty-card">Chưa ghi nhận cặp đoạn trong corpus đã chọn. Điều này không chứng minh báo cáo không có nội dung tương đồng ở nguồn khác.</div>}
      {filteredMatches.length === 0 && (similarity.matches?.length ?? 0) > 0 && <p className="result-empty-card">Không có cặp thuộc nhóm này. Chọn nhóm còn lại để xem các đoạn đã truy xuất.</p>}
      {filteredMatches.slice(0, Math.min(50, visibleMatches)).map((item, index) => {
        const sourceVersion = evidence?.items.find((entry) => entry.source_chunk_id === item.source_chunk_id)?.source_version_id;
        const exact = item.classification_status === 'EVIDENCE_BACKED_EXACT_MATCH';
        return <article className="comparison-card" key={`${item.report_chunk_id}:${item.source_chunk_id}:${index}`}>
          <header><span className="comparison-number">{String(index + 1).padStart(2, '0')}</span><strong>{sourceNames[item.source_document_id] ?? item.source_name ?? 'Nguồn đối chứng'}</strong><span className={`finding-badge ${exact ? 'finding-exact' : ''}`}>{exact ? 'Khớp nguyên văn' : 'Cần kiểm tra'}</span></header>
          <div className="comparison-texts"><div><span>BÁO CÁO SINH VIÊN</span><blockquote>{item.alignment?.report?.text || 'Đoạn truy xuất chưa có alignment xác nhận. Mở evidence để xem ngữ cảnh.'}</blockquote><a href={documentFileUrl(workspaceId, reportVersionId, pageOf(item.alignment?.report?.source_spans))} target="_blank" rel="noreferrer">Mở báo cáo ↗</a></div><div><span>NGUỒN ĐỐI CHỨNG</span><blockquote>{item.alignment?.source?.text || 'Chưa có đoạn khớp được xác nhận.'}</blockquote>{sourceVersion && <a href={documentFileUrl(workspaceId, sourceVersion, pageOf(item.alignment?.source?.source_spans))} target="_blank" rel="noreferrer">Mở nguồn ↗</a>}</div></div>
          {!exact && <p className="finding-note">Đây là ứng viên truy xuất, chưa có nhãn semantic được xác minh.</p>}
          <details className="technical-details"><summary>Vị trí và chi tiết đối chiếu</summary><pre className="auth-evidence-json">{JSON.stringify(item, null, 2)}</pre></details>
        </article>;
      })}
      {filteredMatches.length > visibleMatches && visibleMatches < 50 && <button className="secondary-button" onClick={() => setVisibleMatches((count) => count + 6)}>Xem thêm cặp đối chiếu ({Math.min(visibleMatches, filteredMatches.length)}/{filteredMatches.length})</button>}
      {filteredMatches.length > 50 && <p className="field-help">Hiển thị tối đa 50 cặp của nhóm. Export JSON để xem đầy đủ.</p>}
    </section>}
    {assessment && <section aria-label="Pipeline 2 kết quả" id="panel-assessment" hidden={tab !== 'assessment'}>
      <div className="result-section-copy"><h3>Đánh giá theo từng yêu cầu</h3><p>Baseline kiểm tra yêu cầu cụ thể và dấu hiệu phủ định trong report; chưa xác minh semantic/cross-source.</p></div>
      <div className="assessment-outcome-legend"><span className="outcome-met">{outcomes.MET ?? 0} đạt</span><span className="outcome-unmet">{outcomes.UNMET ?? 0} chưa đạt</span><span className="outcome-cannot">{outcomes.CANNOT_ASSESS ?? 0} chưa đủ bằng chứng</span></div>
      {(assessment.checklist_results ?? []).map((item) => <article className="rubric-result-card" key={item.checklist_id}>
        <header><span className="checklist-key">{item.checklist_id}</span><span className={`outcome-badge outcome-${item.checklist_outcome === 'MET' ? 'met' : item.checklist_outcome === 'UNMET' ? 'unmet' : 'cannot'}`}>{outcomeName(item.checklist_outcome)}</span></header>
        <h4>{item.statement}</h4>
        <p className="checklist-human-reason">{item.reason_code === 'ALL_EXPLICIT_REQUIREMENTS_EVIDENCED' ? 'Tìm thấy bằng chứng cho các yêu cầu được khai báo trong checklist.' : item.reason_code === 'AUTHOR_DEFINED_CONTRADICTION_PATTERN_FOUND' ? 'Tìm thấy nội dung trùng mẫu mâu thuẫn do người soạn rubric khai báo.' : item.reason_code === 'CONFLICTING_REPORT_EVIDENCE' ? 'Có bằng chứng trái chiều trong báo cáo; cần giảng viên kiểm tra.' : item.reason_code === 'NEGATED_REQUIRED_EVIDENCE' ? 'Yêu cầu được nhắc tới trong câu phủ định, chưa đủ để xác nhận đạt.' : 'Chưa tìm đủ bằng chứng để kết luận theo yêu cầu đã khai báo.'}</p>
        {(item.evidence_pack ?? []).length > 0 ? <div className="checklist-evidence"><span>NGỮ CẢNH TRUY XUẤT · CẦN ĐỐI CHIẾU YÊU CẦU</span>{(item.evidence_pack ?? []).slice(0, 3).map((entry) => <blockquote key={entry.evidence_id}>{entry.excerpt}</blockquote>)}<a href={documentFileUrl(workspaceId, reportVersionId, pageOf(item.evidence_pack?.[0]?.source_spans))} target="_blank" rel="noreferrer">Xem trong báo cáo ↗</a></div> : <p className="result-empty-card">Không có evidence truy xuất cho checklist này. Không tự quy đổi việc thiếu evidence thành 0 điểm.</p>}
        <details className="technical-details"><summary>Rationale và evidence spans</summary><p>{item.rationale}</p><pre className="auth-evidence-json">{JSON.stringify({ relation: item.verification_relation, reason: item.reason_code, matched: item.matched_evidence_spans, negated: item.negated_evidence_spans }, null, 2)}</pre></details>
      </article>)}
    </section>}
    <section aria-label="Evidence đã lưu" id="panel-evidence" hidden={tab !== 'evidence'}>
      <div className="result-section-copy"><h3>Bằng chứng có thể truy vết</h3><p>Đoạn văn được khóa theo file version. Liên kết PDF mở trang, chưa highlight vùng trên PDF.</p></div>
      {evidence === null && <p>Đang tải evidence…</p>}
      {evidence?.items.length === 0 && <p>Không có evidence được lưu cho lượt này. Không suy ra kết luận từ việc thiếu evidence.</p>}
      {evidence?.items.map((item) => {
        const locator = item.evidence.locator as { page_index?: number | null } | undefined;
        const quote = typeof item.evidence.quote_text === 'string' ? item.evidence.quote_text : '';
        return <details key={item.id}>
          <summary>{item.pipeline === 'SIMILARITY' ? 'Đối chiếu nguồn' : 'Rubric'} · {item.checklist_id ?? 'Ứng viên đối chứng'}</summary>
          <blockquote>{quote}</blockquote>
          <p>Trang: {typeof locator?.page_index === 'number' ? locator.page_index + 1 : 'Không có tọa độ trang'} · {String(item.evidence.verification_state ?? 'INSUFFICIENT')}</p>
          <a href={documentFileUrl(workspaceId, item.source_version_id ?? reportVersionId, locator?.page_index)} target="_blank" rel="noreferrer">Mở file version đối chứng</a>
          <p className="field-help">Liên kết mở trang nếu PDF có page coordinate; đây chưa phải geometric highlight trên PDF. Exact spans và raw–normalized mapping nằm trong evidence.</p>
          <details className="technical-details"><summary>Provenance kỹ thuật</summary><pre className="auth-evidence-json">{JSON.stringify(item.evidence, null, 2)}</pre></details>
        </details>;
      })}
      {evidence?.page.has_more && <button className="secondary-button" disabled={busy} onClick={() => { void onMoreEvidence(); }}>Tải thêm evidence</button>}
    </section>
    {results.manifest && <details className="technical-details"><summary>Thông tin chạy và khả năng tái lập</summary><pre className="auth-evidence-json">{JSON.stringify(results.manifest, null, 2)}</pre></details>}
  </div>;
}
