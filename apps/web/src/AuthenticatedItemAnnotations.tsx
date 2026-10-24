import { useEffect, useRef, useState, type FormEvent } from 'react';

import {
  AuthenticatedApiError, createItemAnnotation, exportItemAnnotations, getAnalysisRun,
  listAnnotationItems, listItemAnnotations, operationKey,
} from './authenticatedApi';
import type {
  AnalysisRun, AnnotationItem, AnnotationPage, AnnotationSpan, ItemAnnotation, ItemAnnotationBody,
  ItemAnnotationLabel,
} from './authenticatedApi';

type Props = {
  actorId: string; workspaceId: string; runId: string; runRevision: number; canReview: boolean;
  onRunChanged: (run: AnalysisRun) => void; onAccessError: (cause: unknown) => void;
};
type Draft = { label: ItemAnnotationLabel | ''; rationale: string; spanIds: string[]; quote: 'YES' | 'NO' | 'UNSURE' | '' };
type Scope = { key: string; controller: AbortController };
const MAX_VISIBLE = 200;
const SPAN_BATCH = 20;
const P1_LABELS: ItemAnnotationLabel[] = ['VERBATIM', 'PARAPHRASE', 'SUMMARY', 'NONE', 'UNSURE'];
const P2_LABELS: ItemAnnotationLabel[] = ['MET', 'UNMET', 'CANNOT_ASSESS', 'UNSURE'];

function initialDraft(item: AnnotationItem): Draft {
  const annotation = item.latest_annotation;
  return { label: annotation?.label ?? '', rationale: annotation?.rationale ?? '',
    spanIds: annotation?.evidence_span_ids ?? [], quote: annotation?.quote_or_citation ?? '' };
}

function validation(item: AnnotationItem, draft: Draft): string | null {
  if (!(item.pipeline === 'SIMILARITY' ? P1_LABELS : P2_LABELS).includes(draft.label as ItemAnnotationLabel)) return 'Chọn nhãn review.';
  if (!draft.rationale.trim()) return 'Cần lý do review.';
  if (draft.rationale.length > 4000) return 'Lý do tối đa 4000 ký tự.';
  if (draft.spanIds.length > 100) return 'Chọn tối đa 100 evidence spans.';
  const spans = item.span_options.filter((span) => draft.spanIds.includes(span.span_id));
  if (spans.length !== draft.spanIds.length) return 'Evidence phải thuộc đúng mục và version này.';
  const report = spans.some((span) => span.side === 'REPORT');
  const source = spans.some((span) => span.side === 'SOURCE');
  if (item.pipeline === 'SIMILARITY') {
    if (!draft.quote) return 'Chọn trạng thái trích dẫn hoặc citation.';
    if (['VERBATIM', 'PARAPHRASE', 'SUMMARY'].includes(draft.label) && (!report || !source)) return 'Nhãn similarity dương cần evidence ở cả REPORT và SOURCE.';
  } else if (['MET', 'UNMET'].includes(draft.label) && !report) return 'MET và UNMET cần ít nhất một evidence REPORT.';
  return null;
}

function bodyFor(item: AnnotationItem, draft: Draft): ItemAnnotationBody {
  return { item_id: item.item_id, label: draft.label as ItemAnnotationLabel,
    evidence_span_ids: [...draft.spanIds].sort(), rationale: draft.rationale.trim(),
    ...(item.pipeline === 'SIMILARITY' ? { quote_or_citation: draft.quote as 'YES' | 'NO' | 'UNSURE' } : {}) };
}

function annotationSignature(item: AnnotationItem): string | null {
  return item.latest_annotation ? JSON.stringify(bodyFor(item, initialDraft(item))) : null;
}

function accessLost(cause: unknown): boolean {
  return cause instanceof AuthenticatedApiError && ([401, 403, 404].includes(cause.status)
    || ['GOVERNANCE_NOT_APPROVED', 'RESULT_INTEGRITY_FAILED', 'ANALYSIS_INPUT_CHANGED', 'PROVENANCE_INVALID',
      'INDEX_INTEGRITY_FAILED', 'ANNOTATION_INTEGRITY_FAILED'].includes(cause.code));
}

function errorText(cause: unknown): string {
  if (!(cause instanceof AuthenticatedApiError)) return 'Chưa nhận được xác nhận lưu. Có thể thử lại cùng nội dung với cùng mã thao tác.';
  if (cause.code === 'REVISION_CONFLICT') return 'Lượt chạy đã có revision mới. Bản nháp được giữ lại; tải revision mới trước khi thử lưu lại.';
  if (cause.status === 409) return `Chưa lưu phiên bản review. ${cause.message}`;
  if (cause.status === 422) return `Kiểm tra nhãn, lý do và evidence. ${cause.message}`;
  return `Chưa thực hiện được yêu cầu review. ${cause.message}`;
}

function spanLocator(span: AnnotationSpan): string {
  const page = span.locator.page_index;
  return `${span.chunk_id} · raw [${span.raw_start}, ${span.raw_end})${typeof page === 'number' ? ` · trang ${page + 1}` : ''}`;
}

export default function AuthenticatedItemAnnotations({ actorId, workspaceId, runId, runRevision, canReview, onRunChanged, onAccessError }: Props) {
  const key = JSON.stringify([actorId, workspaceId, runId, canReview]);
  const renderedScope = useRef(key);
  renderedScope.current = key;
  const scope = useRef<Scope | null>(null);
  const callbacks = useRef({ onRunChanged, onAccessError });
  callbacks.current = { onRunChanged, onAccessError };
  const retryKeys = useRef(new Map<string, { signature: string; key: string }>());
  const [items, setItems] = useState<AnnotationPage<AnnotationItem> | null>(null);
  const [history, setHistory] = useState<AnnotationPage<ItemAnnotation> | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [visibleSpans, setVisibleSpans] = useState<Record<string, number>>({});
  const [revision, setRevision] = useState(runRevision);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);

  function current(value: Scope | null): value is Scope {
    return value !== null && value === scope.current && value.key === renderedScope.current && !value.controller.signal.aborted;
  }

  function fail(cause: unknown, value: Scope) {
    if (!current(value)) return;
    if (accessLost(cause)) {
      setItems(null); setHistory(null); setDrafts({}); setNotice(null); setError(null);
      retryKeys.current.clear(); value.controller.abort();
      callbacks.current.onAccessError(cause);
      return;
    }
    setError(errorText(cause));
    setRequestId(cause instanceof AuthenticatedApiError ? cause.requestId : null);
    if (cause instanceof AuthenticatedApiError && cause.code === 'REVISION_CONFLICT') setConflict(true);
  }

  useEffect(() => {
    const value: Scope = { key, controller: new AbortController() };
    scope.current = value;
    retryKeys.current.clear();
    setItems(null); setHistory(null); setDrafts({}); setVisibleSpans({}); setRevision(runRevision);
    setError(null); setRequestId(null); setNotice(null); setConflict(false); setLoading(canReview); setBusy(false);
    if (canReview) {
      listAnnotationItems(workspaceId, runId, null, value.controller.signal).then((page) => {
        if (!current(value)) return;
        setItems({ ...page, items: page.items.slice(0, MAX_VISIBLE) });
        setDrafts(Object.fromEntries(page.items.slice(0, MAX_VISIBLE).map((item) => [item.item_id, initialDraft(item)])));
        setRevision((previous) => Math.max(previous, page.run_revision));
      }).catch((cause) => fail(cause, value)).finally(() => { if (current(value)) setLoading(false); });
    }
    return () => { value.controller.abort(); };
    // Only account/workspace/run identity starts a new review scope. Callbacks and revisions can refresh in place.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => { setRevision((previous) => Math.max(previous, runRevision)); }, [runRevision]);

  function edit(itemId: string, patch: Partial<Draft>) {
    setDrafts((previous) => ({ ...previous, [itemId]: { ...previous[itemId], ...patch } }));
    setNotice(null);
  }

  async function refreshRevision() {
    const value = scope.current;
    if (!current(value) || busy) return;
    setBusy(true); setError(null); setRequestId(null);
    try {
      const run = await getAnalysisRun(workspaceId, runId, value.controller.signal);
      if (!current(value)) return;
      setRevision(run.revision); setConflict(false); callbacks.current.onRunChanged(run);
      setNotice('Đã tải revision mới; nhãn, lý do và evidence trong bản nháp được giữ lại.');
    } catch (cause) { fail(cause, value); }
    finally { if (current(value)) setBusy(false); }
  }

  async function save(event: FormEvent, item: AnnotationItem) {
    event.preventDefault();
    const value = scope.current;
    const draft = drafts[item.item_id];
    if (!current(value) || busy || !canReview || !draft || validation(item, draft)) return;
    const body = bodyFor(item, draft);
    const signature = JSON.stringify(body);
    let retry = retryKeys.current.get(item.item_id);
    if (retry?.signature !== signature) {
      retry = { signature, key: operationKey() }; retryKeys.current.set(item.item_id, retry);
    }
    setBusy(true); setError(null); setRequestId(null); setNotice(null);
    try {
      const annotation = await createItemAnnotation(workspaceId, runId, body, revision, retry.key, value.controller.signal);
      if (!current(value)) return;
      setItems((previous) => previous && ({ ...previous, run_revision: Math.max(previous.run_revision, annotation.run_revision),
        items: previous.items.map((entry) => entry.item_id === item.item_id ? { ...entry, latest_annotation: annotation } : entry) }));
      // Reload history explicitly so an append cannot mix with an older cursor snapshot.
      setHistory(null); setRevision((previous) => Math.max(previous, annotation.run_revision)); setConflict(false);
      setNotice(`Đã lưu review phiên bản ${annotation.annotation_revision}. Kết quả máy vẫn giữ nguyên.`);
      const run = await getAnalysisRun(workspaceId, runId, value.controller.signal);
      if (current(value)) { setRevision(run.revision); callbacks.current.onRunChanged(run); }
    } catch (cause) { fail(cause, value); }
    finally { if (current(value)) setBusy(false); }
  }

  async function moreItems() {
    const value = scope.current;
    if (!current(value) || busy || !items?.page.has_more || items.items.length >= MAX_VISIBLE) return;
    setBusy(true); setError(null); setRequestId(null);
    try {
      const page = await listAnnotationItems(workspaceId, runId, items.page.next_cursor, value.controller.signal);
      if (!current(value)) return;
      const known = new Set(items.items.map((item) => item.item_id));
      const additional = page.items.filter((item) => !known.has(item.item_id)).slice(0, MAX_VISIBLE - items.items.length);
      setItems({ ...page, items: [...items.items, ...additional] });
      setDrafts((previous) => ({ ...Object.fromEntries(additional.map((item) => [item.item_id, initialDraft(item)])), ...previous }));
      setRevision((previous) => Math.max(previous, page.run_revision));
    } catch (cause) { fail(cause, value); }
    finally { if (current(value)) setBusy(false); }
  }

  async function loadHistory(more = false) {
    const value = scope.current;
    if (!current(value) || busy || more && (!history?.page.has_more || history.items.length >= MAX_VISIBLE)) return;
    setBusy(true); setError(null); setRequestId(null);
    try {
      const page = await listItemAnnotations(workspaceId, runId, more ? history?.page.next_cursor : null, value.controller.signal);
      if (!current(value)) return;
      const previous = more ? history?.items ?? [] : [];
      const known = new Set(previous.map((annotation) => annotation.id));
      setHistory({ ...page, items: [...previous, ...page.items.filter((annotation) => !known.has(annotation.id))].slice(0, MAX_VISIBLE) });
      setRevision((previousRevision) => Math.max(previousRevision, page.run_revision));
    } catch (cause) { fail(cause, value); }
    finally { if (current(value)) setBusy(false); }
  }

  async function exportReviews() {
    const value = scope.current;
    if (!current(value) || busy) return;
    setBusy(true); setError(null); setRequestId(null);
    try {
      const result = await exportItemAnnotations(workspaceId, runId, value.controller.signal);
      if (!current(value)) return;
      const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }));
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = `item-reviews-${runId.replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 80) || 'run'}.json`;
      anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) { fail(cause, value); }
    finally { if (current(value)) setBusy(false); }
  }

  if (!canReview) return null;
  return <section className="auth-item-annotations" aria-label="Review từng mục">
    <h4>Review từng mục · MODEL_VISIBLE_REVIEW</h4>
    <p className="notice notice-muted">Bạn đang nhìn thấy kết quả máy. Các nhãn này là review có hiển thị dự đoán, không phải gold độc lập được gán nhãn mù. Review không ghi đè kết quả máy hoặc công bố điểm chính thức.</p>
    <p className="field-help">Chỉ hiển thị review của tài khoản hiện tại. Mỗi lần sửa tạo một phiên bản bất biến mới; nhãn và lý do trước đó được giữ trong lịch sử.</p>
    <div aria-live="polite">
      {loading && <p role="status">Đang tải các mục review…</p>}
      {error && <div className="notice notice-error" role="alert">{error}{requestId && <small>Mã yêu cầu: {requestId}</small>}</div>}
      {notice && <p className="notice" role="status">{notice}</p>}
    </div>
    {conflict && <button className="secondary-button" disabled={busy} onClick={() => { void refreshRevision(); }}>Tải revision mới, giữ bản nháp</button>}
    {items?.items.length === 0 && <p>Không có mục review trong kết quả của lượt chạy này.</p>}
    {items?.items.map((item, index) => {
      const draft = drafts[item.item_id] ?? initialDraft(item);
      const invalid = validation(item, draft);
      const unchanged = annotationSignature(item) === JSON.stringify(bodyFor(item, draft));
      const count = visibleSpans[item.item_id] ?? SPAN_BATCH;
      const formId = `item-review-${index}`;
      return <article key={item.item_id} className="auth-item-review" aria-label={`Mục review ${item.item_id}`}>
        <h5>{item.pipeline === 'SIMILARITY' ? 'Pipeline 1 · Cặp báo cáo–nguồn' : `Pipeline 2 · ${item.checklist_id}`}</h5>
        <code className="auth-resource-id">{item.item_id}</code>
        {item.statement && <p>{item.statement}</p>}
        <div className="auth-review-texts">
          <details><summary>Văn bản REPORT đã khóa</summary><code className="auth-resource-id">{item.report_version_id}</code><pre>{item.report_text}</pre></details>
          {item.source_text !== null && <details><summary>Văn bản SOURCE đã khóa</summary><code className="auth-resource-id">{item.source_version_id}</code><pre>{item.source_text}</pre></details>}
        </div>
        {item.latest_annotation && <div className="auth-item-latest"><strong>Review đã lưu · phiên bản {item.latest_annotation.annotation_revision} · {item.latest_annotation.label}</strong>
          <p>{item.latest_annotation.rationale}</p><small>{item.latest_annotation.created_at} · {item.latest_annotation.evidence_span_ids.length} evidence spans{item.latest_annotation.quote_or_citation ? ` · quote/citation: ${item.latest_annotation.quote_or_citation}` : ''}</small></div>}
        <form onSubmit={(event) => { void save(event, item); }}>
          <div className="auth-review-fields"><div><label className="field-label" htmlFor={`${formId}-label`}>Nhãn review {item.item_id}</label>
            <select id={`${formId}-label`} disabled={busy} value={draft.label} onChange={(event) => edit(item.item_id, { label: event.target.value as Draft['label'] })}><option value="">Chọn nhãn</option>{(item.pipeline === 'SIMILARITY' ? P1_LABELS : P2_LABELS).map((label) => <option key={label} value={label}>{label}</option>)}</select></div>
            {item.pipeline === 'SIMILARITY' && <div><label className="field-label" htmlFor={`${formId}-quote`}>Trích dẫn hoặc citation {item.item_id}</label><select id={`${formId}-quote`} disabled={busy} value={draft.quote} onChange={(event) => edit(item.item_id, { quote: event.target.value as Draft['quote'] })}><option value="">Chọn trạng thái</option><option value="YES">YES · Có</option><option value="NO">NO · Không</option><option value="UNSURE">UNSURE · Chưa rõ</option></select></div>}
          </div>
          <fieldset className="auth-review-spans" disabled={busy}><legend>Evidence từ đúng version · đã chọn {draft.spanIds.length}/100</legend>
            <p className="field-help">Chọn các khoảng văn bản có sẵn; raw offsets dùng dạng [start, end). Nhãn VERBATIM/PARAPHRASE/SUMMARY cần cả REPORT và SOURCE; MET/UNMET cần REPORT.</p>
            {item.span_options.length === 0 && <p>Không có span để chọn. Dùng UNSURE hoặc CANNOT_ASSESS khi phù hợp và giải thích lý do.</p>}
            {item.span_options.slice(0, count).map((span) => <label key={span.span_id} className="auth-review-span"><input type="checkbox" checked={draft.spanIds.includes(span.span_id)} disabled={busy || draft.spanIds.length >= 100 && !draft.spanIds.includes(span.span_id)} onChange={(event) => edit(item.item_id, { spanIds: event.target.checked ? [...draft.spanIds, span.span_id] : draft.spanIds.filter((id) => id !== span.span_id) })} />
              <span><strong>{span.side} · {spanLocator(span)}</strong><code>{span.document_version_id}</code><span className="auth-review-quote">{span.quote_text}</span></span></label>)}
            {item.span_options.length > count && <button type="button" className="subtle-button" onClick={() => setVisibleSpans((previous) => ({ ...previous, [item.item_id]: count + SPAN_BATCH }))}>Hiện thêm evidence spans ({count}/{item.span_options.length})</button>}
          </fieldset>
          <label className="field-label" htmlFor={`${formId}-rationale`}>Lý do review {item.item_id}</label><textarea id={`${formId}-rationale`} required maxLength={4000} disabled={busy} value={draft.rationale} onChange={(event) => edit(item.item_id, { rationale: event.target.value })} />
          <p className="field-help">{invalid ?? (unchanged ? 'Nội dung trùng phiên bản đã lưu. Thay đổi nội dung để tạo phiên bản tiếp theo.' : 'Lưu sẽ thêm phiên bản review mới theo tài khoản hiện tại.')}</p>
          <button className="secondary-button" disabled={busy || !!invalid || unchanged || conflict}>Lưu phiên bản review</button>
        </form>
      </article>;
    })}
    {items?.page.has_more && items.items.length < MAX_VISIBLE && <button className="subtle-button" disabled={busy} onClick={() => { void moreItems(); }}>Tải thêm mục review</button>}
    {items && items.items.length >= MAX_VISIBLE && <p>Hiển thị tối đa {MAX_VISIBLE} mục trong trang này. Export JSON review để xem toàn bộ mục và lịch sử của bạn.</p>}
    {!loading && items && <div className="auth-actions"><button className="subtle-button" disabled={busy} onClick={() => { void loadHistory(); }}>Xem lịch sử review</button><button className="secondary-button" disabled={busy} onClick={() => { void exportReviews(); }}>Export JSON review</button></div>}
    {history && <section aria-label="Lịch sử review của bạn"><h5>Lịch sử review bất biến của bạn</h5>
      {history.items.length === 0 && <p>Chưa có review đã lưu.</p>}
      <ol className="auth-review-history">{history.items.map((annotation) => <li key={annotation.id}><strong>{annotation.pipeline} · {annotation.label} · phiên bản {annotation.annotation_revision}</strong><code className="auth-resource-id">{annotation.item_id}</code><p>{annotation.rationale}</p><small>{annotation.created_at} · {annotation.evidence_span_ids.length} evidence spans · {annotation.annotation_mode}</small></li>)}</ol>
      {history.page.has_more && history.items.length < MAX_VISIBLE && <button className="subtle-button" disabled={busy} onClick={() => { void loadHistory(true); }}>Tải thêm lịch sử review</button>}
      {history.items.length >= MAX_VISIBLE && <p>Hiển thị tối đa {MAX_VISIBLE} phiên bản. Export JSON review chứa toàn bộ lịch sử của bạn.</p>}
    </section>}
  </section>;
}
