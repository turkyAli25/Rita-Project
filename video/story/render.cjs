// Renders the storyboard page frame by frame (deterministic: window.seek(t)) to JPEGs.
// usage: node video/story/render.cjs        (reads video/story/timeline.json)
const fs = require('fs'), path = require('path');
const { chromium } = require('/Users/turkyzafir/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const EXE = '/Users/turkyzafir/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const tl = JSON.parse(fs.readFileSync(path.join(__dirname, 'timeline.json'), 'utf8'));
const FRAMES = path.join(__dirname, 'frames');
(async () => {
  fs.rmSync(FRAMES, { recursive: true, force: true }); fs.mkdirSync(FRAMES, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: EXE, args: ['--hide-scrollbars', '--mute-audio', '--font-render-hinting=none'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto('http://localhost:8735/video/story/story.html');
  await page.waitForFunction(() => window.storyReady === true, null, { timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);
  const t0 = Date.now();
  for (let i = 0; i < tl.frames; i++) {
    await page.evaluate(t => window.seek(t), i / tl.fps);
    await page.screenshot({ path: path.join(FRAMES, String(i).padStart(4, '0') + '.jpg'), type: 'jpeg', quality: 92, animations: 'disabled' });
    if (i % 150 === 0) console.log(`frame ${i}/${tl.frames}  (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
  }
  await browser.close();
  console.log(`rendered ${tl.frames} frames in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
})().catch(e => { console.error(e); process.exit(1); });
