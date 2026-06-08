import asyncio, base64, math, struct, time, wave, io
import httpx

BASE = "http://127.0.0.1:6006/v1/chat/completions"
HEADERS = {"Authorization": "Bearer sk-crazy-thursday-viwo50", "Content-Type": "application/json"}


def make_wav(seconds=5.0, freq=220.0, sr=16000):
    n = int(seconds * sr)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            frames += struct.pack("<h", int(12000 * math.sin(2*math.pi*freq*i/sr)))
        w.writeframes(bytes(frames))
    return buf.getvalue()

WAV = base64.b64encode(make_wav()).decode()

def audio_msg(label):
    return {"model": "gemma4-31b-mm", "stream": False, "max_tokens": 256, "messages": [{"role": "user", "content": [
        {"type": "text", "text": f"分析这段{label}音频，输出简短JSON。"},
        {"type": "input_audio", "input_audio": {"data": f"data:audio/wav;base64,{WAV}", "format": "wav"}},
    ]}]}

async def one(c, label):
    t0 = time.perf_counter()
    r = await c.post(BASE, headers=HEADERS, json=audio_msg(label))
    return label, time.perf_counter() - t0, r.status_code

async def main():
    async with httpx.AsyncClient(timeout=120) as c:
        await one(c, "warm")  # warm
        # serial
        t0 = time.perf_counter()
        await one(c, "mic"); await one(c, "desktop")
        serial = time.perf_counter() - t0
        # concurrent
        t0 = time.perf_counter()
        res = await asyncio.gather(one(c, "mic"), one(c, "desktop"))
        concurrent = time.perf_counter() - t0
        print(f"serial(mic+desktop) = {serial:.2f}s")
        print(f"concurrent(mic+desktop) = {concurrent:.2f}s  details={[(l,round(t,2),s) for l,t,s in res]}")

asyncio.run(main())
