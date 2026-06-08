#!/usr/bin/env python3
"""Render the rooms a big reasoning model listed in its natural-language output.
Proves whether gemma-4-31b's geometry is actually accurate. Reads /tmp/s2raw.txt."""
import re, json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw = open('/tmp/s2raw.txt').read()
pat = re.compile(r'([A-Za-z぀-ヿ一-鿿][\w぀-ヿ一-鿿/]*)\s*[:：]\s*'
                 r'(\[\s*\[[-\d\s.,]+\](?:\s*,\s*\[[-\d\s.,]+\])*\s*\])')
rooms, seen = [], set()
for m in pat.finditer(raw):
    try: poly = json.loads(m.group(2))
    except Exception: continue
    if len(poly) < 3: continue
    key = (round(poly[0][0]), round(poly[0][1]), round(poly[1][0]), round(poly[1][1]))
    if key in seen: continue                       # dedup the English/Japanese duplicate lists
    seen.add(key)
    rooms.append({'name': m.group(1).strip(), 'polygon': poly})

allp = [p for r in rooms for p in r['polygon']]
xs = [p[0] for p in allp]; zs = [p[1] for p in allp]
minx, maxx, minz, maxz = min(xs), max(xs), min(zs), max(zs)
W, D = maxx-minx, maxz-minz; sw, fs = max(W, D)/200, max(W, D)/34
cols = ['#e8dcc0','#d8e4d4','#ecd6d2','#d4dde8','#ece2c2','#ddd4e6','#d6e8e2','#e8d8c0',
        '#dde4c8','#e4d0c8','#d0e0d8','#e8d4c0','#d8d8e8','#e0e8d0','#e8dcd0']
cells = []
for i, r in enumerate(rooms):
    pts = ' '.join(f'{x},{z}' for x, z in r['polygon'])
    cx = sum(x for x, z in r['polygon'])/len(r['polygon']); cz = sum(z for x, z in r['polygon'])/len(r['polygon'])
    cells.append(f'<polygon points="{pts}" fill="{cols[i%len(cols)]}" stroke="#3a342c" stroke-width="{sw}"/>'
                 f'<text x="{cx}" y="{cz}" font-size="{fs}" fill="#2a241d" text-anchor="middle" dominant-baseline="middle" font-family="sans-serif">{r["name"]}</text>')
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{minx-W*0.05} {minz-D*0.05} {W*1.1} {D*1.1}" '
       f'width="620" style="background:#faf7f0;border:1px solid #ccc">{"".join(cells)}</svg>')
open(os.path.join(HERE, 'web', 'madori3_debug.html'), 'w').write(
    f'<!doctype html><meta charset=utf-8><body style="margin:0;display:flex;justify-content:center;padding:20px;background:#f3efe6">{svg}</body>')
print(f'✓ rendered {len(rooms)} rooms:', [r['name'] for r in rooms])
