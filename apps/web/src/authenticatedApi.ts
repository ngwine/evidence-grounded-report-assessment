/** Cookie-backed API client. Session/CSRF secrets never enter persistent storage. */

export type Actor = {
  id: string;
  display_name: string;
  memberships: Array<{ workspace_id: string; role: string; capabilities: string[] }>;
};
export type Workspace = { id: string; key: string; name: string; status: string };
export type Page<T> = { items: T[]; page: { limit: number; has_more: boolean; next_cursor: string | null } };
export type RubricDefinition = { max_score: number; criteria: unknown[]; decision_rules?: Record<string, unknown> };
export type Rubric = {
  id: string; workspace_id: string; rubric_key: string; title: string;
  current_version_id: string; lifecycle_state: string; revision: number;
};
export type RubricVersion = {
  id: string; rubric_id: string; version_no: number; status: 'DRAFT' | 'PUBLISHED' | 'RETIRED';
  definition: RubricDefinition; rubric_sha256: string; revision: number;
};
export type DocumentKind = 'REPORT' | 'CORPUS_SOURCE';
export type DocumentRecord = {
  id: string; workspace_id: string; document_key: string; title: string;
  current_version_id: string; lifecycle_state: string; revision: number;
  owner_user_id?: string; governance_state?: string;
};
export type DocumentVersion = {
  id: string; document_id: string; version_no: number; content_sha256: string;
  processing_state: string; governance_state: string; lifecycle_state: string;
  element_count: number; chunk_count: number; failure_code: string | null; revision: number;
};
export type AsyncDocumentUpload = {
  document_id: string; document_version_id: string; job_id: string; state: string;
};
export type JobRecord = {
  id: string; job_type: string; state: string; attempt: number; max_attempts: number;
  progress: { step: string; completed: number; total: number }; error_code: string | null;
};
export type AnalysisConfigId = 'bm25-smoke' | 'research-v0';
export type UploadAuthorization = { id: string; name: string; rights_basis: string; allowed_purposes: string[]; valid_until: string | null; resource_id: string; classification: string };
export type IndexGeneration = {
  id: string; document_version_id: string; state: string; config_id: AnalysisConfigId;
  job_id: string; revision: number; failure_code?: string | null;
};
export type AnalysisRun = {
  id: string; state: string; run_type: 'BOTH' | 'SIMILARITY' | 'ASSESSMENT';
  report_version_id: string; source_version_ids: string[]; index_generation_ids: string[];
  rubric_version_id: string | null; config_id: AnalysisConfigId; job_id: string; revision: number;
  created_at: string; completed_at: string | null; failure_code: string | null; review_state: string;
};
export type AnalysisResults = {
  similarity: import('./types').SimilarityReport | null;
  assessment: import('./types').AssessmentReport | null;
  manifest?: Record<string, unknown>;
};
export type RunEvidence = {
  id: string; analysis_run_id: string; pipeline: string; report_version_id: string; source_version_id: string | null;
  report_chunk_id: string | null; source_chunk_id: string | null; checklist_id: string | null;
  evidence: Record<string, unknown>;
};
export type AnalysisReview = {
  id: string; analysis_run_id: string; reviewer_id: string; decision: 'ACCEPT' | 'REJECT';
  reason_code: string; reason_text: string | null; based_on_revision: number; created_at: string;
};
export type ItemAnnotationLabel = 'VERBATIM' | 'PARAPHRASE' | 'SUMMARY' | 'NONE' | 'UNSURE' | 'MET' | 'UNMET' | 'CANNOT_ASSESS';
export type ItemAnnotation = {
  id: string; item_id: string; pipeline: 'SIMILARITY' | 'ASSESSMENT'; annotator_id: string;
  label: ItemAnnotationLabel; evidence_span_ids: string[]; rationale: string;
  quote_or_citation: 'YES' | 'NO' | 'UNSURE' | null; annotation_revision: number;
  created_at: string; annotation_mode: 'MODEL_VISIBLE_REVIEW'; run_revision: number;
};
export type AnnotationSpan = {
  span_id: string; side: 'REPORT' | 'SOURCE'; document_version_id: string; chunk_id: string;
  raw_start: number; raw_end: number; quote_text: string; locator: Record<string, unknown>;
};
export type AnnotationItem = {
  item_id: string; pipeline: ItemAnnotation['pipeline']; report_version_id: string;
  report_chunk_id: string | null; source_version_id: string | null; source_chunk_id: string | null;
  checklist_id: string | null; statement: string | null; report_text: string; source_text: string | null;
  span_options: AnnotationSpan[]; latest_annotation: ItemAnnotation | null;
};
export type ItemAnnotationBody = {
  item_id: string; label: ItemAnnotationLabel; evidence_span_ids: string[]; rationale: string;
  quote_or_citation?: 'YES' | 'NO' | 'UNSURE';
};
export type AnnotationPage<T> = Page<T> & { run_revision: number };
export class AuthenticatedApiError extends Error {
  constructor(public status: number, public code: string, public requestId: string | null, message: string) {
    super(message);
  }
}

let csrfToken: string | null = null;
const prefix = '/api/v1';
let bootstrapPending: Promise<Actor> | null = null;

async function request<T>(path: string, options: {
  method?: string; body?: unknown; form?: FormData; revision?: number; operationKey?: string; csrfRefresh?: boolean;
  signal?: AbortSignal;
} = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET' && csrfToken !== null) headers['X-CSRF-Token'] = csrfToken;
  if (options.revision !== undefined) headers['If-Match'] = `"rev-${options.revision}"`;
  if (options.operationKey) headers['Idempotency-Key'] = options.operationKey;
  if (options.csrfRefresh) headers['X-CSRF-Refresh'] = '1';
  const response = await fetch(prefix + path, {
    method, headers, credentials: 'same-origin', cache: 'no-store', signal: options.signal,
    // The browser supplies the multipart boundary; never set it manually.
    body: options.form ?? (options.body === undefined ? undefined : JSON.stringify(options.body)),
  });
  if (!response.ok) {
    let code = 'REQUEST_FAILED';
    let message = 'Yêu cầu chưa thực hiện được.';
    let requestId = response.headers.get('X-Request-ID');
    try {
      const error = (await response.json()).error;
      if (typeof error?.code === 'string') code = error.code;
      if (typeof error?.message === 'string') message = error.message;
      if (typeof error?.request_id === 'string') requestId = error.request_id;
    } catch { /* A proxy failure need not have a JSON body. */ }
    if (response.status === 401) csrfToken = null;
    throw new AuthenticatedApiError(response.status, code, requestId, message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function operationKey(): string {
  return crypto.randomUUID();
}

export async function login(email: string, password: string): Promise<Actor> {
  const result = await request<{ actor: Actor; csrf_token: string }>('/auth/sessions', {
    method: 'POST', body: { email, password },
  });
  csrfToken = result.csrf_token;
  return result.actor;
}

export function bootstrapSession(): Promise<Actor> {
  // React StrictMode may mount twice. Share one bootstrap so CSRF rotation
  // cannot race with another bootstrap in this same document.
  if (bootstrapPending === null) {
    bootstrapPending = (async () => {
      const actor = await request<Actor>('/auth/me');
      const csrf = await request<{ csrf_token: string }>('/auth/csrf', { csrfRefresh: true });
      csrfToken = csrf.csrf_token;
      return actor;
    })().finally(() => { bootstrapPending = null; });
  }
  return bootstrapPending;
}

export async function logout(): Promise<void> {
  await request<void>('/auth/session', { method: 'DELETE' });
  csrfToken = null;
}

const scope = (workspaceId: string) => `/workspaces/${encodeURIComponent(workspaceId)}`;
const pageQuery = (cursor?: string | null) => `?limit=25${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;

export const listWorkspaces = (cursor?: string | null) => request<Page<Workspace>>('/workspaces' + pageQuery(cursor));
export const listRubrics = (workspaceId: string, cursor?: string | null) =>
  request<Page<Rubric>>(scope(workspaceId) + '/rubrics' + pageQuery(cursor));
export const getRubric = (workspaceId: string, rubricId: string) =>
  request<Rubric>(scope(workspaceId) + '/rubrics/' + encodeURIComponent(rubricId));
export const getRubricVersion = (workspaceId: string, versionId: string) =>
  request<RubricVersion>(scope(workspaceId) + '/rubric-versions/' + encodeURIComponent(versionId));
export const listRubricVersions = (workspaceId: string, rubricId: string, cursor?: string | null) =>
  request<Page<RubricVersion>>(scope(workspaceId) + '/rubrics/' + encodeURIComponent(rubricId) + '/versions' + pageQuery(cursor));
export const createRubric = (workspaceId: string, body: { rubric_key: string; title: string; definition: RubricDefinition }, key: string) =>
  request<Rubric>(scope(workspaceId) + '/rubrics', { method: 'POST', body, operationKey: key });
export const updateRubricDraft = (workspaceId: string, version: RubricVersion, definition: RubricDefinition) =>
  request<RubricVersion>(scope(workspaceId) + '/rubric-versions/' + encodeURIComponent(version.id), {
    method: 'PUT', body: definition, revision: version.revision,
  });
export const publishRubricVersion = (workspaceId: string, version: RubricVersion) =>
  request<RubricVersion>(scope(workspaceId) + '/rubric-versions/' + encodeURIComponent(version.id) + ':publish', {
    method: 'POST', revision: version.revision, operationKey: `publish:${version.id}:${version.revision}`,
  });
export const cloneRubricVersion = (workspaceId: string, rubric: Rubric, version: RubricVersion, key: string) =>
  request<RubricVersion>(scope(workspaceId) + '/rubrics/' + encodeURIComponent(rubric.id) + '/versions', {
    method: 'POST', body: { clone_from_version_id: version.id }, revision: rubric.revision, operationKey: key,
  });

const collection = (kind: DocumentKind) => kind === 'REPORT' ? '/reports' : '/sources';
export const listDocuments = (workspaceId: string, kind: DocumentKind, cursor?: string | null) =>
  request<Page<DocumentRecord>>(scope(workspaceId) + collection(kind) + pageQuery(cursor));
export const listUploadAuthorizations = (workspaceId: string, kind: DocumentKind, cursor?: string | null) =>
  request<Page<UploadAuthorization>>(scope(workspaceId) + '/upload-authorizations' + pageQuery(cursor) + '&kind=' + kind);
export const getDocumentVersion = (workspaceId: string, versionId: string) =>
  request<DocumentVersion>(scope(workspaceId) + '/document-versions/' + encodeURIComponent(versionId));
export const listDocumentVersions = (workspaceId: string, kind: DocumentKind, documentId: string, cursor?: string | null) =>
  request<Page<DocumentVersion>>(scope(workspaceId) + collection(kind) + '/' + encodeURIComponent(documentId) + '/versions' + pageQuery(cursor));
export const uploadDocument = (workspaceId: string, kind: DocumentKind, form: FormData, key: string, existing?: DocumentRecord) =>
  request<AsyncDocumentUpload>(scope(workspaceId) + collection(kind) + (existing ? '/' + encodeURIComponent(existing.id) + '/versions' : ''), {
    method: 'POST', form, operationKey: key, revision: existing?.revision,
  });
export const getJob = (workspaceId: string, jobId: string) =>
  request<JobRecord>(scope(workspaceId) + '/jobs/' + encodeURIComponent(jobId));
export const createIndexGeneration = (workspaceId: string, versionId: string, configId: AnalysisConfigId, key: string) =>
  request<IndexGeneration>(scope(workspaceId) + '/document-versions/' + encodeURIComponent(versionId) + '/index-generations', {
    method: 'POST', body: { config_id: configId }, operationKey: key,
  });
export const getIndexGeneration = (workspaceId: string, generationId: string) =>
  request<IndexGeneration>(scope(workspaceId) + '/index-generations/' + encodeURIComponent(generationId));
export const createAnalysisRun = async (workspaceId: string, reportId: string, body: {
  run_type: AnalysisRun['run_type']; report_version_id: string;
  source_scope: { source_version_ids: string[] }; rubric_version_id: string | null; config_id: AnalysisConfigId;
}, key: string): Promise<AnalysisRun> => {
  const operation = await request<{ run_id: string; job_id: string; state: string }>(scope(workspaceId) + '/reports/' + encodeURIComponent(reportId) + '/analysis-runs', {
    method: 'POST', body, operationKey: key,
  });
  return getAnalysisRun(workspaceId, operation.run_id);
};
export const getAnalysisRun = (workspaceId: string, runId: string, signal?: AbortSignal) =>
  request<AnalysisRun>(scope(workspaceId) + '/analysis-runs/' + encodeURIComponent(runId), { signal });
export const getAnalysisResults = (workspaceId: string, runId: string) =>
  request<AnalysisResults>(scope(workspaceId) + '/analysis-runs/' + encodeURIComponent(runId) + '/results');
export const getAnalysisEvidence = (workspaceId: string, runId: string, cursor?: string | null) =>
  request<Page<RunEvidence>>(scope(workspaceId) + '/analysis-runs/' + encodeURIComponent(runId) + '/evidence' + pageQuery(cursor));
export const exportAnalysisRun = (workspaceId: string, runId: string) =>
  request<Record<string, unknown>>(scope(workspaceId) + '/analysis-runs/' + encodeURIComponent(runId) + '/export');
export const listAnalysisRuns = (workspaceId: string, reportId: string, cursor?: string | null) =>
  request<Page<AnalysisRun>>(scope(workspaceId) + '/reports/' + encodeURIComponent(reportId) + '/analysis-runs' + pageQuery(cursor));
export const listAnalysisReviews = (workspaceId: string, runId: string, cursor?: string | null) =>
  request<Page<AnalysisReview>>(scope(workspaceId) + '/analysis-runs/' + encodeURIComponent(runId) + '/reviews' + pageQuery(cursor));
export const createAnalysisReview = (workspaceId: string, run: AnalysisRun, body: {
  decision: 'ACCEPT' | 'REJECT'; reason_code: string; reason_text: string | null;
}) => request<AnalysisReview>(scope(workspaceId) + '/analysis-runs/' + encodeURIComponent(run.id) + '/reviews', {
  method: 'POST', body, revision: run.revision,
});
const annotationScope = (workspaceId: string, runId: string) =>
  scope(workspaceId) + '/analysis-runs/' + encodeURIComponent(runId);
export const listAnnotationItems = (workspaceId: string, runId: string, cursor?: string | null, signal?: AbortSignal) =>
  request<AnnotationPage<AnnotationItem>>(annotationScope(workspaceId, runId) + '/annotation-items' + pageQuery(cursor), { signal });
export const listItemAnnotations = (workspaceId: string, runId: string, cursor?: string | null, signal?: AbortSignal) =>
  request<AnnotationPage<ItemAnnotation>>(annotationScope(workspaceId, runId) + '/item-annotations' + pageQuery(cursor), { signal });
export const createItemAnnotation = (workspaceId: string, runId: string, body: ItemAnnotationBody, revision: number, key: string, signal?: AbortSignal) =>
  request<ItemAnnotation>(annotationScope(workspaceId, runId) + '/item-annotations', {
    method: 'POST', body, revision, operationKey: key, signal,
  });
export const exportItemAnnotations = (workspaceId: string, runId: string, signal?: AbortSignal) =>
  request<Record<string, unknown>>(annotationScope(workspaceId, runId) + '/item-annotations/export', { signal });
export const documentFileUrl = (workspaceId: string, versionId: string, pageIndex?: number | null): string =>
  prefix + scope(workspaceId) + '/document-versions/' + encodeURIComponent(versionId) + '/file'
  + (typeof pageIndex === 'number' && Number.isInteger(pageIndex) && pageIndex >= 0 ? `#page=${pageIndex + 1}` : '');
