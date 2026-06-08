#!/usr/bin/env python3
"""Real-building qualitative reading: Gemma reads an EXTERIOR PHOTO across design
lenses (massing / material / context / critique), in plain language. Combine with
the deterministic daylight from real_read.py (when a location is known) for a full
real-building reading.

Usage: python pipeline/building_read.py photo.jpg [--lat .. --lng ..]
"""
import json, base64, urllib.request, re, sys, os

IMG = next((a for a in sys.argv[1:] if not a.startswith('--')), None)
if not IMG: sys.exit("usage: building_read.py photo.jpg [--lat --lng]")
B64 = base64.b64encode(open(IMG, "rb").read()).decode()
LAT = next((float(a.split('=')[-1]) for a in sys.argv if a.startswith('--lat')), None)
LNG = next((float(a.split('=')[-1]) for a in sys.argv if a.startswith('--lng')), None)

def chat(system, user, n=520):
    body = {"model": "gemma4:e4b",
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user, "images": [B64]}],
            "stream": False, "think": False, "keep_alive": "10m",
            "options": {"temperature": 0.3, "num_predict": n}}
    req = urllib.request.Request("http://localhost:11434/api/chat",
        data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=180).read()).get("message", {}).get("content", "").strip()

base = "你是资深建筑师，看一张建筑外观照，面向不懂建筑的普通人用大白话。只依据图中真实可见的推理，看不出说看不出，不编。忽略树、人、操场等无关物。"
def lens(prompt):
    out = chat(base, prompt + "\n输出:第一行一句话标题(≤14字),然后2-3句,不要列表符号。")
    lines = [l for l in out.splitlines() if l.strip()]
    title = re.sub(r'^[#*\-\d.、)\s]+', '', lines[0]).strip() if lines else ""
    return {"title": title[:24], "body": " ".join(lines[1:]).strip() or out}

print(f"▸ real-building reading · {os.path.basename(IMG)}")
LENS = {
 "体量": lens("这栋楼的体量/形态：是什么大形状，有没有切削、凹凸、倾斜?"),
 "材质": lens("外立面材质与处理：什么材料、什么肌理、反光还是哑光?"),
 "文脉": lens("它和周边的关系：尺度对话、突兀还是融入?"),
 "批评": lens("作为建筑师:1个强点+1个弱点(各给图中证据)+1条改进。"),
}
for k, v in LENS.items():
    print(f"\n【{k} · {v['title']}】\n  {v['body']}")

# combine with deterministic daylight if a location is given
if LAT is not None and LNG is not None:
    print(f"\n【採光 · 真实朝向（坐标 {LAT},{LNG}）】")
    try:
        from geo import fetch_tokyo_mesh
        gml, m2, m3 = fetch_tokyo_mesh(LAT, LNG)
        if gml:
            import subprocess
            r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "real_read.py"), gml],
                               capture_output=True, text=True)
            print("  " + "\n  ".join(l for l in r.stdout.splitlines() if "立面" in l or "太阳" in l or "西晒" in l))
        else:
            print(f"  (mesh {m3} 不在已缓存数据；通用城市需走 PLATEAU 数据目录)")
    except Exception as e:
        print(f"  采光计算需 PLATEAU 几何: {e}")
else:
    print("\n（给 --lat --lng 可叠加'真实朝向采光'：从 PLATEAU 几何确定性计算，不靠猜。）")
