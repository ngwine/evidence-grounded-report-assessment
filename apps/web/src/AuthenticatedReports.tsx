import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';

import {
  AuthenticatedApiError, createAnalysisRun, createIndexGeneration, exportAnalysisRun,
  getAnalysisEvidence, getAnalysisResults, getAnalysisRun, getDocumentVersion, getIndexGeneration,
  getJob, listDocuments, listDocumentVersions, listRubrics, listRubricVersions, operationKey, uploadDocument,
  createAnalysisReview,
} from './authenticatedApi';
import type {
  Actor, AnalysisConfigId, AnalysisResults, AnalysisRun, DocumentKind, DocumentRecord,
  DocumentVersion, IndexGeneration, JobRecord, Page, Rubric, RubricVersion, RunEvidence,
} from './authenticatedApi';
import AuthenticatedResults from './AuthenticatedResults';

const TERMINAL = new Set(['SUCCEEDED', 'FAILED', 'FAILED_FINAL', 'CANCELLED', 'READY', 'ACTIVE', 'SUPERSEDED', 'REVOKED', 'INVALIDATED', 'TOMBSTONED']);
const PARSED = new Set(['PARSED', 'INDEXING', 'READY']);
const MAX_FILE_BYTES = 20 * 1024 * 1024;

type DocumentWithKind = DocumentRecord & { kind: DocumentKind };
type ParseOperation = { uploadId: string; versionId: string; job: JobRecord | null };
type Props = { actor: Actor; workspaceId: string; rubricRefreshKey: string; onAuthenticationError: (error: unknown) => void };

function errorText(error: unknown): string {
  if (!(error instanceof AuthenticatedApiError)) return 'Chưa kết nối được API. Không có xác nhận lưu thành công; có thể thử lại.';
  if (error.status === 401) return 'Phiên đã hết hạn. Đăng nhập lại để tiếp tục.';
  if (error.status === 403) return error.code === 'CSRF_INVALID'
    ? 'Phiên bảo vệ đã thay đổi. Tải lại trang trước khi tiếp tục.' : 'Quyền thực hiện thao tác này không còn hiệu lực.';
  if (error.status === 404) return 'Không tìm thấy tài nguyên hoặc quyền truy cập đã thay đổi.';
  if (error.code === 'GOVERNANCE_NOT_APPROVED') return 'Tài liệu chưa có quyền sử dụng hợp lệ. Kiểm tra governance record, đối tượng được duyệt và thời hạn; không thể bỏ qua bước này.';
  if (error.code === 'REVISION_CONFLICT') return 'Tài liệu đã có revision mới. Tải lại danh sách trước khi upload version tiếp theo.';
  if (error.status === 413) return 'File vượt giới hạn 20 MB hoặc request quá lớn.';
  if (error.status === 409) return `Chưa thể thực hiện ở trạng thái hiện tại. ${error.message}`;
  if (error.status === 422 || error.status === 415) return `Kiểm tra lại nội dung hoặc định dạng. ${error.message}`;
  if (error.status === 503) return 'Dịch vụ dữ liệu chưa sẵn sàng. Kết quả chưa được xác nhận; thử tải lại sau.';
  return 'Chưa thực hiện được yêu cầu. Tải lại dữ liệu hoặc kiểm tra worker.';
}

function versionLabel(value: DocumentVersion): string {
  return `v${value.version_no} · ${value.processing_state} · ${value.chunk_count} chunks · ${value.governance_state}`;
}

export default function AuthenticatedReports({ actor, workspaceId, rubricRefreshKey, onAuthenticationError }: Props) {
  const capabilities = actor.memberships.filter((item) => item.workspace_id === workspaceId).flatMap((item) => item.capabilities);
  const canReadReports = capabilities.includes('report.read');
  const canReadSources = capabilities.includes('source.read');
  const canRun = capabilities.includes('run.create');
  const canReadRuns = capabilities.includes('run.read');
  const canUploadReport = capabilities.includes('report.upload');
  const canUploadSource = capabilities.includes('source.upload');
  const canRubrics = capabilities.includes('rubric.manage');
  const active = useRef(false);
  const runSelection = useRef(0);
  const refreshInFlight = useRef(false);
  const [reports, setReports] = useState<Page<DocumentRecord> | null>(null);
  const [sources, setSources] = useState<Page<DocumentRecord> | null>(null);
  const [versionCache, setVersionCache] = useState<Record<string, DocumentVersion>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploadKind, setUploadKind] = useState<DocumentKind>(canUploadReport ? 'REPORT' : 'CORPUS_SOURCE');
  const [uploadExistingId, setUploadExistingId] = useState('');
  const [documentKey, setDocumentKey] = useState('');
  const [title, setTitle] = useState('');
  const [governanceId, setGovernanceId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const uploadRetry = useRef<{ signature: string; file: File; key: string } | null>(null);
  const indexKeys = useRef(new Map<string, string>());
  const runKey = useRef<{ signature: string; key: string } | null>(null);
  const [parseOperations, setParseOperations] = useState<ParseOperation[]>([]);
  const [generations, setGenerations] = useState<Record<string, IndexGeneration>>({});
  const [configId, setConfigId] = useState<AnalysisConfigId>('bm25-smoke');
  const [detail, setDetail] = useState<DocumentWithKind | null>(null);
  const [history, setHistory] = useState<Page<DocumentVersion> | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const historySequence = useRef(0);
  const [selectedReportId, setSelectedReportId] = useState('');
  const [reportVersionId, setReportVersionId] = useState('');
  const [sourceVersions, setSourceVersions] = useState<Record<string, string>>({});
  const [rubrics, setRubrics] = useState<Page<Rubric> | null>(null);
  const [rubricId, setRubricId] = useState('');
  const [rubricVersions, setRubricVersions] = useState<Page<RubricVersion> | null>(null);
  const [rubricVersionId, setRubricVersionId] = useState('');
  const [runType, setRunType] = useState<AnalysisRun['run_type']>('BOTH');
  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [runLookup, setRunLookup] = useState('');
  const [results, setResults] = useState<AnalysisResults | null>(null);
  const [evidence, setEvidence] = useState<Page<RunEvidence> | null>(null);
  const [loadingResults, setLoadingResults] = useState(false);
  const [reviewReason, setReviewReason] = useState('');

  const fail = useCallback((cause: unknown) => {
    if (!active.current) return;
    setError(errorText(cause));
    setRequestId(cause instanceof AuthenticatedApiError ? cause.requestId : null);
    if (cause instanceof AuthenticatedApiError && cause.status === 401) onAuthenticationError(cause);
    if (cause instanceof AuthenticatedApiError && ([401, 403, 404].includes(cause.status)
        || ['GOVERNANCE_NOT_APPROVED', 'RESULT_INTEGRITY_FAILED', 'ANALYSIS_INPUT_CHANGED', 'PROVENANCE_INVALID', 'INDEX_INTEGRITY_FAILED'].includes(cause.code))) {
      // Revoked/expired access must not leave an earlier result on screen.
      setRun(null); setResults(null); setEvidence(null);
      runSelection.current += 1;
    }
  }, [onAuthenticationError]);

  const cacheVersions = useCallback((values: DocumentVersion[]) => {
    if (active.current) setVersionCache((current) => ({ ...current, ...Object.fromEntries(values.map((value) => [value.id, value])) }));
  }, []);

  const refreshDocuments = useCallback(async () => {
    // Avoid an overlapping refresh replacing a newer current-version pointer.
    if (refreshInFlight.current) return;
    refreshInFlight.current = true;
    try {
      const [reportPage, sourcePage] = await Promise.all([
        canReadReports ? listDocuments(workspaceId, 'REPORT') : Promise.resolve(null),
        canReadSources ? listDocuments(workspaceId, 'CORPUS_SOURCE') : Promise.resolve(null),
      ]);
      const documents = [...(reportPage?.items ?? []), ...(sourcePage?.items ?? [])];
      const currentVersions = await Promise.all(documents.map((item) => getDocumentVersion(workspaceId, item.current_version_id)));
      if (!active.current) return;
      setReports(reportPage); setSources(sourcePage); cacheVersions(currentVersions);
    } catch (cause) { fail(cause); }
    finally { refreshInFlight.current = false; if (active.current) setLoading(false); }
  }, [workspaceId, canReadReports, canReadSources, cacheVersions, fail]);

  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  useEffect(() => { void refreshDocuments(); }, [refreshDocuments]);
  useEffect(() => {
    if (!canRun || !canRubrics) return;
    let cancelled = false;
    listRubrics(workspaceId).then((page) => { if (!cancelled && active.current) setRubrics(page); }).catch((cause) => { if (!cancelled) fail(cause); });
    return () => { cancelled = true; };
  }, [workspaceId, canRun, canRubrics, rubricRefreshKey, fail]);

  useEffect(() => {
    setRubricVersions(null); setRubricVersionId('');
    if (!rubricId) return;
    let cancelled = false;
    listRubricVersions(workspaceId, rubricId).then((page) => {
      if (!cancelled && active.current) setRubricVersions(page);
    }).catch((cause) => { if (!cancelled) fail(cause); });
    return () => { cancelled = true; };
  }, [workspaceId, rubricId, rubricRefreshKey, fail]);

  const pendingVersions = Object.values(versionCache).filter((item) => ['QUEUED', 'PARSING'].includes(item.processing_state)).map((item) => item.id);
  const pendingParse = parseOperations.filter((item) => item.job === null || !TERMINAL.has(item.job.state));
  const pendingIndexes = Object.values(generations).filter((item) => !TERMINAL.has(item.state));
  const pendingRunId = run !== null && !TERMINAL.has(run.state) ? run.id : null;
  const pollKey = JSON.stringify([pendingVersions, pendingParse.map((item) => item.uploadId), pendingIndexes.map((item) => item.id), pendingRunId]);

  useEffect(() => {
    if (!pendingVersions.length && !pendingParse.length && !pendingIndexes.length && pendingRunId === null) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const selection = runSelection.current;
    async function tick() {
      try {
        const [versionValues, jobValues, indexValues, runValue] = await Promise.all([
          Promise.all(pendingVersions.map((id) => getDocumentVersion(workspaceId, id))),
          Promise.all(pendingParse.map((item) => getJob(workspaceId, item.uploadId))),
          Promise.all(pendingIndexes.map((item) => getIndexGeneration(workspaceId, item.id))),
          pendingRunId ? getAnalysisRun(workspaceId, pendingRunId) : Promise.resolve(null),
        ]);
        if (stopped || !active.current) return;
        cacheVersions(versionValues);
        setParseOperations((current) => current.map((item) => ({ ...item, job: jobValues.find((job) => job.id === item.uploadId) ?? item.job })));
        setGenerations((current) => ({ ...current, ...Object.fromEntries(indexValues.map((item) => [item.document_version_id, item])) }));
        if (runValue && selection === runSelection.current) setRun(runValue);
        if (jobValues.some((item) => item.state === 'SUCCEEDED') || indexValues.some((item) => item.state === 'ACTIVE')) void refreshDocuments();
      } catch (cause) {
        if (stopped) return;
        fail(cause);
        // Authorization failures stop polling; don't repeatedly request revoked content.
        if (cause instanceof AuthenticatedApiError && [401, 403, 404].includes(cause.status)) return;
      }
      if (!stopped) timer = setTimeout(() => { void tick(); }, 2500);
    }
    timer = setTimeout(() => { void tick(); }, 1000);
    return () => { stopped = true; clearTimeout(timer); };
    // IDs determine the polling lifecycle; state changes keep a single in-flight request per cycle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, pollKey, fail, cacheVersions, refreshDocuments]);

  useEffect(() => {
    if (run === null || run.state !== 'SUCCEEDED') return;
    let cancelled = false;
    const selection = runSelection.current;
    setLoadingResults(true); setResults(null); setEvidence(null);
    Promise.all([getAnalysisResults(workspaceId, run.id), getAnalysisEvidence(workspaceId, run.id)])
      .then(([value, page]) => {
        if (!cancelled && active.current && selection === runSelection.current) { setResults(value); setEvidence(page); }
      }).catch((cause) => { if (!cancelled) fail(cause); })
      .finally(() => { if (!cancelled && active.current) setLoadingResults(false); });
    return () => { cancelled = true; };
  }, [workspaceId, run?.id, run?.state, fail]);

  async function openHistory(document: DocumentWithKind) {
    const sequence = ++historySequence.current;
    setDetail(document); setHistory(null); setLoadingHistory(true); setError(null);
    try {
      const page = await listDocumentVersions(workspaceId, document.kind, document.id);
      if (active.current && sequence === historySequence.current) { setHistory(page); cacheVersions(page.items); }
    } catch (cause) { if (sequence === historySequence.current) fail(cause); }
    finally { if (active.current && sequence === historySequence.current) setLoadingHistory(false); }
  }

  async function submitUpload(event: FormEvent) {
    event.preventDefault();
    if (!file) { setError('Chọn một file trước khi upload.'); return; }
    if (file.size > MAX_FILE_BYTES || file.size === 0) { setError('File cần có nội dung và không vượt 20 MB.'); return; }
    if (!/\.(pdf|docx|txt|md)$/i.test(file.name)) { setError('Chỉ nhận PDF, DOCX, TXT hoặc Markdown.'); return; }
    const existing = (uploadKind === 'REPORT' ? reports : sources)?.items.find((item) => item.id === uploadExistingId);
    if (uploadExistingId && !existing) { setError('Tải lại danh sách tài liệu trước khi tạo version.'); return; }
    const form = new FormData();
    form.set('file', file); form.set('governance_record_id', governanceId.trim());
    if (!existing) { form.set('document_key', documentKey.trim()); form.set('title', title.trim()); }
    const signature = JSON.stringify([workspaceId, uploadKind, existing?.id, existing?.revision, governanceId.trim(), documentKey.trim(), title.trim()]);
    // Retain the key only for this exact in-memory File and request. A network retry
    // replays the operation; a different file never shares an idempotency key.
    if (uploadRetry.current?.signature !== signature || uploadRetry.current.file !== file) uploadRetry.current = { signature, file, key: operationKey() };
    setBusy(true); setError(null); setNotice(null); setRequestId(null);
    try {
      const value = await uploadDocument(workspaceId, uploadKind, form, uploadRetry.current.key, existing);
      if (!active.current) return;
      setParseOperations((current) => [{ uploadId: value.job_id, versionId: value.document_version_id, job: null }, ...current.filter((item) => item.uploadId !== value.job_id)].slice(0, 20));
      setNotice(`Đã nhận file, PARSE ${value.state}. Version ${value.document_version_id}; worker chưa hoàn tất phân tích.`);
      uploadRetry.current = null; setFile(null); if (fileInput.current) fileInput.current.value = '';
      await refreshDocuments();
    } catch (cause) { fail(cause); }
    finally { if (active.current) setBusy(false); }
  }

  async function index(version: DocumentVersion) {
    const signature = `${version.id}:${configId}`;
    if (!indexKeys.current.has(signature)) indexKeys.current.set(signature, operationKey());
    setBusy(true); setError(null); setRequestId(null);
    try {
      const value = await createIndexGeneration(workspaceId, version.id, configId, indexKeys.current.get(signature)!);
      if (active.current) { setGenerations((current) => ({ ...current, [version.id]: value })); setNotice(`INDEX ${value.state} · generation ${value.id}.`); }
    } catch (cause) { fail(cause); }
    finally { if (active.current) setBusy(false); }
  }

  async function startRun(event: FormEvent) {
    event.preventDefault();
    const body = {
      run_type: runType, report_version_id: reportVersionId,
      source_scope: { source_version_ids: runType === 'ASSESSMENT' ? [] : Object.values(sourceVersions).sort() },
      rubric_version_id: runType === 'SIMILARITY' ? null : rubricVersionId, config_id: configId,
    };
    const signature = JSON.stringify([selectedReportId, body]);
    if (runKey.current?.signature !== signature) runKey.current = { signature, key: operationKey() };
    setBusy(true); setError(null); setRequestId(null); setNotice(null);
    try {
      const value = await createAnalysisRun(workspaceId, selectedReportId, body, runKey.current.key);
      if (!active.current) return;
      runSelection.current += 1; setRun(value); setResults(null); setEvidence(null); setRunLookup(value.id);
      setNotice(`Đã tạo lượt chạy ${value.id}. Version report, nguồn, index và rubric đã được khóa cho lượt này.`);
      // Keep the key after an accepted run, so an uncertain/repeated click does not
      // silently enqueue a second identical run. Change inputs for another run.
    } catch (cause) { fail(cause); }
    finally { if (active.current) setBusy(false); }
  }

  async function openRun(event: FormEvent) {
    event.preventDefault();
    const selection = ++runSelection.current;
    setRun(null); setResults(null); setEvidence(null); setBusy(true); setError(null); setRequestId(null);
    try {
      const value = await getAnalysisRun(workspaceId, runLookup.trim());
      if (active.current && selection === runSelection.current) setRun(value);
    } catch (cause) { fail(cause); }
    finally { if (active.current) setBusy(false); }
  }

  async function exportRun() {
    if (!run) return;
    setBusy(true); setError(null);
    try {
      const value = await exportAnalysisRun(workspaceId, run.id);
      if (!active.current) return;
      const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `analysis-${run.id}.json`;
      anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) { fail(cause); }
    finally { if (active.current) setBusy(false); }
  }

  async function moreDocuments(kind: DocumentKind) {
    const current = kind === 'REPORT' ? reports : sources;
    if (!current?.page.has_more) return;
    setBusy(true); setError(null);
    try {
      const page = await listDocuments(workspaceId, kind, current.page.next_cursor);
      const values = await Promise.all(page.items.map((item) => getDocumentVersion(workspaceId, item.current_version_id)));
      if (active.current) {
        const merged = { ...page, items: [...current.items, ...page.items] };
        if (kind === 'REPORT') setReports(merged); else setSources(merged);
        cacheVersions(values);
      }
    } catch (cause) { fail(cause); }
    finally { if (active.current) setBusy(false); }
  }

  const report = reports?.items.find((item) => item.id === selectedReportId);
  const chosenReportVersion = versionCache[reportVersionId];
  const canStart = canRun && !!report && !!chosenReportVersion && PARSED.has(chosenReportVersion.processing_state)
    && (runType === 'SIMILARITY' || !!rubricVersionId)
    && (runType === 'ASSESSMENT' || Object.keys(sourceVersions).length > 0);
  const availableUploads = uploadKind === 'REPORT' ? reports?.items ?? [] : sources?.items ?? [];

  function documentList(page: Page<DocumentRecord> | null, kind: DocumentKind) {
    return <section className="panel auth-document-panel">
      <h3>{kind === 'REPORT' ? 'Báo cáo sinh viên' : 'Nguồn đối chứng'}</h3>
      {loading && <p role="status">Đang tải tài liệu…</p>}
      {page?.items.length === 0 && <p className="section-intro">Chưa có tài liệu có quyền truy cập trong workspace này.</p>}
      <ul className="auth-document-list">{page?.items.map((document) => {
        const current = versionCache[document.current_version_id];
        const generation = generations[document.current_version_id];
        return <li key={document.id}>
          <strong>{document.title}</strong><small>{document.document_key}</small>
          <p>{current ? versionLabel(current) : 'Chưa tải được trạng thái version.'}</p>
          <code className="auth-resource-id">{document.current_version_id}</code>
          {current?.failure_code && <p className="auth-failure">{current.failure_code}</p>}
          {generation && <p role="status">INDEX {generation.state} · {generation.config_id}<small>Generation {generation.id}{generation.failure_code ? ` · ${generation.failure_code}` : ''}</small></p>}
          <div className="auth-actions">
            <button className="subtle-button" disabled={busy} onClick={() => { void openHistory({ ...document, kind }); }}>Version của {document.document_key}</button>
            {canRun && current && <button className="secondary-button" disabled={busy || !PARSED.has(current.processing_state) || !!generation && !TERMINAL.has(generation.state)} onClick={() => { void index(current); }}>Index {document.document_key}</button>}
          </div>
        </li>;
      })}</ul>
      {page?.page.has_more && <button className="subtle-button" disabled={busy} onClick={() => { void moreDocuments(kind); }}>Tải thêm {kind === 'REPORT' ? 'báo cáo' : 'nguồn'}</button>}
    </section>;
  }

  return <div className="auth-reports" aria-label="Tài liệu và phân tích">
    <div aria-live="polite">
      {error && <div role="alert" className="notice notice-error">{error}{requestId && <small>Mã yêu cầu: {requestId}</small>}</div>}
      {notice && <div className="notice">{notice}</div>}
    </div>
    <div className="panel-title"><div><h2>Tài liệu & phân tích</h2><p className="section-intro">Upload và PARSE → INDEX từng version → chạy hai pipeline trên tập đầu vào đã chọn.</p></div>
      <button className="subtle-button" disabled={busy || loading} onClick={() => { setLoading(true); void refreshDocuments(); }}>Tải lại tài liệu</button></div>
    {!canReadReports && !canReadSources && <p className="notice notice-muted">Vai trò hiện tại không có quyền đọc báo cáo hoặc nguồn đối chứng.</p>}
    <div className="auth-document-grid">
      {canReadReports && documentList(reports, 'REPORT')}
      {canReadSources && documentList(sources, 'CORPUS_SOURCE')}
    </div>
    {(canUploadReport || canUploadSource) && <section className="panel auth-upload-panel">
      <h3>Upload tài liệu</h3>
      <p className="section-intro">Cần governance record đã được duyệt cho đúng tài liệu và mục đích sử dụng. Giao diện không tự cấp quyền hoặc bỏ qua consent/license.</p>
      <form onSubmit={submitUpload} className="auth-form-grid">
        <div><label className="field-label" htmlFor="document-kind">Loại tài liệu</label><select id="document-kind" value={uploadKind} disabled={busy} onChange={(event) => { setUploadKind(event.target.value as DocumentKind); setUploadExistingId(''); }}>
          {canUploadReport && <option value="REPORT">Báo cáo sinh viên</option>}{canUploadSource && <option value="CORPUS_SOURCE">Nguồn đối chứng</option>}
        </select></div>
        <div><label className="field-label" htmlFor="document-existing">Tạo mới hay thêm version</label><select id="document-existing" value={uploadExistingId} disabled={busy} onChange={(event) => setUploadExistingId(event.target.value)}>
          <option value="">Tài liệu mới</option>{availableUploads.map((item) => <option key={item.id} value={item.id}>Version mới của {item.document_key}</option>)}
        </select></div>
        {!uploadExistingId && <><div><label className="field-label" htmlFor="document-key">Mã tài liệu</label><input id="document-key" required pattern="[A-Za-z0-9][A-Za-z0-9_.:\-]*" maxLength={128} value={documentKey} disabled={busy} onChange={(event) => setDocumentKey(event.target.value)} /></div>
          <div><label className="field-label" htmlFor="document-title">Tên tài liệu</label><input id="document-title" required maxLength={256} value={title} disabled={busy} onChange={(event) => setTitle(event.target.value)} /></div></>}
        <div><label className="field-label" htmlFor="document-governance">Governance record ID đã duyệt</label><input id="document-governance" required pattern="[0-9a-fA-F]{24}" maxLength={24} value={governanceId} disabled={busy} onChange={(event) => setGovernanceId(event.target.value)} placeholder="24 ký tự hex của record được cấp quyền" /></div>
        <div><label className="field-label" htmlFor="document-file">File tài liệu</label><input ref={fileInput} id="document-file" type="file" required accept=".pdf,.docx,.txt,.md" disabled={busy} onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><small className="field-help">PDF, DOCX, TXT, Markdown · tối đa 20 MB.</small></div>
        <div className="auth-form-full"><button className="primary-button" disabled={busy}>{busy ? 'Đang thực hiện…' : 'Upload & tạo PARSE job'}</button></div>
      </form>
      {parseOperations.length > 0 && <ul className="auth-job-list">{parseOperations.map((item) => <li key={item.uploadId}><strong>PARSE {item.job?.state ?? 'QUEUED'}</strong> · version <code>{item.versionId}</code>{item.job && <small>Attempt {item.job.attempt}/{item.job.max_attempts} · {item.job.progress.step}{item.job.error_code ? ` · ${item.job.error_code}` : ''}</small>}</li>)}</ul>}
    </section>}
    {detail && <section className="panel auth-history-panel">
      <div className="panel-title"><h3>Version · {detail.document_key}</h3><button className="subtle-button" onClick={() => { historySequence.current += 1; setDetail(null); setHistory(null); }}>Đóng version</button></div>
      {loadingHistory && <p role="status">Đang tải version…</p>}
      <ul className="auth-document-list">{history?.items.map((item) => <li key={item.id}><strong>{versionLabel(item)}</strong><code className="auth-resource-id">{item.id}</code><small>SHA-256 {item.content_sha256}</small>
        {item.failure_code && <p className="auth-failure">{item.failure_code}</p>}
        {canRun && <div className="auth-actions"><button className="secondary-button" disabled={busy || !PARSED.has(item.processing_state)} onClick={() => { void index(item); }}>Index v{item.version_no}</button>
          <button className="subtle-button" disabled={busy || !PARSED.has(item.processing_state)} onClick={() => {
            if (detail.kind === 'REPORT') { setSelectedReportId(detail.id); setReportVersionId(item.id); }
            else setSourceVersions((current) => ({ ...current, [detail.id]: item.id }));
            setNotice(`Đã chọn ${detail.document_key} v${item.version_no} cho lượt chạy tiếp theo.`);
          }}>Chọn {detail.document_key} v{item.version_no} để chạy</button></div>}
      </li>)}</ul>
      {history?.page.has_more && <button className="subtle-button" disabled={busy} onClick={async () => {
        const sequence = historySequence.current; setBusy(true);
        try { const page = await listDocumentVersions(workspaceId, detail.kind, detail.id, history.page.next_cursor); if (active.current && sequence === historySequence.current) { setHistory({ ...page, items: [...history.items, ...page.items] }); cacheVersions(page.items); } }
        catch (cause) { if (sequence === historySequence.current) fail(cause); } finally { if (active.current) setBusy(false); }
      }}>Tải thêm version tài liệu</button>}
    </section>}
    {canRun && <section className="panel auth-analysis-panel">
      <h3>Chạy phân tích</h3>
      <p className="section-intro">Index các version cần dùng với cùng config trước. Backend kiểm tra lại quyền, governance và active index generation khi nhận lượt chạy.</p>
      <form onSubmit={startRun} className="auth-form-grid">
        <div><label className="field-label" htmlFor="analysis-config">Config retrieval/index</label><select id="analysis-config" value={configId} disabled={busy} onChange={(event) => setConfigId(event.target.value as AnalysisConfigId)}><option value="bm25-smoke">BM25 smoke · không tải model</option><option value="research-v0">Research v0 · dense + hybrid + reranker</option></select></div>
        <div><label className="field-label" htmlFor="analysis-type">Pipeline cần chạy</label><select id="analysis-type" value={runType} disabled={busy} onChange={(event) => setRunType(event.target.value as AnalysisRun['run_type'])}><option value="BOTH">Cả hai pipeline</option><option value="SIMILARITY">Pipeline 1 · Similarity</option><option value="ASSESSMENT">Pipeline 2 · Assessment</option></select></div>
        <div><label className="field-label" htmlFor="analysis-report">Báo cáo để phân tích</label><select id="analysis-report" required value={selectedReportId} disabled={busy} onChange={(event) => { const item = reports?.items.find((candidate) => candidate.id === event.target.value); setSelectedReportId(item?.id ?? ''); setReportVersionId(item?.current_version_id ?? ''); }}><option value="">Chọn báo cáo</option>{reports?.items.map((item) => <option key={item.id} value={item.id}>{item.title} · {item.document_key}</option>)}</select></div>
        <div><label className="field-label" htmlFor="analysis-report-version">Report version đã khóa</label><input id="analysis-report-version" readOnly value={reportVersionId} /><small>{chosenReportVersion ? versionLabel(chosenReportVersion) : 'Chọn version đã parse; mở danh sách version nếu cần bản cũ.'}</small></div>
        {runType !== 'ASSESSMENT' && <fieldset className="auth-form-full auth-source-choices"><legend>Nguồn đối chứng được chọn</legend>
          {sources?.items.length === 0 && <p>Upload và index ít nhất một nguồn đã được cấp quyền.</p>}
          {sources?.items.map((item) => <label key={item.id}><input type="checkbox" checked={!!sourceVersions[item.id]} disabled={busy || !versionCache[item.current_version_id] || !PARSED.has(versionCache[item.current_version_id].processing_state)} onChange={(event) => setSourceVersions((current) => { const next = { ...current }; if (event.target.checked) next[item.id] = item.current_version_id; else delete next[item.id]; return next; })} />
            <span>{item.title}<small>{sourceVersions[item.id] ?? item.current_version_id}</small>{sourceVersions[item.id] && versionCache[sourceVersions[item.id]] && <small>{versionLabel(versionCache[sourceVersions[item.id]])}</small>}</span>
          </label>)}
        </fieldset>}
        {runType !== 'SIMILARITY' && <><div><label className="field-label" htmlFor="analysis-rubric">Rubric cho assessment</label><select id="analysis-rubric" required value={rubricId} disabled={busy} onChange={(event) => setRubricId(event.target.value)}><option value="">Chọn rubric</option>{rubrics?.items.map((item) => <option key={item.id} value={item.id}>{item.title} · {item.rubric_key}</option>)}</select>
          {rubrics?.page.has_more && <button type="button" className="subtle-button" disabled={busy} onClick={async () => {
            setBusy(true); try { const page = await listRubrics(workspaceId, rubrics.page.next_cursor); if (active.current) setRubrics({ ...page, items: [...rubrics.items, ...page.items] }); } catch (cause) { fail(cause); } finally { if (active.current) setBusy(false); }
          }}>Tải thêm rubric để phân tích</button>}</div>
          <div><label className="field-label" htmlFor="analysis-rubric-version">Published rubric version</label><select id="analysis-rubric-version" required value={rubricVersionId} disabled={busy || !rubricId || rubricVersions === null} onChange={(event) => setRubricVersionId(event.target.value)}><option value="">Chọn version đã publish</option>{rubricVersions?.items.filter((item) => item.status === 'PUBLISHED').map((item) => <option key={item.id} value={item.id}>v{item.version_no} · {item.id}</option>)}</select>
            {rubricVersions?.page.has_more && <button type="button" className="subtle-button" disabled={busy} onClick={async () => { setBusy(true); try { const page = await listRubricVersions(workspaceId, rubricId, rubricVersions.page.next_cursor); if (active.current) setRubricVersions({ ...page, items: [...rubricVersions.items, ...page.items] }); } catch (cause) { fail(cause); } finally { if (active.current) setBusy(false); } }}>Tải thêm rubric version</button>}
            {rubricVersions && !rubricVersions.items.some((item) => item.status === 'PUBLISHED') && <small>Chưa có version publish trong trang này. Publish rubric hoặc tải thêm version nếu còn.</small>}</div></>}
        <div className="auth-form-full"><button className="primary-button" disabled={busy || !canStart}>Tạo lượt chạy</button><p className="field-help">BM25 smoke kiểm tra integration, không tương đương kết quả research-v0. Similarity không tự kết luận đạo văn; assessment chỉ đề xuất để giảng viên review.</p></div>
      </form>
    </section>}
    {canReadRuns && <section className="panel auth-run-panel">
      <h3>Theo dõi & kết quả</h3>
      <form className="auth-run-lookup" onSubmit={openRun}><label className="field-label" htmlFor="analysis-run-id">Mở lượt chạy theo ID</label><div><input id="analysis-run-id" pattern="[0-9a-fA-F]{24}" maxLength={24} required value={runLookup} onChange={(event) => setRunLookup(event.target.value)} /><button className="secondary-button" disabled={busy}>Mở lượt chạy</button></div></form>
      {!run && <p className="section-intro">Tạo lượt chạy hoặc nhập run ID đã có quyền truy cập. Nội dung không được lưu trong localStorage.</p>}
      {run && <>
        <div className="panel-title"><h4>Lượt chạy <code>{run.id}</code></h4><span className="panel-chip" role="status">ANALYZE {run.state}</span></div>
        <dl className="auth-run-provenance"><dt>Config / pipeline</dt><dd>{run.config_id} · {run.run_type}</dd><dt>Report version</dt><dd>{run.report_version_id}</dd><dt>Source versions</dt><dd>{run.source_version_ids.length ? run.source_version_ids.join(', ') : 'Không dùng nguồn đối chứng'}</dd><dt>Index generations</dt><dd>{run.index_generation_ids.join(', ') || 'Chưa có'}</dd><dt>Rubric version</dt><dd>{run.rubric_version_id ?? 'Không dùng rubric'}</dd><dt>Job</dt><dd>{run.job_id}</dd></dl>
        {run.failure_code && <p className="notice notice-error" role="alert">Worker chưa tạo được kết quả: {run.failure_code}. Không có kết luận cho lượt này.</p>}
        {!TERMINAL.has(run.state) && <p role="status">Đang chờ worker hoặc xử lý. Cấu hình Research v0 cần model đã chuẩn bị trên máy worker.</p>}
        <div className="auth-actions"><button className="subtle-button" disabled={busy} onClick={async () => {
          const selection = runSelection.current; setBusy(true); setError(null); try { const value = await getAnalysisRun(workspaceId, run.id); if (active.current && selection === runSelection.current) setRun(value); } catch (cause) { fail(cause); } finally { if (active.current) setBusy(false); }
        }}>Tải lại lượt chạy</button>{run.state === 'SUCCEEDED' && <button className="secondary-button" disabled={busy || results === null} onClick={() => { void exportRun(); }}>Export JSON kết quả</button>}</div>
        {loadingResults && <p role="status">Đang tải kết quả và evidence…</p>}
        {results && <AuthenticatedResults results={results} evidence={evidence} workspaceId={workspaceId} reportVersionId={run.report_version_id} onMoreEvidence={async () => {
          if (!evidence?.page.has_more) return; const selection = runSelection.current; setBusy(true);
          try { const page = await getAnalysisEvidence(workspaceId, run.id, evidence.page.next_cursor); if (active.current && selection === runSelection.current) setEvidence({ ...page, items: [...evidence.items, ...page.items] }); } catch (cause) { fail(cause); } finally { if (active.current) setBusy(false); }
        }} busy={busy} />}
        {run.state === 'SUCCEEDED' && results && capabilities.includes('review.create') && <section aria-label="Review kết quả đề xuất">
          <h4>Giảng viên review · {run.review_state}</h4>
          <label className="field-label" htmlFor="analysis-review-reason">Nhận xét review</label>
          <textarea id="analysis-review-reason" value={reviewReason} maxLength={4000} disabled={busy} onChange={(event) => setReviewReason(event.target.value)} />
          <div className="auth-actions">{(['ACCEPT', 'REJECT'] as const).map((decision) => <button key={decision} className="secondary-button" disabled={busy || !reviewReason.trim()} onClick={async () => {
            setBusy(true); setError(null);
            try {
              await createAnalysisReview(workspaceId, run, { decision, reason_code: 'LECTURER_MANUAL_REVIEW', reason_text: reviewReason.trim() });
              const updated = await getAnalysisRun(workspaceId, run.id);
              if (active.current) { setRun(updated); setNotice('Đã lưu review theo tài khoản và revision. Chưa công bố điểm chính thức.'); }
            } catch (cause) { fail(cause); } finally { if (active.current) setBusy(false); }
          }}>{decision === 'ACCEPT' ? 'Chấp nhận đề xuất' : 'Từ chối đề xuất'}</button>)}</div>
        </section>}
      </>}
    </section>}
  </div>;
}
