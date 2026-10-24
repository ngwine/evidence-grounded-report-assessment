/** Real browser -> cookie-auth API -> scoped Mongo -> workers; synthetic only. */
import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test('real Mongo: upload report/source → parse → BM25 index → BOTH results/export', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill('browser@example.invalid');
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Browser-Fixture-Only-Password');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await page.getByLabel('Workspace', { exact: true }).selectOption('000000000000000000000101');
  const phrase = 'Measured benchmark evidence retains exact source spans and reproducible version identifiers. ';
  await page.getByRole('button', { name: 'Kho tài liệu', exact: true }).click();
  for (const [kind, key, gov, text] of [
    ['REPORT', 'browser-report', '000000000000000000000201', phrase.repeat(8) + 'Report conclusion.'],
    ['CORPUS_SOURCE', 'browser-source', '000000000000000000000202', phrase.repeat(9) + 'Source conclusion.'],
  ]) {
    await page.getByLabel('Loại tài liệu', { exact: true }).selectOption(kind);
    await page.getByLabel('Tên tài liệu', { exact: true }).fill(key);
    await page.getByLabel('Quyền sử dụng tài liệu', { exact: true }).selectOption(gov);
    await page.getByLabel('File tài liệu', { exact: true }).setInputFiles({ name: key + '.txt', mimeType: 'text/plain', buffer: Buffer.from(text) });
    await page.getByRole('button', { name: 'Tải lên và xử lý tài liệu', exact: true }).click();
    await expect(page.getByText(key, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByText('Sẵn sàng', { exact: true })).toHaveCount(2, { timeout: 30_000 });
  await page.getByRole('button', { name: 'Phân tích báo cáo', exact: true }).click();
  await page.getByLabel('Báo cáo để phân tích', { exact: true }).selectOption({ index: 1 });
  await page.getByRole('checkbox', { name: /browser-source/ }).check();
  await page.getByLabel('Rubric cho assessment', { exact: true }).selectOption({ label: 'Browser fixture rubric · browser-rubric' });
  await page.getByLabel('Published rubric version', { exact: true }).selectOption({ index: 1 });
  await page.getByRole('button', { name: 'Phân tích báo cáo', exact: true }).last().click();
  await expect(page.getByText('Phân tích hoàn tất', { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole('region', { name: 'Pipeline 1 kết quả' })).toBeVisible();
  await page.getByRole('tab', { name: 'Đánh giá rubric', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Pipeline 2 kết quả' })).toBeVisible();
  await page.getByRole('tab', { name: 'Bằng chứng đã lưu', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Evidence đã lưu' })).toBeVisible();
  await page.getByText('Review chi tiết từng cặp đoạn / checklist', { exact: false }).click();
  const itemReview = page.getByRole('region', { name: 'Review từng mục', exact: true });
  await expect(itemReview).toBeVisible();
  const pair = itemReview.getByRole('article').filter({ hasText: 'Pipeline 1 · Cặp báo cáo–nguồn' }).first();
  await pair.getByRole('combobox', { name: /^Nhãn review / }).selectOption('VERBATIM');
  await pair.getByRole('combobox', { name: /^Trích dẫn hoặc citation / }).selectOption('NO');
  await pair.getByRole('textbox', { name: /^Lý do review / }).fill('Synthetic reviewer checked exact raw evidence on both sides.');
  await expect(pair.getByRole('button', { name: 'Lưu phiên bản review', exact: true })).toBeDisabled();
  await pair.getByRole('checkbox', { name: /^REPORT/ }).first().check();
  await pair.getByRole('checkbox', { name: /^SOURCE/ }).first().check();
  await pair.getByRole('button', { name: 'Lưu phiên bản review', exact: true }).click();
  await expect(pair.getByText('Review đã lưu · phiên bản 1 · VERBATIM', { exact: true })).toBeVisible();
  const checklist = itemReview.getByRole('article').filter({ hasText: 'Pipeline 2 · C1.1' }).first();
  await checklist.getByRole('combobox', { name: /^Nhãn review / }).selectOption('MET');
  await checklist.getByRole('checkbox', { name: /^REPORT/ }).first().check();
  await checklist.getByRole('textbox', { name: /^Lý do review / }).fill('Synthetic checklist evidence inspected independently of its numeric score.');
  await checklist.getByRole('button', { name: 'Lưu phiên bản review', exact: true }).click();
  await expect(checklist.getByText('Review đã lưu · phiên bản 1 · MET', { exact: true })).toBeVisible();
  await itemReview.getByRole('button', { name: 'Xem lịch sử review', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Lịch sử review của bạn' }).getByRole('listitem')).toHaveCount(2);
  const reviewDownload = page.waitForEvent('download');
  await itemReview.getByRole('button', { name: 'Export JSON review', exact: true }).click();
  const reviewFile = await reviewDownload;
  expect(reviewFile.suggestedFilename()).toMatch(/^item-reviews-[0-9a-f]{24}\.json$/);
  const exportedReviews = JSON.parse(await readFile((await reviewFile.path())!, 'utf8'));
  expect(exportedReviews.annotations).toHaveLength(2);
  expect(exportedReviews.independent_gold).toBe(false);
  expect(exportedReviews.predictions_visible).toBe(true);
  expect(exportedReviews.official_grade).toBe(false);
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
  await page.getByText('Mở lượt phân tích bằng mã', { exact: true }).click();
  await page.getByLabel('Mở lượt chạy theo ID').fill(runId);
  await page.getByRole('button', { name: 'Mở lượt chạy', exact: true }).click();
  await expect(page.getByText('Phân tích hoàn tất', { exact: true })).toBeVisible();
  await page.getByText('Review chi tiết từng cặp đoạn / checklist', { exact: false }).click();
  await expect(page.getByText('Review đã lưu · phiên bản 1 · VERBATIM', { exact: true })).toBeVisible();
});
