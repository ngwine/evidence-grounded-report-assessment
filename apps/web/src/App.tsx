import { useEffect, useState, type FormEvent, type ReactNode } from 'react';

import { ApiError, createRun, getRun, submitReview } from './api';
import type {
  AssessmentEvidence,
  AssessmentReport,
  AssessmentSpan,
  ChecklistResult,
  ConfigId,
  EvidenceRange,
  ReviewDecision,
  RunRecord,
  SimilarityMatch,
  SimilarityReport,
  SimilarityReviewSourceGroup,
  SourceSpan,
} from './types';

type ResultTab = 'similarity' | 'assessment';

const DOCUMENT_EXTENSIONS = ['.pdf', '.docx', '.md', '.txt'];
const CONFIGS: Array<{ id: ConfigId; name: string; description: string; meta: string }> = [
  {
    id: 'bm25-smoke',
    name: 'BM25 smoke',
    description: 'Kiểm tra luồng tích hợp nhanh, không dùng Dense hay Cross-Encoder.',
    meta: 'Nhanh · baseline',
  },
  {
    id: 'research-v0',
    name: 'Research v0',
    description: 'Cấu hình Dense + RRF + Cross-Encoder đã khóa; cần model cài trên máy chạy worker.',
    meta: 'Chậm hơn · đầy đủ',
  },
];

function statusKey(status: string): string {
  return status.toUpperCase();
}

function statusLabel(status: string): string {
  switch (statusKey(status)) {
    case 'QUEUED': return 'Đang xếp hàng';
    case 'RUNNING': return 'Đang phân tích';
    case 'SUCCEEDED': return 'Đã có kết quả';
    case 'FAILED': return 'Chạy thất bại';
    case 'BLOCKED': return 'Kết quả đã bị khóa';
    case 'CANCELLED': return 'Đã hủy';
    default: return status;
  }
}

function isTerminal(status: string): boolean {
  return ['FAILED', 'BLOCKED', 'CANCELLED'].includes(statusKey(status));
}

function isProcessing(status: string): boolean {
  return ['QUEUED', 'RUNNING'].includes(statusKey(status));
}

function percent(value: number | null | undefined): string {
  return typeof value === 'number'
    ? `${value.toLocaleString('vi-VN', { maximumFractionDigits: 2 })}%`
    : 'Chưa có';
}

function shortId(id: string): string {
  return id.length > 24 ? `${id.slice(0, 12)}…${id.slice(-8)}` : id;
}

function displayDocumentName(name: string | null | undefined, inputs?: RunRecord['inputs']): string {
  if (!name) return 'Tài liệu';
  if (/^report\.(pdf|docx|md|txt)$/i.test(name)) return inputs?.report ?? name;
  const sourceIndex = /^source-(\d+)\.(pdf|docx|md|txt)$/i.exec(name);
  if (sourceIndex) return inputs?.sources?.[Number(sourceIndex[1]) - 1] ?? name;
  return name;
}

function fileHasExtension(file: File, allowed: string[]): boolean {
  return allowed.some((extension) => file.name.toLowerCase().endsWith(extension));
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return 'Không kết nối được API cục bộ. Kiểm tra backend đang chạy ở 127.0.0.1:8001 rồi thử lại.';
}

function spanLocation(spans?: SourceSpan[], range?: EvidenceRange): string {
  const first = spans?.[0];
  const locator = first?.locator ?? first;
  const page = locator?.page_label ??
    (typeof locator?.page_index === 'number' ? locator.page_index + 1 : null);
  const parts: string[] = [];
  if (page !== null && page !== undefined && String(page).trim()) parts.push(`trang ${page}`);
  if (first && typeof first.matched_element_raw_start === 'number' && typeof first.matched_element_raw_end === 'number') {
    parts.push(`ký tự trong phần tử ${first.matched_element_raw_start}–${first.matched_element_raw_end}`);
  } else if (typeof range?.raw_start === 'number' && typeof range.raw_end === 'number') {
    parts.push(`ký tự thô trong chunk ${range.raw_start}–${range.raw_end}`);
  } else if (first && typeof first.element_raw_char_start === 'number' && typeof first.element_raw_char_end === 'number') {
    parts.push(`phạm vi phần tử ${first.element_raw_char_start}–${first.element_raw_char_end}`);
  }
  return parts.join(' · ') || 'Có vị trí trong chunk; mở artifact để xem đầy đủ';
}

function Quote({ text, empty = 'Không có trích đoạn' }: { text?: string; empty?: string }) {
  if (!text) return <p className="quote-empty">{empty}</p>;
  const long = text.length > 650;
  return (
    <div className="quote">
      <p>{long ? `${text.slice(0, 650).trimEnd()}…` : text}</p>
      {long && <details><summary>Xem toàn bộ trích đoạn</summary><p>{text}</p></details>}
    </div>
  );
}

function PanelTitle({ eyebrow, title, trailing }: {
  eyebrow: string;
  title: string;
  trailing?: ReactNode;
}) {
  return (
    <div className="panel-title">
      <div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div>
      {trailing}
    </div>
  );
}

function UploadPanel({ onCreated }: { onCreated: (run: RunRecord) => void }) {
  const [report, setReport] = useState<File | null>(null);
  const [sources, setSources] = useState<File[]>([]);
  const [rubric, setRubric] = useState<File | null>(null);
  const [configId, setConfigId] = useState<ConfigId>('bm25-smoke');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rightsBlocked, setRightsBlocked] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setRightsBlocked(false);
    if (!report || sources.length === 0 || !rubric) {
      setError('Chọn một báo cáo, ít nhất một tài liệu đối chứng và một rubric JSON.');
      return;
    }
    if (!fileHasExtension(report, DOCUMENT_EXTENSIONS) ||
      sources.some((source) => !fileHasExtension(source, DOCUMENT_EXTENSIONS)) ||
      !fileHasExtension(rubric, ['.json'])) {
      setError('Báo cáo/nguồn cần là PDF, DOCX, MD hoặc TXT; rubric cần là JSON.');
      return;
    }
    setSubmitting(true);
    try {
      const created = await createRun({ report, sources, rubric, configId });
      onCreated(created);
    } catch (cause) {
      setRightsBlocked(cause instanceof ApiError && cause.status === 409);
      setError(errorMessage(cause));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel upload-panel" aria-label="Tạo lượt phân tích">
      <PanelTitle eyebrow="01 / ĐẦU VÀO" title="Tạo lượt phân tích" trailing={<span className="panel-chip">2 pipeline</span>} />
      <p className="section-intro">Dữ liệu ở máy chạy local. API chỉ nhận tệp tải lên; web không chạy model.</p>
      <form onSubmit={onSubmit}>
        <label className="field-label" htmlFor="report-file">Báo cáo cần kiểm tra <span aria-hidden="true">*</span></label>
        <input
          id="report-file"
          className="file-control"
          type="file"
          accept=".pdf,.docx,.md,.txt"
          onChange={(event) => setReport(event.currentTarget.files?.[0] ?? null)}
          required
        />
        <p className="field-help">PDF, DOCX, MD hoặc TXT. Chọn đúng version cần phân tích.</p>

        <label className="field-label" htmlFor="source-files">Tài liệu đối chứng <span aria-hidden="true">*</span></label>
        <input
          id="source-files"
          className="file-control"
          type="file"
          accept=".pdf,.docx,.md,.txt"
          multiple
          onChange={(event) => setSources(Array.from(event.currentTarget.files ?? []))}
          required
        />
        <p className="field-help">Có thể chọn nhiều tệp. Nguồn cần được người phụ trách phê duyệt quyền trước khi worker chạy.</p>
        {sources.length > 0 && <div className="file-list" aria-label="Nguồn đã chọn">{sources.map((source, index) => <span key={`${source.name}-${index}`}>{source.name}</span>)}</div>}

        <label className="field-label" htmlFor="rubric-file">Rubric <span aria-hidden="true">*</span></label>
        <input
          id="rubric-file"
          className="file-control"
          type="file"
          accept=".json,application/json"
          onChange={(event) => setRubric(event.currentTarget.files?.[0] ?? null)}
          required
        />
        <p className="field-help">Rubric JSON theo schema của core MVP. Đây là tiêu chí đầu vào, không phải đáp án.</p>

        <fieldset className="config-fieldset">
          <legend>Cấu hình chạy</legend>
          {CONFIGS.map((config) => (
            <label className={`config-option ${configId === config.id ? 'selected' : ''}`} key={config.id}>
              <input type="radio" name="config-id" value={config.id} checked={configId === config.id} onChange={() => setConfigId(config.id)} />
              <span className="config-copy"><strong>{config.name}</strong><small>{config.description}</small></span>
              <span className="config-meta">{config.meta}</span>
            </label>
          ))}
        </fieldset>

        {error && <div role="alert" className="notice notice-error"><strong>Chưa tạo được lượt chạy.</strong><span>{error}</span>{rightsBlocked && <span>Nhờ người phụ trách backend kiểm tra quyền sử dụng và phê duyệt checksum của từng nguồn theo <code>services/backend/README.md</code>, rồi gửi lại. Không tự đánh dấu “đã duyệt” trên web.</span>}</div>}

        <button className="primary-button submit-button" type="submit" disabled={submitting}>
          {submitting ? 'Đang gửi tệp…' : 'Chạy hai pipeline'}
          <span aria-hidden="true">↗</span>
        </button>
      </form>
      <p className="safe-note">Chỉ chạy trong môi trường local. Không tải dữ liệu chưa được phép dùng vào thí nghiệm hoặc hệ thống công khai.</p>
    </section>
  );
}

function SimilarityCard({ match, index, inputs }: { match: SimilarityMatch; index: number; inputs?: RunRecord['inputs'] }) {
  const exact = match.classification_status === 'EVIDENCE_BACKED_EXACT_MATCH';
  const candidateLabel = match.provisional_similarity_type === 'VERBATIM'
    ? 'Khớp chữ cần kiểm tra — chưa đủ bằng chứng VERBATIM'
    : 'Ứng viên liên quan — chưa xác minh';
  const reportSpan = match.alignment?.report;
  const sourceSpan = match.alignment?.source;
  return (
    <article className="evidence-card">
      <div className="evidence-head">
        <div><span className="list-number">{String(index + 1).padStart(2, '0')}</span><strong>{displayDocumentName(match.source_name, inputs)}</strong></div>
        <span className={`status-pill ${exact ? 'exact' : 'pending'}`}>
          {exact ? 'Khớp nguyên văn có evidence' : 'Cần xác minh thủ công'}
        </span>
      </div>
      <div className="evidence-grid">
        <div><span className="quote-label">TRONG BÁO CÁO</span><Quote text={reportSpan?.text} /><p className="locator">{spanLocation(reportSpan?.source_spans, reportSpan)}</p></div>
        <div><span className="quote-label">TRONG NGUỒN ĐỐI CHỨNG</span><Quote text={sourceSpan?.text} /><p className="locator">{spanLocation(sourceSpan?.source_spans, sourceSpan)}</p></div>
      </div>
      <div className="evidence-footer">
        <span>{exact ? match.similarity_type ?? 'VERBATIM' : candidateLabel}</span>
        <span>Passage #{shortId(match.report_chunk_id)} · source #{shortId(match.source_chunk_id)}</span>
      </div>
    </article>
  );
}

function SimilarityView({ report, inputs }: { report: SimilarityReport | null | undefined; inputs?: RunRecord['inputs'] }) {
  const [showAll, setShowAll] = useState(false);
  if (!report) return <div className="empty-result">Pipeline 1 chưa có kết quả.</div>;
  const matches = (report.matches ?? []).filter(
    (match) => match.selected_for_document_coverage || match.selected_for_manual_review,
  );
  const sourceGroups = new Map((report.review_source_groups ?? []).map((group) => [group.group_id, group]));
  const displayGroups: Array<{ key: string; group?: SimilarityReviewSourceGroup; matches: SimilarityMatch[] }> = [];
  const groupedReviews = new Map<string, (typeof displayGroups)[number]>();
  for (const match of matches) {
    const group = match.selected_for_manual_review && match.review_group_id
      ? sourceGroups.get(match.review_group_id)
      : undefined;
    if (group) {
      let entry = groupedReviews.get(group.group_id);
      if (!entry) {
        entry = { key: `review-${group.group_id}`, group, matches: [] };
        groupedReviews.set(group.group_id, entry);
        displayGroups.push(entry);
      }
      entry.matches.push(match);
    } else {
      displayGroups.push({ key: `${match.query_id}-${match.source_chunk_id}-${match.rank}`, matches: [match] });
    }
  }
  // Page by source group so repeated candidates stay together and none are dropped.
  const selected = showAll ? displayGroups : displayGroups.slice(0, 10);
  const displayedMatches = selected.flatMap((entry) => entry.matches);
  const matchIndices = new Map(displayedMatches.map((match, index) => [match, index]));
  return (
    <div className="result-body">
      <div className="explainer"><strong>Đọc kết quả này thế nào?</strong><p>Chỉ những đoạn khớp nguyên văn đủ bằng chứng mới vào coverage đã xác nhận. Các đoạn có điểm truy xuất cao là ứng viên liên quan cần giảng viên xác minh; điểm này chưa chứng minh diễn đạt lại, tóm tắt hay đạo văn.</p></div>
      <div className="stats-grid">
        <div className="stat"><span>Khớp chính xác có bằng chứng</span><strong>{percent(report.exact_match_coverage_percentage)}</strong><small>Coverage token trong báo cáo; không phải tỷ lệ đạo văn</small></div>
        <div className="stat"><span>Đoạn cần kiểm tra tiếp</span><strong>{report.provisional_review_report_chunks ?? 0}</strong><small>{percent(report.provisional_review_passage_coverage_percentage)}: tỷ lệ token trong các chunk cần review, không phải tỷ lệ tương đồng</small></div>
        <div className="stat"><span>Tỷ lệ tương đồng hiệu chuẩn</span><strong>{percent(report.calibrated_similarity_percentage)}</strong><small>Chưa có gold set để hiệu chuẩn</small></div>
      </div>
      {(report.source_summary ?? []).length > 0 && <div className="source-summary"><h3>Nguồn có đoạn khớp nguyên văn được chọn</h3>{(report.source_summary ?? []).map((source) => <div key={source.source_document_id}><span>{displayDocumentName(source.source_name, inputs)}</span><strong>{source.selected_report_passages} đoạn</strong></div>)}</div>}
      <div className="list-heading"><div><h3>Đoạn đối chiếu</h3><p>{matches.length} đoạn được chọn để xem bằng chứng hoặc review thủ công.</p></div><span className="count-badge">{matches.length}</span></div>
      {selected.length ? selected.map((entry) => <section key={entry.key}>
        {entry.group && <div className="list-heading"><div><h3>{displayDocumentName(entry.group.source_name, inputs)}</h3><p>{entry.matches.length} đoạn báo cáo cùng đối chiếu với source #{shortId(entry.group.source_chunk_id)}.</p></div></div>}
        {entry.group && (entry.group.warning === 'REPEATED_SOURCE_CHUNK_NOT_INDEPENDENT_EVIDENCE' || entry.matches.length > 1) && <div className="notice"><strong>Nhiều ứng viên cùng trỏ tới một đoạn nguồn</strong><span>Các cặp này không phải những bằng chứng hỗ trợ độc lập. Cần kiểm tra từng đoạn báo cáo và vị trí đối chiếu bên dưới.</span></div>}
        {entry.matches.map((match) => <SimilarityCard key={`${match.query_id}-${match.source_chunk_id}-${match.rank}`} match={match} index={matchIndices.get(match)!} inputs={inputs} />)}
      </section>) : <div className="empty-result">Chưa có đoạn được chọn để gắn cờ. Điều này không chứng minh báo cáo không có tương đồng; cần kiểm tra corpus và độ bao phủ truy xuất.</div>}
      {!showAll && matches.length > displayedMatches.length && <button className="subtle-button load-more" type="button" onClick={() => setShowAll(true)}>Xem thêm {matches.length - displayedMatches.length} đoạn</button>}
    </div>
  );
}

function ChecklistEvidence({ result, inputs }: { result: ChecklistResult; inputs?: RunRecord['inputs'] }) {
  const matched = result.matched_evidence_spans ?? [];
  const negated = result.negated_evidence_spans ?? [];
  const pack = result.evidence_pack ?? [];
  return (
    <div className="checklist-evidence">
      {matched.length > 0 && <EvidenceSpanList title="Đoạn khớp điều kiện" items={matched} pack={pack} inputs={inputs} />}
      {negated.length > 0 && <EvidenceSpanList title="Đoạn có phủ định cần xem lại" items={negated} pack={pack} inputs={inputs} />}
      {matched.length === 0 && negated.length === 0 && (
        <div className="retrieval-only"><strong>Chưa có span đáp ứng checklist.</strong><p>{pack.length ? 'Các đoạn dưới đây chỉ là ứng viên truy xuất, không phải bằng chứng đã xác nhận:' : 'Không có ứng viên truy xuất để hiển thị.'}</p>{pack.slice(0, 2).map((evidence) => <div className="small-evidence" key={evidence.evidence_id}><Quote text={evidence.excerpt} /><span>{displayDocumentName(evidence.source_name, inputs)} · {spanLocation(evidence.source_spans)}</span></div>)}</div>
      )}
    </div>
  );
}

function EvidenceSpanList({ title, items, pack, inputs }: {
  title: string;
  items: AssessmentSpan[];
  pack: AssessmentEvidence[];
  inputs?: RunRecord['inputs'];
}) {
  return (
    <div className="span-group"><h5>{title}</h5>{items.slice(0, 3).map((item, index) => {
      const evidence = pack.find((entry) => entry.evidence_id === item.evidence_id);
      return <div className="small-evidence" key={`${item.evidence_id ?? 'span'}-${index}`}><Quote text={item.span?.text || evidence?.excerpt} /><span>{displayDocumentName(evidence?.source_name, inputs)} · {spanLocation(item.span?.source_spans ?? evidence?.source_spans, item.span)}</span></div>;
    })}{items.length > 3 && <small>Còn {items.length - 3} span trong artifact JSON của lượt chạy.</small>}</div>
  );
}

function outcomeLabel(outcome: string): string {
  switch (outcome) {
    case 'MET': return 'Có bằng chứng';
    case 'UNMET': return 'Chưa đáp ứng';
    case 'CANNOT_ASSESS': return 'Chưa thể đánh giá';
    default: return outcome;
  }
}

function AssessmentView({ report, inputs }: { report: AssessmentReport | null | undefined; inputs?: RunRecord['inputs'] }) {
  if (!report) return <div className="empty-result">Pipeline 2 chưa có kết quả.</div>;
  const counts = report.checklist_outcome_counts ?? {};
  return (
    <div className="result-body">
      <div className="explainer warning"><strong>Đây là bản đề xuất, không phải điểm chính thức.</strong><p>Verifier v0 đối chiếu yêu cầu rubric với đoạn trong chính báo cáo. Nó chưa kiểm chứng claim với PDF nguồn ngoài, và câu phủ định/ngữ cảnh vẫn cần người xem.</p></div>
      <div className="stats-grid">
        <div className="stat"><span>Điểm đề xuất</span><strong>{typeof report.proposed_total_score === 'number' ? `${report.proposed_total_score.toLocaleString('vi-VN')} / ${report.max_score ?? '?'}` : 'Chưa thể đề xuất'}</strong><small>CANNOT_ASSESS sẽ giữ tổng điểm ở trạng thái chưa xác định</small></div>
        <div className="stat"><span>Checklist có bằng chứng</span><strong>{counts.MET ?? 0}</strong><small>MET là tình trạng checklist, không xác nhận mọi claim đúng</small></div>
        <div className="stat"><span>Cần xem lại</span><strong>{(counts.UNMET ?? 0) + (counts.CANNOT_ASSESS ?? 0)}</strong><small>{counts.UNMET ?? 0} UNMET · {counts.CANNOT_ASSESS ?? 0} CANNOT_ASSESS</small></div>
      </div>
      {(report.criterion_results ?? []).length > 0 && <div className="criterion-summary"><h3>Đề xuất theo tiêu chí rubric</h3>{(report.criterion_results ?? []).map((criterion) => <div key={criterion.criterion_id}><span><strong>{criterion.title}</strong><small>{criterion.criterion_id} · {criterion.score_reason ?? 'Cần review'}</small></span><b>{typeof criterion.proposed_score === 'number' ? `${criterion.proposed_score.toLocaleString('vi-VN')} / ${criterion.weight}` : 'Chưa chấm'}</b></div>)}</div>}
      <div className="list-heading"><div><h3>Rubric checklist</h3><p>Reason code và trích đoạn đi cùng từng nhận định.</p></div><span className="count-badge">{report.checklist_results?.length ?? 0}</span></div>
      {(report.checklist_results ?? []).length ? (report.checklist_results ?? []).map((result) => <article className="checklist-card" key={result.checklist_id}><div className="checklist-top"><div><span className="eyebrow">{result.criterion_id} · {result.checklist_id} · {result.mode}</span><h4>{result.statement}</h4></div><span className={`status-pill outcome-${result.checklist_outcome.toLowerCase()}`}>{outcomeLabel(result.checklist_outcome)}</span></div><p className="reason">{result.reason_code ?? result.verification_relation ?? 'Chưa có lý do'}</p><ChecklistEvidence result={result} inputs={inputs} /></article>) : <div className="empty-result">Rubric chưa tạo được checklist để hiển thị.</div>}
    </div>
  );
}

function ReviewPanel({ run, onUpdated }: { run: RunRecord; onUpdated: (run: RunRecord) => void }) {
  const [reviewerName, setReviewerName] = useState('');
  const [comment, setComment] = useState('');
  const [decision, setDecision] = useState<ReviewDecision>('DEFER');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!reviewerName.trim() || !comment.trim()) {
      setError('Nhập tên người review và nhận xét trước khi lưu.');
      return;
    }
    setSubmitting(true);
    try {
      await submitReview({
        runId: run.run_id,
        decision,
        comment: comment.trim(),
        expectedRevision: run.revision ?? 0,
        reviewerName: reviewerName.trim(),
      });
      onUpdated(await getRun(run.run_id));
      setComment('');
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 409
        ? 'Lượt chạy đã được cập nhật ở nơi khác. Tải lại trang kết quả rồi review trên revision mới.'
        : errorMessage(cause));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel review-panel">
      <PanelTitle eyebrow="03 / HUMAN-IN-THE-LOOP" title="Ghi nhận review cục bộ" trailing={<span className="panel-chip">Không publish</span>} />
      <p className="section-intro">Quyết định này chỉ lưu phản hồi trên lượt chạy local, không xác thực vai trò giảng viên và không tạo điểm/kết luận chính thức.</p>
      {run.review && <div className="previous-review"><strong>Review đã lưu: {run.review.decision ?? '—'}</strong><span>{run.review.reviewer_name ? `Bởi ${run.review.reviewer_name}` : 'Người review local'} · revision {run.revision ?? '—'}</span>{run.review.comment && <p>{run.review.comment}</p>}</div>}
      <form onSubmit={onSubmit} className="review-form">
        <label className="field-label" htmlFor="reviewer-name">Tên người review local</label>
        <input id="reviewer-name" type="text" value={reviewerName} onChange={(event) => setReviewerName(event.currentTarget.value)} maxLength={80} placeholder="Ví dụ: Quý / Yến" required />
        <label className="field-label" htmlFor="review-decision">Phản hồi</label>
        <select id="review-decision" value={decision} onChange={(event) => setDecision(event.currentTarget.value as ReviewDecision)}>
          <option value="DEFER">Để kiểm tra thêm</option>
          <option value="ACCEPT">Đồng ý với đề xuất thử nghiệm</option>
          <option value="REJECT">Không đồng ý; cần sửa</option>
        </select>
        <label className="field-label" htmlFor="review-comment">Nhận xét / lý do</label>
        <textarea id="review-comment" rows={3} value={comment} onChange={(event) => setComment(event.currentTarget.value)} maxLength={2000} placeholder="Nêu đoạn evidence nào hợp lý hoặc cần xem lại…" required />
        {error && <div role="alert" className="notice notice-error">{error}</div>}
        <button type="submit" className="secondary-button" disabled={submitting}>{submitting ? 'Đang lưu…' : 'Lưu phản hồi local'}</button>
      </form>
    </section>
  );
}

function RunPanel({ run, pollError, onUpdated }: {
  run: RunRecord | null;
  pollError: string | null;
  onUpdated: (run: RunRecord) => void;
}) {
  const [tab, setTab] = useState<ResultTab>('similarity');
  if (!run) return (
    <section className="panel output-panel empty-state" aria-label="Kết quả phân tích">
      <div className="empty-icon" aria-hidden="true">⌁</div>
      <span className="eyebrow">02 / KẾT QUẢ</span>
      <h2>Chưa có lượt chạy</h2>
      <p>Chọn báo cáo, nguồn đối chứng và rubric ở bên trái. Khi worker hoàn tất, bằng chứng của hai pipeline sẽ xuất hiện ở đây.</p>
      <div className="empty-steps"><span>01 &nbsp; Upload</span><span>02 &nbsp; Worker xử lý</span><span>03 &nbsp; Xem evidence</span></div>
    </section>
  );
  const status = statusKey(run.status);
  const ready = status === 'SUCCEEDED';
  return (
    <div className="output-stack">
      <section className="panel run-status" aria-live="polite">
        <PanelTitle eyebrow="02 / LƯỢT CHẠY" title="Tiến trình phân tích" trailing={<span className={`run-state state-${status.toLowerCase()}`}>{statusLabel(run.status)}</span>} />
        <div className="run-meta"><span>Run <code title={run.run_id}>{shortId(run.run_id)}</code></span><span>Config <strong>{CONFIGS.find((config) => config.id === run.config_id)?.name ?? run.config_id ?? '—'}</strong></span>{run.job_id && <span>Job <code title={run.job_id}>{shortId(run.job_id)}</code></span>}</div>
        {isProcessing(run.status) && <div className="progress-track" role="progressbar" aria-label="Worker đang xử lý" aria-valuetext={statusLabel(run.status)}><span /></div>}
        {isProcessing(run.status) && <p className="progress-copy">Worker đang parse/chunk và chạy hai pipeline. Cấu hình Research v0 có thể cần tải model lần đầu và mất thêm thời gian.</p>}
        {pollError && <div className="notice notice-error" role="alert">{pollError}</div>}
        {status === 'FAILED' && <div className="notice notice-error" role="alert"><strong>Worker không hoàn tất lượt chạy.</strong><span>{run.error || 'Xem log worker cục bộ để biết chi tiết.'}</span></div>}
        {status === 'BLOCKED' && <div className="notice notice-error" role="alert"><strong>Kết quả đã bị khóa vì quyền nguồn thay đổi.</strong><span>{run.error || 'Liên hệ người phụ trách dữ liệu để kiểm tra.'}</span></div>}
        {run.method_warning && <div className="notice notice-muted">{run.method_warning}</div>}
      </section>
      {ready && <>
        <section className="panel results-panel">
          <PanelTitle eyebrow="KẾT QUẢ / DRAFT" title="Hai góc nhìn trên cùng báo cáo" trailing={<span className="panel-chip">Cần giảng viên xem lại</span>} />
          <div className="result-tabs" role="tablist" aria-label="Chọn pipeline">
            <button id="similarity-tab" type="button" role="tab" aria-controls="pipeline-panel" aria-selected={tab === 'similarity'} onClick={() => setTab('similarity')}>01 &nbsp; Tương đồng</button>
            <button id="assessment-tab" type="button" role="tab" aria-controls="pipeline-panel" aria-selected={tab === 'assessment'} onClick={() => setTab('assessment')}>02 &nbsp; Rubric & evidence</button>
          </div>
          <div id="pipeline-panel" role="tabpanel" aria-labelledby={tab === 'similarity' ? 'similarity-tab' : 'assessment-tab'}>
            {tab === 'similarity'
              ? <SimilarityView report={run.similarity_report} inputs={run.inputs} />
              : <AssessmentView report={run.assessment_report} inputs={run.inputs} />}
          </div>
        </section>
        <ReviewPanel key={run.run_id} run={run} onUpdated={onUpdated} />
      </>}
    </div>
  );
}

export default function App() {
  const [run, setRun] = useState<RunRecord | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);

  useEffect(() => {
    const lastRunId = window.localStorage.getItem('kltn-local-last-run-id');
    if (!lastRunId) return;
    const controller = new AbortController();
    getRun(lastRunId, controller.signal)
      .then((restored) => { if (!controller.signal.aborted) setRun(restored); })
      .catch((cause) => {
        if (!controller.signal.aborted && cause instanceof ApiError && cause.status === 404) {
          window.localStorage.removeItem('kltn-local-last-run-id');
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!run || isTerminal(run.status)) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      if (!active || !run) return;
      try {
        const next = await getRun(run.run_id, controller.signal);
        if (!active) return;
        setRun(next);
        setPollError(null);
      } catch (cause) {
        if (active) setPollError(errorMessage(cause));
      } finally {
        if (active) timer = setTimeout(poll, statusKey(run.status) === 'SUCCEEDED' ? 15000 : 2500);
      }
    }
    timer = setTimeout(poll, 1000);
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [run?.run_id, run?.status]);

  function onCreated(next: RunRecord) {
    setPollError(null);
    window.localStorage.setItem('kltn-local-last-run-id', next.run_id);
    setRun(next);
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace">Bỏ qua điều hướng</a>
      <header className="site-header">
        <div className="brand"><span className="brand-mark">EG</span><div><strong>Evidence Grounded</strong><small>Research workspace</small></div></div>
        <div className="header-right"><span className="local-pill"><span aria-hidden="true" /> LOCAL DEMO</span><span className="header-caption">Hai pipeline · Một luồng chạy</span></div>
      </header>
      <main id="workspace">
        <div className="hero"><div><span className="eyebrow">KLTN / CORE FEASIBILITY</span><h1>Phân tích báo cáo<br /><em>dựa trên bằng chứng.</em></h1><p>Upload một báo cáo, nguồn đối chứng và rubric. Worker chạy hai pipeline; kết quả hiển thị cùng đoạn dẫn chứng để người review kiểm tra.</p></div><div className="hero-aside"><span className="hero-aside-number">01 — 02</span><p>Similarity retrieval<br />Evidence-grounded assessment</p></div></div>
        <div className="scope-banner" role="note"><span className="scope-icon" aria-hidden="true">i</span><p>Đây là bản chạy thử cục bộ. Kết quả không phải kết luận đạo văn, không phải điểm chính thức; phản hồi review trên màn hình này cũng chưa được xác thực hoặc publish.</p></div>
        <div className="workspace-grid"><UploadPanel onCreated={onCreated} /><RunPanel run={run} pollError={pollError} onUpdated={setRun} /></div>
      </main>
      <footer className="site-footer"><span>Evidence Grounded · Local research build</span><span>Luôn kiểm tra quyền dữ liệu và đối chiếu evidence trước khi sử dụng.</span></footer>
    </div>
  );
}
