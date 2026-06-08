/**
 * Auto-record a silent operation demo of Madori's four views (for the hackathon
 * demo video). Drives web/madori.html through the DEMO_SCRIPT operations and
 * records it via Playwright (system Chrome). Output: web/demo/madori-demo.mp4
 *
 *   node pipeline/record_demo.mjs
 *
 * NOTE: this is the silent operation footage — add voiceover/intro/outro in edit.
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
fs.mkdirSync(OUT, { recursive: true });

const ct = { '.html': 'text/html', '.png': 'image/png', '.js': 'text/javascript', '.json': 'application/json', '.jpg': 'image/jpeg' };
const server = http.createServer((req, res) => {
  let p = path.join(WEB, decodeURIComponent(req.url.split('?')[0]));
  if (p.endsWith('/')) p = path.join(p, 'madori.html');
  fs.readFile(p, (err, data) => {
    if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'content-type': ct[path.extname(p)] || 'text/plain' }); res.end(data);
  });
});
await new Promise(r => server.listen(8877, r));

const browser = await chromium.launch({ channel: 'chrome' });
const ctx = await browser.newContext({
  viewport: { width: 1920, height: 1200 },             // 原生 1920×1200 录制（比 1440 更清晰，且 size=viewport 不裁切）
  recordVideo: { dir: OUT, size: { width: 1920, height: 1200 } },
});
const page = await ctx.newPage();
const SLOW = 1.9;                                   // slower pacing → room for voiceover per shot
const wait = ms => page.waitForTimeout(Math.round(ms * SLOW));
const clickId = async id => page.evaluate(i => document.getElementById(i)?.click(), id);
// 平滑绕模型转 90°（直接绕 target 旋转相机位置，不依赖 setAzimuthalAngle —— three@0.128 OrbitControls 无此法）
const orbitQuarter = () => page.evaluate(() => new Promise(res => {
  const tgt = controls.target, off = camera.position.clone().sub(tgt);
  const r = Math.hypot(off.x, off.z), y = off.y, a0 = Math.atan2(off.z, off.x), dur = 1300, t0 = performance.now();
  (function s(){ const t = Math.min(1,(performance.now()-t0)/dur), a = a0 + t*Math.PI/2;
    camera.position.set(tgt.x + r*Math.cos(a), tgt.y + y, tgt.z + r*Math.sin(a)); controls.update(); t<1?requestAnimationFrame(s):res(); })();
}));
// 记下默认 3/4 视角；camTo 在 近俯视(plan，平面清晰可见) 与 默认3/4 之间平滑移动相机
const grabCam = () => page.evaluate(() => { window.__cam34 = camera.position.clone(); });
const camTo = (mode, dur) => page.evaluate((arg) => new Promise(res => {
  const tgt = controls.target.clone(), R = (window.__cam34.distanceTo(tgt)) || 14;
  const dest = arg.mode === 'plan'
    ? new THREE.Vector3(tgt.x + R*0.20, tgt.y + R*0.95, tgt.z + R*0.20)   // 近俯视：带轻微立体阴影，平面看得清
    : window.__cam34.clone();                                              // 默认 3/4
  if (arg.dur <= 1) { camera.position.copy(dest); controls.update(); return res(); }
  const p0 = camera.position.clone(), t0 = performance.now();
  (function s(){ const t = Math.min(1,(performance.now()-t0)/arg.dur), e = t<.5?2*t*t:1-Math.pow(-2*t+2,2)/2;
    camera.position.lerpVectors(p0, dest, e); controls.update(); t<1?requestAnimationFrame(s):res(); })();
}), { mode, dur });

console.log('▸ 录制中…');
await page.goto('http://localhost:8877/madori.html', { waitUntil: 'networkidle' });
await wait(500);   // 仅等 three.js 初始化，不留立体预卷

// ═══ 1. 魔法时刻：源户型图 → 升起 3D 白模 → 快速绕一圈（3D 只此一次，过场惊艳）═══
await clickId('tabRead'); await grabCam();
await page.evaluate(() => { const m = document.getElementById('morph'); m.value = 0; m.dispatchEvent(new Event('input')); });   // 先摊平（藏在源图放大之下）
// 源户型图放大：清楚这是「一张户型图」（crisp，解决白底隐形）
await page.evaluate(() => document.getElementById('planCard')?.click()); await wait(2800);
await page.evaluate(() => document.getElementById('lightbox')?.click()); await wait(600);
// 平面 → 立体：白模升起
await page.evaluate(() => new Promise(res => { const m = document.getElementById('morph'), t0 = performance.now(), dur = 2000;
  (function s(){ const t = Math.min(1,(performance.now()-t0)/dur); m.value = Math.round(t*100); m.dispatchEvent(new Event('input')); t<1?requestAnimationFrame(s):res(); })(); }));
await wait(1000);
// 快速绕一圈看四个面
for (let i = 0; i < 4; i++) { await orbitQuarter(); await wait(550); }
await camTo('default', 700);        // 复位默认 3/4 —— 关键：后续讲解段干净，不被开场相机污染
await wait(900);
await page.waitForTimeout(2000);    // +2s：绕完让 3D 模型多定格一会儿再切采光

// ═══ 2. 主角：采光转朝向实时重算（给足时长，全片最重）═══
await clickId('tabDay'); await wait(2400);
for (const d of ['up', 'right', 'down', 'left']) {   // 北/东/南/西 各停顿看清重算
  await page.evaluate(dir => document.querySelector(`.cbtn[data-dir="${dir}"]`)?.click(), d);
  await wait(2100);
}
await wait(1400);

// ═══ 3. 广度：五镜头解读 + 房间联动 + 面积（快扫，证明完整）═══
await clickId('tabRead'); await wait(1500);   // 3/4 立体白模 + 文字解读（干净，不再有怪托盘）
for (const k of ['动线', '采光', '无障碍', '走读', '批评']) {
  await page.evaluate(key => { const t = [...document.querySelectorAll('.lens')].find(e => e.dataset.k === key); t && t.scrollIntoView({ behavior: 'smooth', block: 'center' }); }, k);
  await wait(1800);
}
await page.evaluate(() => document.querySelector('.read .scroll')?.scrollTo({ top: 0, behavior: 'smooth' })); await wait(900);
for (const i of [0, 2, 4]) {
  await page.evaluate(n => { const c = [...document.querySelectorAll('.chip')]; c[n] && c[n].dispatchEvent(new MouseEvent('mouseenter')); }, i); await wait(850);
}
await page.evaluate(() => { const c = [...document.querySelectorAll('.chip')]; c[0] && c[0].dispatchEvent(new MouseEvent('mouseleave')); });
await page.fill('#areaIn', '66'); await wait(2000);

// ═══ 4. 动线 + 无障碍（干净俯视，快扫）═══
await clickId('tabCirc'); await wait(2200);
await clickId('tabA11y'); await wait(2200);

await ctx.close();                                  // flush video
await browser.close();
server.close();

// rename + transcode to mp4
const webm = fs.readdirSync(OUT).filter(f => f.endsWith('.webm')).map(f => path.join(OUT, f)).sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0];
const mp4 = path.join(OUT, 'demo-core.mp4');   // pure functional demo; record_cards.mjs wraps it with intro/outro → madori-demo.mp4
try {
  // -movflags +faststart: moov atom to the front, else web <video>/Finder-preview/streaming
  // show a BLANK screen until the whole file downloads. -profile:v main for max player compat.
  execSync(`ffmpeg -y -i "${webm}" -vf "scale=1920:1200:flags=lanczos" -c:v libx264 -profile:v high -pix_fmt yuv420p -crf 18 -movflags +faststart "${mp4}"`, { stdio: 'ignore' });
  console.log(`✓ ${path.relative(ROOT, mp4)}`);
} catch (e) {
  console.log(`✓ webm: ${path.relative(ROOT, webm)}（ffmpeg 转码失败，webm 可用）`);
}
