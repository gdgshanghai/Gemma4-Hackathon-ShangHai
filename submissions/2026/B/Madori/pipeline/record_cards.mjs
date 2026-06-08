/**
 * Record the intro/outro title cards (web/demo/{intro,outro}.html, CSS-timeline auto-play)
 * and concat them around the core demo into the final emotional-arc video.
 *
 *   intro card (~12.5s) → demo-core.mp4 (functional demo) → outro claim card (~9s)
 *
 * Output: web/demo/madori-demo.mp4 (faststart, h264 main, 1440×900 25fps).
 * demo-core.mp4 is the pure functional demo (re-create via record_demo.mjs).
 *
 *   node pipeline/record_cards.mjs
 */
import { chromium } from 'playwright';
import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WEB = path.join(ROOT, 'web');
const OUT = path.join(WEB, 'demo');

const ct = { '.html': 'text/html', '.png': 'image/png', '.js': 'text/javascript', '.json': 'application/json', '.jpg': 'image/jpeg', '.mp4': 'video/mp4' };
const server = http.createServer((req, res) => {
  const p = path.join(WEB, decodeURIComponent(req.url.split('?')[0]));
  fs.readFile(p, (e, d) => { if (e) { res.writeHead(404); res.end(); return; } res.writeHead(200, { 'content-type': ct[path.extname(p)] || 'text/plain' }); res.end(d); });
});
await new Promise(r => server.listen(8879, r));

async function rec(file, ms) {
  const browser = await chromium.launch({ channel: 'chrome' });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: OUT, size: { width: 1440, height: 900 } } });
  const page = await ctx.newPage();
  const vp = page.video();
  await page.goto(`http://localhost:8879/demo/${file}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(ms);                        // let the CSS timeline play out
  await ctx.close(); await browser.close();
  return await vp.path();
}

console.log('▸ 录 intro 卡…'); const introW = await rec('intro.html', 12800);
console.log('▸ 录 outro 卡…'); const outroW = await rec('outro.html', 9200);
server.close();

const core = path.join(OUT, 'demo-core.mp4');
const final = path.join(OUT, 'madori-demo.mp4');
console.log('▸ 拼接 intro + demo + outro…');
// re-encode all three to a common 1440×900/25fps/h264 then concat; faststart for web preview
execSync(`ffmpeg -y -i "${introW}" -i "${core}" -i "${outroW}" -filter_complex ` +
  `"[0:v]scale=1440:900,fps=25,setsar=1[a];[1:v]scale=1440:900,fps=25,setsar=1[b];[2:v]scale=1440:900,fps=25,setsar=1[c];[a][b][c]concat=n=3:v=1[out]" ` +
  `-map "[out]" -c:v libx264 -profile:v main -pix_fmt yuv420p -crf 22 -movflags +faststart "${final}"`, { stdio: 'ignore' });
fs.rmSync(introW, { force: true }); fs.rmSync(outroW, { force: true });
console.log('✓ ' + path.relative(ROOT, final));
