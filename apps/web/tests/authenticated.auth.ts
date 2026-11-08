/** Browser interaction checks against a mocked /api/v1 contract only. */
import { expect, test, type Page } from '@playwright/test';

const WORKSPACE = '000000000000000000000001';
const RUBRIC = '000000000000000000000002';
const VERSION = '000000000000000000000003';
const CLONE = '000000000000000000000004';
const INITIAL_CSRF = 'synthetic-csrf-initial';
const REFRESHED_CSRF = 'synthetic-csrf-refreshed';

async function mockApi(page: Page, options: { loggedIn?: boolean; canManage?: boolean; staleOnce?: boolean } = {}) {
  let loggedIn = options.loggedIn ?? false;
  let csrf = INITIAL_CSRF;
  let staleOnce = options.staleOnce ?? false;
  const calls: Array<{ path: string; method: string; headers: Record<string, string> }> = [];
  const actor = { id: '000000000000000000000005', display_name: 'Giảng viên thử nghiệm', memberships: [
    { workspace_id: WORKSPACE, role: options.canManage === false ? 'STUDENT' : 'LECTURER',
      capabilities: options.canManage === false ? ['workspace.read'] : ['workspace.read', 'rubric.manage'] },
  ] };
  let parent: Record<string, unknown> | null = null;
  const versions = new Map<string, Record<string, unknown>>();
  const makePage = (items: unknown[]) => ({ items, page: { limit: 25, has_more: false, next_cursor: null } });
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const headers = request.headers();
    calls.push({ path, method, headers });
    const reply = (value: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) });
    const deny = (status: number, code: string) => reply({ error: { code, message: 'Synthetic error', request_id: 'req-ui-synthetic' } }, status);
    if (path === '/api/v1/auth/sessions') {
      expect(request.postDataJSON()).toEqual({ email: 'lecturer@example.invalid', password: 'Synthetic-Only-Password' });
      loggedIn = true;
      return reply({ actor, csrf_token: csrf, expires_at: '2026-10-24T00:00:00Z' });
    }
    if (!loggedIn) return deny(401, 'AUTHENTICATION_REQUIRED');
    if (path === '/api/v1/auth/me') return reply(actor);
    if (path === '/api/v1/auth/csrf') {
      expect(headers['x-csrf-refresh']).toBe('1');
      csrf = REFRESHED_CSRF;
      return reply({ csrf_token: csrf });
    }
    if (method !== 'GET') expect(headers['x-csrf-token']).toBe(csrf);
    if (path === '/api/v1/auth/session') { loggedIn = false; return route.fulfill({ status: 204 }); }
    if (path === '/api/v1/workspaces') return reply(makePage([{ id: WORKSPACE, key: 'synthetic', name: 'Workspace thử nghiệm', status: 'ACTIVE' }]));
    if (path.endsWith('/rubrics') && method === 'POST') {
      expect(headers['idempotency-key'].length).toBeGreaterThanOrEqual(16);
      const body = request.postDataJSON();
      parent = { id: RUBRIC, workspace_id: WORKSPACE, rubric_key: body.rubric_key, title: body.title,
        current_version_id: VERSION, lifecycle_state: 'ACTIVE', revision: 1 };
      versions.set(VERSION, { id: VERSION, rubric_id: RUBRIC, version_no: 1, status: 'DRAFT',
        definition: body.definition, rubric_sha256: 'a'.repeat(64), revision: 1 });
      return reply(parent, 201);
    }
    if (path.endsWith('/rubrics')) return reply(makePage(parent ? [parent] : []));
    if (path.endsWith('/rubrics/' + RUBRIC)) return reply(parent);
    if (path.endsWith('/versions') && method === 'GET') return reply(makePage([...versions.values()]));
    if (path.endsWith('/versions') && method === 'POST') {
      expect(headers['if-match']).toBe('"rev-2"');
      const source = versions.get(request.postDataJSON().clone_from_version_id)!;
      const clone = { ...source, id: CLONE, version_no: 2, status: 'DRAFT', revision: 1 };
      versions.set(CLONE, clone); parent!.revision = 3;
      return reply(clone, 201);
    }
    const id = path.split('/').at(-1)!.replace(':publish', '');
    const version = versions.get(id);
    if (version && method === 'GET') return reply(version);
    if (version && method === 'PUT') {
      if (staleOnce) { staleOnce = false; return deny(409, 'REVISION_CONFLICT'); }
      expect(headers['if-match']).toBe(`"rev-${version.revision}"`);
      version.definition = request.postDataJSON(); version.revision = Number(version.revision) + 1;
      return reply(version);
    }
    if (version && path.endsWith(':publish')) {
      expect(headers['if-match']).toBe(`"rev-${version.revision}"`);
      version.status = 'PUBLISHED'; version.revision = Number(version.revision) + 1;
      parent!.revision = Number(parent!.revision) + 1;
      return reply(version);
    }
    return deny(404, 'RESOURCE_NOT_FOUND');
  });
  return calls;
}

async function signIn(page: Page) {
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill('lecturer@example.invalid');
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Synthetic-Only-Password');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await page.getByLabel('Workspace', { exact: true }).selectOption(WORKSPACE);
}

async function createDraft(page: Page) {
  await page.getByRole('button', { name: 'Rubric đánh giá', exact: true }).click();
  await page.getByRole('button', { name: 'Tạo rubric', exact: true }).click();
  await page.getByLabel('Mã rubric', { exact: true }).fill('synthetic');
  await page.getByLabel('Tên rubric', { exact: true }).fill('Rubric thử nghiệm');
  await page.getByLabel('Tên tiêu chí', { exact: true }).fill('Phương pháp');
  await page.getByLabel('Phát biểu cần kiểm chứng', { exact: true }).fill('Báo cáo trình bày phương pháp đánh giá.');
  await page.getByLabel('Cách diễn đạt 1 của yêu cầu 1.1.1', { exact: true }).fill('phương pháp đánh giá');
  await page.getByRole('button', { name: 'Lưu draft', exact: true }).click();
  await expect(page.getByLabel('Các version đã lưu')).toHaveValue(VERSION);
  await page.getByText('JSON nâng cao', { exact: true }).click();
}

test('mocked API: login → author → CAS save → immutable publish → clone and recover draft', async ({ page }) => {
  const calls = await mockApi(page);
  await signIn(page);
  await createDraft(page);
  const editor = page.getByLabel('Rubric definition JSON', { exact: true });
  const definition = JSON.parse(await editor.inputValue());
  definition.criteria[0].title = 'Tiêu chí đã sửa';
  await editor.fill(JSON.stringify(definition));
  await expect(page.getByRole('button', { name: 'Kiểm tra & publish' })).toBeDisabled();
  await page.getByRole('button', { name: 'Lưu draft', exact: true }).click();
  await page.getByRole('button', { name: 'Kiểm tra & publish' }).click();
  await expect(editor).toHaveAttribute('readonly');
  await page.getByRole('button', { name: 'Clone thành draft mới' }).click();
  await expect(page.getByLabel('Các version đã lưu')).toHaveValue(CLONE);
  await page.getByRole('button', { name: 'Tải lại bản hiện tại' }).click();
  await expect(page.getByLabel('Các version đã lưu')).toHaveValue(VERSION);
  await page.getByLabel('Các version đã lưu').selectOption(CLONE);
  await expect(editor).not.toHaveAttribute('readonly');
  expect(await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) })))
    .toEqual({ local: [], session: [] });
  expect(calls.some((call) => call.method === 'PUT' && call.headers['if-match'] === '"rev-1"')).toBe(true);
  await page.getByRole('button', { name: 'Đăng xuất', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Đăng nhập', exact: true })).toBeVisible();
});

test('mocked API: existing cookie session refreshes memory CSRF; forbidden UI stays closed', async ({ page }) => {
  const calls = await mockApi(page, { loggedIn: true, canManage: false });
  await page.goto('/');
  await page.getByLabel('Workspace', { exact: true }).selectOption(WORKSPACE);
  await expect(page.getByText('Bạn có quyền vào workspace này nhưng không có quyền quản lý rubric.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Tạo rubric', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Đăng xuất', exact: true }).click();
  expect(calls.find((call) => call.path === '/api/v1/auth/session')?.headers['x-csrf-token']).toBe(REFRESHED_CSRF);
});

test('mocked API: visual rubric editor updates real definition without exposing JSON by default', async ({ page }) => {
  await mockApi(page);
  await signIn(page);
  await page.getByRole('button', { name: 'Rubric đánh giá', exact: true }).click();
  await page.getByRole('button', { name: 'Tạo rubric', exact: true }).click();
  await expect(page.getByLabel('Rubric definition JSON', { exact: true })).toBeHidden();
  await expect(page.getByLabel('Tên tiêu chí', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('Phát biểu cần kiểm chứng', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('Cách diễn đạt 1 của yêu cầu 1.1.1', { exact: true })).toHaveValue('');
  await page.getByLabel('Mã rubric', { exact: true }).fill('visual');
  await page.getByLabel('Tên rubric', { exact: true }).fill('Rubric nhập bằng form');
  await page.getByLabel('Tên tiêu chí', { exact: true }).fill('Chất lượng phương pháp');
  await page.getByLabel('Phát biểu cần kiểm chứng', { exact: true }).fill('Báo cáo có mô tả phương pháp đánh giá.');
  await page.getByLabel('Cách diễn đạt 1 của yêu cầu 1.1.1', { exact: true }).fill('phương pháp đánh giá');
  await page.locator('summary').filter({ hasText: 'Cụm từ thể hiện không đáp ứng' }).click();
  await page.getByRole('button', { name: 'Thêm cụm không đáp ứng', exact: true }).click();
  await page.getByLabel('Cụm không đáp ứng 1 của checklist 1.1', { exact: true }).fill('chưa thực hiện đánh giá');
  await page.getByRole('button', { name: 'Lưu draft', exact: true }).click();
  await expect(page.getByLabel('Các version đã lưu')).toHaveValue(VERSION);
  await page.getByRole('button', { name: 'Kiểm tra & publish' }).click();
  await expect(page.getByText('Chất lượng phương pháp', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Tên tiêu chí', { exact: true })).toHaveCount(0);
  await page.getByText('JSON nâng cao', { exact: true }).click();
  const definition = JSON.parse(await page.getByLabel('Rubric definition JSON', { exact: true }).inputValue());
  expect(definition.criteria[0].title).toBe('Chất lượng phương pháp');
  expect(definition.criteria[0].checklists[0].statement).toBe('Báo cáo có mô tả phương pháp đánh giá.');
  expect(definition.criteria[0].checklists[0].requirements[0].any_of).toEqual(['phương pháp đánh giá']);
  expect(definition.criteria[0].checklists[0].contradiction_patterns).toEqual(['chưa thực hiện đánh giá']);
});

test('mocked API: revision conflict preserves authored draft instead of claiming saved', async ({ page }) => {
  await mockApi(page, { staleOnce: true });
  await signIn(page);
  await createDraft(page);
  const editor = page.getByLabel('Rubric definition JSON', { exact: true });
  const authored = JSON.parse(await editor.inputValue());
  authored.criteria[0].title = 'Nội dung chưa được lưu';
  await editor.fill(JSON.stringify(authored));
  await page.getByRole('button', { name: 'Lưu draft', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Nội dung đã được cập nhật ở nơi khác');
  expect(JSON.parse(await editor.inputValue()).criteria[0].title).toBe('Nội dung chưa được lưu');
  await expect(page.getByRole('button', { name: 'Kiểm tra & publish' })).toBeDisabled();
});

const REVIEW_RUN = '000000000000000000000010';
const REVIEW_ITEM = '1'.repeat(64);
const CHECKLIST_ITEM = '2'.repeat(64);
const REPORT_SPAN = 'a'.repeat(64);
const SOURCE_SPAN = 'b'.repeat(64);

async function mockItemReviewApi(page: Page, options: { holdItems?: boolean; failFirstSave?: boolean; results?: Record<string, unknown> } = {}) {
  const calls: Array<{ path: string; method: string; headers: Record<string, string>; body: Record<string, unknown> | null }> = [];
  const annotations: Array<Record<string, unknown>> = [];
  let revision = 1;
  let conflictNext = false;
  let failSave = options.failFirstSave ?? false;
  let releaseItems: () => void = () => {};
  const heldItems = new Promise<void>((resolve) => { releaseItems = resolve; });
  const makePage = (items: unknown[]) => ({ items, page: { limit: 25, has_more: false, next_cursor: null }, run_revision: revision });
  const actor = { id: '000000000000000000000005', display_name: 'Reviewer thử nghiệm', memberships: [
    { workspace_id: WORKSPACE, role: 'LECTURER', capabilities: ['workspace.read', 'run.read', 'review.create'] },
  ] };
  const span = (side: 'REPORT' | 'SOURCE', id: string) => ({ span_id: id, side, document_version_id: VERSION,
    chunk_id: side.toLowerCase() + '-chunk', raw_start: 0, raw_end: 15,
    quote_text: side === 'REPORT' ? '<script>window.reviewXss = true</script>' : 'Synthetic source evidence.', locator: { page_index: 0 } });
  const items = [
    { item_id: REVIEW_ITEM, pipeline: 'SIMILARITY', report_version_id: VERSION, report_chunk_id: 'report-chunk',
      source_version_id: VERSION, source_chunk_id: 'source-chunk', checklist_id: null, statement: null,
      report_text: '<script>window.reviewXss = true</script>', source_text: 'Synthetic source evidence.',
      span_options: [span('REPORT', REPORT_SPAN), span('SOURCE', SOURCE_SPAN)] },
    { item_id: CHECKLIST_ITEM, pipeline: 'ASSESSMENT', report_version_id: VERSION, report_chunk_id: null,
      source_version_id: null, source_chunk_id: null, checklist_id: 'C1.1', statement: 'Synthetic checklist without retrieved machine evidence.',
      report_text: 'Report text remains available for manual evidence selection.', source_text: null,
      span_options: [span('REPORT', REPORT_SPAN)] },
  ];
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const headers = request.headers();
    const body = method === 'POST' ? request.postDataJSON() : null;
    calls.push({ path, method, headers, body });
    const reply = (value: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) });
    const deny = (status: number, code: string) => reply({ error: { code, message: 'Synthetic review error', request_id: 'req-item-review' } }, status);
    if (path.endsWith('/auth/me')) return reply(actor);
    if (path.endsWith('/auth/csrf')) return reply({ csrf_token: REFRESHED_CSRF });
    if (path === '/api/v1/workspaces') return reply(makePage([{ id: WORKSPACE, key: 'review', name: 'Review workspace', status: 'ACTIVE' }]));
    if (path.endsWith('/analysis-runs/' + REVIEW_RUN)) return reply({ id: REVIEW_RUN, state: 'SUCCEEDED', run_type: 'BOTH',
      report_version_id: VERSION, source_version_ids: [VERSION], index_generation_ids: [], rubric_version_id: VERSION,
      config_id: 'bm25-smoke', job_id: 'synthetic-job', revision, created_at: '2026-10-24T00:00:00Z',
      completed_at: '2026-10-24T00:00:01Z', failure_code: null, review_state: 'UNREVIEWED' });
    if (path.endsWith('/results')) return reply(options.results ?? { similarity: null, assessment: null });
    if (path.endsWith('/evidence')) return reply(makePage([]));
    if (path.endsWith('/annotation-items')) {
      if (options.holdItems) await heldItems;
      return reply(makePage(items.map((item) => ({ ...item,
        latest_annotation: [...annotations].reverse().find((annotation) => annotation.item_id === item.item_id) ?? null }))));
    }
    if (path.endsWith('/item-annotations/export')) return reply({ analysis_run_id: REVIEW_RUN, annotation_mode: 'MODEL_VISIBLE_REVIEW',
      predictions_visible: true, independent_gold: false, items, annotations });
    if (path.endsWith('/item-annotations') && method === 'GET') return reply(makePage(annotations));
    if (path.endsWith('/item-annotations') && method === 'POST') {
      expect(headers['x-csrf-token']).toBe(REFRESHED_CSRF);
      expect(headers['idempotency-key'].length).toBeGreaterThanOrEqual(16);
      if (failSave) { failSave = false; return deny(503, 'DATASTORE_UNAVAILABLE'); }
      if (conflictNext) { conflictNext = false; revision += 1; return deny(409, 'REVISION_CONFLICT'); }
      expect(headers['if-match']).toBe(`"rev-${revision}"`);
      revision += 1;
      const annotation = { ...body, id: `review-${annotations.length + 1}`, pipeline: body.item_id === REVIEW_ITEM ? 'SIMILARITY' : 'ASSESSMENT',
        annotator_id: actor.id, quote_or_citation: body.quote_or_citation ?? null,
        annotation_revision: annotations.filter((entry) => entry.item_id === body.item_id).length + 1,
        created_at: '2026-10-24T00:00:02Z', annotation_mode: 'MODEL_VISIBLE_REVIEW', run_revision: revision };
      annotations.push(annotation);
      return reply(annotation, 201);
    }
    if (path.endsWith('/reviews') && method === 'POST') {
      expect(headers['if-match']).toBe(`"rev-${revision}"`);
      revision += 1;
      return reply({ id: 'whole-review', ...body }, 201);
    }
    return deny(404, 'RESOURCE_NOT_FOUND');
  });
  return { calls, annotations, releaseItems, conflictNextSave: () => { conflictNext = true; } };
}

async function openReviewRun(page: Page) {
  await page.goto('/');
  await page.getByLabel('Workspace', { exact: true }).selectOption(WORKSPACE);
  await page.getByText('Mở lượt phân tích bằng mã', { exact: true }).click();
  await page.getByLabel('Mở lượt chạy theo ID', { exact: true }).fill(REVIEW_RUN);
  await page.getByRole('button', { name: 'Mở lượt chạy', exact: true }).click();
  await page.getByText('Review chi tiết từng cặp đoạn / checklist', { exact: false }).click();
}

test('mocked API: negative-only similarity pairs remain visible without claiming a clean report', async ({ page }) => {
  const matches = ['MODEL_REJECTED_EQUIVALENCE', 'NO_SIMILARITY_HYPOTHESIS'].map((classification_status, index) => ({
    classification_status, report_chunk_id: `negative-report-${index}`, source_chunk_id: `negative-source-${index}`,
    source_document_id: `source-${index}`, source_name: `Negative source ${index + 1}`, similarity_type: 'NONE',
    selected_for_manual_review: false, selected_for_document_coverage: false,
    alignment: { report: { text: `Negative report passage ${index + 1}` }, source: { text: `Negative source passage ${index + 1}` } },
  }));
  await mockItemReviewApi(page, { results: { similarity: { matches, exact_match_coverage_percentage: 0, semantic_classifier_available: true }, assessment: null } });
  await openReviewRun(page);
  const results = page.getByRole('region', { name: 'Pipeline 1 kết quả', exact: true });
  const negative = results.getByRole('button', { name: 'Không đề xuất tương đồng 2', exact: true });
  await expect(negative).toHaveAttribute('aria-pressed', 'true');
  await expect(results.locator('.comparison-card')).toHaveCount(2);
  await expect(results).toContainText('Negative report passage 1');
  await expect(results).toContainText('Negative report passage 2');
  await expect(results).toContainText('không chứng minh toàn báo cáo không có nội dung tương đồng');
  await expect(results).toContainText('chưa phải xác nhận không có sao chép');
  await expect(results.getByRole('button', { name: /^Chưa xác định/ })).toHaveCount(0);
  await results.getByRole('button', { name: 'Khớp nguyên văn 0', exact: true }).click();
  await expect(results.locator('.comparison-card')).toHaveCount(0);
  await negative.click();
  await expect(results.locator('.comparison-card')).toHaveCount(2);
});

test('mocked API: unknown similarity status stays inspectable as unresolved', async ({ page }) => {
  await mockItemReviewApi(page, { results: { similarity: { matches: [{
    classification_status: 'FUTURE_REVIEW_STATUS', report_chunk_id: 'future-report', source_chunk_id: 'future-source',
    source_document_id: 'future-document', source_name: 'Future source', selected_for_manual_review: true,
    selected_for_document_coverage: false, alignment: { report: { text: 'Future report passage' }, source: { text: 'Future source passage' } },
  }], exact_match_coverage_percentage: 0 }, assessment: null } });
  await openReviewRun(page);
  const results = page.getByRole('region', { name: 'Pipeline 1 kết quả', exact: true });
  await expect(results.getByRole('button', { name: 'Chưa xác định 1', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(results.locator('.comparison-card')).toHaveCount(1);
  await expect(results).toContainText('Future report passage');
  await expect(results.locator('.finding-badge')).toHaveText('Chưa xác định');
  await expect(results.getByRole('button', { name: /^Không đề xuất tương đồng/ })).toHaveCount(0);
  await results.getByText('Vị trí và chi tiết đối chiếu', { exact: true }).click();
  await expect(results.locator('.auth-evidence-json')).toContainText('FUTURE_REVIEW_STATUS');
});

test('mocked API: item review loading, retry, immutable correction and conflict preserve draft and CAS', async ({ page }) => {
  const api = await mockItemReviewApi(page, { holdItems: true, failFirstSave: true });
  await openReviewRun(page);
  await expect(page.getByText('Đang tải các mục review…', { exact: true })).toBeVisible();
  api.releaseItems();
  const item = page.getByRole('article', { name: `Mục review ${REVIEW_ITEM}`, exact: true });
  await item.getByLabel(`Nhãn review ${REVIEW_ITEM}`, { exact: true }).selectOption('VERBATIM');
  await item.getByLabel(`Trích dẫn hoặc citation ${REVIEW_ITEM}`, { exact: true }).selectOption('NO');
  await item.getByRole('checkbox', { name: /^REPORT/ }).check();
  await item.getByRole('checkbox', { name: /^SOURCE/ }).check();
  const rationale = item.getByLabel(`Lý do review ${REVIEW_ITEM}`, { exact: true });
  await rationale.fill('Synthetic reviewer checked both pinned spans.');
  const save = item.getByRole('button', { name: 'Lưu phiên bản review', exact: true });
  await save.click();
  await expect(page.getByRole('alert')).toContainText('Chưa thực hiện được yêu cầu review');
  await save.click();
  await expect(item.getByText('Review đã lưu · phiên bản 1 · VERBATIM', { exact: true })).toBeVisible();
  await expect(save).toBeDisabled();
  const writes = () => api.calls.filter((call) => call.method === 'POST' && call.path.endsWith('/item-annotations'));
  expect(writes()[0].headers['idempotency-key']).toBe(writes()[1].headers['idempotency-key']);
  const first = { ...api.annotations[0] };
  await rationale.fill('Synthetic correction retains the first immutable review.');
  api.conflictNextSave();
  await save.click();
  await expect(page.getByRole('alert')).toContainText('Bản nháp được giữ lại');
  await expect(rationale).toHaveValue('Synthetic correction retains the first immutable review.');
  await expect(item.getByRole('checkbox', { name: /^SOURCE/ })).toBeChecked();
  await page.getByRole('button', { name: 'Tải revision mới, giữ bản nháp', exact: true }).click();
  await expect(save).toBeEnabled();
  await save.click();
  await expect(item.getByText('Review đã lưu · phiên bản 2 · VERBATIM', { exact: true })).toBeVisible();
  expect(writes()[2].headers['idempotency-key']).not.toBe(writes()[1].headers['idempotency-key']);
  expect(writes()[3].headers['idempotency-key']).toBe(writes()[2].headers['idempotency-key']);
  expect(api.annotations[0]).toEqual(first);
  await page.getByRole('button', { name: 'Xem lịch sử review', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Lịch sử review của bạn' }).getByRole('listitem')).toHaveCount(2);
  await page.getByLabel('Nhận xét review', { exact: true }).fill('Whole-run review uses refreshed item-annotation revision.');
  await page.getByRole('button', { name: 'Chấp nhận đề xuất', exact: true }).click();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export JSON review', exact: true }).click();
  expect((await downloaded).suggestedFilename()).toBe(`item-reviews-${REVIEW_RUN}.json`);
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
});

test('mocked API: per-pipeline evidence and rationale validation blocks invalid saves and renders source text safely', async ({ page }) => {
  const api = await mockItemReviewApi(page);
  await openReviewRun(page);
  const section = page.getByRole('region', { name: 'Review từng mục', exact: true });
  await expect(section).toContainText('không phải gold độc lập được gán nhãn mù');
  const item = page.getByRole('article', { name: `Mục review ${REVIEW_ITEM}`, exact: true });
  const save = item.getByRole('button', { name: 'Lưu phiên bản review', exact: true });
  await item.getByLabel(`Nhãn review ${REVIEW_ITEM}`, { exact: true }).selectOption('PARAPHRASE');
  await item.getByLabel(`Lý do review ${REVIEW_ITEM}`, { exact: true }).fill('Evidence must support this positive relationship.');
  await expect(save).toBeDisabled();
  await item.getByLabel(`Trích dẫn hoặc citation ${REVIEW_ITEM}`, { exact: true }).selectOption('UNSURE');
  await item.getByRole('checkbox', { name: /^REPORT/ }).check();
  await expect(save).toBeDisabled();
  await item.getByRole('checkbox', { name: /^SOURCE/ }).check();
  await expect(save).toBeEnabled();
  await item.getByLabel(`Lý do review ${REVIEW_ITEM}`, { exact: true }).fill('   ');
  await expect(save).toBeDisabled();
  expect(await page.evaluate(() => (window as unknown as Record<string, unknown>).reviewXss)).toBeUndefined();
  await expect(item.locator('script')).toHaveCount(0);
  const checklist = page.getByRole('article', { name: `Mục review ${CHECKLIST_ITEM}`, exact: true });
  const checklistSave = checklist.getByRole('button', { name: 'Lưu phiên bản review', exact: true });
  await checklist.getByLabel(`Nhãn review ${CHECKLIST_ITEM}`, { exact: true }).selectOption('UNMET');
  await checklist.getByLabel(`Lý do review ${CHECKLIST_ITEM}`, { exact: true }).fill('Reviewer inspected report despite no retrieved machine evidence.');
  await expect(checklistSave).toBeDisabled();
  await checklist.getByRole('checkbox', { name: /^REPORT/ }).check();
  await expect(checklistSave).toBeEnabled();
  await checklistSave.click();
  await expect(checklist.getByText('Review đã lưu · phiên bản 1 · UNMET', { exact: true })).toBeVisible();
  const writes = api.calls.filter((call) => call.method === 'POST' && call.path.endsWith('/item-annotations'));
  expect(writes).toHaveLength(1);
  expect(writes[0].body).toEqual({ item_id: CHECKLIST_ITEM, label: 'UNMET', evidence_span_ids: [REPORT_SPAN],
    rationale: 'Reviewer inspected report despite no retrieved machine evidence.' });
});
