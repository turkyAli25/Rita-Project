// Renders single storyboard frames at the given times (seconds) for a quick look, without a full render.
// usage: node video/story/qa.cjs 10.0 17.0 33.3   →  video/story/qa/qa-10.00.png …
const fs = require('fs'), path = require('path');
const { chromium } = require('/Users/turkyzafir/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const EXE = '/Users/turkyzafir/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const OUT = path.join(process.cwd(), 'video/story/qa');
(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const times = process.argv.slice(2).map(Number);
  const browser = await chromium.launch({ headless: true, executablePath: EXE, args: ['--hide-scrollbars'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto('http://localhost:8735/video/story/story.html');
  await page.waitForFunction(() => window.storyReady && [...document.images].every(i => i.complete));
  await page.evaluate(() => document.fonts.ready);
  for (const t of times) {
    await page.evaluate(t => window.seek(t), t);
    await page.waitForTimeout(80);
    const file = path.join(OUT, 'qa-' + t.toFixed(2) + '.png');
    await page.screenshot({ path: file });
    console.log(file);
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
