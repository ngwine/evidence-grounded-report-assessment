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
  await page.getByRole('button', { name: 'Tạo rubric', exact: true }).click();
  await page.getByLabel('Mã rubric', { exact: true }).fill('synthetic');
  await page.getByLabel('Tên rubric', { exact: true }).fill('Rubric thử nghiệm');
  await page.getByRole('button', { name: 'Cấu trúc mẫu', exact: true }).click();
  await page.getByRole('button', { name: 'Lưu draft', exact: true }).click();
  await expect(page.getByLabel('Các version đã lưu')).toHaveValue(VERSION);
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
