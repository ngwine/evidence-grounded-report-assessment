import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';

import {
  AuthenticatedApiError, createAnalysisRun, createIndexGeneration, exportAnalysisRun,
  getAnalysisEvidence, getAnalysisResults, getAnalysisRun, getDocumentVersion, getIndexGeneration,
  getJob, listDocuments, listDocumentVersions, listRubrics, listRubricVersions, operationKey, uploadDocument,
  createAnalysisReview, listAnalysisRuns, listUploadAuthorizations, createUploadDeclaration, documentFileUrl,
} from './authenticatedApi';
import type {
  Actor, AnalysisConfigId, AnalysisResults, AnalysisRun, DocumentKind, DocumentRecord,
  DocumentVersion, IndexGeneration, JobRecord, Page, Rubric, RubricVersion, RunEvidence, UploadAuthorization,
} from './authenticatedApi';
import AuthenticatedResults from './AuthenticatedResults';
import AuthenticatedItemAnnotations from './AuthenticatedItemAnnotations';

const TERMINAL = new Set(['SUCCEEDED', 'FAILED', 'FAILED_FINAL', 'CANCELLED', 'READY', 'ACTIVE', 'SUPERSEDED', 'REVOKED', 'INVALIDATED', 'TOMBSTONED']);
const PARSED = new Set(['PARSED', 'INDEXING', 'READY']);
const MAX_FILE_BYTES = 20 * 1024 * 1024;
const configLabel = (id: AnalysisConfigId) => id === 'bm25-smoke' ? 'BM25 baseline' : id === 'bm25-p2-llm-v2' ? 'LLM · đọc đủ báo cáo ngắn' : id === 'bm25-p2-llm-v1' ? 'LLM · phiên bản 1' : id.startsWith('bm25-nli-') ? 'BM25 + kiểm tra ngữ nghĩa' : id.startsWith('rrf-nli-') ? 'RRF + kiểm tra ngữ nghĩa' : 'Hybrid + Cross-Encoder';

type DocumentWithKind = DocumentRecord & { kind: DocumentKind };
type ParseOperation = { uploadId: string; versionId: string; job: JobRecord | null };
type Props = { actor: Actor; workspaceId: string; rubricRefreshKey: string; onAuthenticationError: (error: unknown) => void; view: 'analysis' | 'documents'; onViewChange: (view: 'analysis' | 'documents' | 'rubrics') => void };

function errorText(error: unknown): string {
  if (!(error instanceof AuthenticatedApiError)) return 'Chưa kết nối được API. Không có xác nhận lưu thành công; có thể thử lại.';
  if (error.status === 401) return 'Phiên đã hết hạn. Đăng nhập lại để tiếp tục.';
  if (error.code === 'DECLARATION_SCOPE_NOT_ALLOWED') return 'Khai báo tự tạo chỉ dùng trong workspace demo/kiểm thử nội bộ. Với workspace này, hãy chọn hồ sơ quyền đã được duyệt.';
  if (error.code === 'INVALID_DECLARATION') return 'Chưa ghi nhận được xác nhận cho file này. Chọn lại file rồi thử tải lên.';
  if (error.code === 'DECLARATION_FILE_MISMATCH') return 'File hoặc phạm vi không khớp khai báo đã ghi nhận. Chọn lại file và khai báo cho đúng tài liệu trước khi thử lại.';
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

export default function AuthenticatedReports({ actor, workspaceId, rubricRefreshKey, onAuthenticationError, view, onViewChange }: Props) {
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
  const [authorizationMode, setAuthorizationMode] = useState<'SELF_AUTHORED' | 'PREAPPROVED'>('SELF_AUTHORED');
  const [file, setFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const uploadRetry = useRef<{ signature: string; file: File; key: string } | null>(null);
  const declarationRetry = useRef<{ signature: string; file: File; key: string } | null>(null);
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
  const [authorizations, setAuthorizations] = useState<Page<UploadAuthorization> | null>(null);
  const [recentRuns, setRecentRuns] = useState<Page<AnalysisRun> | null>(null);
  const [loadingRecentRuns, setLoadingRecentRuns] = useState(false);
  const recentRunsSelection = useRef(0);
  const [preparing, setPreparing] = useState(false);
  const [preparationStep, setPreparationStep] = useState('');
  const stopPreparation = useRef(false);

  const fail = useCallback((cause: unknown) => {
    if (!active.current) return;
    setError(errorText(cause));
    setRequestId(cause instanceof AuthenticatedApiError ? cause.requestId : null);
    if (cause instanceof AuthenticatedApiError && cause.status === 401) onAuthenticationError(cause);
    if (cause instanceof AuthenticatedApiError && ([401, 403, 404].includes(cause.status)
        || ['GOVERNANCE_NOT_APPROVED', 'RESULT_INTEGRITY_FAILED', 'ANALYSIS_INPUT_CHANGED', 'PROVENANCE_INVALID', 'INDEX_INTEGRITY_FAILED', 'ANNOTATION_INTEGRITY_FAILED'].includes(cause.code))) {
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
      if (reportPage?.items.length === 1) { setSelectedReportId((current) => current || reportPage.items[0].id); setReportVersionId((current) => current || reportPage.items[0].current_version_id); }
    } catch (cause) { fail(cause); }
    finally { refreshInFlight.current = false; if (active.current) setLoading(false); }
  }, [workspaceId, canReadReports, canReadSources, cacheVersions, fail]);

  useEffect(() => { active.current = true; stopPreparation.current = false; return () => { active.current = false; stopPreparation.current = true; }; }, []);
  useEffect(() => { void refreshDocuments(); }, [refreshDocuments]);
  useEffect(() => {
    if (!canRun || !canRubrics) return;
    let cancelled = false;
    listRubrics(workspaceId).then((page) => { if (!cancelled && active.current) { setRubrics(page); if (page.items.length === 1) setRubricId((current) => current || page.items[0].id); } }).catch((cause) => { if (!cancelled) fail(cause); });
    return () => { cancelled = true; };
  }, [workspaceId, canRun, canRubrics, rubricRefreshKey, fail]);

  useEffect(() => {
    if (!(uploadKind === 'REPORT' ? canUploadReport : canUploadSource)) return;
    let cancelled = false; setAuthorizations(null); setGovernanceId('');
    listUploadAuthorizations(workspaceId, uploadKind).then((page) => {
      if (!cancelled && active.current) { setAuthorizations(page); if (page.items.length === 1) setGovernanceId(page.items[0].id); }
    }).catch((cause) => { if (!cancelled) fail(cause); });
    return () => { cancelled = true; };
  }, [workspaceId, uploadKind, canUploadReport, canUploadSource, fail]);

  useEffect(() => {
    const selection = ++recentRunsSelection.current;
    setRecentRuns(null);
    if (!selectedReportId || !canReadRuns) { setLoadingRecentRuns(false); return; }
    let cancelled = false;
    setLoadingRecentRuns(true);
    listAnalysisRuns(workspaceId, selectedReportId)
      .then((page) => { if (!cancelled && active.current && selection === recentRunsSelection.current) setRecentRuns(page); })
      .catch((cause) => { if (!cancelled && selection === recentRunsSelection.current) fail(cause); })
      .finally(() => { if (!cancelled && active.current && selection === recentRunsSelection.current) setLoadingRecentRuns(false); });
    return () => { cancelled = true; };
  }, [workspaceId, selectedReportId, canReadRuns, run?.state, fail]);

  useEffect(() => {
    setRubricVersions(null); setRubricVersionId('');
    if (!rubricId) return;
    let cancelled = false;
    listRubricVersions(workspaceId, rubricId).then((page) => {
      if (!cancelled && active.current) { setRubricVersions(page); const published = page.items.find((item) => item.status === 'PUBLISHED'); if (published) setRubricVersionId(published.id); }
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
    if (authorizationMode === 'PREAPPROVED' && !governanceId.trim()) { setError('Chọn hồ sơ quyền sử dụng trước khi tải lên.'); return; }
    if (authorizationMode === 'SELF_AUTHORED' && !crypto.subtle) { setError('Trình duyệt chưa hỗ trợ kiểm tra SHA-256. Mở ứng dụng bằng localhost hoặc HTTPS rồi thử lại.'); return; }
    const chosenFile = file;
    setBusy(true); setError(null); setNotice(null); setRequestId(null);
    try {
      let resolvedGovernanceId = governanceId.trim();
      if (authorizationMode === 'SELF_AUTHORED') {
        setNotice('Đang chuẩn bị tài liệu…');
        // File objects are immutable: the bytes hashed here are the same File
        // passed to upload below. The API checks this digest again server-side.
        const digest = await crypto.subtle.digest('SHA-256', await chosenFile.arrayBuffer());
        if (!active.current) return;
        const contentSha256 = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
        // Clicking Upload confirms the notice beside the button for this file.
        const declaration = {
          kind: uploadKind, filename: chosenFile.name, content_sha256: contentSha256,
          rights_basis: 'SELF_AUTHORED' as const, attested_authority: true as const,
          pii_reviewed: true as const, internal_use_only: true as const,
          ...(existing ? { document_id: existing.id } : {}),
        };
        const declarationSignature = JSON.stringify([workspaceId, declaration]);
        if (declarationRetry.current?.signature !== declarationSignature || declarationRetry.current.file !== chosenFile) {
          declarationRetry.current = { signature: declarationSignature, file: chosenFile, key: operationKey() };
        }
        const authorization = await createUploadDeclaration(workspaceId, declaration, declarationRetry.current.key);
        if (!active.current) return;
        resolvedGovernanceId = authorization.id;
      }
      const form = new FormData();
      form.set('file', chosenFile); form.set('governance_record_id', resolvedGovernanceId);
      if (!existing) { form.set('document_key', documentKey.trim()); form.set('title', title.trim()); }
      const signature = JSON.stringify([workspaceId, uploadKind, existing?.id, existing?.revision, resolvedGovernanceId, documentKey.trim(), title.trim()]);
      // A retry reuses the exact request key; changing its file/scope never does.
      if (uploadRetry.current?.signature !== signature || uploadRetry.current.file !== chosenFile) uploadRetry.current = { signature, file: chosenFile, key: operationKey() };
      const value = await uploadDocument(workspaceId, uploadKind, form, uploadRetry.current.key, existing);
      if (!active.current) return;
      // A freshly uploaded report is the next analysis input, not a stale
      // version selected before the upload. Saved runs remain immutable.
      if (uploadKind === 'REPORT') {
        setSelectedReportId(value.document_id); setReportVersionId(value.document_version_id);
      } else {
        setSourceVersions((current) => current[value.document_id]
          ? { ...current, [value.document_id]: value.document_version_id } : current);
      }
      setParseOperations((current) => [{ uploadId: value.job_id, versionId: value.document_version_id, job: null }, ...current.filter((item) => item.uploadId !== value.job_id)].slice(0, 20));
      setNotice('Đã nhận tài liệu. Hệ thống đang đọc nội dung và chuẩn bị các đoạn văn.');
      uploadRetry.current = null; resetDeclaration(); setFile(null); if (fileInput.current) fileInput.current.value = '';
      if (!existing) { setTitle(''); setDocumentKey(''); }
      await refreshDocuments();
    } catch (cause) { if (active.current) setNotice(null); fail(cause); }
    finally { if (active.current) setBusy(false); }
  }

  function resetDeclaration() {
    declarationRetry.current = null;
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
      stopPreparation.current = false; setPreparing(true);
      // Indexing is a real prerequisite, not a separate technical step the lecturer
      // must remember. Await each server generation; errors never trigger fallback.
      for (const versionId of body.source_scope.source_version_ids) {
        if (!active.current || stopPreparation.current) return;
        setPreparationStep('Chuẩn bị nguồn đối chứng…');
        const indexKey = `${versionId}:${configId}`;
        if (!indexKeys.current.has(indexKey)) indexKeys.current.set(indexKey, operationKey());
        let generation = await createIndexGeneration(workspaceId, versionId, configId, indexKeys.current.get(indexKey)!);
        if (active.current) setGenerations((current) => ({ ...current, [versionId]: generation }));
        const deadline = Date.now() + 240_000;
        while (!TERMINAL.has(generation.state)) {
          if (!active.current || stopPreparation.current) return;
          if (Date.now() > deadline) throw new AuthenticatedApiError(408, 'INDEX_WAIT_TIMEOUT', null, 'Nguồn vẫn đang được xử lý. Kiểm tra worker và thử lại sau; chưa tạo lượt phân tích.');
          await new Promise((resolve) => setTimeout(resolve, 1500));
          generation = await getIndexGeneration(workspaceId, generation.id);
        }
        if (!['ACTIVE', 'SUPERSEDED'].includes(generation.state)) throw new AuthenticatedApiError(409, generation.failure_code ?? 'INDEX_FAILED', null, 'Không thể chuẩn bị index cho nguồn đã chọn.');
      }
      if (!active.current || stopPreparation.current) return;
      setPreparationStep('Đang tạo lượt phân tích…');
      const value = await createAnalysisRun(workspaceId, selectedReportId, body, runKey.current.key);
      if (!active.current) return;
      runSelection.current += 1; setRun(value); setResults(null); setEvidence(null); setRunLookup(value.id);
      setNotice('Đã gửi yêu cầu phân tích. Phiên bản báo cáo, nguồn và rubric được giữ nguyên cho lượt này.');
      // Keep the key after an accepted run, so an uncertain/repeated click does not
      // silently enqueue a second identical run. Change inputs for another run.
    } catch (cause) { fail(cause); }
    finally { if (active.current) { setBusy(false); setPreparing(false); setPreparationStep(''); } }
  }

  function selectReport(document: DocumentRecord | undefined, versionId = document?.current_version_id ?? '') {
    setSelectedReportId(document?.id ?? '');
    setReportVersionId(versionId);
    if ((document?.id ?? '') === selectedReportId) return;
    recentRunsSelection.current += 1;
    runSelection.current += 1;
    setRecentRuns(null); setLoadingRecentRuns(false);
    setRun(null); setRunLookup(''); setResults(null); setEvidence(null); setLoadingResults(false);
    setReviewReason(''); setError(null); setRequestId(null);
  }

  async function loadRun(runId: string) {
    const selection = ++runSelection.current;
    setRun(null); setResults(null); setEvidence(null); setBusy(true); setError(null); setRequestId(null);
    try {
      const value = await getAnalysisRun(workspaceId, runId);
      if (active.current && selection === runSelection.current) { setRun(value); setRunLookup(value.id); setReviewReason(''); }
    } catch (cause) { if (selection === runSelection.current) fail(cause); }
    finally { if (active.current) setBusy(false); }
  }

  async function openRun(event: FormEvent) {
    event.preventDefault();
    await loadRun(runLookup.trim());
  }

  async function moreRuns() {
    if (loadingRecentRuns || !recentRuns?.page.has_more) return;
    const selection = recentRunsSelection.current;
    const previous = recentRuns;
    setLoadingRecentRuns(true);
    try {
      const page = await listAnalysisRuns(workspaceId, selectedReportId, previous.page.next_cursor);
      if (active.current && selection === recentRunsSelection.current) setRecentRuns({ ...page, items: [...previous.items, ...page.items] });
    } catch (cause) { if (selection === recentRunsSelection.current) fail(cause); }
    finally { if (active.current && selection === recentRunsSelection.current) setLoadingRecentRuns(false); }
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
          <div className="library-doc-head"><span className="document-glyph" aria-hidden="true">▤</span><div><strong>{document.title}</strong><small>Phiên bản {current?.version_no ?? '—'} · {current?.chunk_count ?? 0} đoạn văn</small></div><span className={`status-tag ${current && PARSED.has(current.processing_state) ? 'status-ready' : ''}`}>{current && PARSED.has(current.processing_state) ? 'Sẵn sàng' : current?.processing_state === 'FAILED' ? 'Cần kiểm tra' : 'Đang xử lý'}</span></div>
          {current?.failure_code && <p className="auth-failure">{current.failure_code}</p>}
          {generation && <p role="status">INDEX {generation.state} · {generation.config_id}<small>Generation {generation.id}{generation.failure_code ? ` · ${generation.failure_code}` : ''}</small></p>}
          <div className="auth-actions">
            <a className="subtle-button" href={documentFileUrl(workspaceId, document.current_version_id)} target="_blank" rel="noreferrer">Mở tài liệu ↗</a>
            <button className="subtle-button" disabled={busy} onClick={() => { void openHistory({ ...document, kind }); }}>Xem phiên bản</button>
            {kind === 'REPORT' && canRun && <button className="secondary-button" disabled={busy || !current || !PARSED.has(current.processing_state)} onClick={() => { selectReport(document); onViewChange('analysis'); }}>Phân tích báo cáo →</button>}
            {canRun && current && <details className="technical-details"><summary>Công cụ nâng cao</summary><button className="secondary-button" disabled={busy || !PARSED.has(current.processing_state) || !!generation && !TERMINAL.has(generation.state)} onClick={() => { void index(current); }}>Index {document.document_key}</button><code>{document.current_version_id}</code></details>}
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
    <div className="workspace-summary-grid" hidden={view !== 'analysis'}><div><span className="summary-symbol">▤</span><span>Báo cáo trong workspace<strong>{reports?.items.length ?? '—'}{reports?.page.has_more ? '+' : ''}</strong></span></div><div><span className="summary-symbol">⌕</span><span>Nguồn đối chứng<strong>{sources?.items.length ?? '—'}{sources?.page.has_more ? '+' : ''}</strong></span></div><div><span className="summary-symbol">☷</span><span>Rubric khả dụng<strong>{rubrics?.items.length ?? '—'}{rubrics?.page.has_more ? '+' : ''}</strong></span></div></div>
    <div className="panel-title" hidden={view !== 'documents'}><div><h2>Tài liệu trong workspace</h2><p className="section-intro">Chọn tài liệu đã lưu hoặc tải lên báo cáo và nguồn đối chứng mới.</p></div>
      <button className="subtle-button" disabled={busy || loading} onClick={() => { setLoading(true); void refreshDocuments(); }}>Tải lại tài liệu</button></div>
    {!canReadReports && !canReadSources && <p className="notice notice-muted">Vai trò hiện tại không có quyền đọc báo cáo hoặc nguồn đối chứng.</p>}
    <div className="auth-document-grid" hidden={view !== 'documents'}>
      {canReadReports && documentList(reports, 'REPORT')}
      {canReadSources && documentList(sources, 'CORPUS_SOURCE')}
    </div>
    {(canUploadReport || canUploadSource) && <section className="panel auth-upload-panel" hidden={view !== 'documents'}>
      <h3>Thêm tài liệu</h3>
      <p className="section-intro">Tải báo cáo và nguồn đối chứng lên để phân tích.</p>
      <form onSubmit={submitUpload} className="auth-form-grid">
        <div><label className="field-label" htmlFor="document-kind">Loại tài liệu</label><select id="document-kind" value={uploadKind} disabled={busy} onChange={(event) => { setUploadKind(event.target.value as DocumentKind); setUploadExistingId(''); resetDeclaration(); }}>
          {canUploadReport && <option value="REPORT">Báo cáo sinh viên</option>}{canUploadSource && <option value="CORPUS_SOURCE">Nguồn đối chứng</option>}
        </select></div>
        <div><label className="field-label" htmlFor="document-existing">Tạo mới hay thêm version</label><select id="document-existing" value={uploadExistingId} disabled={busy} onChange={(event) => { setUploadExistingId(event.target.value); resetDeclaration(); }}>
          <option value="">Tài liệu mới</option>{availableUploads.map((item) => <option key={item.id} value={item.id}>Version mới của {item.document_key}</option>)}
        </select></div>
        {!uploadExistingId && <><details className="technical-details"><summary>Mã tài liệu tự tạo · có thể chỉnh</summary><label className="field-label" htmlFor="document-key">Mã tài liệu</label><input id="document-key" required pattern="[A-Za-z0-9][A-Za-z0-9_.:\-]*" maxLength={128} value={documentKey} disabled={busy} onChange={(event) => setDocumentKey(event.target.value)} /></details>
          <div><label className="field-label" htmlFor="document-title">Tên tài liệu</label><input id="document-title" required maxLength={256} value={title} disabled={busy} onChange={(event) => setTitle(event.target.value)} /></div></>}
        <div><label className="field-label" htmlFor="upload-rights-mode">Cách xác nhận quyền sử dụng</label><select id="upload-rights-mode" value={authorizationMode} disabled={busy} onChange={(event) => { setAuthorizationMode(event.target.value as typeof authorizationMode); resetDeclaration(); }}><option value="SELF_AUTHORED">Khai báo tài liệu của tôi/nhóm</option><option value="PREAPPROVED">Dùng hồ sơ quyền đã có</option></select></div>
        <div className="upload-file-area"><label className="field-label" htmlFor="document-file">File tài liệu</label><input ref={fileInput} id="document-file" type="file" required accept=".pdf,.docx,.txt,.md" disabled={busy} onChange={(event) => { const chosen = event.target.files?.[0] ?? null; setFile(chosen); resetDeclaration(); if (chosen && !uploadExistingId) { setDocumentKey(`doc-${crypto.randomUUID().slice(0, 12)}`); setTitle((current) => current || chosen.name.replace(/\.[^.]+$/, '')); } }} /><small className="field-help">PDF, DOCX, TXT hoặc Markdown · Tối đa 20 MB.</small></div>
        {authorizationMode === 'PREAPPROVED' && <div className="auth-form-full"><label className="field-label" htmlFor="upload-authorization">Quyền sử dụng tài liệu</label><select id="upload-authorization" value={governanceId} disabled={busy || authorizations === null} onChange={(event) => setGovernanceId(event.target.value)}><option value="">{authorizations === null ? 'Đang tải hồ sơ quyền…' : 'Chọn hồ sơ đã được duyệt'}</option>{authorizations?.items.map((item, i) => <option key={item.id} value={item.id}>Hồ sơ {i + 1} · {item.name}</option>)}{governanceId && !authorizations?.items.some((item) => item.id === governanceId) && <option value={governanceId}>Hồ sơ được nhập thủ công</option>}</select>
          {authorizations?.items.length === 0 && <p className="field-help">Chưa có hồ sơ cho tài liệu mới. Người phụ trách cần xác nhận quyền sử dụng; ứng dụng không tự cấp quyền.</p>}
          {authorizations?.page.has_more && <button type="button" className="subtle-button" onClick={async () => { try { const page = await listUploadAuthorizations(workspaceId, uploadKind, authorizations.page.next_cursor); if (active.current) setAuthorizations({ ...page, items: [...authorizations.items, ...page.items] }); } catch (cause) { fail(cause); } }}>Tải thêm hồ sơ quyền</button>}
          <details className="technical-details"><summary>Nhập mã hồ sơ được cấp riêng</summary><label className="field-label" htmlFor="document-governance">Governance record ID đã duyệt</label><input id="document-governance" pattern="[0-9a-fA-F]{24}" maxLength={24} value={governanceId} disabled={busy} onChange={(event) => setGovernanceId(event.target.value)} /></details></div>}
        <div className="auth-form-full upload-actions"><button className="primary-button" disabled={busy || !file || (authorizationMode === 'PREAPPROVED' && !governanceId)}>{busy ? 'Đang tải lên…' : 'Tải lên và xử lý tài liệu'}</button>
          {authorizationMode === 'SELF_AUTHORED' && <p className="upload-consent-note">Khi tải lên, bạn xác nhận có quyền dùng file, đã rà thông tin cá nhân và chỉ sử dụng nội bộ.</p>}
        </div>
      </form>
      {parseOperations.length > 0 && <ul className="auth-job-list">{parseOperations.map((item) => <li key={item.uploadId}><strong>PARSE {item.job?.state ?? 'QUEUED'}</strong> · version <code>{item.versionId}</code>{item.job && <small>Attempt {item.job.attempt}/{item.job.max_attempts} · {item.job.progress.step}{item.job.error_code ? ` · ${item.job.error_code}` : ''}</small>}</li>)}</ul>}
    </section>}
    {detail && <section className="panel auth-history-panel" hidden={view !== 'documents'}>
      <div className="panel-title"><h3>Version · {detail.document_key}</h3><button className="subtle-button" onClick={() => { historySequence.current += 1; setDetail(null); setHistory(null); }}>Đóng version</button></div>
      {loadingHistory && <p role="status">Đang tải version…</p>}
      <ul className="auth-document-list">{history?.items.map((item) => <li key={item.id}><strong>{versionLabel(item)}</strong><code className="auth-resource-id">{item.id}</code><small>SHA-256 {item.content_sha256}</small>
        {item.failure_code && <p className="auth-failure">{item.failure_code}</p>}
        {canRun && <div className="auth-actions"><button className="secondary-button" disabled={busy || !PARSED.has(item.processing_state)} onClick={() => { void index(item); }}>Index v{item.version_no}</button>
          <button className="subtle-button" disabled={busy || !PARSED.has(item.processing_state)} onClick={() => {
            if (detail.kind === 'REPORT') selectReport(detail, item.id);
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
    <div className="analysis-workbench" hidden={view !== 'analysis'}>
    {canRun && <section className="panel auth-analysis-panel">
      <div className="panel-section-heading"><span className="step-number">01</span><div><h2>Thiết lập phân tích</h2><p>Chọn đầu vào. Hệ thống chuẩn bị index và chạy các bước còn lại.</p></div></div>
      <form onSubmit={startRun} className="auth-form-grid">
        <details className="technical-details"><summary>Cấu hình phân tích · {configLabel(configId)}</summary><label className="field-label" htmlFor="analysis-config">Config retrieval/index</label><select id="analysis-config" value={configId} disabled={busy} onChange={(event) => setConfigId(event.target.value as AnalysisConfigId)}><option value="bm25-smoke">BM25 · chạy thử luồng nhanh</option><option value="research-v0">Hybrid · BM25 + E5 + Cross-Encoder</option><option value="bm25-p2-llm-v2">LLM · đọc đủ báo cáo ngắn</option><option value="bm25-p2-llm-v1">LLM · phiên bản 1</option><option value="bm25-nli-v2">BM25 + kiểm tra ngữ nghĩa từng cặp đoạn</option><option value="rrf-nli-v2">BM25 + E5 + RRF, kiểm tra ngữ nghĩa từng cặp đoạn</option></select><p className="field-help">BM25 là baseline. Chế độ LLM cần model local đã khóa; khi thiếu bằng chứng hệ thống có thể chưa kết luận được.</p></details>
        <div><label className="field-label" htmlFor="analysis-type">Pipeline cần chạy</label><select id="analysis-type" value={runType} disabled={busy} onChange={(event) => setRunType(event.target.value as AnalysisRun['run_type'])}><option value="BOTH">Cả hai pipeline</option><option value="SIMILARITY">Pipeline 1 · Similarity</option><option value="ASSESSMENT">Pipeline 2 · Assessment</option></select></div>
        <div><label className="field-label" htmlFor="analysis-report">Báo cáo để phân tích</label><select id="analysis-report" required value={selectedReportId} disabled={busy} onChange={(event) => selectReport(reports?.items.find((item) => item.id === event.target.value))}><option value="">Chọn báo cáo</option>{reports?.items.map((item) => <option key={item.id} value={item.id}>{item.title} · {item.document_key}</option>)}</select></div>
        <p className="selection-caption">{chosenReportVersion ? `Phiên bản ${chosenReportVersion.version_no} · ${chosenReportVersion.chunk_count} đoạn · ${PARSED.has(chosenReportVersion.processing_state) ? 'Đã xử lý' : 'Đang xử lý'}` : 'Chưa có báo cáo? Thêm tài liệu vào kho trước khi phân tích.'}<button type="button" className="text-action" onClick={() => onViewChange('documents')}>Mở kho tài liệu ↗</button></p>
        {runType !== 'ASSESSMENT' && <fieldset className="auth-form-full auth-source-choices"><legend>Nguồn đối chứng được chọn</legend>
          {sources?.items.length === 0 && <p>Upload và index ít nhất một nguồn đã được cấp quyền.</p>}
          {sources?.items.map((item) => <label key={item.id}><input type="checkbox" checked={!!sourceVersions[item.id]} disabled={busy || !versionCache[item.current_version_id] || !PARSED.has(versionCache[item.current_version_id].processing_state)} onChange={(event) => setSourceVersions((current) => { const next = { ...current }; if (event.target.checked) next[item.id] = item.current_version_id; else delete next[item.id]; return next; })} />
            <span>{item.title}<small>Phiên bản {versionCache[item.current_version_id]?.version_no ?? '—'} · {versionCache[item.current_version_id]?.chunk_count ?? 0} đoạn · {versionCache[item.current_version_id] && PARSED.has(versionCache[item.current_version_id].processing_state) ? 'Sẵn sàng' : 'Đang xử lý'}</small></span>
          </label>)}
        </fieldset>}
        {runType !== 'SIMILARITY' && <><div><label className="field-label" htmlFor="analysis-rubric">Rubric cho assessment</label><select id="analysis-rubric" required value={rubricId} disabled={busy} onChange={(event) => setRubricId(event.target.value)}><option value="">Chọn rubric</option>{rubrics?.items.map((item) => <option key={item.id} value={item.id}>{item.title} · {item.rubric_key}</option>)}</select>
          {rubrics?.page.has_more && <button type="button" className="subtle-button" disabled={busy} onClick={async () => {
            setBusy(true); try { const page = await listRubrics(workspaceId, rubrics.page.next_cursor); if (active.current) setRubrics({ ...page, items: [...rubrics.items, ...page.items] }); } catch (cause) { fail(cause); } finally { if (active.current) setBusy(false); }
          }}>Tải thêm rubric để phân tích</button>}</div>
          <div><label className="field-label" htmlFor="analysis-rubric-version">Published rubric version</label><select id="analysis-rubric-version" required value={rubricVersionId} disabled={busy || !rubricId || rubricVersions === null} onChange={(event) => setRubricVersionId(event.target.value)}><option value="">Chọn version đã publish</option>{rubricVersions?.items.filter((item) => item.status === 'PUBLISHED').map((item) => <option key={item.id} value={item.id}>Phiên bản {item.version_no} · Đã publish</option>)}</select>
            {rubricVersions?.page.has_more && <button type="button" className="subtle-button" disabled={busy} onClick={async () => { setBusy(true); try { const page = await listRubricVersions(workspaceId, rubricId, rubricVersions.page.next_cursor); if (active.current) setRubricVersions({ ...page, items: [...rubricVersions.items, ...page.items] }); } catch (cause) { fail(cause); } finally { if (active.current) setBusy(false); } }}>Tải thêm rubric version</button>}
            {rubricVersions && !rubricVersions.items.some((item) => item.status === 'PUBLISHED') && <small>Chưa có version publish trong trang này. Publish rubric hoặc tải thêm version nếu còn.</small>}</div></>}
        <div className="auth-form-full"><button className="primary-button analysis-submit" disabled={busy || !canStart || !!pendingRunId}>{preparing ? preparationStep : pendingRunId ? 'Đang phân tích…' : 'Phân tích báo cáo'}<span aria-hidden="true">↗</span></button><p className="field-help">Kết quả là đề xuất có bằng chứng, không phải điểm chính thức hay kết luận đạo văn.</p></div>
      </form>
    </section>}
    {canReadRuns && <section className="panel auth-run-panel">
      <div className="panel-section-heading"><span className="step-number">02</span><div><h2>Kết quả & bằng chứng</h2><p>Đọc nhận xét cùng đoạn văn và nguồn được đối chiếu.</p></div></div>
      <div className="recent-analysis">
        <div className="recent-analysis-controls">
          {canReadReports && <div><label className="field-label" htmlFor="results-report">Xem kết quả của báo cáo</label><select id="results-report" value={selectedReportId} disabled={busy || loading} onChange={(event) => selectReport(reports?.items.find((item) => item.id === event.target.value))}>
            <option value="">{loading ? 'Đang tải báo cáo…' : 'Chọn báo cáo để xem kết quả'}</option>{reports?.items.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select>{reports?.page.has_more && <button className="text-action" disabled={busy} onClick={() => { void moreDocuments('REPORT'); }}>Tải thêm báo cáo</button>}</div>}
          <div><label className="field-label" htmlFor="recent-analysis">Lượt phân tích đã lưu</label><select id="recent-analysis" value={run && recentRuns?.items.some((item) => item.id === run.id) ? run.id : ''} disabled={busy || loadingRecentRuns || !recentRuns?.items.length} onChange={(event) => { if (event.target.value) void loadRun(event.target.value); }}>
            <option value="">{!selectedReportId ? 'Chọn báo cáo để xem các lượt đã lưu' : loadingRecentRuns ? 'Đang tải các lượt đã lưu…' : recentRuns === null ? 'Chưa tải được các lượt đã lưu' : recentRuns.items.length === 0 ? 'Chưa có lượt phân tích đã lưu' : 'Chọn một lượt phân tích'}</option>{recentRuns?.items.map((item) => <option value={item.id} key={item.id}>{new Date(item.created_at).toLocaleString('vi-VN')} · {configLabel(item.config_id)} · {item.state === 'SUCCEEDED' ? 'Hoàn tất' : item.state}</option>)}
          </select>{recentRuns?.page.has_more && <button className="text-action" disabled={busy || loadingRecentRuns} onClick={() => { void moreRuns(); }}>Xem thêm lượt đã lưu</button>}</div>
        </div>
        {!selectedReportId && <p className="selection-caption">{canReadReports ? 'Chọn báo cáo tại đây để mở lại kết quả đã lưu.' : 'Nhập mã lượt phân tích bên dưới để mở kết quả.'}</p>}
      </div>
      <details className="technical-details"><summary>Mở lượt phân tích bằng mã</summary><form className="auth-run-lookup" onSubmit={openRun}><label className="field-label" htmlFor="analysis-run-id">Mở lượt chạy theo ID</label><div><input id="analysis-run-id" pattern="[0-9a-fA-F]{24}" maxLength={24} required value={runLookup} onChange={(event) => setRunLookup(event.target.value)} /><button className="secondary-button" disabled={busy}>Mở lượt chạy</button></div></form></details>
      {!run && <div className="analysis-empty"><div className="empty-paper" aria-hidden="true">▤<span>✓</span></div><span className="eyebrow">SẴN SÀNG KHI BẠN SẴN SÀNG</span><h3>Mỗi kết luận bắt đầu<br />từ một bằng chứng.</h3><p>Mở một lượt đã lưu ở trên, hoặc chọn báo cáo, nguồn và rubric ở bên trái để phân tích mới.</p><div className="empty-flow"><span>Đối chiếu nguồn</span><span>Đánh giá rubric</span><span>Review</span></div></div>}
      {run && <>
        <div className="analysis-run-heading"><div><h3>{run.state === 'SUCCEEDED' ? 'Phân tích hoàn tất' : run.state === 'FAILED' ? 'Chưa thể hoàn tất' : 'Đang phân tích báo cáo'}</h3><small>{new Date(run.created_at).toLocaleString('vi-VN')} · {configLabel(run.config_id)}</small></div><span className={`status-tag ${run.state === 'SUCCEEDED' ? 'status-ready' : ''}`} role="status">{run.state === 'SUCCEEDED' ? 'Hoàn tất' : run.state === 'FAILED' ? 'Lỗi xử lý' : 'Đang xử lý'}</span></div>
        <details className="technical-details"><summary>Thông tin kỹ thuật của lượt phân tích</summary><code>{run.id}</code><dl className="auth-run-provenance"><dt>Config / pipeline</dt><dd>{run.config_id} · {run.run_type}</dd><dt>Report version</dt><dd>{run.report_version_id}</dd><dt>Source versions</dt><dd>{run.source_version_ids.join(', ') || 'Không dùng'}</dd><dt>Index generations</dt><dd>{run.index_generation_ids.join(', ') || 'Không có'}</dd><dt>Rubric version</dt><dd>{run.rubric_version_id ?? 'Không dùng'}</dd><dt>Job</dt><dd>{run.job_id}</dd></dl></details>
        {run.failure_code && <p className="notice notice-error" role="alert">Worker chưa tạo được kết quả: {run.failure_code}. Không có kết luận cho lượt này.</p>}
        {!TERMINAL.has(run.state) && <p role="status">Đang chờ worker hoặc xử lý. Cấu hình Research v0 cần model đã chuẩn bị trên máy worker.</p>}
        <div className="auth-actions"><button className="subtle-button" disabled={busy} onClick={async () => {
          const selection = runSelection.current; setBusy(true); setError(null); try { const value = await getAnalysisRun(workspaceId, run.id); if (active.current && selection === runSelection.current) setRun(value); } catch (cause) { fail(cause); } finally { if (active.current) setBusy(false); }
        }}>Tải lại lượt chạy</button>{run.state === 'SUCCEEDED' && <button className="secondary-button" disabled={busy || results === null} onClick={() => { void exportRun(); }}>Export JSON kết quả</button>}</div>
        {loadingResults && <p role="status">Đang tải kết quả và evidence…</p>}
        {results && <AuthenticatedResults key={run.id} results={results} evidence={evidence} workspaceId={workspaceId} reportVersionId={run.report_version_id} sourceNames={Object.fromEntries((sources?.items ?? []).map((item) => [item.id, item.title]))} onMoreEvidence={async () => {
          if (!evidence?.page.has_more) return; const selection = runSelection.current; setBusy(true);
          try { const page = await getAnalysisEvidence(workspaceId, run.id, evidence.page.next_cursor); if (active.current && selection === runSelection.current) setEvidence({ ...page, items: [...evidence.items, ...page.items] }); } catch (cause) { fail(cause); } finally { if (active.current) setBusy(false); }
        }} busy={busy} />}
        {run.state === 'SUCCEEDED' && results && capabilities.includes('review.create') && <details className="item-review-disclosure"><summary>Review chi tiết từng cặp đoạn / checklist <span>Gán nhãn và chọn evidence →</span></summary><AuthenticatedItemAnnotations
          key={`${actor.id}:${workspaceId}:${run.id}`} actorId={actor.id} workspaceId={workspaceId} runId={run.id}
          runRevision={run.revision} canReview={true} onRunChanged={setRun} onAccessError={fail} /></details>}
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
    </div>
  </div>;
}
