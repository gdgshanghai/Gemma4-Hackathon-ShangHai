#!/usr/bin/env python3
"""Bridge the precise cloud-Gemma-4 layout into the four-view reading format.

madori3.py (cloud gemma-4-31b) produces last_reading3.json = polygon + mm geometry
(15 rooms, accurately matching the source plan) but NO five-lens text and NO windows
(Stage-3 openings came back empty). The combined viewer (web/madori.html) instead eats
last_reading.json = rect + metres + win + lenses. This converts the former into the latter
so the demo can show the PRECISE 15-room layout instead of the e4b sketch (5 rooms).

Three gaps bridged:
  1. geometry — every precise room is a rectangle, so polygon -> bbox rect is LOSSLESS;
     mm -> metres (/1000).
  2. windows — openings empty, so inferred from geometry: a room touching an outer wall
     MAY have a window there — but ONLY for habitable/wet rooms (a window on storage /
     closet / stairs would mislead the 采光 view).
  3. lenses — geometry-only pipeline has none, so reuse last_reading.json's five-lens text
     (general enough to still fit) + its source image + walls.

Output: last_reading_precise.json (kept separate — e4b's last_reading.json stays for the
        local-vs-cloud dual-track comparison) + renders web/madori.html.

Usage: python pipeline/precise_to_reading.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(HERE, "last_reading3.json")    # precise polygon + mm
BASE = os.path.join(HERE, "last_reading.json")     # reuse lenses / walls / img
OUT  = os.path.join(HERE, "last_reading_precise.json")

EPS = 0.25                                          # metres: closeness to outer wall = "touching"
WIN_OK = {"DK", "LDK", "客厅", "餐厅", "厨房", "卧室", "和室",
          "儿童房", "书房", "浴室", "盥洗", "更衣室", "卫生间"}   # rooms that may have a daylight window

def bbox(poly):
    xs = [p[0] for p in poly]; zs = [p[1] for p in poly]
    return min(xs), min(zs), max(xs), max(zs)

def gen_openings(rooms, W, D):
    """Door/window positions (rule-based). Windows: each room's exterior-wall win dirs.
    Doors: every non-living room opens ONE door to an ADJACENT room (preferring the
    corridor 走廊, then the living room, then its largest neighbour — corridors exist to
    connect, so service rooms route through them), plus a front-door for 玄関 on its
    exterior wall. A window is skipped if it collides with a door on the same wall."""
    ops, EPS = [], 0.05
    living = max(rooms, key=lambda r: r["rect"][2] * r["rect"][3])   # 客厅 = largest room

    def edge(a, b):
        """If rects a,b share a wall segment ≥0.7m, return (dir_of_a, fixed_coord, mid)."""
        ax, ay, aw, ah = a["rect"]; bx, by, bw, bh = b["rect"]
        if abs((ax+aw) - bx) < EPS:                                 # a right touches b left
            lo, hi = max(ay, by), min(ay+ah, by+bh)
            if hi-lo > 0.7: return ("right", ax+aw, (lo+hi)/2)
        if abs((bx+bw) - ax) < EPS:                                 # a left touches b right
            lo, hi = max(ay, by), min(ay+ah, by+bh)
            if hi-lo > 0.7: return ("left", ax, (lo+hi)/2)
        if abs((ay+ah) - by) < EPS:                                 # a bottom touches b top
            lo, hi = max(ax, bx), min(ax+aw, bx+bw)
            if hi-lo > 0.7: return ("down", ay+ah, (lo+hi)/2)
        if abs((by+bh) - ay) < EPS:                                 # a top touches b bottom
            lo, hi = max(ax, bx), min(ax+aw, bx+bw)
            if hi-lo > 0.7: return ("up", ay, (lo+hi)/2)
        return None

    def add_door(a, b, w=0.9):
        e = edge(a, b)
        if not e: return
        d, coord, mid = e
        o = ({"type": "door", "x": round(coord, 2), "z": round(mid, 2), "dir": d, "w": w}
             if d in ("left", "right")
             else {"type": "door", "x": round(mid, 2), "z": round(coord, 2), "dir": d, "w": w})
        ops.append(o)

    corridor = next((r for r in rooms if r["name"] in ("走廊", "门厅", "门廊")), None)
    for r in rooms:                                                 # one door per non-living room
        if r is living: continue
        if corridor and r is not corridor and edge(r, corridor):   # prefer routing through corridor
            add_door(r, corridor)
        elif edge(r, living):                                      # else straight into living
            add_door(r, living)
        else:                                                      # else into largest adjacent neighbour
            neigh = sorted(((o["rect"][2]*o["rect"][3], o) for o in rooms
                            if o is not r and edge(r, o)), key=lambda t: t[0], reverse=True)
            if neigh: add_door(r, neigh[0][1])

    for r in rooms:                                                # 玄関 front door on its exterior wall
        if r["name"] != "玄关": continue
        x, y, w, h = r["rect"]
        if   abs((y+h) - D) < 0.25: ops.append({"type": "door", "x": round(x+w/2, 2), "z": round(y+h, 2), "dir": "down",  "w": 1.0})
        elif y <= 0.25:             ops.append({"type": "door", "x": round(x+w/2, 2), "z": round(y, 2),   "dir": "up",    "w": 1.0})
        elif x <= 0.25:             ops.append({"type": "door", "x": round(x, 2),     "z": round(y+h/2, 2),"dir": "left",  "w": 1.0})
        elif abs((x+w) - W) < 0.25: ops.append({"type": "door", "x": round(x+w, 2),   "z": round(y+h/2, 2),"dir": "right", "w": 1.0})

    def collides(o):
        return any(d["type"] == "door" and d["dir"] == o["dir"] and abs(d["x"]-o["x"]) < 1.0 and abs(d["z"]-o["z"]) < 1.0 for d in ops)
    for r in rooms:                                                 # windows on exterior walls (skip if a door is there)
        x, y, w, h = r["rect"]
        for d in r["win"]:
            if d == 'up':    o = {"type": "window", "x": round(x+w/2, 2), "z": round(y, 2),   "dir": "up",    "w": round(min(w*0.5, 1.6), 2)}
            elif d == 'down':o = {"type": "window", "x": round(x+w/2, 2), "z": round(y+h, 2), "dir": "down",  "w": round(min(w*0.5, 1.6), 2)}
            elif d == 'left':o = {"type": "window", "x": round(x, 2),     "z": round(y+h/2, 2),"dir": "left",  "w": round(min(h*0.5, 1.6), 2)}
            else:            o = {"type": "window", "x": round(x+w, 2),   "z": round(y+h/2, 2),"dir": "right", "w": round(min(h*0.5, 1.6), 2)}
            if not collides(o): ops.append(o)
    return ops

def rect_walls(rects, W, D):
    """Build wall segments that MATCH the precise rooms (outer frame + each room's
    edges, deduped on shared edges). The e4b last_reading.json walls are a DIFFERENT
    layout/scale, so reusing them puts windows on phantom walls — generate our own."""
    walls = [[0, 0, W, 0], [W, 0, W, D], [W, D, 0, D], [0, D, 0, 0]]   # outer frame
    seen = set()
    for x, y, w, h in rects:
        for e in ((x, y, x+w, y), (x+w, y, x+w, y+h), (x+w, y+h, x, y+h), (x, y+h, x, y)):
            a = (round(e[0], 2), round(e[1], 2)); b = (round(e[2], 2), round(e[3], 2))
            key = tuple(sorted([a, b]))
            if key in seen:
                continue
            seen.add(key)
            walls.append([round(c, 2) for c in e])
    return walls

def main():
    d3 = json.load(open(SRC))
    base = json.load(open(BASE)) if os.path.exists(BASE) else {}
    W = d3["bounds"]["width"] / 1000.0
    D = d3["bounds"]["depth"] / 1000.0
    rooms = []
    for r in d3["rooms"]:
        minx, minz, maxx, maxz = bbox(r["polygon"])
        x, y, w, h = minx/1000.0, minz/1000.0, (maxx-minx)/1000.0, (maxz-minz)/1000.0
        win = []
        if r["name"] in WIN_OK:                     # only habitable/wet rooms get inferred windows
            if x <= EPS:          win.append("left")
            if y <= EPS:          win.append("up")
            if x + w >= W - EPS:  win.append("right")
            if y + h >= D - EPS:  win.append("down")
        rooms.append({"name": r["name"], "rect": [round(x,2), round(y,2), round(w,2), round(h,2)], "win": win})
    cover = sum(r["rect"][2]*r["rect"][3] for r in rooms) / (W*D) if W*D else 0
    out = {
        "dims":  [round(W,2), round(D,2)],
        "walls": rect_walls([r["rect"] for r in rooms], round(W,2), round(D,2)),   # walls that match the precise rooms
        "rooms": rooms,
        "openings": gen_openings(rooms, round(W,2), round(D,2)),   # 门窗(规则推断) → 3D 墙开洞
        "lenses": base.get("lenses", {}),
        "img":   base.get("img"),
        "geom":  {"coverage": round(cover,2), "level": "high", "calibrated": None},
    }
    if d3.get("balcony"):                                          # open balcony slab + railing (not a walled room)
        b = d3["balcony"]
        out["balcony"] = {k: round(b[k] / 1000.0, 2) for k in ("x", "z", "w", "d")}
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=2)
    nwin = sum(len(r["win"]) for r in rooms)
    print(f"✓ {len(rooms)} rooms · dims {round(W,1)}×{round(D,1)}m · cover {round(cover,2)} · {nwin} windows inferred")
    print("  rooms:", [r["name"] for r in rooms])

    sys.path.insert(0, os.path.join(HERE, "pipeline"))
    import combine
    combine.render(out, img_path=out.get("img"), open_browser=False)
    print("✓ rendered web/madori.html (precise layout)")

if __name__ == "__main__":
    main()
