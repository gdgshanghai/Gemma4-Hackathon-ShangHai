/**
 * Visual regression for Madori's four views × desktop/mobile.
 *
 * Screenshots: 解读 / 采光 / 动线 / 无障碍  ×  desktop(1440×900) / mobile(390×844) = 8 shots.
 * Uses system Chrome via puppeteer-core (no chromium download).
 *
 *   node pipeline/visual_regression.mjs --save   → save current as baseline
 *   node pipeline/visual_regression.mjs          → shoot + diff vs baseline, report changed views
 *
 * 3D canvas has minor render noise, so a per-view diff under THRESHOLD is treated as "same".
 */
import puppeteer from 'puppeteer-core';
import http from 'http';
import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WEB = path.join(ROOT, 'web');
const OUT = path.join(WEB, 'regression');
const SAVE = process.argv.includes('--save');
const dir = path.join(OUT, SAVE ? 'baseline' : 'current');
const baseDir = path.join(OUT, 'baseline');
const THRESHOLD = 0.012;            // >1.2% of pixels differ ⇒ flag as changed (tolerates 3D noise)

fs.mkdirSync(dir, { recursive: true });

const VIEWS = [
  { id: 'read', tab: 'tabRead', label: '解读' },
  { id: 'day',  tab: 'tabDay',  label: '采光' },
  { id: 'circ', tab: 'tabCirc', label: '动线' },
  { id: 'a11y', tab: 'tabA11y', label: '无障碍' },
];
const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile',  width: 390,  height: 844 },
];

const ct = { '.html': 'text/html', '.png': 'image/png', '.js': 'text/javascript', '.json': 'application/json', '.jpg': 'image/jpeg' };
const server = http.createServer((req, res) => {
  let p = path.join(WEB, decodeURIComponent(req.url.split('?')[0]));
  if (p.endsWith('/')) p = path.join(p, 'madori.html');
  fs.readFile(p, (err, data) => {
    if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'content-type': ct[path.extname(p)] || 'text/plain' });
    res.end(data);
  });
});
const sleep = ms => new Promise(r => setTimeout(r, ms));

await new Promise(r => server.listen(8866, r));
const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--force-color-profile=srgb'] });

const shots = [];
for (const vp of VIEWPORTS) {
  const page = await browser.newPage();
  await page.setViewport({ width: vp.width, height: vp.height, deviceScaleFactor: 1 });
  await page.goto('http://localhost:8866/madori.html', { waitUntil: 'networkidle0' });
  await sleep(1600);                                       // intro animation settle
  for (const v of VIEWS) {
    await page.evaluate(id => document.getElementById(id)?.click(), v.tab);
    await sleep(1100);                                     // view transition settle
    const name = `${vp.name}-${v.id}.png`;
    await page.screenshot({ path: path.join(dir, name) });
    shots.push({ name, vp: vp.name, label: v.label });
    process.stdout.write(`  ✓ ${vp.name}/${v.label}\n`);
  }
  await page.close();
}
await browser.close();
server.close();

if (SAVE) {
  console.log(`\n✓ 基线已保存 → web/regression/baseline/ (${shots.length} 张)`);
} else if (fs.existsSync(baseDir)) {
  console.log('\n— diff vs baseline —');
  let hasMagick = true;
  try { execSync('magick -version', { stdio: 'ignore' }); } catch { hasMagick = false; }
  if (!hasMagick) { console.log('  (magick 未装，跳过像素 diff；截图在 regression/current/ 可人工对比)'); }
  else {
    const changed = [];
    for (const s of shots) {
      const base = path.join(baseDir, s.name), cur = path.join(dir, s.name), df = path.join(OUT, 'diff-' + s.name);
      if (!fs.existsSync(base)) { console.log(`  + ${s.vp}/${s.label} 新增（无基线）`); continue; }
      let ae = 0, total = 1;
      try {
        const wh = execSync(`magick identify -format "%w %h" "${base}"`).toString().trim().split(/\s+/).map(Number);
        total = (wh[0] * wh[1]) || 1;
        execSync(`magick compare -metric AE "${base}" "${cur}" "${df}" 2>/tmp/ae.txt || true`);
        ae = parseInt(fs.readFileSync('/tmp/ae.txt', 'utf8').trim()) || 0;
      } catch {}
      const ratio = ae / total;
      const flag = ratio > THRESHOLD;
      console.log(`  ${flag ? '⚠ CHANGED' : '· same   '} ${s.vp}/${s.label}  (${(ratio*100).toFixed(2)}% px)`);
      if (flag) changed.push(s); else fs.rmSync(df, { force: true });
    }
    console.log(changed.length
      ? `\n⚠ ${changed.length} 个视图变化超阈值 → 看 web/regression/diff-*.png 确认是否回归`
      : `\n✓ 全部视图无明显变化（≤${THRESHOLD*100}% px）`);
  }
} else {
  console.log('\n首次运行：用 `node pipeline/visual_regression.mjs --save` 建立基线，之后改动跑无参数版对比。');
}
