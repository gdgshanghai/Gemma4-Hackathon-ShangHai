# 给前端/客户端 AI 的说明：Gemma 4 流式返回读取与调试

## 1. 当前服务端结论

前端持续请求时，服务端已经能收到请求，并且通常在 8~16 秒内完成推理。最新定位到的关键点是：

- Ollama/Gemma 的流式 SSE chunk 里，经常会有 `choices[0].delta.reasoning`；
- `reasoning` 是模型思考过程，可能是英文，**不是正式业务结果**；
- 前端业务 UI **不要显示 reasoning**，只显示 `choices[0].delta.content`；
- 如果只收到 reasoning、没有 content，说明模型没有产出最终答案，服务端会返回中文降级 JSON。

因此：`reasoning` 只能用于 debug 日志，不能作为直播分析报告显示给用户。

---

## 2. 先用 curl 验证服务端是否真的在流式返回

请在客户端机器上，用实际的 `BASE_URL` 和 `GEMMA_API_KEY` 测试一个最小流式请求。

### 2.1 最小文本流式测试

```bash
curl -N --no-buffer \
  -X POST "${BASE_URL}/chat/completions" \
  -H "Authorization: Bearer ${GEMMA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"gemma4-31b-mm",
    "stream":true,
    "max_tokens":64,
    "messages":[{"role":"user","content":"请用一句话回复：连接正常"}]
  }'
```

注意：如果你的 `BASE_URL` 已经包含 `/v1`，那么路径是：

```text
${BASE_URL}/chat/completions
```

如果你的 `BASE_URL` 不包含 `/v1`，那么路径是：

```text
${BASE_URL}/v1/chat/completions
```

正确现象：终端应持续打印类似：

```text
: connected

data: {"choices":[{"delta":{"content":"..."}}]}
...
data: [DONE]
```

说明：以 `:` 开头的行是 SSE 注释/心跳，不是模型文本，客户端要忽略但不要当成错误。

---

## 3. Python/httpx 推荐读取方式

客户端不要只依赖 OpenAI SDK 的高级封装来判断是否有内容。建议在 debug 阶段先用 httpx 直接读 SSE，确认字段。

```python
import json
import time
import httpx

BASE_URL = "http://127.0.0.1:6006/v1"  # 或 AutoDL/SSH 隧道地址
API_KEY = "sk-..."

body = {
    "model": "gemma4-31b-mm",
    "stream": True,
    "max_tokens": 256,
    "messages": [
        {"role": "user", "content": "请输出一个简短JSON：{\"ok\":true,\"message\":\"连接正常\"}"}
    ],
}

url = f"{BASE_URL}/chat/completions"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

t0 = time.perf_counter()
first_any = None
first_text = None
parts: list[str] = []

with httpx.stream("POST", url, headers=headers, json=body, timeout=None) as resp:
    print("status=", resp.status_code)
    resp.raise_for_status()

    for raw_line in resp.iter_lines():
        if not raw_line:
            continue

        # 1. SSE 心跳/注释行：服务端会发 : connected / : keepalive
        #    这些行证明连接还活着，但不是模型文本。
        if raw_line.startswith(":"):
            if first_any is None:
                first_any = time.perf_counter() - t0
                print(f"first_sse_byte={first_any:.2f}s line={raw_line!r}")
            continue

        # 2. 标准 SSE 数据行
        if not raw_line.startswith("data: "):
            print("unknown_sse_line:", raw_line[:200])
            continue

        data_str = raw_line[len("data: "):]
        if data_str == "[DONE]":
            print("DONE")
            break

        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            print("bad_json:", data_str[:200])
            continue

        choice = (event.get("choices") or [{}])[0]
        delta = choice.get("delta") or {}

        # 3. 业务显示：只读 content，不要显示 reasoning
        # reasoning 是模型思考过程，可能是英文，只能写 debug 日志。
        debug_reasoning = delta.get("reasoning") or ""
        text = delta.get("content") or ""
        if text:
            if first_text is None:
                first_text = time.perf_counter() - t0
                print(f"first_text={first_text:.2f}s")
            parts.append(text)
            print(text, end="", flush=True)

        finish_reason = choice.get("finish_reason")
        if finish_reason:
            print("\nfinish_reason=", finish_reason)

answer = "".join(parts)
print("\nanswer_len=", len(answer))
print("answer_preview=", answer[:500])
```

关键点：

- 不要把 `: connected` / `: keepalive` 当成模型内容；
- 不要因为某些 chunk 的 `content == ""` 就认为没有返回；
- 读取文本时用：

```python
text = delta.get("content") or ""  # 业务 UI 不要显示 delta.reasoning
```

---

## 4. 如果使用 OpenAI Python SDK，建议这样写

SDK 不一定暴露非标准的 `reasoning` 字段；所以如果继续用 SDK，高级对象可能看不到文本。推荐：

1. debug 阶段先用上面的 `httpx.stream`；
2. 如果必须用 SDK，打印每个 chunk 的原始结构或 `model_dump()`，确认字段名；
3. 客户端聚合业务结果时只使用 `content`；`reasoning` 只写 debug 日志，不显示给用户。

示例：

```python
async for chunk in stream:
    # 不同 SDK 版本对象结构不同，先 dump 出来确认
    raw = chunk.model_dump() if hasattr(chunk, "model_dump") else chunk
    choice = raw.get("choices", [{}])[0]
    delta = choice.get("delta", {}) or {}
    text = delta.get("content") or ""  # 业务 UI 不要显示 delta.reasoning
    if text:
        buffer.append(text)
        update_ui("".join(buffer))
```

如果 SDK 完全拿不到 `reasoning`，请切换到 `httpx.stream` 直接解析 SSE。

---

## 5. 前端 UI 层不要等完整 JSON 才显示

当前模型有时会先输出推理文本，再输出结构化 JSON；如果前端逻辑是“等到能 `json.loads()` 成功才显示”，用户会看到长时间空白。

建议：

- SSE 每收到一段文本就更新 debug 面板或临时文本区；
- 最终再尝试从完整文本中提取 JSON；
- 如果最终不是合法 JSON，也要把原始文本显示出来，避免“无返回”。

伪代码：

```python
buffer = []

for text in stream_text_chunks():
    buffer.append(text)
    raw = "".join(buffer)

    # 先显示原始流式文本，保证用户看到进度
    ui.raw_model_output = raw

    # 再尝试解析 JSON，解析失败不要清空 UI
    try:
        ui.parsed_report = json.loads(raw)
    except Exception:
        pass
```

---

## 6. 超时判断请分三类，不要混在一起

客户端日志里现在常见：`upload + server-first-byte took XXs`。建议拆成三段：

1. **上传耗时**：请求体从客户端发出到服务端收到；
2. **服务端首字节耗时**：服务端收到 body 后，到第一条 SSE；
3. **首个模型文本耗时**：第一段 `delta.content` 或 `delta.reasoning` 出现。

注意：服务端会立即发 `: connected` 心跳，这只能说明连接建立，不代表模型 token 已出现。

建议日志字段：

```text
body_size_mb=...
http_status=...
first_sse_byte=...
first_text_chunk=...
total_time=...
content_chunks=...
reasoning_chunks=...
raw_sse_lines=...
```

如果 `raw_sse_lines > 0` 但 `content_chunks == 0`，不要把 reasoning 当报告展示；这代表模型没有给出最终 content，应该展示服务端降级 JSON 或提示重试。

---

## 7. 上传链路仍需单独测试

服务端已提供上传探测接口：

```text
POST /v1/echo_size
```

这个接口只读 body，不做推理。请用它分别测试：

- AutoDL `:8443` 地址；
- SSH 隧道 `http://127.0.0.1:6006/v1`。

示例：

```bash
head -c 580000 /dev/urandom | base64 | \
  curl -s -w "\nclient_total=%{time_total}s\n" \
  -X POST "${BASE_URL}/echo_size" \
  -H "Authorization: Bearer ${GEMMA_API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary @-
```

如果返回：

```json
{"server_body_read_seconds":0.001}
```

但 `client_total` 很大，说明慢在客户端到网关/隧道之间，不是服务端推理。

---

## 8. 服务端目前的健康基线

服务端最近真实联合请求表现：

- 请求体约 460~540KB；
- `audio=2 image=1 stream=True`；
- 服务端 `stream_ttfb` 通常约 2.5~3.0s；
- `stream_total` 通常约 8s；
- 若前端看不到内容，优先检查 SSE 解析和 UI 显示逻辑。

---

## 9. 请前端 AI 回传这些 debug 信息

如果修改后仍“无返回”，请回传以下日志：

1. 请求 `BASE_URL`（可脱敏，但要看是否含 `:8443` 或是否走 SSH 隧道）；
2. `body_size_mb`；
3. HTTP status；
4. `first_sse_byte`；
5. `first_text_chunk`；
6. `content_chunks` / `reasoning_chunks` / `raw_sse_lines`；
7. 前 5 条原始 SSE 行（脱敏即可）；
8. UI 层是否等待完整 JSON 后才显示。

拿到这些就能判断是：上传链路、SSE 字段解析、还是 UI JSON 解析策略的问题。
