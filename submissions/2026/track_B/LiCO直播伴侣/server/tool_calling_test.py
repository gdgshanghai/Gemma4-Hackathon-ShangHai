import json, sys, time, urllib.request, urllib.parse, re

API = "http://127.0.0.1:11434/api/generate"
# Ollama 多模态：31B-mm（文本+工具调用；图像见 gemma_api）
MODEL = "gemma4-31b-mm"
Q = '<|"|>'  # Gemma4 quote marker

# Open-Meteo: 免密钥、国内访问较快、支持中文城市名
GEOCODE_API = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_API = "https://api.open-meteo.com/v1/forecast"

# WMO weather code -> 中文描述
WMO = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇", 51: "毛毛雨(弱)", 53: "毛毛雨(中)", 55: "毛毛雨(强)",
    56: "冻毛毛雨(弱)", 57: "冻毛毛雨(强)", 61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨(弱)", 67: "冻雨(强)", 71: "小雪", 73: "中雪", 75: "大雪", 77: "米雪",
    80: "阵雨(弱)", 81: "阵雨(中)", 82: "阵雨(强)", 85: "阵雪(弱)", 86: "阵雪(强)",
    95: "雷阵雨", 96: "雷阵雨伴小冰雹", 99: "雷阵雨伴大冰雹",
}

def wind_dir(deg):
    if deg is None:
        return "未知"
    dirs = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
    return dirs[int((deg + 22.5) // 45) % 8] + "风"

def call(prompt, stops, num_predict=256, timeout=600):
    body = {
        "model": MODEL,
        "prompt": prompt,
        "raw": True,
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": 0.0, "stop": stops, "num_predict": num_predict},
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(API, data=data, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read())
    dt = time.time() - t0
    return out.get("response", ""), out.get("done_reason"), dt

# ---- 真实天气后端: Open-Meteo ----
def _get_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "gemma4-tool-test/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def get_weather(city):
    # 1) 中文城市名 -> 经纬度
    q = urllib.parse.urlencode({"name": city, "count": 1, "language": "zh", "format": "json"})
    geo = _get_json(GEOCODE_API + "?" + q)
    results = geo.get("results") or []
    if not results:
        return {"city": city, "error": "未找到该城市"}
    loc = results[0]
    lat, lon = loc["latitude"], loc["longitude"]
    full_name = "".join(x for x in [loc.get("country"), loc.get("admin1"), loc.get("name")] if x)

    # 2) 经纬度 -> 实时天气 + 今日最高/最低
    q2 = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m",
        "daily": "temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min",
        "forecast_days": 1,
        "timezone": "Asia/Shanghai",
    })
    data = _get_json(FORECAST_API + "?" + q2)
    cur = data.get("current", {})
    daily = data.get("daily", {})

    def _today(key):
        arr = daily.get(key) or []
        return arr[0] if arr else None

    return {
        "city": full_name,
        "temperature_c": cur.get("temperature_2m"),
        "temp_max_c": _today("temperature_2m_max"),
        "temp_min_c": _today("temperature_2m_min"),
        "feels_like_c": cur.get("apparent_temperature"),
        "feels_like_max_c": _today("apparent_temperature_max"),
        "feels_like_min_c": _today("apparent_temperature_min"),
        "condition": WMO.get(cur.get("weather_code"), "未知"),
        "humidity_pct": cur.get("relative_humidity_2m"),
        "wind": wind_dir(cur.get("wind_direction_10m")),
        "wind_speed_kmh": cur.get("wind_speed_10m"),
        "observed_at": cur.get("time"),
    }

# ---- Gemma4 tool declaration block ----
TOOL_DECL = (
    "<|tool>declaration:get_weather{description:" + Q + "获取指定城市的实时天气" + Q +
    ",parameters:{properties:{ city:{description:" + Q + "城市名称，例如 北京" + Q +
    ",type:" + Q + "STRING" + Q + "} },required:[" + Q + "city" + Q + "],type:" + Q + "OBJECT" + Q + "}}<tool|>"
)

SYSTEM_TURN = "<|turn>system\n" + TOOL_DECL + "<turn|>\n"
_city = sys.argv[1] if len(sys.argv) > 1 else "北京"
USER = "%s今天天气怎么样？请告诉我今天的最高气温、最低气温和体感温度（用摄氏度）。" % _city
USER_TURN = "<|turn>user\n" + USER + "<turn|>\n"

bos = "<bos>"
prompt1 = bos + SYSTEM_TURN + USER_TURN + "<|turn>model\n"

print("=" * 70)
print("步骤1: 用户提问 ->", USER)
print("已向模型注入工具: get_weather(city)")
print("=" * 70)

resp1, dr1, dt1 = call(prompt1, stops=["<tool_call|>", "<turn|>", "<eos>"], num_predict=200)
print("\n[模型原始输出 #1] (%.1fs, done=%s):" % (dt1, dr1))
print(repr(resp1))

# ---- parse tool call ----
m = re.search(r"<\|tool_call>call:([A-Za-z_][A-Za-z0-9_]*)\{(.*?)\}\s*$", resp1, re.S)
if not m:
    m = re.search(r"call:([A-Za-z_][A-Za-z0-9_]*)\{(.*)\}", resp1, re.S)

if not m:
    print("\n[结果] 未解析到工具调用。原始输出见上。")
    sys.exit(2)

fname = m.group(1)
argstr = m.group(2)
print("\n[解析] 模型请求调用函数:", fname)
print("[解析] 原始参数串:", repr(argstr))

# parse args: key:<|"|>value<|"|>  or key:value
args = {}
for part in re.split(r",(?=[A-Za-z_][A-Za-z0-9_]*:)", argstr):
    if ":" not in part:
        continue
    k, v = part.split(":", 1)
    v = v.strip().replace(Q, "").strip()
    args[k.strip()] = v
print("[解析] 解析后的参数:", args)

if fname != "get_weather":
    print("[警告] 模型调用了非预期函数:", fname)

city = args.get("city", "北京")
result = get_weather(city)
print("\n[执行] 调用本地 get_weather(%r) =>" % city, result)

# ---- build tool response and ask again ----
resp_body = "{" + ",".join(
    (k + ":" + (Q + str(v) + Q if isinstance(v, str) else str(v))) for k, v in result.items()
) + "}"
tool_call_text = "<|tool_call>call:" + fname + "{" + argstr.strip() + "}<tool_call|>"
tool_resp_block = "<|tool_response>response:" + fname + resp_body + "<tool_response|>"

prompt2 = (
    bos + SYSTEM_TURN + USER_TURN
    + "<|turn>model\n" + tool_call_text
    + tool_resp_block
    + "<turn|>\n<|turn>model\n"
)

resp2, dr2, dt2 = call(prompt2, stops=["<turn|>", "<eos>"], num_predict=300)
final = resp2.replace(Q, "").strip()
print("\n" + "=" * 70)
print("[最终回答] (%.1fs, done=%s):" % (dt2, dr2))
print(final)
print("=" * 70)
print("\n[结论] Gemma 4 31B 工具调用验证: 成功" if final else "[结论] 最终回答为空")
