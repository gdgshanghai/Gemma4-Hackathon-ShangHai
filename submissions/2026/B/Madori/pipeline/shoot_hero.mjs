/**
 * Shoot the four-view hero stills from web/madori.html (the precise 2LDK layout)
 * at 2× for README hero + landing. Output: web/assets/hero-{read,day,circ,a11y}.png
 *
 *   node pipeline/shoot_hero.mjs
 */
import { chromium } from 'playwright';
import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WEB = path.join(ROOT, 'web');
const OUT = path.join(WEB, 'assets');
fs.mkdirSync(OUT, { recursive: true });

const ct = { '.html': 'text/html', '.png': 'image/png', '.js': 'text/javascript', '.json': 'application/json', '.jpg': 'image/jpeg' };
const server = http.createServer((req, res) => {
  let p = path.join(WEB, decodeURIComponent(req.url.split('?')[0]));
  if (p.endsWith('/')) p = path.join(p, 'madori.html');
  fs.readFile(p, (e, d) => { if (e) { res.writeHead(404); res.end(); return; } res.writeHead(200, { 'content-type': ct[path.extname(p)] || 'text/plain' }); res.end(d); });
});
await new Promise(r => server.listen(8878, r));

const browser = await chromium.launch({ channel: 'chrome' });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
await page.goto('http://localhost:8878/madori.html', { waitUntil: 'networkidle' });
await page.waitForTimeout(2600);                     // intro camera ease-in

const shots = [['read', 'tabRead'], ['day', 'tabDay'], ['circ', 'tabCirc'], ['a11y', 'tabA11y']];
for (const [name, tab] of shots) {
  await page.evaluate(id => document.getElementById(id).click(), tab);
  await page.waitForTimeout(1700);                   // view tween settle
  await page.screenshot({ path: path.join(OUT, `hero-${name}.png`) });
  console.log('✓ hero-' + name + '.png');
}
await browser.close();
server.close();
console.log('done → web/assets/');
