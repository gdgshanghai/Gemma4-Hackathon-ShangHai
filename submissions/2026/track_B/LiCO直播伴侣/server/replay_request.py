#!/usr/bin/env python
"""回放已保存的真实客户端请求，定位耗时瓶颈。

用法:
  python replay_request.py                 # 回放最近一个保存的请求
  python replay_request.py <file.json>     # 回放指定请求
  python replay_request.py --all           # 依次回放全部保存的请求
  python replay_request.py <file> --stream # 强制流式回放，测首字节时间(TTFB)
"""
import asyncio, glob, json, os, sys, time
import httpx

BASE = os.getenv("GEMMA_BASE", "http://127.0.0.1:6006/v1/chat/completions")
KEY = os.getenv("GEMMA_API_KEY", "sk-crazy-thursday-viwo50")
REQ_DIR = os.getenv("RECEIVED_REQUEST_DIR", "/root/Gemma/received_requests")
HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def summarize(body):
    msgs = body.get("messages", [])
    n_audio = n_image = n_text = 0
    for m in msgs:
        c = m.get("content")
        if isinstance(c, list):
            for p in c:
                t = p.get("type")
                if t == "input_audio":
                    n_audio += 1
                elif t == "image_url":
                    n_image += 1
                elif t == "text":
                    n_text += 1
        elif isinstance(c, str):
            n_text += 1
    return f"model={body.get('model')} stream={body.get('stream')} max_tokens={body.get('max_tokens')} audio={n_audio} image={n_image} text_parts={n_text} msgs={len(msgs)}"


async def replay(path, force_stream=None):
    body = json.loads(open(path, encoding="utf-8").read())
    if force_stream is not None:
        body["stream"] = force_stream
    stream = body.get("stream", False)
    print(f"\n=== {os.path.basename(path)} ===")
    print("  " + summarize(body))
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=300) as c:
        if stream:
            ttfb = None
            n_chunks = 0
            try:
                async with c.stream("POST", BASE, headers=HEADERS, json=body) as r:
                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        if ttfb is None:
                            ttfb = time.perf_counter() - t0
                        n_chunks += 1
                total = time.perf_counter() - t0
                print(f"  [stream] status={r.status_code} TTFB={ttfb:.2f}s total={total:.2f}s chunks={n_chunks}")
            except Exception as e:
                print(f"  [stream] ERROR after {time.perf_counter()-t0:.2f}s: {type(e).__name__}: {e}")
        else:
            try:
                r = await c.post(BASE, headers=HEADERS, json=body)
                total = time.perf_counter() - t0
                try:
                    j = r.json()
                    u = j.get("usage", {})
                    fr = j.get("choices", [{}])[0].get("finish_reason")
                    print(f"  [non-stream] status={r.status_code} total={total:.2f}s prompt_tok={u.get('prompt_tokens')} completion_tok={u.get('completion_tokens')} finish={fr}")
                except Exception:
                    print(f"  [non-stream] status={r.status_code} total={total:.2f}s (non-json {len(r.text)}B)")
            except Exception as e:
                print(f"  [non-stream] ERROR after {time.perf_counter()-t0:.2f}s: {type(e).__name__}: {e}")


async def main():
    args = [a for a in sys.argv[1:]]
    force_stream = None
    if "--stream" in args:
        force_stream = True; args.remove("--stream")
    if "--no-stream" in args:
        force_stream = False; args.remove("--no-stream")
    files = sorted(glob.glob(os.path.join(REQ_DIR, "*.json")), key=os.path.getmtime)
    if not files:
        print(f"未找到已保存请求于 {REQ_DIR}")
        return
    if "--all" in args:
        for f in files:
            await replay(f, force_stream)
    elif args:
        await replay(args[0], force_stream)
    else:
        await replay(files[-1], force_stream)  # 最近一个

asyncio.run(main())
