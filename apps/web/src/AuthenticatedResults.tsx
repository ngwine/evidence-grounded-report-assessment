import { useState } from 'react';
import type { AnalysisResults, Page, RunEvidence } from './authenticatedApi';
import { documentFileUrl } from './authenticatedApi';
import './results.css';

const ASSESSMENT_REASONS: Record<string, string> = {
  ALL_EXPLICIT_REQUIREMENTS_EVIDENCED: 'Tìm thấy bằng chứng cho các yêu cầu được khai báo trong checklist.',
  AUTHOR_DEFINED_CONTRADICTION_PATTERN_FOUND: 'Tìm thấy nội dung trùng mẫu mâu thuẫn do người soạn rubric khai báo.',
  CONFLICTING_REPORT_EVIDENCE: 'Có bằng chứng trái chiều trong báo cáo; cần giảng viên kiểm tra.',
  UNRESOLVED_COUNTERCLAIM_SCOPE: 'Có nội dung có thể là phản chứng nhưng ngữ cảnh chưa rõ; cần giảng viên kiểm tra.',
  NEGATED_REQUIRED_EVIDENCE: 'Yêu cầu được nhắc tới trong câu phủ định, chưa đủ để xác nhận đạt.',
  NON_ACTUAL_REQUIRED_EVIDENCE: 'Nội dung đang là kế hoạch, công việc chờ thực hiện hoặc tình huống giả định; chưa xác nhận đã hoàn thành.',
  LLM_ALL_REQUIREMENTS_EVIDENCED: 'Mô hình đề xuất bằng chứng đáp ứng đầy đủ ý nghĩa của yêu cầu. Cần giảng viên đối chiếu trước khi chấp nhận.',
  LLM_DIRECT_CONTRADICTION_EVIDENCED: 'Mô hình chỉ ra bằng chứng cho thấy yêu cầu chưa được đáp ứng. Cần giảng viên đối chiếu phần phản chứng.',
  LLM_INSUFFICIENT_EVIDENCE: 'Bằng chứng hiện có chưa đủ để xác định yêu cầu đạt hay chưa đạt.',
};

const NEGATIVE_SIMILARITY_STATUSES = new Set(['MODEL_REJECTED_EQUIVALENCE', 'NO_SIMILARITY_HYPOTHESIS']);

type Props = {
  results: AnalysisResults; evidence: Page<RunEvidence> | null; busy: boolean;
  workspaceId: string; reportVersionId: string; onMoreEvidence: () => Promise<void>;
  sourceNames?: Record<string, string>;
};

export default function AuthenticatedResults({ results, evidence, busy, workspaceId, reportVersionId, onMoreEvidence, sourceNames = {} }: Props) {
  const similarity = results.similarity;
  const assessment = results.assessment;
  const llmAssessment = assessment?.verification_method === 'LOCAL_LLM_REQUIREMENT_VERIFIER_V1';
  const [tab, setTab] = useState<'similarity' | 'assessment' | 'evidence'>(similarity ? 'similarity' : 'assessment');
  const exactMatches = (similarity?.matches ?? []).filter((item) => item.classification_status === 'EVIDENCE_BACKED_EXACT_MATCH');
  const semanticMatches = (similarity?.matches ?? []).filter((item) => item.classification_status === 'MODEL_SUPPORTED_SEMANTIC_MATCH');
  const provisionalMatches = (similarity?.matches ?? []).filter((item) => item.classification_status === 'PROVISIONAL_REVIEW_REQUIRED');
  const reviewMatches = provisionalMatches.filter((item) => item.selected_for_manual_review);
  const negativeMatches = (similarity?.matches ?? []).filter((item) => NEGATIVE_SIMILARITY_STATUSES.has(item.classification_status));
  // Preserve every pair, including unknown future statuses, without claiming
  // that an unsupported status establishes either similarity or its absence.
  const unresolvedMatches = (similarity?.matches ?? []).filter((item) =>
    item.classification_status !== 'EVIDENCE_BACKED_EXACT_MATCH'
    && item.classification_status !== 'MODEL_SUPPORTED_SEMANTIC_MATCH'
    && !NEGATIVE_SIMILARITY_STATUSES.has(item.classification_status)
    && !(item.classification_status === 'PROVISIONAL_REVIEW_REQUIRED' && item.selected_for_manual_review));
  const [matchFilter, setMatchFilter] = useState<'exact' | 'semantic' | 'review' | 'negative' | 'unresolved'>(exactMatches.length ? 'exact' : semanticMatches.length ? 'semantic' : reviewMatches.length ? 'review' : negativeMatches.length ? 'negative' : 'unresolved');
  const [visibleMatches, setVisibleMatches] = useState(6);
  const filteredMatches = matchFilter === 'exact' ? exactMatches : matchFilter === 'semantic' ? semanticMatches : matchFilter === 'review' ? reviewMatches : matchFilter === 'negative' ? negativeMatches : unresolvedMatches;
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
      <div className="result-section-copy"><h3>Nội dung đối chiếu</h3><p>Xem các đoạn khớp và bằng chứng cho từng cặp. Đề xuất tương đương ngữ nghĩa cần được đối chiếu trước khi kết luận.</p></div>
      <div className="match-filter"><button aria-pressed={matchFilter === 'exact'} onClick={() => { setMatchFilter('exact'); setVisibleMatches(6); }}>Khớp nguyên văn <span>{exactMatches.length}</span></button>{(similarity.semantic_classifier_available || semanticMatches.length > 0) && <button aria-pressed={matchFilter === 'semantic'} onClick={() => { setMatchFilter('semantic'); setVisibleMatches(6); }}>Diễn đạt tương đương <span>{semanticMatches.length}</span></button>}<button aria-pressed={matchFilter === 'review'} onClick={() => { setMatchFilter('review'); setVisibleMatches(6); }}>Ứng viên cần review <span>{reviewMatches.length}</span></button>{negativeMatches.length > 0 && <button aria-pressed={matchFilter === 'negative'} onClick={() => { setMatchFilter('negative'); setVisibleMatches(6); }}>Không đề xuất tương đồng <span>{negativeMatches.length}</span></button>}{unresolvedMatches.length > 0 && <button aria-pressed={matchFilter === 'unresolved'} onClick={() => { setMatchFilter('unresolved'); setVisibleMatches(6); }}>Chưa xác định <span>{unresolvedMatches.length}</span></button>}</div>
      {matchFilter === 'negative' && <p className="field-help">Các cặp này không được đề xuất là tương đồng theo cấu hình đã chạy. Kết quả chỉ áp dụng cho từng cặp và không chứng minh toàn báo cáo không có nội dung tương đồng.</p>}
      {matchFilter === 'unresolved' && <p className="field-help">Các cặp này chưa có kết luận tương đồng có thể hiển thị; cần giảng viên đối chiếu trạng thái và bằng chứng. Chúng không tính vào tỷ lệ khớp nguyên văn.</p>}
      {(similarity.matches?.length ?? 0) === 0 && <div className="result-empty-card">Chưa ghi nhận cặp đoạn trong corpus đã chọn. Điều này không chứng minh báo cáo không có nội dung tương đồng ở nguồn khác.</div>}
      {filteredMatches.length === 0 && (similarity.matches?.length ?? 0) > 0 && <p className="result-empty-card">Không có cặp thuộc nhóm này. Chọn nhóm còn lại để xem các đoạn đã truy xuất.</p>}
      {filteredMatches.slice(0, Math.min(50, visibleMatches)).map((item, index) => {
        const sourceVersion = evidence?.items.find((entry) => entry.source_chunk_id === item.source_chunk_id)?.source_version_id;
        const exact = item.classification_status === 'EVIDENCE_BACKED_EXACT_MATCH';
        const semantic = item.classification_status === 'MODEL_SUPPORTED_SEMANTIC_MATCH';
        const negative = NEGATIVE_SIMILARITY_STATUSES.has(item.classification_status);
        const review = item.classification_status === 'PROVISIONAL_REVIEW_REQUIRED' && item.selected_for_manual_review;
        const compared = semantic ? item.semantic_evidence?.[0] : item.alignment;
        return <article className="comparison-card" key={`${item.report_chunk_id}:${item.source_chunk_id}:${index}`}>
          <header><span className="comparison-number">{String(index + 1).padStart(2, '0')}</span><strong>{sourceNames[item.source_document_id] ?? item.source_name ?? 'Nguồn đối chứng'}</strong><span className={`finding-badge ${exact || semantic ? 'finding-exact' : ''}`}>{exact ? 'Khớp nguyên văn' : semantic ? 'Mô hình đề xuất tương đương' : negative ? 'Không đề xuất tương đồng' : review ? 'Cần kiểm tra' : 'Chưa xác định'}</span></header>
          <div className="comparison-texts"><div><span>BÁO CÁO SINH VIÊN</span><blockquote>{compared?.report?.text || 'Đoạn truy xuất chưa có alignment xác nhận. Mở evidence để xem ngữ cảnh.'}</blockquote><a href={documentFileUrl(workspaceId, reportVersionId, pageOf(compared?.report?.source_spans))} target="_blank" rel="noreferrer">Mở báo cáo ↗</a></div><div><span>NGUỒN ĐỐI CHỨNG</span><blockquote>{compared?.source?.text || 'Chưa có đoạn khớp được xác nhận.'}</blockquote>{sourceVersion && <a href={documentFileUrl(workspaceId, sourceVersion, pageOf(compared?.source?.source_spans))} target="_blank" rel="noreferrer">Mở nguồn ↗</a>}</div></div>
          {!exact && <p className="finding-note">{semantic ? 'Mô hình đề xuất các câu được hiển thị có nghĩa tương đương. Cần review ngữ cảnh; đề xuất này không cộng vào tỷ lệ khớp nguyên văn.' : item.classification_status === 'MODEL_REJECTED_EQUIVALENCE' ? 'Mô hình không xác nhận hai đoạn tương đương về nghĩa. Đây là đề xuất cho cặp đoạn đang xem, cần đối chiếu ngữ cảnh.' : item.classification_status === 'NO_SIMILARITY_HYPOTHESIS' ? 'Cấu hình đã chạy không tạo giả thuyết tương đồng cho cặp này; đây chưa phải xác nhận không có sao chép.' : 'Chưa đủ cơ sở xác nhận quan hệ giữa hai đoạn; cần đối chiếu thêm.'}</p>}
          <details className="technical-details"><summary>Vị trí và chi tiết đối chiếu</summary><pre className="auth-evidence-json">{JSON.stringify(item, null, 2)}</pre></details>
        </article>;
      })}
      {filteredMatches.length > visibleMatches && visibleMatches < 50 && <button className="secondary-button" onClick={() => setVisibleMatches((count) => count + 6)}>Xem thêm cặp đối chiếu ({Math.min(visibleMatches, filteredMatches.length)}/{filteredMatches.length})</button>}
      {filteredMatches.length > 50 && <p className="field-help">Hiển thị tối đa 50 cặp của nhóm. Export JSON để xem đầy đủ.</p>}
    </section>}
    {assessment && <section aria-label="Pipeline 2 kết quả" id="panel-assessment" hidden={tab !== 'assessment'}>
      <div className="result-section-copy"><h3>Đánh giá theo từng yêu cầu</h3><p>{llmAssessment ? 'Đánh giá ý nghĩa của yêu cầu dựa trên bằng chứng đã truy xuất. Mỗi kết luận cần được giảng viên đối chiếu.' : 'Baseline kiểm tra yêu cầu cụ thể và dấu hiệu phủ định trong report; chưa xác minh semantic/cross-source.'}</p></div>
      <div className="assessment-outcome-legend"><span className="outcome-met">{outcomes.MET ?? 0} đạt</span><span className="outcome-unmet">{outcomes.UNMET ?? 0} chưa đạt</span><span className="outcome-cannot">{outcomes.CANNOT_ASSESS ?? 0} chưa đủ bằng chứng</span></div>
      {(assessment.checklist_results ?? []).map((item) => <article className="rubric-result-card" key={item.checklist_id}>
        <header><span className="checklist-key">{item.checklist_id}</span><span className={`outcome-badge outcome-${item.checklist_outcome === 'MET' ? 'met' : item.checklist_outcome === 'UNMET' ? 'unmet' : 'cannot'}`}>{outcomeName(item.checklist_outcome)}</span></header>
        <h4>{item.statement}</h4>
        <p className="checklist-human-reason">{ASSESSMENT_REASONS[item.reason_code ?? ''] ?? (item.reason_code?.startsWith('LLM_') ? 'Chưa thể hoàn tất bước xác minh bằng chứng. Xem lý do chi tiết hoặc thử lại lượt phân tích.' : item.checklist_outcome === 'MET' ? 'Bằng chứng được dùng để đề xuất yêu cầu đã được đáp ứng.' : item.checklist_outcome === 'UNMET' ? 'Có căn cứ đề xuất yêu cầu chưa được đáp ứng; cần đối chiếu bằng chứng.' : 'Chưa tìm đủ bằng chứng để kết luận theo yêu cầu đã khai báo.')}</p>
        {(item.evidence_pack ?? []).length > 0 ? <div className="checklist-evidence"><span>NGỮ CẢNH TRUY XUẤT · CẦN ĐỐI CHIẾU YÊU CẦU</span>{(item.evidence_pack ?? []).slice(0, 3).map((entry) => <blockquote key={entry.evidence_id}>{entry.excerpt}</blockquote>)}<a href={documentFileUrl(workspaceId, reportVersionId, pageOf(item.evidence_pack?.[0]?.source_spans))} target="_blank" rel="noreferrer">Xem trong báo cáo ↗</a></div> : <p className="result-empty-card">Không có evidence truy xuất cho checklist này. Không tự quy đổi việc thiếu evidence thành 0 điểm.</p>}
        <details className="technical-details"><summary>Rationale và evidence spans</summary><p>{item.rationale}</p><pre className="auth-evidence-json">{JSON.stringify({ relation: item.verification_relation, reason: item.reason_code, matched: item.matched_evidence_spans, contradictions: item.contradiction_hits, negated: item.negated_evidence_spans, non_asserted: item.non_asserted_evidence_spans, withheld_contradictions: item.withheld_contradiction_spans, verification: item.llm_verification }, null, 2)}</pre></details>
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
