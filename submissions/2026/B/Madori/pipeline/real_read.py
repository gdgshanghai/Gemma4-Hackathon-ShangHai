#!/usr/bin/env python3
"""Real-building reading: with a real LOCATION, daylight stops being a guess.

Given a PLATEAU CityGML + lat/lng, this computes — deterministically, from real
geometry + real sun path — each facade's compass orientation and its daylight
exposure. This is the upgrade leg B gives leg A: real coords → real 採光.

Usage: python pipeline/real_read.py [gml] [--bldg N]
"""
import xml.etree.ElementTree as ET, math, sys, os

GML = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else "/tmp/plateau_dl/bldg/53393496_bldg_6697_op2.gml"
ns = {'gml':'http://www.opengis.net/gml', 'bldg':'http://www.opengis.net/citygml/building/2.0'}

# ---- parse buildings (footprint lat/lon + height) ----
root = ET.parse(GML).getroot()
blds = []
for b in root.iter('{http://www.opengis.net/citygml/building/2.0}Building'):
    h = b.find('.//bldg:measuredHeight', ns); height = float(h.text) if (h is not None and h.text) else None
    pl = b.find('.//bldg:lod0RoofEdge//gml:posList', ns)
    if pl is None: pl = b.find('.//bldg:lod0FootPrint//gml:posList', ns)
    if pl is None or not pl.text: continue
    n = [float(x) for x in pl.text.split()]
    pts = [(n[i], n[i+1]) for i in range(0, len(n)-2, 3)]
    if len(pts) >= 4: blds.append({'pts': pts, 'height': height})
if not blds: sys.exit("no buildings parsed")

lat0 = sum(p[0] for b in blds for p in b['pts']) / sum(len(b['pts']) for b in blds)
mlat, mlon = 111320.0, 111320.0*math.cos(math.radians(lat0))

def area(pts):
    a = 0
    for i in range(len(pts)-1):
        x1,y1 = pts[i][1]*mlon, pts[i][0]*mlat; x2,y2 = pts[i+1][1]*mlon, pts[i+1][0]*mlat
        a += x1*y2 - x2*y1
    return abs(a)/2

# pick the biggest building (most "interesting" to read)
import re as _re
idx = int(next((a.split('=')[-1] for a in sys.argv if a.startswith('--bldg')), -1))
target = max(blds, key=lambda b: area(b['pts'])) if idx < 0 else blds[idx % len(blds)]
pts = target['pts']

# centroid (metres, x=east y=north)
cxm = sum(p[1] for p in pts)/len(pts)*mlon; cym = sum(p[0] for p in pts)/len(pts)*mlat

# ---- per-facade outward orientation + length ----
DIRS = {'北':0,'东':90,'南':180,'西':270}
facing = {'北':0.0,'东':0.0,'南':0.0,'西':0.0}
for i in range(len(pts)-1):
    (la1,lo1),(la2,lo2) = pts[i], pts[i+1]
    x1,y1 = lo1*mlon, la1*mlat; x2,y2 = lo2*mlon, la2*mlat
    ex,ey = x2-x1, y2-y1; L = math.hypot(ex,ey)
    if L < 0.3: continue
    # outward normal (two candidates), pick the one pointing away from centroid
    mx,my = (x1+x2)/2,(y1+y2)/2
    for nx,ny in [(-ey,ex),(ey,-ex)]:
        if (mx-cxm)*nx + (my-cym)*ny > 0:
            brg = (math.degrees(math.atan2(nx,ny))) % 360      # bearing from north, east=90
            # classify to nearest of N/E/S/W
            best = min(DIRS, key=lambda d: min(abs(brg-DIRS[d]), 360-abs(brg-DIRS[d])))
            facing[best] += L
            break
tot = sum(facing.values()) or 1

# ---- real sun path at this latitude ----
def noon_elev(decl): return 90 - abs(lat0 - decl)
winter, summer = noon_elev(-23.44), noon_elev(23.44)

# ---- compose a REAL daylight reading ----
order = sorted(facing, key=lambda d: -facing[d])
def pct(d): return round(facing[d]/tot*100)
south_good = facing['南'] >= max(facing.values())*0.8
west_warn  = facing['西'] > tot*0.18
lines = []
lines.append(f"这栋楼立面朝向分布：南 {pct('南')}% · 东 {pct('东')}% · 西 {pct('西')}% · 北 {pct('北')}%（按立面长度）。")
if south_good:
    lines.append(f"最长立面朝{order[0]}向" + ("，南向得全天日照，採光条件好。" if order[0]=='南' else f"；南向立面也较长，採光不差。"))
else:
    lines.append(f"最长立面朝{order[0]}向，南向立面偏少，正午直射日照相对有限。")
if west_warn:
    lines.append(f"西侧立面占 {pct('西')}%，夏季午后会有明显西晒，需注意遮阳。")
lines.append(f"位置纬度 {lat0:.2f}°N：正午太阳高度，冬至约 {winter:.0f}°、夏至约 {summer:.0f}°（真实日照角度，非估计）。")

print(f"▸ real-building reading · {os.path.basename(GML).split('_')[0]} · {len(blds)} 栋中最大一栋（{round(area(pts))} m²，高 {target['height'] or '?'} m）")
print(f"  位置：lat {lat0:.5f}  (东京 中野/杉並一带)")
print("\n【採光 · 真实朝向计算】")
for l in lines: print("  " + l)
print("\n（对比：户型图模式因图上没标朝向，採光只能说\"未知\"；接入真实坐标后，採光变成可算的事实。）")
