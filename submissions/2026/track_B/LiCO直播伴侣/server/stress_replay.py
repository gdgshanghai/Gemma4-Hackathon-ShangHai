import asyncio, glob, json, os, time
import httpx

BASE = "http://127.0.0.1:6006/v1/chat/completions"
HEADERS = {"Authorization": "Bearer sk-crazy-thursday-viwo50", "Content-Type": "application/json"}
REQ_DIR = "/root/Gemma/received_requests"


def pick(audio, image, stream, n=1):
    out = []
    for f in sorted(glob.glob(os.path.join(REQ_DIR, "*.json")), key=os.path.getmtime, reverse=True):
        try:
            b = json.load(open(f))
        except Exception:
            continue
        msgs = b.get("messages", [])
        na = sum(1 for m in msgs if isinstance(m.get("content"), list) for p in m["content"] if p.get("type") == "input_audio")
        ni = sum(1 for m in msgs if isinstance(m.get("content"), list) for p in m["content"] if p.get("type") == "image_url")
        if na == audio and ni == image:
            b["stream"] = stream
            out.append((os.path.basename(f), b))
            if len(out) >= n:
                break
    return out


async def fire(c, label, body):
    t0 = time.perf_counter()
    if body.get("stream"):
        ttfb_token = None
        try:
            async with c.stream("POST", BASE, headers=HEADERS, json=body) as r:
                async for line in r.aiter_lines():
                    if line.startswith("data: ") and '"content"' in line:
                        if ttfb_token is None:
                            ttfb_token = time.perf_counter() - t0
            return label, "stream", round(ttfb_token or -1, 2), round(time.perf_counter() - t0, 2), r.status_code
        except Exception as e:
            return label, "stream", "ERR", round(time.perf_counter() - t0, 2), str(e)[:40]
    else:
        try:
            r = await c.post(BASE, headers=HEADERS, json=body)
            return label, "non-stream", "-", round(time.perf_counter() - t0, 2), r.status_code
        except Exception as e:
            return label, "non-stream", "-", round(time.perf_counter() - t0, 2), str(e)[:40]


async def main():
    jobs = []
    jobs += [("stream-asr", b) for _, b in pick(1, 0, True, 2)]
    jobs += [("joint", b) for _, b in pick(2, 1, False, 1)]
    jobs += [("vision", b) for _, b in pick(0, 1, False, 1)]
    print(f"并发触发 {len(jobs)} 个真实请求(同时发出)...")
    async with httpx.AsyncClient(timeout=120) as c:
        res = await asyncio.gather(*[fire(c, lbl, b) for lbl, b in jobs])
    print(f"{'label':12} {'mode':11} {'token_ttfb':>10} {'total':>7} status")
    for lbl, mode, ttfb, total, st in res:
        print(f"{lbl:12} {mode:11} {str(ttfb):>10} {str(total):>7} {st}")

asyncio.run(main())
