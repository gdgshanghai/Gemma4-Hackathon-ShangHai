# 给客户端 AI 的说明：联合多模态请求超时问题（服务端已排查）

> 适用现象：客户端日志反复出现
> `WARNING [api.qwen_multimodal]: Qwen joint report timeout (no streamed token in 60s)`

---

## 1. 结论先行（已更新：定位到上传链路）

**这不是服务端推理慢，也不是服务端 bug。** 服务端逐请求落盘 + 全链路打点，已拿到铁证：

> 客户端日志（22:29）：`upload + server-first-byte took 55.28s (body=0.58MB)`
> 客户端已把图片压到 130KB、整包降到 0.58MB —— **但仍然 55s**。

对照同一笔请求在服务端的记录（请求 `0fffd124`）：

```
客户端发出           22:28:41
        │  ← 上传 0.58MB 经 :8443 网关耗时 ≈ 54 秒   ←← 真正的瓶颈
服务端收完 body      22:29:35   （服务端 request_id 时间戳）
        │  ← 服务端 ASR 0.10s + 首 token 3.02s
首字节回到客户端     22:29:36
```

**结论：0.58MB 上传花了约 54 秒（≈11 KB/s），而服务端处理只用 3 秒。** 同时段服务端所有联合请求 `stream_ttfb` 都稳定在 ~3s。
**瓶颈不在包体大小，而在客户端 → AutoDL `:8443` HTTPS 网关的上传带宽极低。** 压缩图片只是把上传从更久降到 54s，治标不治本。

服务端本地用探测接口收 0.77MB 仅需 **0.001s**（5600+ Mbps），证明服务端/容器内完全没问题。

---

## 2. 客户端需要做的修改（已更新优先级）

### ⭐ 修改 0（最高优先级）：换掉 `:8443` 网关，改用 SSH 隧道直连（根治上传慢）

`:8443` 是 AutoDL 的 HTTPS 自定义服务网关，上传带宽被限得很低（实测 ~11KB/s）。
最有效的办法是用 **SSH 端口转发**绕过它，让客户端直连容器内 6006：

```bash
# 在客户端机器上建立隧道（AutoDL 实例页有 SSH 登录指令和端口）
ssh -p <SSH端口> root@<实例SSH主机> -L 6006:127.0.0.1:6006 -N
```

然后客户端 `BASE_URL` 改为：

```
http://127.0.0.1:6006/v1
```

SSH 隧道走的是数据通道，上传带宽通常远高于 `:8443` 网关，0.58MB 可在 1–2s 内传完。
**这是治本方案。** 如果暂时无法用 SSH 隧道，再依赖下面的压缩（治标）。

> 用第 4 节的 `/v1/echo_size` 探测接口，分别对 `:8443` 和 SSH 隧道各发一次同样大小的包，
> 对比客户端测得的总耗时，即可直观看到差距。

### 修改 1：截图改用 JPEG + 降分辨率（已完成 ✅，继续保持）

- 现状：以 `data:image/png;base64,...` 发送 1080p 无损 PNG（~1.47MB 原始）。
- 改为：JPEG，质量 ~70，最长边缩到 1280px。一般压到 **80–250KB**。
- 请求字段不变，仅前缀换成 `data:image/jpeg;base64,...`。
- **服务端已原生支持 JPEG，无需服务端任何改动。**

伪代码（示意）：
```python
# 发送前压缩
from PIL import Image
import io, base64

def encode_image_jpeg(img: Image.Image, max_side=1280, quality=70) -> str:
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w*scale), int(h*scale)))
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"
```

### 修改 2：音频改用压缩格式（WAV → mp3/m4a/opus）

- 现状：每段是未压缩 16kHz 单声道 PCM WAV（~157KB 原始）。
- 改为：mp3 / m4a / opus，单段约 **15–25KB**（约 10 倍压缩）。
- `input_audio.format` 字段填实际格式（如 `"mp3"` / `"m4a"`），data 前缀同步改为 `data:audio/mpeg;base64,...` 等。
- **服务端 ASR（faster-whisper + ffmpeg）已支持 wav/mp3/m4a/opus 解码，无需服务端改动。**

> 做完 1+2 后，联合请求体从 ~2.3MB 降到 **~250KB**，比现在能稳定到达的画面请求（1.6MB）还小，上传超时会消失。

### 修改 3：修正客户端超时计时逻辑

当前的「60s 内无流式 token」会把**上传耗时**也算进去。建议：

- 把"无 token"判定起点放在**请求体上传完成之后**，而不是 `create()` 调用一开始。
- 或直接把该超时阈值放宽到 **90–120s**（仅作为兜底）。
- 继续使用 `stream=true`（服务端已对流式做了即时 `: connected` 心跳 + 每 10s `: keepalive`，连接建立后绝不会再"60s 无字节"）。

### 修改 4（可选）：失败重试要带退避，且不要无限重试同一大包

- 若一次联合请求超时，**先确认是否上传失败**（见下方探测接口），不要立刻原样重试 2.3MB 大包，否则会加剧网关拥塞。

---

## 3. 服务端接口契约（确认客户端按此发送）

- **Endpoint**：`POST {BASE_URL}/v1/chat/completions`
  - `BASE_URL` 用 AutoDL「自定义服务」生成的 6006 映射地址，**不要带 `:8443`**（那是别的服务，会 404）。
- **鉴权**：`Authorization: Bearer <GEMMA_API_KEY>`
- **支持的输入**：
  - 图片：`image_url.url = data:image/jpeg;base64,...`（也支持 png/webp）
  - 音频：`input_audio.data = data:audio/<fmt>;base64,...`，`input_audio.format = "mp3"/"m4a"/"wav"/...`
  - 文本：`type:"text"`
- **服务端联合推理限制**（超出会返回 413，请遵守）：
  - 音频片段 ≤ 2 段
  - 图片 ≤ 2 张
  - 单段音频时长 ≤ 8 秒
  - 输出 `max_tokens` 服务端封顶 256（建议客户端显式设 200 左右，更快）
- **流式响应**：标准 OpenAI SSE；客户端应忽略以 `:` 开头的 SSE 注释行（心跳），它们不是 token。

---

## 4. 为定位/debug，我（服务端）希望看到客户端这几处代码

请把以下片段贴出来，便于确认问题已根除：

1. **联合报告请求的构建代码**（`api/qwen_multimodal.py` 里的 joint report / `_post_*report` 相关函数）——重点看：
   - 图片如何编码（PNG 还是 JPEG？是否压缩/缩放？）
   - 音频如何编码（WAV 还是压缩格式？采样率/时长？）
2. **HTTP 客户端的超时配置**（`base.py` 或创建 `OpenAI()/httpx` 客户端处）——重点看：
   - `timeout` 的各项值（connect / read / write / pool）
   - "no streamed token in 60s" 这个 60s 判定的具体实现位置和起点
3. **流式读取循环**——确认：
   - 是否把 `:` 开头的 SSE 注释/心跳误判为"无 token"
   - 首 token 计时从何时开始
4. **`BASE_URL` 的实际取值**（脱敏即可）——确认没有 `:8443`、且走的是 6006 映射域名。

---

## 5. 上传探测接口（已上线，请客户端用它定位/验证）

服务端已新增 `POST /v1/echo_size`：**只读取请求体、返回字节数与服务端读取耗时，不做任何推理。**

用法：客户端把真实联合请求体（或等大小的随机数据）POST 过去，自己记录**客户端总耗时**，再对比返回里的 `server_body_read_seconds`：

```bash
# 示例：发 0.58MB 测上传
head -c 580000 /dev/urandom | base64 | \
  curl -s -w "\n客户端总耗时: %{time_total}s\n" \
  -X POST "{BASE_URL}/v1/echo_size" \
  -H "Authorization: Bearer <GEMMA_API_KEY>" \
  -H "Content-Type: application/json" --data-binary @-
```

返回示例：
```json
{"bytes":786743,"megabytes":0.75,"server_body_read_seconds":0.001,"server_read_throughput_mbps":5600,"hint":"..."}
```

判读：
- **客户端总耗时很大、但 `server_body_read_seconds`≈0** → 网关在上游缓冲整个 body，瓶颈在客户端↔`:8443` 网关 → **请用 SSH 隧道**（修改 0）。
- 对 `:8443` 和 SSH 隧道各测一次，对比客户端总耗时即可验证 SSH 隧道是否解决。

---

## 6. 一句话给客户端 AI

> 真正瓶颈是 **`:8443` 网关上传带宽极低（0.58MB 传了 54s，服务端处理只用 3s）**。
> **首选：改用 SSH 隧道直连 6006（`BASE_URL=http://127.0.0.1:6006/v1`），绕过 `:8443`。**
> 同时把**音频也压成 mp3/m4a**（再省 ~370KB），并把"60s 无 token"计时改到**上传完成后**再起算。
> 服务端已上线 `/v1/echo_size` 探测接口，可先用它量化 `:8443` vs SSH 隧道的上传耗时。服务端本身无需任何改动。
