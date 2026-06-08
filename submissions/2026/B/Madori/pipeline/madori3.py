#!/usr/bin/env python3
"""Madori v3 — staged floor-plan geometry pipeline on LOCAL Gemma e4b.

Ports floor-to-3d's 3-stage method (outline → rooms → openings) to local gemma4:e4b,
which the spike proved reads the RELATIVE layout right (vs the old one-shot rect, which
scrambled it). Adds the fixes the spike exposed:
  - scale-normalize Stage-2 rooms onto the Stage-1 bounds (e4b drifts the absolute scale)
  - snap vertices to a grid so neighbouring rooms share endpoints (less overlap/gap)
  - openings as POINTS (e4b gives a location; downstream snaps to the nearest wall) —
    more robust on a small model than wallId matching.

Output: last_reading3.json  { bounds, rooms[{id,name,polygon,function}], openings[{type,at}] }
Plus a debug SVG (web/madori3_debug.html) to eyeball the cleaned layout.

Usage: python pipeline/madori3.py samples/madorizu_1f.png
"""
import json, base64, urllib.request, re, sys, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "samples", "madorizu_1f.png")
B64 = base64.b64encode(open(IMG, "rb").read()).decode()

MODEL = os.environ.get("MADORI_MODEL", "gemma4:e4b")   # local: gemma4:e4b | cloud: gemma-4-31b-it
CLOUD = MODEL.startswith("gemma-4-")                    # AI Studio cloud Gemma 4
_KEY = ""
if CLOUD:
    _envf = os.path.join(HERE, ".env.local")
    if os.path.exists(_envf):
        for _ln in open(_envf):
            if _ln.startswith("GOOGLE_AI_KEY="): _KEY = _ln.split("=", 1)[1].strip()

def chat(system, user, n=1400):
    if CLOUD:                                            # Gemini API (Gemma has no system role → fold into user)
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": B64}},
                    {"text": user}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": n,
                                     "responseMimeType": "application/json"}}   # system role + force JSON
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={_KEY}"
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=300).read())
            return r["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"    [cloud err: {e}]"); return ""
    body = {"model": MODEL,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user, "images": [B64]}],
            "stream": False, "think": False, "keep_alive": "10m",
            "options": {"temperature": 0.2, "num_predict": n}}
    req = urllib.request.Request("http://localhost:11434/api/chat",
        data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=240).read()).get("message", {}).get("content", "").strip()

def parse_reasoning_rooms(raw):
    """Fallback: big reasoning models (gemma-4-31b) list rooms as natural-language
    'Name: [[x,y],[x,y],...]' instead of JSON. Extract polygons directly.
    Handles negative coords (balconies/porches) + dedups EN/JP duplicate lists."""
    rooms, seen = [], set()
    pat = re.compile(r'([A-Za-z぀-ヿ一-鿿][\w぀-ヿ一-鿿/]*)\s*[:：]\s*'
                     r'(\[\s*\[[-\d\s.,]+\](?:\s*,\s*\[[-\d\s.,]+\])*\s*\])')
    for m in pat.finditer(raw):
        try: poly = json.loads(m.group(2))
        except Exception: continue
        poly = [[float(p[0]), float(p[1])] for p in poly if isinstance(p, list) and len(p) >= 2]
        if len(poly) < 3: continue
        key = (round(poly[0][0]), round(poly[0][1]), round(poly[1][0]), round(poly[1][1]))
        if key in seen: continue
        seen.add(key)
        rooms.append({"id": f"r{len(rooms)+1}", "name": m.group(1).strip(),
                      "polygon": poly, "function": "その他"})
    return rooms

NAME_MAP = {
    'dk': 'DK', 'ldk': 'LDK',
    'entrance': '玄关', 'genkan': '玄关', '玄関': '玄关',
    'hall': '门厅', 'ホール': '门厅', 'corridor': '走廊', '廊下': '走廊',
    'living': '客厅', 'livingroom': '客厅', '居間': '客厅', 'リビング': '客厅',
    'kitchen': '厨房', '台所': '厨房', 'キッチン': '厨房',
    'dining': '餐厅', 'ダイニング': '餐厅',
    'bathroom': '浴室', 'bath': '浴室', 'ub': '浴室', '浴室': '浴室', 'unitbath': '浴室',
    'washroom': '盥洗', 'washstand': '盥洗', '洗面': '盥洗',
    'toilet': '卫生间', 'wc': '卫生间', 'トイレ': '卫生间', '便所': '卫生间',
    'closet': '壁橱', 'wic': '壁橱', '押入': '壁橱', 'クローゼット': '壁橱',
    'storage': '储物', 'storeroom': '储物', '物入': '储物', '収納': '储物', '納戸': '储物',
    'utility': '家政间', 'ユーティリティ': '家政间',
    'balcony': '阳台', 'バルコニー': '阳台', 'veranda': '阳台',
    'porch': '门廊', 'ポーチ': '门廊',
    'stairs': '楼梯', 'stair': '楼梯', 'staircase': '楼梯', '階段': '楼梯',
    'room': '和室', 'washitsu': '和室', 'japaneseroom': '和室', '和室': '和室', 'tatami': '和室',
    'bedroom': '卧室', '寝室': '卧室', '洋室': '卧室',
    'childroom': '儿童房', 'kidsroom': '儿童房', '子供室': '儿童房', '子供部屋': '儿童房',
}
DROP = ('gap', 'space', 'void', 'area', 'wall', 'margin', 'cutout', 'すきま', '間隙', 'なし')

def clean_names(rooms):
    """Reasoning output mixes EN/JP names and sometimes lists non-rooms like 'gap'.
    Map names to Chinese (matching the front-end's language) and drop non-rooms."""
    out = []
    for r in rooms:
        raw = str(r.get("name", "")).strip()
        low = re.sub(r'[\s\d()（）.\-_]', '', raw).lower()
        if not low or any(d in low for d in DROP):
            continue
        r["name"] = NAME_MAP.get(low, raw)
        out.append(r)
    return out

def _balanced(raw, key):
    """Extract the {...} object beginning at the LAST occurrence of `key`, by brace-counting.
    Reasoning models (gemma-4-31b) emit long prose then a final {"rooms":...}; the greedy {.*}
    regex gets fooled by stray {} in the prose (e.g. 'empty frame `{}`'), so target the real one."""
    i = raw.rfind(key)
    if i < 0: return None
    depth = 0
    for j in range(i, len(raw)):
        if raw[j] == '{': depth += 1
        elif raw[j] == '}':
            depth -= 1
            if depth == 0:
                try: return json.loads(raw[i:j+1])
                except Exception: return None
    return None

def grab_json(raw):
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if m:
        try: return json.loads(m.group(1))
        except Exception: pass
    for key in ('{"rooms"', '{"bounds"', '{"walls"', '{"openings"'):   # real objects, skip stray {} in reasoning prose
        obj = _balanced(raw, key)
        if obj: return obj
    mm = re.search(r"\{[\s\S]*\}", raw)                                  # last-resort greedy
    if mm:
        try: return json.loads(mm.group(0))
        except Exception: return None
    return None

# ---------------- Stage 1: outline + outer walls ----------------
S1_SYS = """你是日本住宅平面图(間取り)判读专家。3阶段流程第1阶段，只负责【外框 + 4面外墙】。
- 先读图上写的尺寸数字(如7300/6000/3640/1820/910)当实际mm，直接用不要猜；无尺寸才用910的倍数。
- 坐标取100mm倍数，图面左上为原点(0,0)，右=+x，下=+z。
- 只输出一个JSON，不解释不markdown。外墙顺时针: w-n(上) w-e(右) w-s(下) w-w(左)，共享端点完全一致。
schema: {"bounds":{"width":数,"depth":数},"walls":[{"id":"w-n","start":[x,z],"end":[x,z]},...4本]}"""
S1_USER = "读这张平面图的外周尺寸，返回外框+4外墙JSON。只输出JSON。"

# ---------------- Stage 2: room polygons ----------------
S2_SYS = """你是日本住宅平面图(間取り)判读专家。3阶段流程第2阶段，只负责【房间多边形】。
输入: 平面图 + 第1阶段外框JSON。
- 每个房间用顺时针多边形(polygon)顶点包围,≥3点(L型/凹型用6或8点,别压成矩形)。
- 相邻房间共享边顶点坐标完全一致,不留缝不重叠,合起来铺满外框。
- 坐标用和外框相同的尺度(落在 0~width × 0~depth 范围内),100mm倍数。
- 房间数目安: 日本独栋1階(含玄関/ホール/浴室/トイレ/洗面/収納)通常6-10个,太少=漏读。
- function取: リビング/ダイニング/キッチン/寝室/和室/子供部屋/玄関/土間/廊下/浴室/洗面/トイレ/収納/吹抜/その他。
- 只输出一个JSON,不解释不markdown,不确定不编,不要门窗(第3阶段)。
schema: {"rooms":[{"id":"r1","name":"和室","polygon":[[x,z],...],"function":"和室"},...]}
示例(模仿这个格式,直接输出,不要解释):
{"rooms":[{"id":"r1","name":"DK","polygon":[[0,0],[4500,0],[4500,2800],[0,2800]],"function":"ダイニング"},{"id":"r2","name":"居間","polygon":[[0,2800],[6000,2800],[6000,7000],[0,7000]],"function":"リビング"}]}
⚠ 立即只输出JSON对象,第一个字符必须是 { 。禁止任何思考过程/解释/英文说明/markdown围栏。Output ONLY the JSON object starting with {."""

# ---------------- Stage 3: openings as points ----------------
S3_SYS = """你是日本住宅平面图(間取り)判读专家。3阶段流程第3阶段，只负责【门窗】。
输入: 平面图 + 累积plan(外框+房间)。
- 找图上的门和窗。窗=外墙上的双线/落地窗;门=圆弧(开き戸)或双线箭头(引戸)。
- 每个门窗给一个位置点[x,z](就在那面墙的中间),用和plan相同的尺度。
- type取: door(门)/window(窗)/sliding(引戸)。
- 只输出一个JSON,不解释不markdown,不确定不编。
schema: {"openings":[{"id":"o1","type":"window","at":[x,z]},...]}"""

# ---------------- post-processing ----------------
def bbox(pts):
    xs = [p[0] for p in pts]; zs = [p[1] for p in pts]
    return min(xs), min(zs), max(xs), max(zs)

def poly_area(poly):
    a = 0
    for i in range(len(poly)):
        x1, z1 = poly[i]; x2, z2 = poly[(i+1) % len(poly)]
        a += x1*z2 - x2*z1
    return abs(a) / 2

def bbox_overlap(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iz = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iz

def score_rooms(rooms, W, D):
    """higher = cleaner layout. e4b polygon quality varies run-to-run; this lets us
    sample N times and keep the best. Penalizes overlap, a dominant oversized room,
    bad coverage, and odd room counts."""
    if len(rooms) < 2: return -1e9
    A = max(W*D, 1)
    areas = [poly_area(r["polygon"]) for r in rooms]
    total = sum(areas) or 1
    boxes = [bbox(r["polygon"]) for r in rooms]
    ov = sum(bbox_overlap(boxes[i], boxes[j]) for i in range(len(boxes)) for j in range(i+1, len(boxes)))
    cover, dom, n = total / A, max(areas) / total, len(rooms)
    s = 0.0
    s -= abs(cover - 1.0) * 2.0        # rooms should ~fill bounds
    s -= (ov / A) * 3.0                # overlap is the worst symptom
    s -= max(0, dom - 0.4) * 4.0       # one giant room (e.g. 巨大洗面) = bad read
    s += 1.0 if 2 <= n <= 16 else -0.3 * abs(n - 11)
    s += (len(set(r.get("name", "") for r in rooms)) / max(n, 1)) * 2.0   # reward distinct names (kill 'Polygon'×N)
    return s

def normalize_rooms(rooms, W, D):
    """e4b often emits Stage-2 coords at a different absolute scale than bounds;
    map the rooms' real bbox exactly onto [0,W]x[0,D]."""
    pts = [p for r in rooms for p in r.get("polygon", []) if len(r.get("polygon", [])) >= 3]
    if not pts: return lambda p: p
    minx, minz, maxx, maxz = bbox(pts)
    sx = W / (maxx - minx) if maxx > minx else 1
    sz = D / (maxz - minz) if maxz > minz else 1
    def f(p): return [(p[0] - minx) * sx, (p[1] - minz) * sz]
    for r in rooms:
        r["polygon"] = [f(p) for p in r.get("polygon", [])]
    return f  # return the same transform so openings can use it

def recenter(rooms):
    """Shift rooms so the min corner = (0,0); return resulting (width, depth).
    The extracted polygons are already a self-consistent coordinate system, so we
    use their own bbox as bounds instead of forcing onto a separate Stage-1 frame."""
    pts = [p for r in rooms for p in r['polygon']]
    minx = min(p[0] for p in pts); minz = min(p[1] for p in pts)
    for r in rooms:
        r['polygon'] = [[p[0]-minx, p[1]-minz] for p in r['polygon']]
    return (max(p[0] for r in rooms for p in r['polygon']),
            max(p[1] for r in rooms for p in r['polygon']))

def snap_round(rooms, grid):
    """snap vertices to a grid so adjacent rooms share endpoints + clean coords."""
    def s(v): return round(v / grid) * grid
    for r in rooms:
        r["polygon"] = [[s(x), s(z)] for x, z in r.get("polygon", [])]
        # drop consecutive duplicate points created by snapping
        poly, prev = [], None
        for p in r["polygon"]:
            if p != prev: poly.append(p); prev = p
        if len(poly) >= 3 and poly[0] == poly[-1]: poly = poly[:-1]
        r["polygon"] = poly

# ============================================================
print(f"▸ madori3 pipeline · {os.path.basename(IMG)}")

print("  Stage 1 (outline) …")
d1 = {}
for _ in range(3):                                    # retry until bounds sane + 4 walls
    d1 = grab_json(chat(S1_SYS, S1_USER, n=900)) or {}
    b = d1.get("bounds", {}); W = b.get("width", 0) or 0; D = b.get("depth", 0) or 0
    if 3000 < W < 16000 and 3000 < D < 14000 and len(d1.get("walls", [])) == 4: break
b = d1.get("bounds", {}); W = b.get("width") or 9000; D = b.get("depth") or 7000
print(f"    bounds {W}×{D} = {round(W*D/1e6,1)}㎡")

print("  Stage 2 (rooms · 多采样选优) …")
s2u = f"第1阶段外框:\n{json.dumps(d1, ensure_ascii=False)}\n\n识别所有房间(多边形)。只输出JSON。"
cands = []
_NS = int(os.environ.get("MADORI_SAMPLES", "5")); _TOK = int(os.environ.get("MADORI_S2TOK", "6000"))
for att in range(_NS):                                # sample N, keep best
    raw2 = chat(S2_SYS, s2u, n=_TOK)
    open('/tmp/s2raw.txt', 'w').write(raw2)            # debug dump for regex tuning
    d2 = grab_json(raw2) or {}
    rms = [r for r in d2.get("rooms", []) if isinstance(r.get("polygon"), list) and len(r["polygon"]) >= 3]
    if len(rms) < 2:                                   # JSON failed → try extracting from reasoning text (≥2 supports simple apartments)
        rms = parse_reasoning_rooms(raw2)
        if len(rms) >= 2: print(f"    sample {att+1}: JSON 失败，从 reasoning 提取到 {len(rms)} rooms")
    if len(rms) < 2:
        print(f"    sample {att+1}: {len(rms)} rooms (skip) · len={len(raw2)}"); continue
    rw, rd = recenter(rms)                            # bounds from the rooms' own bbox
    snap_round(rms, grid=max(rw, rd) / 36)
    rms = [r for r in rms if len(r.get("polygon", [])) >= 3]
    sc = score_rooms(rms, rw, rd)
    cands.append((sc, rms, rw, rd))
    print(f"    sample {att+1}: {len(rms)} rooms · score {sc:.2f} · bounds {round(rw)}×{round(rd)}")
cands.sort(key=lambda c: -c[0])
if cands: _, rooms, W, D = cands[0]; print(f"    → 选中 score {cands[0][0]:.2f}")
else: rooms = []; print("    → 全部失败")
_u = []                                               # dedup by POSITION (overlap), not name
for r in rooms:
    rb = bbox(r["polygon"]); dup = False
    for u in _u:
        ub = bbox(u["polygon"])
        ix = max(0, min(rb[2], ub[2]) - max(rb[0], ub[0])); iz = max(0, min(rb[3], ub[3]) - max(rb[1], ub[1]))
        if ix*iz > 0.5*min(poly_area(r["polygon"]), poly_area(u["polygon"])): dup = True; break
    if not dup: _u.append(r)
rooms = clean_names(_u)                                # EN/JP → 中文 + drop non-rooms (gap)
print(f"    {len(rooms)} rooms (final)")

print("  Stage 3 (openings) …")
plan_for_s3 = {"bounds": b, "rooms": [{"id": r.get("id"), "name": r.get("name")} for r in rooms]}
d3 = grab_json(chat(S3_SYS, f"累积plan:\n{json.dumps(plan_for_s3, ensure_ascii=False)}\n\n找门窗,给位置点。只输出JSON。", n=1200)) or {}
openings = []
for o in d3.get("openings", []):
    at = o.get("at")
    if isinstance(at, list) and len(at) == 2:
        openings.append({"id": o.get("id", f"o{len(openings)+1}"), "type": o.get("type", "window"),
                         "at": [at[0], at[1]]})        # already in bounds scale (Stage-3 input is bounds)
print(f"    {len(openings)} openings")

# ---------------- output ----------------
out = {"bounds": {"width": round(W), "depth": round(D)}, "rooms": rooms, "openings": openings}
json.dump(out, open(os.path.join(HERE, "last_reading3.json"), "w"), ensure_ascii=False, indent=2)

# debug SVG
cols = ["#e8dcc0","#d8e4d4","#ecd6d2","#d4dde8","#ece2c2","#ddd4e6","#d6e8e2","#e8d8c0","#dde4c8","#e4d0c8"]
sw, fs = max(W, D) / 200, max(W, D) / 30
cells = []
for i, r in enumerate(rooms):
    poly = r["polygon"]
    pts = " ".join(f"{x},{z}" for x, z in poly)
    cx = sum(x for x, z in poly) / len(poly); cz = sum(z for x, z in poly) / len(poly)
    cells.append(f'<polygon points="{pts}" fill="{cols[i%len(cols)]}" stroke="#3a342c" stroke-width="{sw}"/>'
                 f'<text x="{cx}" y="{cz}" font-size="{fs}" fill="#2a241d" text-anchor="middle" dominant-baseline="middle" font-family="sans-serif">{r.get("name","")}</text>')
for o in openings:
    x, z = o["at"]; c = {"window": "#2a6f8f", "sliding": "#8a6f2a"}.get(o["type"], "#b34a26")
    cells.append(f'<circle cx="{x}" cy="{z}" r="{sw*2.5}" fill="{c}"/>')
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-W*0.05} {-D*0.05} {W*1.1} {D*1.1}" width="600" '
       f'style="background:#faf7f0;border:1px solid #ccc"><rect x="0" y="0" width="{W}" height="{D}" fill="none" stroke="#000" stroke-width="{sw*1.5}"/>{"".join(cells)}</svg>')
open(os.path.join(HERE, "web", "madori3_debug.html"), "w").write(
    f'<!doctype html><meta charset=utf-8><body style="margin:0;display:flex;justify-content:center;padding:20px;background:#f3efe6">{svg}</body>')

print(f"\n✓ last_reading3.json + web/madori3_debug.html")
print("  rooms:", [r.get("name") for r in rooms])
