#!/usr/bin/env python3
"""Locate: pull lat/lng from a photo's EXIF GPS — the front door of leg B.

Most phone photos carry GPS. With it we know WHERE the building is → we can fetch
its real PLATEAU geometry and compute real orientation/daylight (see real_read.py).
No GPS (e.g. screenshots) → fall back to a manually supplied --lat/--lng.

Usage: python pipeline/locate.py photo.jpg
       python pipeline/locate.py --lat 35.6586 --lng 139.7454
"""
import sys, json

def manual():
    lat = lng = None
    for a in sys.argv:
        if a.startswith('--lat'): lat = float(a.split('=')[-1] if '=' in a else sys.argv[sys.argv.index(a)+1])
        if a.startswith('--lng'): lng = float(a.split('=')[-1] if '=' in a else sys.argv[sys.argv.index(a)+1])
    return lat, lng

def exif_gps(path):
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
    except ImportError:
        return None, "Pillow 未安装（pip install pillow）—— 改用 --lat/--lng 手填"
    try:
        exif = Image.open(path)._getexif() or {}
    except Exception as e:
        return None, f"读图失败: {e}"
    gps = {}
    for k, v in exif.items():
        if TAGS.get(k) == 'GPSInfo':
            for gk, gv in v.items(): gps[GPSTAGS.get(gk, gk)] = gv
    if 'GPSLatitude' not in gps or 'GPSLongitude' not in gps:
        return None, "照片无 GPS 信息（截图/已抹除）—— 改用 --lat/--lng 手填，或换一张手机原图"
    def dms(t, ref):
        d = float(t[0]) + float(t[1])/60 + float(t[2])/3600
        return -d if ref in ('S', 'W') else d
    lat = dms(gps['GPSLatitude'], gps.get('GPSLatitudeRef', 'N'))
    lng = dms(gps['GPSLongitude'], gps.get('GPSLongitudeRef', 'E'))
    return (lat, lng), None

if __name__ == "__main__":
    img = next((a for a in sys.argv[1:] if not a.startswith('--')), None)
    lat = lng = None; note = ""
    if img:
        res, note = exif_gps(img)
        if res: lat, lng = res
    if lat is None:
        lat, lng = manual()
    if lat is None:
        print(json.dumps({"ok": False, "note": note or "未提供位置：给一张带 GPS 的照片，或 --lat/--lng"}, ensure_ascii=False)); sys.exit(1)
    print(json.dumps({"ok": True, "lat": round(lat, 6), "lng": round(lng, 6),
                      "next": "→ 用此坐标取对应 PLATEAU mesh 渲染白模 + 跑 real_read.py 真实采光"}, ensure_ascii=False))
