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
export class AuthenticatedApiError extends Error {
  constructor(public status: number, public code: string, public requestId: string | null, message: string) {
    super(message);
  }
}

let csrfToken: string | null = null;
const prefix = '/api/v1';
let bootstrapPending: Promise<Actor> | null = null;

async function request<T>(path: string, options: {
  method?: string; body?: unknown; revision?: number; operationKey?: string; csrfRefresh?: boolean;
} = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET' && csrfToken !== null) headers['X-CSRF-Token'] = csrfToken;
  if (options.revision !== undefined) headers['If-Match'] = `"rev-${options.revision}"`;
  if (options.operationKey) headers['Idempotency-Key'] = options.operationKey;
  if (options.csrfRefresh) headers['X-CSRF-Refresh'] = '1';
  const response = await fetch(prefix + path, {
    method, headers, credentials: 'same-origin', cache: 'no-store',
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
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
