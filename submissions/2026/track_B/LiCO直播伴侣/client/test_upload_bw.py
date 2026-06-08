# -*- coding: utf-8 -*-
"""
实测到 :8443 网关的上传带宽。

方法：复用同一条 keep-alive 连接，向同一 endpoint 发送不同大小的请求体，
测量「上传完成 + 服务端首字节(响应头)」耗时。再用增量法抵消固定开销
（连接 RTT / 网关排队 / 服务端起步），估算纯上传带宽。

发送的是「故意非法的 JSON 垃圾字节」，服务端需要先把整个 body 读完才能解析并返回错误，
因此 time-to-response ≈ 上传时间 + 极小的解析时间，几乎不含模型推理 prefill。
"""
import time
import statistics
import httpx

BASE = "https://u1027991-ab00-48a182a5.westb.seetacloud.com:8443/v1"
URL = f"{BASE}/chat/completions"
API_KEY = "sk-crazy-thursday-viwo50"

# 测试的请求体大小（MB）
SIZES_MB = [0.05, 0.3, 0.6, 1.0]
TRIALS = 2  # 每个大小测几次取中位数


def make_body(mb: float) -> bytes:
    # 故意非法的 JSON：以 '{' 开头，后面跟一大段填充，服务端解析时会 400/422，
    # 但必须先读完整个 body。
    n = int(mb * 1024 * 1024)
    return b'{"x":"' + (b'A' * max(0, n - 16)) + b'"'


def main():
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    timing = {"started": 0.0, "headers_at": 0.0}

    def on_request(_req):
        pass

    def on_response(_resp):
        timing["headers_at"] = time.perf_counter()

    results = {}
    with httpx.Client(
        timeout=httpx.Timeout(connect=10.0, read=60.0, write=120.0, pool=10.0),
        event_hooks={"request": [on_request], "response": [on_response]},
        verify=True,
    ) as client:
        # 预热：建立 TLS 连接 + 让网关/服务端进入就绪态
        print("warmup...")
        try:
            warm = make_body(0.02)
            t0 = time.perf_counter()
            r = client.post(URL, headers=headers, content=warm)
            print(f"  warmup status={r.status_code}, took={time.perf_counter()-t0:.2f}s")
        except Exception as e:
            print(f"  warmup error: {type(e).__name__}: {e}")

        for mb in SIZES_MB:
            body = make_body(mb)
            real_mb = len(body) / (1024 * 1024)
            ttfbs = []
            status = None
            for _ in range(TRIALS):
                timing["headers_at"] = 0.0
                t0 = time.perf_counter()
                try:
                    r = client.post(URL, headers=headers, content=body)
                    status = r.status_code
                    ttfb = (timing["headers_at"] or time.perf_counter()) - t0
                    ttfbs.append(ttfb)
                    _ = r.content  # 读完，保持连接干净
                except Exception as e:
                    print(f"  [{real_mb:.2f}MB] error: {type(e).__name__}: {e}")
                time.sleep(0.3)
            if ttfbs:
                med = statistics.median(ttfbs)
                results[real_mb] = med
                speed = real_mb / med if med > 0 else 0
                print(
                    f"  body={real_mb:5.2f}MB  status={status}  "
                    f"TTFB median={med:6.2f}s  ({[f'{t:.2f}' for t in ttfbs]})  "
                    f"=> {speed:.2f} MB/s ({speed*8:.2f} Mbps)"
                )

    # 增量法：用最大与最小样本估算纯上传带宽
    print("\n==== 增量法估算纯上传带宽 ====")
    keys = sorted(results.keys())
    if len(keys) >= 2:
        small, big = keys[0], keys[-1]
        d_mb = big - small
        d_t = results[big] - results[small]
        if d_t > 0:
            bw = d_mb / d_t
            print(
                f"({big:.2f}MB - {small:.2f}MB) / ({results[big]:.2f}s - {results[small]:.2f}s) "
                f"= {d_mb:.2f}MB / {d_t:.2f}s"
            )
            print(f"=> 纯上传带宽 ≈ {bw:.2f} MB/s = {bw*8:.2f} Mbps")
            # 用这个带宽估算 0.58MB 包体的纯上传耗时
            payload = 0.58
            print(f"\n按此带宽，0.58MB 包体纯上传耗时 ≈ {payload/bw:.1f}s")
        else:
            print("时间差为负或为零，样本噪声过大，无法用增量法估算。")
    else:
        print("有效样本不足。")


if __name__ == "__main__":
    main()
