import type { ConfigId, ReviewDecision, RunRecord } from './types';

const BASE = '/api/local/v1';

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function extractMessage(body: unknown, status: number): string {
  if (typeof body === 'string' && body.trim()) return body.slice(0, 400);
  if (body && typeof body === 'object') {
    const record = body as Record<string, unknown>;
    const detail = record.detail ?? record.message ?? record.error;
    if (typeof detail === 'string' && detail.trim()) return detail.slice(0, 400);
    if (detail && typeof detail === 'object') {
      const nested = detail as Record<string, unknown>;
      if (typeof nested.message === 'string') return nested.message.slice(0, 400);
    }
  }
  return `Yêu cầu không thành công (HTTP ${status}).`;
}

async function readResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  let body: unknown;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!response.ok) throw new ApiError(extractMessage(body, response.status), response.status);
  return body as T;
}

export async function createRun(input: {
  report: File;
  sources: File[];
  rubric: File;
  configId: ConfigId;
}): Promise<RunRecord> {
  const form = new FormData();
  form.append('report', input.report);
  input.sources.forEach((source) => form.append('sources', source));
  form.append('rubric', input.rubric);
  form.append('config_id', input.configId);
  const response = await fetch(`${BASE}/runs`, {
    method: 'POST',
    headers: { 'X-KLTN-Local-UI': '1' },
    body: form,
  });
  return readResponse<RunRecord>(response);
}

export async function getRun(runId: string, signal?: AbortSignal): Promise<RunRecord> {
  const response = await fetch(`${BASE}/runs/${encodeURIComponent(runId)}`, { signal });
  return readResponse<RunRecord>(response);
}

export async function submitReview(input: {
  runId: string;
  decision: ReviewDecision;
  comment: string;
  expectedRevision: number;
  reviewerName: string;
}): Promise<{ review: RunRecord['review']; revision: number }> {
  const response = await fetch(`${BASE}/runs/${encodeURIComponent(input.runId)}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-KLTN-Local-UI': '1' },
    body: JSON.stringify({
      decision: input.decision,
      comment: input.comment,
      expected_revision: input.expectedRevision,
      reviewer_name: input.reviewerName,
    }),
  });
  return readResponse<{ review: RunRecord['review']; revision: number }>(response);
}
