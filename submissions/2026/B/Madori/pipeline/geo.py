#!/usr/bin/env python3
"""Auto mesh-selection: lat/lng → Japan standard grid (地域メッシュ) code → fetch the
matching PLATEAU CityGML. Deterministic (JIS X 0410), so any coordinate resolves to a
specific mesh file with no lookup service.

  2nd mesh (10km, 6 digits) → the downloadable .zip unit
  3rd mesh (1km, 8 digits)  → the specific *_bldg_*.gml inside it

Usage: python pipeline/geo.py --lat 35.6638 --lng 139.5872
"""
import math, os, sys, glob, zipfile, urllib.request

def mesh_codes(lat, lng):
    p = int(lat*1.5)                       # 1st mesh lat (40-min rows)
    u = int(lng-100)                       # 1st mesh lng
    q = int((lat*60 - p*40)/5)             # 2nd mesh lat (5-min)
    v = int(((lng-100) - u)*8)             # 2nd mesh lng (7.5-min → *8)
    r = int((lat*60 - p*40 - q*5)*2)       # 3rd mesh lat (0.5-min → *2)
    w = int((((lng-100) - u) - v*0.125)/0.0125)   # 3rd mesh lng (0.0125-deg)
    return f"{p}{u}{q}{v}", f"{p}{u}{q}{v}{r}{w}"

def fetch_tokyo_mesh(lat, lng, cache="/tmp/plateau_dl"):
    """For the Tokyo-23ku 2020 dataset: lat/lng → the 1km bldg .gml (downloads the
    10km zip on first use, then reads from cache offline). Returns gml path or None."""
    m2, m3 = mesh_codes(lat, lng)
    hit = glob.glob(f"{cache}/bldg/{m3}_bldg_*.gml")
    if hit: return hit[0], m2, m3
    os.makedirs(cache, exist_ok=True)
    url = f"https://gic-plateau.s3-ap-northeast-1.amazonaws.com/2020/tokyo23ku/{m2}_2.zip"
    try:
        zp = os.path.join(cache, f"{m2}.zip")
        if not os.path.exists(zp):
            urllib.request.urlretrieve(url, zp)
        with zipfile.ZipFile(zp) as z: z.extract("bldg.zip", cache)
        with zipfile.ZipFile(os.path.join(cache, "bldg.zip")) as z: z.extractall(os.path.join(cache, "bldg"))
    except Exception as e:
        return None, m2, m3
    hit = glob.glob(f"{cache}/bldg/{m3}_bldg_*.gml")
    return (hit[0] if hit else None), m2, m3

if __name__ == "__main__":
    lat = lng = None
    for a in sys.argv:
        if a.startswith('--lat'): lat = float(a.split('=')[-1])
        if a.startswith('--lng'): lng = float(a.split('=')[-1])
    if lat is None: lat, lng = 35.66381, 139.58723
    m2, m3 = mesh_codes(lat, lng)
    print(f"lat {lat} lng {lng}  →  2次メッシュ {m2}  ·  3次メッシュ {m3}")
    gml, _, _ = fetch_tokyo_mesh(lat, lng)
    print(f"gml: {gml or '(not in tokyo23ku-2020 cache; 通用城市需走 PLATEAU 数据目录 API)'}")
