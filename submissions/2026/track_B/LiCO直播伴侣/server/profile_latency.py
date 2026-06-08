import asyncio, base64, json, math, struct, time, wave, io
import httpx

BASE = "http://127.0.0.1:6006/v1/chat/completions"
KEY = "sk-crazy-thursday-viwo50"
HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def make_wav(seconds=5.0, freq=220.0, sr=16000):
    n = int(seconds * sr)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            v = int(12000 * math.sin(2 * math.pi * freq * i / sr))
            frames += struct.pack("<h", v)
        w.writeframes(bytes(frames))
    return buf.getvalue()


WAV_B64 = base64.b64encode(make_wav()).decode()
PNG_B64 = open("/root/Gemma/_test_img.b64").read().strip()
IMG_MIME = "jpeg"


async def call(label, messages, extra=None):
    body = {"model": "gemma4-31b-mm", "messages": messages, "stream": False, "max_tokens": 256}
    if extra:
        body.update(extra)
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(BASE, headers=HEADERS, json=body)
    dt = time.perf_counter() - t0
    try:
        j = r.json()
        usage = j.get("usage", {})
        ct = usage.get("completion_tokens", "?")
        pt = usage.get("prompt_tokens", "?")
    except Exception:
        ct = pt = "?"
    print(f"[{label}] status={r.status_code} time={dt:.2f}s prompt_tok={pt} completion_tok={ct}")
    return dt


async def main():
    # warm up
    await call("warmup-text", [{"role": "user", "content": "你好，请回复一个字。"}])

    await call("text-only", [{"role": "user", "content": "请用一句话总结：今天天气不错。"}])

    await call("image-only", [{"role": "user", "content": [
        {"type": "text", "text": "请描述这张图。"},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{PNG_B64}"}},
    ]}])

    await call("audio-only", [{"role": "user", "content": [
        {"type": "text", "text": "请分析这段音频说了什么。"},
        {"type": "input_audio", "input_audio": {"data": f"data:audio/wav;base64,{WAV_B64}", "format": "wav"}},
    ]}])

    await call("joint(img+2audio)", [{"role": "user", "content": [
        {"type": "text", "text": "联合分析画面与两段音频，输出简短JSON。"},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{PNG_B64}"}},
        {"type": "input_audio", "input_audio": {"data": f"data:audio/wav;base64,{WAV_B64}", "format": "wav"}},
        {"type": "input_audio", "input_audio": {"data": f"data:audio/wav;base64,{WAV_B64}", "format": "wav"}},
    ]}])


asyncio.run(main())
