#!/usr/bin/env python3
"""Render the combined viewer: 3D study model (stage) + multi-lens reading (panel),
two-way linked (hover a room -> it lights up in 3D; click a lens -> its rooms light up).

Reads last_reading.json (produced by plan_read.py) and writes web/madori.html.
Called automatically at the end of plan_read.py; also runnable standalone to re-render
without re-invoking Gemma.

Usage: python pipeline/combine.py
"""
import json, os, sys, base64, re, webbrowser

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# product is Chinese-first: map Japanese (and a few English) room names to Chinese
ROOM_ZH = {
    "居間": "客厅", "リビング": "客厅", "寝室": "卧室", "洋室": "卧室", "和室": "和室",
    "台所": "厨房", "キッチン": "厨房", "ダイニング": "餐厅", "DK": "DK", "LDK": "LDK",
    "玄関": "玄关", "ホール": "门厅", "廊下": "走廊", "階段": "楼梯",
    "浴室": "浴室", "洗面": "盥洗", "脱衣": "更衣室", "トイレ": "卫生间", "便所": "卫生间",
    "収納": "储物", "物入": "储物", "押入": "壁橱", "納戸": "储物", "クローゼット": "壁橱",
    "子供室": "儿童房", "子供部屋": "儿童房", "書斎": "书房", "ポーチ": "门廊",
    "バルコニー": "阳台", "ユーティリティ": "家政间",
}
def _zh_name(n):
    b = re.sub(r"[（(].*$", "", re.sub(r"[\s\d]", "", str(n))).strip()   # "居間 (LDK)" -> "居間"
    return ROOM_ZH.get(b, n)

def render(data, img_path=None, out_html=None, open_browser=True):
    """data = {dims, walls, rooms, lenses}. img_path = source floor plan to embed
    as the panel thumbnail (falls back to data['img']). Returns the written path."""
    for r in data.get("rooms", []):                  # Chinese-first room labels
        r["name"] = _zh_name(r.get("name", ""))
    web = os.path.join(HERE, "web")
    tpl = open(os.path.join(web, "combined.template.html")).read()
    keep = {k: data[k] for k in ("dims", "walls", "rooms", "lenses", "geom", "openings", "balcony") if k in data}
    p = img_path or data.get("img")
    b64 = base64.b64encode(open(p, "rb").read()).decode() if (p and os.path.exists(p)) else ""
    html = (tpl.replace("__DATA_JSON__", json.dumps(keep, ensure_ascii=False))
               .replace("__IMG_B64__", b64))
    out = out_html or os.path.join(web, "madori.html")
    open(out, "w").write(html)
    if open_browser:
        try: webbrowser.open("file://" + out)
        except Exception: pass
    return out

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "last_reading.json")
    data = json.load(open(src))
    img = data.get("img") or os.path.join(HERE, "samples", "floorplan.png")
    p = render(data, img_path=img)
    print(f"✓ wrote {p}  (floor plan: {os.path.basename(img) if os.path.exists(img) else 'none'})")
