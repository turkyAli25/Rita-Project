// Captures real screens of the Arabic demo and landing page for the explainer storyboard.
// Run from the project root:  node video/story/shots.cjs
const fs = require('fs');
const path = require('path');
const { chromium } = require('/Users/turkyzafir/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const EXE = '/Users/turkyzafir/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const OUT = path.join(process.cwd(), 'video/story/shots');
const BASE = 'http://localhost:8735';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: EXE, args: ['--hide-scrollbars', '--mute-audio'] });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, locale: 'ar-SA' });
  if (process.env.PLAIN_DEMO) await ctx.route('**/demo-enhancements.*', r => r.abort());   // PLAIN_DEMO=1 captures the original single-page layout
  await ctx.addInitScript(() => {
    let seed = 7; Math.random = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
    localStorage.setItem('riati_lang', 'ar');
    localStorage.removeItem('riati_demo_orders_v5');
    window.setInterval = () => 0;  // the page must not advance on its own; we drive it
  });
  const shot = async (page, el, name, clipHeight) => {
    const box = await el.boundingBox();
    if (!box) { console.log(name, 'SKIPPED (element not visible in this layout)'); return; }
    const sc = await page.evaluate(() => ({ x: window.scrollX, y: window.scrollY }));   // boundingBox is viewport-relative; a fullPage clip is page-relative
    const clip = { x: box.x + sc.x, y: box.y + sc.y, width: box.width, height: clipHeight ? Math.min(box.height, clipHeight) : box.height };
    await page.screenshot({ path: path.join(OUT, name + '.png'), clip, fullPage: true, animations: 'disabled' });
    console.log(name, Math.round(clip.width) + 'x' + Math.round(clip.height));
  };

  // ---- the live demo, Arabic, driven to a state with a treated episode, a report and a journal conversation
  const page = await ctx.newPage();
  await page.goto(BASE + '/demo.html');
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: '*{animation:none!important;transition:none!important;caret-color:transparent!important} #journal,#log{scrollbar-width:none}' });
  await page.evaluate(() => {
    speakOn = false; S.running = false;
    el.repInt.value = '60'; el.repInt.onchange();
    while (S.minute < 75) { S.minute++; stepMinute(S.minute); }
    renderAll();
  });
  await page.waitForTimeout(300);
  const state = await page.evaluate(() => ({
    minute: S.minute,
    journal: S.journal.map(j => j.who + ': ' + (j.mk ? j.mk() : j.text).slice(0, 50)),
    events: S.events.filter(e => e.type !== 'report').map(e => e.type + ': ' + e.mkTitle().slice(0, 60)),
    reports: S.events.filter(e => e.type === 'report').length
  }));
  console.log(JSON.stringify(state, null, 1));

  // clinician shell (present when demo-enhancements.js is loaded)
  if (!process.env.PLAIN_DEMO) {
    await shot(page, page.locator('#cx-metrics'), 'cx-metrics');
    await shot(page, page.locator('#cx-events').locator('xpath=ancestor::section[1]'), 'cx-events', 900);
    await shot(page, page.locator('#cx-detail'), 'cx-detail');
    await shot(page, page.locator('#cx-chart').locator('xpath=ancestor::section[1]'), 'cx-chart');
    await shot(page, page.locator('.cx-heading'), 'cx-heading');
    await page.screenshot({ path: path.join(OUT, 'cx-full.png'), fullPage: true });
  }
  await shot(page, page.locator('#tiles'), 'tiles');
  await shot(page, page.locator('#kAI').locator('xpath=ancestor::div[contains(@class,"card")][1]'), 'ai');
  await shot(page, page.locator('#kOrders').locator('xpath=ancestor::div[contains(@class,"card")][1]'), 'orders', 720);
  await shot(page, page.locator('#kJournal').locator('xpath=ancestor::div[contains(@class,"card")][1]'), 'journal');
  await shot(page, page.locator('#chart').locator('xpath=ancestor::div[contains(@class,"card")][1]'), 'chart');
  await page.evaluate(() => { el.log.scrollTop = 0; });
  const report = page.locator('#log .e-report').first();
  if (await report.count()) { await report.scrollIntoViewIfNeeded(); await shot(page, report, 'report'); }
  const alert = page.locator('#log .e-alert').first();
  if (await alert.count()) { await alert.scrollIntoViewIfNeeded(); await shot(page, alert, 'alert'); }
  const therapy = page.locator('#log .e-therapy').first();
  if (await therapy.count()) { await therapy.scrollIntoViewIfNeeded(); await shot(page, therapy, 'therapy'); }
  await shot(page, page.locator('#zoneChip').locator('xpath=ancestor::div[contains(@class,"card")][1]'), 'patient');

  // ---- the landing page, Arabic
  const home = await ctx.newPage();
  await home.goto(BASE + '/Riati.dc.html');
  await home.waitForTimeout(2500);
  await home.evaluate(() => document.fonts.ready);
  await home.addStyleTag({ content: '*{animation:none!important;transition:none!important} [data-reveal]{opacity:1!important;transform:none!important}' });
  await home.waitForTimeout(500);
  await shot(home, home.locator('#top'), 'hero');
  await shot(home, home.locator('#serve'), 'serve');

  await browser.close();
  console.log('Shots complete');
})().catch(e => { console.error(e); process.exit(1); });
