#!/usr/bin/env python3
"""SPIKE — can local Gemma e4b follow floor-to-3d's staged JSON pipeline?

Ports floor-to-3d's Stage 1 (outline + outer walls) + Stage 2 (interior walls +
room polygons) to LOCAL gemma4:e4b, with the same精度 tricks (read dimensions
first / 910mm module / 100mm snap / room-count sanity / polygon rooms).

This does NOT touch plan_read.py. Goal: judge whether e4b can produce clean
staged JSON + accurate polygons, before committing to the full rewrite.

Usage: python pipeline/madori3_spike.py samples/madorizu_1f.png
"""
import json, base64, urllib.request, re, sys, os

IMG = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else "samples/madorizu_1f.png"
B64 = base64.b64encode(open(IMG, "rb").read()).decode()

def chat(system, user, n=1200):
    body = {"model": "gemma4:e4b",
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user, "images": [B64]}],
            "stream": False, "think": False, "keep_alive": "10m",
            "options": {"temperature": 0.2, "num_predict": n}}
    req = urllib.request.Request("http://localhost:11434/api/chat",
        data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=240).read()).get("message", {}).get("content", "").strip()

def grab_json(raw):
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    s = m.group(1) if m else (re.search(r"\{[\s\S]*\}", raw) or [None])[0] if re.search(r"\{[\s\S]*\}", raw) else None
    if not s: return None, "no-json"
    try: return json.loads(s), None
    except Exception as e: return None, f"invalid-json: {e}"

# ---------- STAGE 1: outline + outer walls ----------
S1_SYS = """你是日本住宅平面图(間取り)判读专家。这是3阶段流程的第1阶段，只负责【外框 + 4面外墙】。
规则:
- 先读图上写的尺寸数字(如 7300/6000/3640/1820/910)，这些是实际毫米(mm)，直接用，不要猜。
- 外周尺寸优先。完全没有尺寸数字时才用日本标准模块: 柱间=910的倍数(1820/2730/3640/4550)。
- 所有坐标四舍五入到100mm的倍数。图面左上为原点(0,0)，右=+x，下=+z。
- 只输出一个JSON对象，不要解释、不要markdown。不确定的不编。
- 外墙固定4本，顺时针: w-n(上,左→右) w-e(右,上→下) w-s(下,右→左) w-w(左,下→上)，共享端点完全一致。
输出schema(只能有这些字段):
{"bounds":{"width":数,"depth":数},"walls":[{"id":"w-n","start":[x,z],"end":[x,z]}, ...4本]}
例(外形7300×6000):
{"bounds":{"width":7300,"depth":6000},"walls":[{"id":"w-n","start":[0,0],"end":[7300,0]},{"id":"w-e","start":[7300,0],"end":[7300,6000]},{"id":"w-s","start":[7300,6000],"end":[0,6000]},{"id":"w-w","start":[0,6000],"end":[0,0]}]}"""
S1_USER = "读这张平面图的外周尺寸，按第1阶段schema返回外框+4外墙的JSON。只输出JSON。"

print(f"▸ STAGE 1 (outline) on {os.path.basename(IMG)} …")
raw1 = chat(S1_SYS, S1_USER, n=900)
print("--- raw ---\n", raw1[:600])
d1, err1 = grab_json(raw1)
print("\n--- parsed ---")
if err1:
    print("FAIL:", err1)
else:
    b = d1.get("bounds", {})
    print(f"bounds: {b.get('width')} × {b.get('depth')} mm  = {round(b.get('width',0)*b.get('depth',0)/1e6,1)} ㎡")
    print(f"walls: {len(d1.get('walls',[]))} 本")
    for w in d1.get("walls", []): print(f"  {w.get('id')}: {w.get('start')} → {w.get('end')}")
    # sanity: 4 walls, clockwise, endpoints shared
    ws = d1.get("walls", [])
    ok4 = len(ws) == 4
    shared = all(ws[i].get("end") == ws[(i+1) % 4].get("start") for i in range(4)) if ok4 else False
    print(f"\nSANITY: 4墙={ok4}  端点闭合={shared}  bounds合理={3000 < b.get('width',0) < 30000 and 3000 < b.get('depth',0) < 30000}")

# ---------- STAGE 2: interior walls + room polygons ----------
S2_SYS = """你是日本住宅平面图(間取り)判读专家。这是3阶段流程的第2阶段，只负责【内墙 + 房间多边形】。
输入: 平面图 + 第1阶段的外框JSON。
规则:
- 在外框内识别所有房间，每个房间用顺时针多边形(polygon)顶点包围，≥3点(L型/凹型用6或8点，别强行压成矩形)。
- 相邻房间共享边的顶点坐标必须完全一致，不留缝/不重叠，所有房间合起来铺满外框。
- 先读图上尺寸数字；无尺寸用910模块。坐标100mm倍数，落在外框bounds内。
- 房间数目安: 日本独栋1階(含玄関/ホール/浴室/トイレ/洗面/収納)通常6-10个，太少=漏读。
- function只能取: リビング/ダイニング/キッチン/寝室/和室/子供部屋/玄関/土間/廊下/浴室/洗面/トイレ/収納/吹抜/その他。日本符号: 畳格子=和室, UB/浴槽=浴室, 玄関+土間ハッチ=玄関。
- 只输出一个JSON对象，不解释不markdown，不确定的不编。不要输出门窗(那是第3阶段)。
输出schema(只能有这些字段):
{"rooms":[{"id":"r1","name":"和室","polygon":[[x,z],[x,z],...],"function":"和室"}, ...]}"""

if not err1 and d1:
    print("\n▸ STAGE 2 (interior + room polygons) …")
    s2_user = f"第1阶段外框:\n{json.dumps(d1, ensure_ascii=False)}\n\n在这个外框内，按第2阶段schema识别所有房间(多边形)。只输出JSON。"
    raw2 = chat(S2_SYS, s2_user, n=2200)
    print("--- raw (head) ---\n", raw2[:300])
    d2, err2 = grab_json(raw2)
    print("\n--- parsed ---")
    if err2:
        print("FAIL:", err2)
    else:
        rooms = d2.get("rooms", [])
        print(f"rooms: {len(rooms)}")
        for r in rooms:
            poly = r.get("polygon", [])
            print(f"  {r.get('name')} ({r.get('function')}): {len(poly)}点 {poly if len(poly)<=4 else poly[:4]+['...']}")
        # render SVG — viewBox ADAPTS to the rooms' real extent (ignore Stage1 scale mismatch),
        # so we can judge the RELATIVE layout regardless of the absolute scale bug.
        cols = ["#e8dcc0","#d8e4d4","#ecd6d2","#d4dde8","#ece2c2","#ddd4e6","#d6e8e2","#e8d8c0"]
        allpts = [(x, z) for r in rooms for x, z in r.get("polygon", []) if len(r.get("polygon", [])) >= 3]
        xs = [p[0] for p in allpts]; zs = [p[1] for p in allpts]
        minx, maxx, minz, maxz = min(xs), max(xs), min(zs), max(zs)
        span = max(maxx-minx, maxz-minz, 1); pad = span*0.05
        sw = span/220; fs = span/26
        cells = []
        for i, r in enumerate(rooms):
            poly = r.get("polygon", [])
            if len(poly) < 3: continue
            pts = " ".join(f"{x},{z}" for x, z in poly)
            cx = sum(x for x, z in poly)/len(poly); cz = sum(z for x, z in poly)/len(poly)
            cells.append(f'<polygon points="{pts}" fill="{cols[i%len(cols)]}" stroke="#3a342c" stroke-width="{sw}"/>'
                         f'<text x="{cx}" y="{cz}" font-size="{fs}" fill="#2a241d" text-anchor="middle" dominant-baseline="middle" font-family="sans-serif">{r.get("name","")}</text>')
        vb = f"{minx-pad} {minz-pad} {maxx-minx+2*pad} {maxz-minz+2*pad}"
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="560" '
               f'style="background:#faf7f0;border:1px solid #ccc">{"".join(cells)}</svg>')
        out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spike_out.html")
        open(out, "w").write(f'<!doctype html><meta charset=utf-8><body style="margin:0;display:flex;justify-content:center;padding:20px;background:#f3efe6">{svg}</body>')
        print(f"\n✓ rendered {out} — 截图对比源图看布局对不对")
