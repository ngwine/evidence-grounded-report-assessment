/** Render the native SVG paper diagrams into matching high-resolution PNGs. */
import assert from 'node:assert/strict';
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from '../apps/web/node_modules/@playwright/test/index.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const figures = path.join(root, 'docs/paper/figures');
const review = path.join(root, 'var/paper/figure-render-review');
const names = ['framework_overview', 'pipeline1_experiment'];
await mkdir(review, { recursive: true });

const browser = await chromium.launch({ headless: true });
const results = [];
try {
  const page = await browser.newPage({
    viewport: { width: 1600, height: 900 },
    deviceScaleFactor: 2,
  });
  await page.route(/^https?:/, (route) => route.abort());
  for (const name of names) {
    const source = path.join(figures, `${name}.svg`);
    const text = await readFile(source, 'utf8');
    assert(!text.includes('markerUnits="strokeWidth"'), 'Arrowheads must have fixed geometry');
    await page.goto(pathToFileURL(source).href);
    await page.evaluate(() => document.fonts.ready);
    const geometry = await page.locator('svg').evaluate((svg) => {
      const frame = svg.getBoundingClientRect();
      const outsideText = [...svg.querySelectorAll('text')]
        .filter((text) => {
          const box = text.getBoundingClientRect();
          return box.left < frame.left || box.right > frame.right
            || box.top < frame.top || box.bottom > frame.bottom;
        })
        .map((text) => text.textContent);
      return {
        width: frame.width,
        height: frame.height,
        viewBox: svg.getAttribute('viewBox'),
        arrows: svg.querySelectorAll('.arrowhead').length,
        outsideText,
      };
    });
    assert.equal(geometry.width, 1600);
    assert.equal(geometry.height, 900);
    assert.equal(geometry.viewBox, '0 0 1600 900');
    assert.deepEqual(geometry.outsideText, [], 'All labels must fit the canvas');
    assert.equal(geometry.arrows, name === 'framework_overview' ? 5 : 7);
    const temporary = path.join(review, `${name}.png`);
    await page.locator('svg').screenshot({ path: temporary, animations: 'disabled' });
    results.push({ name, ...geometry, rasterWidth: 3200, rasterHeight: 1800 });
  }
  // Publish both raster assets only after both SVGs pass layout checks.
  for (const name of names) {
    await copyFile(path.join(review, `${name}.png`), path.join(figures, `${name}.png`));
  }
  await writeFile(path.join(review, 'render-checks.json'), `${JSON.stringify(results, null, 2)}\n`);
  process.stdout.write(`${JSON.stringify({ status: 'PASS', figures: results })}\n`);
} finally {
  await browser.close();
}
