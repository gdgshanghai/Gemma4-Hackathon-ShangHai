#!/usr/bin/env python3
"""Parse a PLATEAU CityGML (bldg) → building footprints + heights → inject into the
all-local white-massing extrude viewer (web/plateau_view.html). No network, no DRACO.

Usage: python pipeline/plateau_parse.py [path/to/xxx_bldg_6697_op2.gml]
"""
import xml.etree.ElementTree as ET, json, math, sys, os, statistics

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GML  = sys.argv[1] if len(sys.argv) > 1 else "/tmp/plateau_dl/bldg/53393496_bldg_6697_op2.gml"
ns = {'gml':'http://www.opengis.net/gml', 'bldg':'http://www.opengis.net/citygml/building/2.0'}

root = ET.parse(GML).getroot()
raw = []
for b in root.iter('{http://www.opengis.net/citygml/building/2.0}Building'):
    h = b.find('.//bldg:measuredHeight', ns)
    height = float(h.text) if (h is not None and h.text) else None
    pl = b.find('.//bldg:lod0RoofEdge//gml:posList', ns)
    if pl is None: pl = b.find('.//bldg:lod0FootPrint//gml:posList', ns)
    if pl is None: pl = b.find('.//bldg:lod1Solid//gml:posList', ns)
    if pl is None or not pl.text: continue
    nums = [float(x) for x in pl.text.split()]
    pts = [(nums[i], nums[i+1]) for i in range(0, len(nums)-2, 3)]     # (lat, lon) drop alt
    if len(pts) < 3: continue
    raw.append({'pts': pts, 'height': height})

if not raw:
    sys.exit("no buildings parsed (check gml path / structure)")

hs = [r['height'] for r in raw if r['height']]
med = statistics.median(hs) if hs else 9.0
allpts = [p for r in raw for p in r['pts']]
lat0 = sum(p[0] for p in allpts)/len(allpts); lon0 = sum(p[1] for p in allpts)/len(allpts)
mlat = 111320.0; mlon = 111320.0*math.cos(math.radians(lat0))      # local equirectangular metres

buildings = []
for r in raw:
    xz = [[(lon-lon0)*mlon, -(lat-lat0)*mlat] for (lat, lon) in r['pts']]
    buildings.append({'pts': [[round(x,2), round(z,2)] for x,z in xz], 'height': round(r['height'] or med, 1)})

meta = {'mesh': os.path.basename(GML).split('_')[0], 'count': len(buildings)}
tpl = open(os.path.join(HERE, 'web', 'plateau.template.html')).read()
tpl = tpl.replace('__BUILDINGS_JSON__', json.dumps(buildings)).replace('__META_JSON__', json.dumps(meta, ensure_ascii=False))
out = os.path.join(HERE, 'web', 'plateau_view.html')
open(out, 'w').write(tpl)
print(f"parsed {len(buildings)} buildings · origin lat0={lat0:.5f} lon0={lon0:.5f} · median height={med}m")
print(f"wrote web/plateau_view.html")
