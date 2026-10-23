/** Real browser -> cookie-auth API -> scoped Mongo -> workers; synthetic only. */
import { test, expect } from '@playwright/test';

test('real Mongo: upload report/source → parse → BM25 index → BOTH results/export', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill('browser@example.invalid');
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Browser-Fixture-Only-Password');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await page.getByLabel('Workspace', { exact: true }).selectOption('000000000000000000000101');
  const phrase = 'Measured benchmark evidence retains exact source spans and reproducible version identifiers. ';
  for (const [kind, key, gov, text] of [
    ['REPORT', 'browser-report', '000000000000000000000201', phrase.repeat(8) + 'Report conclusion.'],
    ['CORPUS_SOURCE', 'browser-source', '000000000000000000000202', phrase.repeat(9) + 'Source conclusion.'],
  ]) {
    await page.getByLabel('Loại tài liệu', { exact: true }).selectOption(kind);
    await page.getByLabel('Mã tài liệu', { exact: true }).fill(key);
    await page.getByLabel('Tên tài liệu', { exact: true }).fill(key);
    await page.getByLabel('Governance record ID đã duyệt', { exact: true }).fill(gov);
    await page.getByLabel('File tài liệu', { exact: true }).setInputFiles({ name: key + '.txt', mimeType: 'text/plain', buffer: Buffer.from(text) });
    await page.getByRole('button', { name: 'Upload & tạo PARSE job', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Index ' + key, exact: true })).toBeEnabled({ timeout: 30_000 });
  }
  await page.getByRole('button', { name: 'Index browser-source', exact: true }).click();
  await expect(page.getByText('INDEX ACTIVE · bm25-smoke', { exact: false })).toBeVisible({ timeout: 30_000 });
  await page.getByLabel('Báo cáo để phân tích', { exact: true }).selectOption({ label: 'browser-report · browser-report' });
  await page.getByRole('checkbox', { name: /browser-source/ }).check();
  await page.getByLabel('Rubric cho assessment', { exact: true }).selectOption({ label: 'Browser fixture rubric · browser-rubric' });
  await page.getByLabel('Published rubric version', { exact: true }).selectOption({ index: 1 });
  await page.getByRole('button', { name: 'Tạo lượt chạy', exact: true }).click();
  await expect(page.getByText('ANALYZE SUCCEEDED', { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole('region', { name: 'Pipeline 1 kết quả' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Pipeline 2 kết quả' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Evidence đã lưu' })).toBeVisible();
  await page.getByLabel('Nhận xét review', { exact: true }).fill('Synthetic manual review checked evidence.');
  await page.getByRole('button', { name: 'Chấp nhận đề xuất', exact: true }).click();
  await expect(page.getByText('Giảng viên review · REVIEWED', { exact: true })).toBeVisible();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export JSON kết quả', exact: true }).click();
  expect((await downloaded).suggestedFilename()).toMatch(/^analysis-[0-9a-f]{24}\.json$/);
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
  const runId = await page.getByLabel('Mở lượt chạy theo ID').inputValue();
  await page.reload();
  await page.getByLabel('Workspace', { exact: true }).selectOption('000000000000000000000101');
  await page.getByLabel('Mở lượt chạy theo ID').fill(runId);
  await page.getByRole('button', { name: 'Mở lượt chạy', exact: true }).click();
  await expect(page.getByText('ANALYZE SUCCEEDED', { exact: true })).toBeVisible();
});
