import { expect, test } from '@playwright/test';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const fixtures = resolve(repoRoot, 'research/tests/fixtures/core_mvp');
const report = resolve(fixtures, 'report.txt');
const source = resolve(fixtures, 'source-overlap.txt');
const unapprovedSource = resolve(fixtures, 'source-unrelated.txt');
const rubric = resolve(fixtures, 'rubric.json');

test('empty state, source approval gate, two evidence views, review and revision conflict', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Chưa có lượt chạy' })).toBeVisible();
  await expect(page.getByRole('note')).toContainText('không phải kết luận đạo văn');

  await page.locator('#report-file').setInputFiles(report);
  await page.locator('#source-files').setInputFiles(unapprovedSource);
  await page.locator('#rubric-file').setInputFiles(rubric);
  await page.getByRole('button', { name: /Chạy hai pipeline/ }).click();
  await expect(page.getByRole('alert')).toContainText('lacks private-local rights approval');
  await expect(page.getByRole('heading', { name: 'Chưa có lượt chạy' })).toBeVisible();

  await page.locator('#source-files').setInputFiles(source);
  const queuedResponse = page.waitForResponse(response =>
    response.url().endsWith('/api/local/v1/runs') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: /Chạy hai pipeline/ }).click();
  expect((await queuedResponse).status()).toBe(202);
  await expect(page.getByRole('tab', { name: /Tương đồng/ })).toBeVisible();
  await expect(page.getByRole('tab', { name: /Rubric & evidence/ })).toBeVisible();

  const match = page.locator('.evidence-card').first();
  await expect(match).toBeVisible();
  await expect(match.locator('.evidence-grid > div')).toHaveCount(2);
  await expect(match).toContainText('Đoạn văn này được giữ nguyên');
  await expect(page.getByText('Coverage token trong báo cáo; không phải tỷ lệ đạo văn')).toBeVisible();

  await page.getByRole('tab', { name: /Rubric & evidence/ }).click();
  await expect(page.getByRole('heading', { name: 'Rubric checklist' })).toBeVisible();
  await expect(page.locator('.checklist-card')).toHaveCount(3);
  await expect(page.getByText('Đây là bản đề xuất, không phải điểm chính thức.')).toBeVisible();

  await page.locator('#reviewer-name').fill('Synthetic reviewer');
  await page.locator('#review-comment').fill('Evidence in both pipeline views was inspected.');
  await page.getByRole('button', { name: 'Lưu phản hồi local' }).click();
  await expect(page.getByText('Review đã lưu: DEFER')).toBeVisible();
  await expect(page.locator('.previous-review')).toContainText('revision 1');

  const runId = await page.evaluate(() => localStorage.getItem('kltn-local-last-run-id'));
  expect(runId).toMatch(/^[0-9a-f]{32}$/);
  const externalReview = await page.request.post(
    `http://127.0.0.1:8001/api/local/v1/runs/${runId}/review`,
    {
      headers: { 'X-KLTN-Local-UI': '1' },
      data: {
        decision: 'DEFER',
        comment: 'Second local review to trigger a revision conflict.',
        expected_revision: 1,
        reviewer_name: 'Synthetic second reviewer',
      },
    },
  );
  expect(externalReview.status()).toBe(200);
  await page.locator('#review-comment').fill('Attempt from stale page revision.');
  await page.getByRole('button', { name: 'Lưu phản hồi local' }).click();
  await expect(page.getByRole('alert')).toContainText('Lượt chạy đã được cập nhật ở nơi khác');
});
