/** Real browser -> cookie-auth API -> scoped Mongo -> workers; synthetic only. */
import { test, expect } from '@playwright/test';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';

test('real Mongo: declare/upload new files + author rubric → workers → BOTH evidence/review/export', async ({ page }) => {
  const uploadNotice = page.getByText('Khi tải lên, bạn xác nhận có quyền dùng file, đã rà thông tin cá nhân và chỉ sử dụng nội bộ.', { exact: true });
  const declarations: Array<{ status: number; content_sha256: string; filename: string;
    attested_authority: boolean; pii_reviewed: boolean; internal_use_only: boolean }> = [];
  page.on('response', (response) => {
    if (response.request().method() === 'POST' && response.url().endsWith('/upload-declarations')) {
      const body = response.request().postDataJSON();
      declarations.push({ status: response.status(), content_sha256: body.content_sha256, filename: body.filename,
        attested_authority: body.attested_authority, pii_reviewed: body.pii_reviewed, internal_use_only: body.internal_use_only });
    }
  });
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill('browser@example.invalid');
  await page.getByLabel('Mật khẩu', { exact: true }).fill('Browser-Fixture-Only-Password');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await page.getByLabel('Workspace', { exact: true }).selectOption('000000000000000000000101');
  const phrase = 'Measured benchmark evidence retains exact source spans and reproducible version identifiers. ';
  await page.getByRole('button', { name: 'Kho tài liệu', exact: true }).click();
  const expectedDeclarations = [];
  let firstReportVersionId = '';
  for (const [kind, key, text] of [
    ['REPORT', 'browser-report', phrase.repeat(8) + 'Report conclusion.'],
    ['CORPUS_SOURCE', 'browser-source', phrase.repeat(9) + 'Source conclusion.'],
  ]) {
    await page.getByLabel('Loại tài liệu', { exact: true }).selectOption(kind);
    await page.getByLabel('Tên tài liệu', { exact: true }).fill(key);
    await page.getByLabel('File tài liệu', { exact: true }).setInputFiles({ name: key + '.txt', mimeType: 'text/plain', buffer: Buffer.from(text) });
    // No governance records are seeded. These new, self-authored test files
    // use the upload action and its visible notice to record consent.
    await expect(uploadNotice).toBeVisible();
    await expect(page.getByRole('button', { name: 'Tải lên và xử lý tài liệu', exact: true })).toBeEnabled();
    const uploaded = page.waitForResponse((response) => response.request().method() === 'POST'
      && new URL(response.url()).pathname.endsWith(kind === 'REPORT' ? '/reports' : '/sources'));
    await page.getByRole('button', { name: 'Tải lên và xử lý tài liệu', exact: true }).click();
    const uploadResponse = await uploaded;
    expect(uploadResponse.status()).toBe(202);
    const uploadOperation = await uploadResponse.json();
    if (kind === 'REPORT') firstReportVersionId = uploadOperation.document_version_id;
    await expect(page.getByText(key, { exact: true }).first()).toBeVisible();
    expectedDeclarations.push({ status: 201, filename: key + '.txt', content_sha256: createHash('sha256').update(text).digest('hex'),
      attested_authority: true, pii_reviewed: true, internal_use_only: true });
  }
  await expect(page.getByText('Sẵn sàng', { exact: true })).toHaveCount(2, { timeout: 30_000 });

  // A second declaration for the same document must allocate a new governance
  // record_version under the real Mongo unique index, not overwrite/reuse v1.
  await page.getByLabel('Loại tài liệu', { exact: true }).selectOption('REPORT');
  const secondReportText = phrase.repeat(8) + 'Second version conclusion with a new immutable checksum.';
  await page.getByLabel('File tài liệu', { exact: true }).setInputFiles({
    name: 'browser-report-v2.txt', mimeType: 'text/plain', buffer: Buffer.from(secondReportText),
  });
  await page.getByLabel('Tạo mới hay thêm version', { exact: true }).selectOption({ index: 1 });
  await expect(uploadNotice).toBeVisible();
  await expect(page.getByRole('button', { name: 'Tải lên và xử lý tài liệu', exact: true })).toBeEnabled();
  const versionUploaded = page.waitForResponse((response) => response.request().method() === 'POST'
    && /\/reports\/[0-9a-f]{24}\/versions$/.test(new URL(response.url()).pathname));
  await page.getByRole('button', { name: 'Tải lên và xử lý tài liệu', exact: true }).click();
  const secondUploadResponse = await versionUploaded;
  expect(secondUploadResponse.status()).toBe(202);
  const secondUpload = await secondUploadResponse.json();
  const secondReportVersionId = secondUpload.document_version_id;
  expect(secondReportVersionId).toMatch(/^[0-9a-f]{24}$/);
  expect(secondReportVersionId).not.toBe(firstReportVersionId);
  expectedDeclarations.push({ status: 201, filename: 'browser-report-v2.txt', content_sha256: createHash('sha256').update(secondReportText).digest('hex'),
    attested_authority: true, pii_reviewed: true, internal_use_only: true });
  expect(declarations).toEqual(expectedDeclarations);
  const reportCard = page.locator('.auth-document-list > li').filter({ has: page.getByText('browser-report', { exact: true }) });
  await expect(reportCard).toContainText('Phiên bản 2');
  await expect(reportCard.getByText('Sẵn sàng', { exact: true })).toBeVisible({ timeout: 30_000 });

  // Author and publish a brand-new rubric without JSON or an API shortcut.
  await page.getByRole('button', { name: 'Rubric đánh giá', exact: true }).click();
  await page.getByRole('button', { name: 'Tạo rubric', exact: true }).click();
  await expect(page.getByLabel('Rubric definition JSON', { exact: true })).toBeHidden();
  await page.getByLabel('Mã rubric', { exact: true }).fill('browser-authored-rubric');
  await page.getByLabel('Tên rubric', { exact: true }).fill('Rubric nhập trực tiếp trên web');
  await page.getByLabel('Tên tiêu chí', { exact: true }).fill('Kết quả benchmark');
  await page.getByLabel('Phát biểu cần kiểm chứng', { exact: true }).fill('Presents measured benchmark evidence');
  await page.getByLabel('Cách diễn đạt 1 của yêu cầu 1.1.1', { exact: true }).fill('measured benchmark');
  await page.getByRole('button', { name: 'Lưu draft', exact: true }).click();
  await expect(page.getByLabel('Các version đã lưu', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Kiểm tra & publish', exact: true }).click();
  await expect(page.getByText('Published · bất biến', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Phân tích báo cáo', exact: true }).click();
  await page.getByLabel('Báo cáo để phân tích', { exact: true }).selectOption({ index: 1 });
  await expect(page.locator('.selection-caption').first()).toContainText('Phiên bản 2');
  await page.getByRole('checkbox', { name: /browser-source/ }).check();
  await page.getByLabel('Rubric cho assessment', { exact: true }).selectOption({ label: 'Rubric nhập trực tiếp trên web · browser-authored-rubric' });
  await page.getByLabel('Published rubric version', { exact: true }).selectOption({ index: 1 });
  await page.getByLabel('Pipeline cần chạy', { exact: true }).selectOption('BOTH');
  await page.getByRole('button', { name: 'Phân tích báo cáo', exact: true }).last().click();
  await expect(page.getByText('Phân tích hoàn tất', { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole('region', { name: 'Pipeline 1 kết quả' })).toBeVisible();
  const similarity = page.getByRole('region', { name: 'Pipeline 1 kết quả' });
  await expect(similarity.getByRole('article').first()).toContainText('Khớp nguyên văn');
  await expect(similarity.getByRole('article').first().locator('blockquote').first()).toContainText('Measured benchmark');
  await page.getByRole('tab', { name: 'Đánh giá rubric', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Pipeline 2 kết quả' })).toBeVisible();
  const assessment = page.getByRole('region', { name: 'Pipeline 2 kết quả' });
  await expect(assessment.getByRole('article').first()).toContainText('Presents measured benchmark evidence');
  await expect(assessment.getByRole('article').first().getByText('Đạt', { exact: true })).toBeVisible();
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
  const resultFile = await downloaded;
  expect(resultFile.suggestedFilename()).toMatch(/^analysis-[0-9a-f]{24}\.json$/);
  const exportedResults = JSON.parse(await readFile((await resultFile.path())!, 'utf8'));
  expect(exportedResults.run.run_type).toBe('BOTH');
  expect(exportedResults.run.report_version_id).toBe(secondReportVersionId);
  expect(exportedResults.run.report_version_id).not.toBe(firstReportVersionId);
  expect(exportedResults.results.similarity.exact_match_coverage_percentage).toBeGreaterThan(0);
  expect(exportedResults.results.similarity.matches.some((match: { classification_status: string }) => match.classification_status === 'EVIDENCE_BACKED_EXACT_MATCH')).toBe(true);
  expect(exportedResults.results.assessment.checklist_outcome_counts.MET).toBe(1);
  expect(exportedResults.results.assessment.checklist_results[0].evidence_pack.length).toBeGreaterThan(0);
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
