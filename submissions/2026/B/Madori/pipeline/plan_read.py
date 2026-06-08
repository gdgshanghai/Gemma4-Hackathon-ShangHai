#!/usr/bin/env python3
"""Madori — read a floor plan with local Gemma 4, across expert lenses.

Pipeline: extract structure (once) -> lock as context -> run each lens with that
locked context (consistent room names) -> render a plain-language reading report
+ a flat->3D white study model. All local (Ollama + gemma4:e4b vision).

Usage:  python pipeline/plan_read.py [path/to/plan.png]
"""
import json, base64, urllib.request, re, html, sys, os, webbrowser

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # project root
ARGS = sys.argv[1:]
def _argf(flag):                       # parse --flag N or --flag=N
    for i, a in enumerate(ARGS):
        if a == flag and i+1 < len(ARGS): return float(ARGS[i+1])
        if a.startswith(flag+"="): return float(a.split("=", 1)[1])
    return None
_imgarg = next((a for a in ARGS if not a.startswith("--")), None)
IMG  = os.path.abspath(_imgarg) if _imgarg else os.path.join(HERE, "samples", "floorplan.png")
B64  = base64.b64encode(open(IMG, "rb").read()).decode()
CAL_W, CAL_H, CAL_AREA = _argf("--width"), _argf("--depth"), _argf("--area")  # known-size calibration
MODEL = "gemma4:e4b"

def chat(system, user, n=700):
    body = {"model": MODEL,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user, "images": [B64]}],
            "stream": False, "think": False, "keep_alive": "10m",
            "options": {"temperature": 0.25, "num_predict": n}}
    req = urllib.request.Request("http://localhost:11434/api/chat",
        data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=180).read()).get("message", {}).get("content", "").strip()

# ---------------- 1. extract structure (robust: mm->m, retry, sanity, snap) --------------
def parse_struct():
    raw = chat("你是建筑平面图判读AI。只依据图中可见的墙线、房间文字、尺寸数字推理，读不到的不编。",
        "先在心里做两步(不要输出思考)：①外框总尺寸——把图中横向排成一行的几段尺寸数字相加得总宽、纵向几段相加得总进深(单位mm，如2750+2400+2850=8000)；若图上写了总尺寸或外墙总长直接用。②每个房间在外框内的网格位置，房间互不重叠、合起来基本铺满整个户型。\n"
        "只输出这些行(不要任何解释或思考)：\n"
        "DIMS|总宽|总进深  (米；8000mm 写 8)\n"
        "ROOM|名|x|y|宽|高  (米；左上角原点，x向右增、y向下增；各房间不可重叠)", n=520)
    W = H = None; rooms = []
    def m(v):
        f = re.findall(r'[\d.]+', v)
        if not f: return None
        x = float(f[0]); return x/1000.0 if x > 50 else x          # mm -> m
    def dim(v):                                                     # outer dimension: sum a "+"-joined chain
        v = v.split("(")[0]                                        # drop "(或 N)" alternative totals
        nums = [float(x) for x in re.findall(r'[\d.]+', v)]
        if not nums: return None
        s = sum(nums) if len(nums) > 1 else nums[0]                # 1299+2914+3448 -> 7661 (not just 1299)
        return s/1000.0 if s > 50 else s                          # mm -> m
    for ln in raw.splitlines():
        p = [x.strip(" <>") for x in ln.split("|")]
        if p[0].upper().endswith("DIMS") and len(p) >= 3:
            W = dim(p[1]); H = dim(p[2])
        elif p[0].upper().endswith("ROOM") and len(p) >= 6:
            vals = [m(v) for v in p[2:6]]
            if all(v is not None for v in vals): rooms.append({"name": p[1], "rect": vals})
    return raw, (W or 9.0), (H or 7.0), rooms

def _overlap(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    ix = max(0, min(ax+aw, bx+bw) - max(ax, bx))
    iy = max(0, min(ay+ah, by+bh) - max(ay, by))
    return ix*iy

def sane(W, H, rooms):
    if not (2 <= len(rooms) <= 10): return False
    if W < 3 or H < 3: return False                      # whole-flat box can't be tiny
    A = W*H
    for r in rooms:
        x, y, w, h = r["rect"]
        if w <= 0 or h <= 0 or x < -0.5 or y < -0.5 or x+w > W+0.6 or y+h > H+0.6: return False
        if w*h > 0.85*A and len(rooms) > 1: return False
    tov = sum(_overlap(rooms[i]["rect"], rooms[j]["rect"])     # tolerate minor overlap, reject pile-ups
              for i in range(len(rooms)) for j in range(i+1, len(rooms)))
    if tov > 0.30*A: return False
    return True

print(f"▸ reading {os.path.basename(IMG)} with {MODEL} …")
extract = ""; W = H = 9.0; rooms = []
for _ in range(3):
    extract, W, H, rooms = parse_struct()
    if sane(W, H, rooms): break
for r in rooms:
    x, y, w, h = [round(v*2)/2 for v in r["rect"]]
    if abs(x) < 0.6: x = 0.0
    if abs(y) < 0.6: y = 0.0
    if x+w > W-0.4: w = W-x
    if y+h > H-0.4: h = H-y
    r["rect"] = [x, y, w, h]

# de-dup: a real floor plan rarely repeats a room name; a duplicate name = Gemma read it twice
_uniq = []
for r in rooms:
    if any(u["name"] == r["name"] for u in _uniq): continue
    _uniq.append(r)
rooms = _uniq

# optional scale calibration: pin absolute size to a user-known dimension (real width/depth
# or floor area). Keeps Gemma's relative layout, fixes only the absolute scale.
CALIB = None
if CAL_W and CAL_H:
    sx, sy = CAL_W/max(W, 1e-6), CAL_H/max(H, 1e-6)
    for r in rooms:
        x, y, w, h = r["rect"]; r["rect"] = [x*sx, y*sy, w*sx, h*sy]
    W, H, CALIB = CAL_W, CAL_H, f"宽×深 {CAL_W}×{CAL_H}m"
elif CAL_W or CAL_AREA:
    s = (CAL_W/max(W, 1e-6)) if CAL_W else (CAL_AREA/max(W*H, 1e-6))**0.5
    for r in rooms:
        r["rect"] = [v*s for v in r["rect"]]
    W, H = W*s, H*s
    CALIB = f"总宽 {CAL_W}m" if CAL_W else f"面积 {CAL_AREA}㎡"
if W < 3 or H < 3:                      # degenerate parse (whole flat can't be <3m) → neutral box, never a sliver
    W, H = 9.0, 7.0
W, H = round(W, 2), round(H, 2)
if CALIB: print(f"✓ 已按已知尺寸标定：{CALIB}  →  外框 {W}×{H}m")

# geometry confidence: was the parse trustworthy enough to draw a precise massing?
# (room coords from messy photos are the weakest link — degrade honestly when unsure)
A = max(W*H, 1)
cover = sum(max(r["rect"][2], 0)*max(r["rect"][3], 0) for r in rooms) / A
tov = sum(_overlap(rooms[i]["rect"], rooms[j]["rect"])
          for i in range(len(rooms)) for j in range(i+1, len(rooms)))
hi = (2 <= len(rooms) <= 10 and 0.5 <= cover <= 1.2 and tov < 0.25*A and W >= 3 and H >= 3)
GEOM = {"coverage": round(cover, 2), "level": "high" if hi else "low", "calibrated": CALIB}
print(f"GEOM: {GEOM['level']} (铺满率 {GEOM['coverage']})")

def where(r):
    x, y, w, h = r["rect"]; cx, cy = x+w/2, y+h/2
    v = "上" if cy < H*0.45 else ("下" if cy > H*0.55 else "中")
    hh = "左" if cx < W*0.4 else ("右" if cx > W*0.6 else "中")
    return (v+hh).replace("中中", "中央")

# ---------------- 2. lock context, run lenses --------------
ctx = (f"这是一套 {W}×{H}米的住宅平面图。已确认的房间(只能用这些名字,不许改叫别的):"
       + "；".join(f"{r['name']}(位于{where(r)})" for r in rooms) + "。玄关入口在图底部。")
base = "你是资深建筑师，面向完全不懂图纸的普通人，用大白话。只依据图+下面已确认信息推理,看不出说看不出,不编。\n" + ctx

def lens(prompt):
    out = chat(base, prompt + "\n输出:第一行一句话标题(≤14字),然后2-3句分析,不要列表符号。", n=520)
    lines = [l for l in out.splitlines() if l.strip()]
    title = re.sub(r'^[#*\-\d.、)\s]+', '', lines[0]).strip() if lines else ""
    body  = " ".join(lines[1:]).strip() or out
    return {"title": title[:24], "body": body}

LENS = {
 "动线":   lens("分析动线:从玄关进来怎么到各房间,有无穿越/瓶颈?"),
 "采光":   lens("分析采光:各房间靠哪面窗,谁好谁差?图未标朝向=朝向未知必须说明。"),
 "无障碍": lens("无障碍:门宽/台阶/高差/浴室厕所可达性,对老人或轮椅友好吗?图上看不出的尺寸(如门宽)要说看不出,别编。"),
 "走读":   lens("用大白话带不懂图的人走一遍:从玄关进门先到哪再到哪,像带朋友看房。"),
 "批评":   lens("作为建筑师:1个强点+1个弱点(各给图中证据)+1条具体改进。"),
}
print("STRUCT:", extract.replace("\n", " | "))
for k, v in LENS.items(): print(f"[{k}] {v['title']} — {v['body'][:60]}")

# ---------------- 2.5 windows: which OUTER side of each room has a window (qualitative) ----
# upgrades daylight from "touches which exterior wall" -> "which wall actually has a window"
def parse_windows():
    out = chat(base, "图上窗户=外墙上的双线/开口/落地窗(阳台门)。对每个已确认房间,报它在户型最外缘的哪几面墙有窗:上/下/左/右(图的方向)。内墙之间不算;没有外窗报'无'。\n只输出行,每房间一行:WIN|房间名|方向(上/下/左/右,逗号分隔;或 无)", n=420)
    DM = {'上':'up','下':'down','左':'left','右':'right'}; res = {}
    for ln in out.splitlines():
        p = [x.strip(" <>") for x in ln.split("|")]
        if p[0].upper().endswith("WIN") and len(p) >= 3:
            res[p[1]] = [DM[c] for c in p[2] if c in DM]
    return res
WIN = parse_windows()
for r in rooms: r["win"] = WIN.get(r["name"], [])
print("WIN:", {r["name"]: r["win"] for r in rooms})

# ---------------- 3. derive walls from room rects (for the 3D massing) --------------
def edges(x, y, w, h): return [(x,y,x+w,y),(x+w,y,x+w,y+h),(x+w,y+h,x,y+h),(x,y+h,x,y)]
def kk(s): a,b,c,d = s; return (round(min(a,c),2),round(min(b,d),2),round(max(a,c),2),round(max(b,d),2))
OPEN = ("DK", "LDK", "居間", "客厅", "餐厅", "リビング", "ダイニング", "客餐厅", "起居", "居间")
def is_open(name): return any(o in name for o in OPEN) or "LDK" in str(name).upper()
def on_frame(s):                                          # edge lies on the outer boundary?
    a, b, c, d = s
    return ((abs(a) < 0.3 and abs(c) < 0.3) or (abs(a-W) < 0.3 and abs(c-W) < 0.3) or
            (abs(b) < 0.3 and abs(d) < 0.3) or (abs(b-H) < 0.3 and abs(d-H) < 0.3))
seen = set(); walls = []
for s in edges(0, 0, W, H):
    if kk(s) not in seen: seen.add(kk(s)); walls.append(list(s))
for r in rooms:
    op = is_open(r["name"])
    for s in edges(*r["rect"]):
        k = kk(s)
        if k in seen: continue
        if op and not on_frame(s): continue              # open-plan room: no interior partition walls
        seen.add(k); walls.append(list(s))
bld = {"dims": [W, H], "walls": walls, "rooms": rooms}

# ---------------- 4. render outputs --------------
def esc(s): return html.escape(s or "")
imgb = base64.b64encode(open(IMG, "rb").read()).decode()
LC = {"动线":"#b34a26","采光":"#a8842f","无障碍":"#3a6b6e","走读":"#7a5a8a","批评":"#6f7d4a"}
LEN_EN = {"动线":"circulation","采光":"daylight","无障碍":"accessibility","走读":"walkthrough","批评":"critique"}
lensHtml = "".join(
    f'<div class="lens"><div class="lab" style="color:{LC.get(k,"#b34a26")}">{esc(k)} · {LEN_EN.get(k,"")} '
    f'<span class="ti">{esc(v["title"])}</span></div><p>{esc(v["body"])}</p></div>'
    for k, v in LENS.items())
rooms_txt = " / ".join(esc(r["name"]) for r in rooms)

READING = f"""<!doctype html><html lang=zh><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>户型解读 · Madori</title>
<style>
:root{{--paper:#f3efe6;--ink:#1c1814;--soft:#6b6052;--hair:#cabfa8;--accent:#b34a26;
--serif:"Songti SC",Georgia,serif;--mono:"SFMono-Regular",ui-monospace,Menlo,monospace}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:var(--serif);line-height:1.7}}
.wrap{{max-width:1080px;margin:0 auto;padding:38px 26px 80px}}
header{{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--hair);padding-bottom:13px;margin-bottom:26px}}
.mark b{{font-weight:600;font-size:1.2rem}}.mark .en{{font-family:var(--mono);font-size:.6rem;letter-spacing:.22em;text-transform:uppercase;color:var(--soft);margin-left:10px}}
.pipe{{font-family:var(--mono);font-size:.6rem;letter-spacing:.1em;color:var(--soft);text-transform:uppercase}}.pipe b{{color:var(--accent)}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:34px;align-items:start}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}
.plate{{border:1px solid var(--hair);background:#fff}}.plate img{{width:100%;display:block}}
.cap{{font-family:var(--mono);font-size:.58rem;letter-spacing:.08em;color:var(--soft);text-transform:uppercase;margin-top:8px}}
.kdr{{font-family:var(--mono);font-size:.62rem;letter-spacing:.2em;text-transform:uppercase;color:var(--soft);margin:0 0 6px}}
h1{{font-size:1.5rem;font-weight:600;margin:0 0 14px}}
.dims{{font-family:var(--mono);font-size:.7rem;color:var(--soft);margin-bottom:16px}}.dims b{{color:var(--accent)}}
.lens{{border-top:1px solid var(--hair);padding:12px 0}}
.lens .lab{{font-family:var(--mono);font-size:.64rem;letter-spacing:.1em;margin-bottom:5px;text-transform:uppercase}}
.lens .ti{{color:var(--ink);text-transform:none;font-family:var(--serif);font-size:.9rem;margin-left:6px}}
.lens p{{margin:0;font-size:.94rem;color:#2a241d}}
.note{{font-family:var(--mono);font-size:.6rem;line-height:1.7;color:var(--soft);border-top:1px dashed var(--hair);margin-top:22px;padding-top:11px}}
footer{{font-family:var(--mono);font-size:.62rem;letter-spacing:.1em;color:var(--soft);text-align:center;margin-top:40px;text-transform:uppercase}}
</style></head><body><div class=wrap>
<header><div class=mark><b>户型解读</b><span class=en>Madori · Gemma reads the plan</span></div>
<div class=pipe>extract → <b>lock</b> → 5 lenses</div></header>
<div class=grid>
 <div><div class=plate><img src="data:image/png;base64,{imgb}"></div>
   <div class=cap>{esc(os.path.basename(IMG))} · 全本地 Gemma 4 读图</div></div>
 <div>
  <div class=kdr>reading · 多维度解读</div>
  <h1>一张图，几位专家的眼睛</h1>
  <div class=dims>结构 · <b>{W}×{H}m</b> · {rooms_txt}{(" · <b style=color:#3a6b6e>✓ 已按"+esc(CALIB)+"标定</b>") if CALIB else ""}</div>
  {lensHtml}
  <div class=note>⚠ 全本地 Gemma 4 · 先读结构锁进上下文,各维度共用同一套房间名(防漂移) · 图上没标的(如朝向/门宽)AI 会说"未知"不编 · 设计通识级,非结构/无障碍合规认证,涉及法律安全请咨询专业人士。</div>
 </div>
</div>
<footer>Madori · all-local Gemma 4 · multimodal · 赛道 B · 让人人读懂自己的家</footer>
</div></body></html>"""

WEB = os.path.join(HERE, "web")
tpl = open(os.path.join(WEB, "massing.template.html")).read().replace("__BUILDING_JSON__", json.dumps(bld, ensure_ascii=False))
open(os.path.join(WEB, "index.html"), "w").write(tpl)
rp = os.path.join(HERE, "reading.html"); open(rp, "w").write(READING)
json.dump({**bld, "lenses": LENS, "img": IMG, "geom": GEOM}, open(os.path.join(HERE, "last_reading.json"), "w"), ensure_ascii=False, indent=2)

# combined viewer: 3D stage + reading panel + source floor plan, two-way linked
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("combine", os.path.join(os.path.dirname(__file__), "combine.py"))
_cmb = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_cmb)
madori = _cmb.render({**bld, "lenses": LENS, "geom": GEOM}, img_path=IMG, open_browser=False)

print(f"\n✓ wrote reading.html + web/index.html + web/madori.html (合并联动页)")
try:
    webbrowser.open("file://" + madori)   # the combined page is now the main deliverable
except Exception:
    pass
