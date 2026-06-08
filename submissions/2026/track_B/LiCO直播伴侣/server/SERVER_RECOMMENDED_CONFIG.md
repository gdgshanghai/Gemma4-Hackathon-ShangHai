# Gemma 4 多模态服务端推荐配置

本文档基于当前 Gemma 4 服务端技术报告与实测运行结果，给出推荐的生产/评测部署配置。适用于将本服务部署到具备 NVIDIA GPU 的远程服务器，并由本地 OBS 客户端通过 OpenAI 兼容接口调用。

## 1. 推荐硬件配置

### 1.1 推荐配置（当前实测配置）

```text
GPU: NVIDIA H800 PCIe 80GB
显存: 80GB 级别
CPU: 16 核或以上
内存: 64GB 或以上
磁盘: 100GB 以上可用空间
OS: Ubuntu 22.04 / Linux 5.15+
Driver: 580.82.07 或兼容版本
CUDA: 13.0 或兼容 CUDA 12/13 运行环境
```

当前实测环境：

```text
GPU: NVIDIA H800 PCIe
显存: 81559 MiB
Driver: 580.82.07
CUDA: 13.0
服务端端口: 6006
Ollama 端口: 11434
```

### 1.2 最低可运行配置

```text
GPU: NVIDIA 48GB 显存级别，或更高
内存: 32GB+
磁盘: 80GB+
```

说明：Gemma 4 31B 多模态模型可通过量化降低显存占用，但并发、上下文长度和图片输入都会增加 KV cache 压力。评测/展示建议使用 80GB 级别 GPU。

---

## 2. 模型推荐配置

### 2.1 主模型

```bash
export OLLAMA_MODEL="gemma4-31b-mm"
export OLLAMA_VISION_MODEL="gemma4-31b-mm"
```

用途：

- 文本分析
- 图片理解
- 弹幕统计分析
- 多模态联合推理
- 最终中文 JSON 报告输出

选择理由：31B 规格在复杂直播语境、多模态融合、严格字段输出方面稳定性更好，是服务端主推理模型。

### 2.2 音频兼容模型

```bash
export OLLAMA_AUDIO_MODEL="gemma4-e4b-mm"
```

用途：

- 保留旧 Qwen 音频模型路由兼容
- 后续轻量音频模型扩展

当前推荐：联合推理中不依赖 E4B 做最终判断，而是使用 faster-whisper 转写音频，再交给 31B 统一分析。

### 2.3 Whisper ASR

```bash
export WHISPER_MODEL="/root/Gemma/whisper-base"
export WHISPER_DEVICE="cuda"
export WHISPER_COMPUTE="float16"
export ASR_MAX_CONCURRENCY="1"
```

说明：

- `cuda + float16` 在 H800 上速度最好。
- `ASR_MAX_CONCURRENCY=1` 是推荐值，避免多路 faster-whisper 同时争抢 GPU 导致延迟抖动。
- 如果 CUDA 运行库不可用，可临时改为：

```bash
export WHISPER_DEVICE="cpu"
export WHISPER_COMPUTE="int8"
```

但 CPU 模式延迟更高，仅建议故障兜底。

---

## 3. Ollama 推荐配置

建议在启动服务前设置：

```bash
export OLLAMA_HOST="http://127.0.0.1:11434"
export OLLAMA_NUM_PARALLEL="4"
export OLLAMA_KEEP_ALIVE="-1"
export OLLAMA_FLASH_ATTENTION="1"
export OLLAMA_KV_CACHE_TYPE="q8_0"
export OLLAMA_MAX_LOADED_MODELS="2"
```

参数说明：

| 参数 | 推荐值 | 说明 |
|---|---:|---|
| `OLLAMA_NUM_PARALLEL` | `4` | H800 显存充足，允许分轨音频、视觉、联合报告并发处理 |
| `OLLAMA_KEEP_ALIVE` | `-1` | 模型常驻显存，避免首请求冷加载 |
| `OLLAMA_FLASH_ATTENTION` | `1` | 开启 Flash Attention，降低长上下文开销 |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` | 压缩 KV cache，提升并发余量 |
| `OLLAMA_MAX_LOADED_MODELS` | `2` | 允许 31B 和 E4B/辅助模型共存 |

当前服务端实际启动脚本已包含以上配置。

---

## 4. FastAPI 服务推荐配置

```bash
export GEMMA_API_HOST="0.0.0.0"
export GEMMA_API_PORT="6006"
export GEMMA_API_KEY="<请替换为评测/部署环境的 API Key>"
```

推荐监听：

```text
0.0.0.0:6006
```

原因：

- AutoDL/云服务器自定义服务通常要求应用监听容器内 `6006`。
- `0.0.0.0` 允许外部代理或 SSH 隧道访问。
- 本地调试仍可通过 `127.0.0.1:6006` 访问。

---

## 5. 联网搜索推荐配置

```bash
export SEARCH_BACKENDS="baidu_ai"
export SEARCH_TIMEOUT="60"
export QIANFAN_SEARCH_MODEL="ernie-4.5-turbo-32k"
export QIANFAN_SEARCH_SOURCE="baidu_search_v2"
export QIANFAN_ENABLE_DEEP_SEARCH="0"
export QIANFAN_SEARCH_API_KEY="<百度千帆 API Key>"
```

说明：

- 国内中文事实检索优先使用百度千帆 AI Search。
- `SEARCH_TIMEOUT=60` 给联网搜索保留足够等待时间。
- `QIANFAN_ENABLE_DEEP_SEARCH=0` 默认关闭深搜索，避免单次请求时间过长。

### Browser-use / Playwright 深读配置

```bash
export AUTO_BROWSER_USE="1"
export BROWSER_USE_MODEL="gemma4-31b-mm"
export BROWSER_USE_MAX_STEPS="12"
export BROWSER_USE_WAIT_BETWEEN_ACTIONS="0.05"
export BROWSER_USE_IDLE_WAIT_SEC="0.2"
export SEARCH_READ_TOP_N="3"
export BROWSER_USE_DISABLE_EXTENSIONS="1"
export ANONYMIZED_TELEMETRY="false"
```

说明：

- TopN 建议为 3，保证证据覆盖与延迟平衡。
- 禁用扩展下载，避免国内网络环境下 CRX 下载阻塞。

---

## 6. 多模态联合请求推荐限制

服务端推荐限制：

```text
单次音频片段数: <= 2
单次图片数: <= 2
单段音频时长: <= 8 秒
图片格式: JPEG 优先
图片最长边: 1280px 左右
音频格式: mp3/m4a/opus 优先，wav 可用但体积较大
```

当前服务端常量：

```python
JOINT_MAX_AUDIO_CLIPS = 2
JOINT_MAX_IMAGES = 2
JOINT_MAX_AUDIO_SECONDS = 8.0
JOINT_ASR_TIMEOUT_SECONDS = 15.0
JOINT_MAIN_TIMEOUT_SECONDS = 600.0
```

说明：

- 已取消服务端输出 token 上限，不再强制截断 `max_tokens`。
- 已取消 18 秒短超时，联合主推理最多等待 600 秒，由客户端/评测端自行控制等待策略。
- 前端业务 UI 只应显示 `delta.content`，不要显示 `delta.reasoning`。

---

## 7. 网络连接推荐配置

### 7.1 推荐：SSH 隧道直连

```bash
ssh -p <SSH端口> root@<服务器SSH主机> -L 6006:127.0.0.1:6006 -N
```

客户端配置：

```text
BASE_URL=http://127.0.0.1:6006/v1
API_KEY=<GEMMA_API_KEY>
```

原因：

- 客户端在个人 PC 上，需要低延迟读取 OBS、音频、弹幕。
- 服务端在 H800 服务器上，需要大模型推理。
- SSH 隧道比 AutoDL `:8443` 网关上传更稳定，尤其是 0.5MB 以上联合请求体。

### 7.2 上传性能测试

```bash
head -c 580000 /dev/urandom | base64 | \
  curl -s -w "\nclient_total=%{time_total}s\n" \
  -X POST "${BASE_URL}/echo_size" \
  -H "Authorization: Bearer ${GEMMA_API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary @-
```

如果 `server_body_read_seconds` 很小但 `client_total` 很大，说明瓶颈在客户端到网关之间，应改用 SSH 隧道。

---

## 8. 一键启动推荐命令

首次部署：

```bash
cd /root/Gemma
bash scripts/setup_gemma311_cn.sh
```

日常启动：

```bash
cd /root/Gemma
bash start_gemma_api.sh
```

查看最新日志：

```bash
ls -t gemma_*.log | head -1
```

检查服务：

```bash
curl http://127.0.0.1:6006/health
```

检查 Ollama 模型：

```bash
curl http://127.0.0.1:11434/api/ps
```

---

## 9. 推荐 `.env` 示例

可保存为 `/root/Gemma/.env.recommended`，也可直接写入启动脚本或部署平台环境变量。

```bash
# Base
export GEMMA_API_HOST="0.0.0.0"
export GEMMA_API_PORT="6006"
export GEMMA_API_KEY="replace-with-your-api-key"
export HF_ENDPOINT="https://hf-mirror.com"

# Ollama
export OLLAMA_HOST="http://127.0.0.1:11434"
export OLLAMA_MODEL="gemma4-31b-mm"
export OLLAMA_VISION_MODEL="gemma4-31b-mm"
export OLLAMA_AUDIO_MODEL="gemma4-e4b-mm"
export OLLAMA_NUM_PARALLEL="4"
export OLLAMA_KEEP_ALIVE="-1"
export OLLAMA_FLASH_ATTENTION="1"
export OLLAMA_KV_CACHE_TYPE="q8_0"
export OLLAMA_MAX_LOADED_MODELS="2"

# Whisper ASR
export WHISPER_MODEL="/root/Gemma/whisper-base"
export WHISPER_DEVICE="cuda"
export WHISPER_COMPUTE="float16"
export ASR_MAX_CONCURRENCY="1"
export RECEIVED_AUDIO_DIR="/root/Gemma/received_audio"
export RECEIVED_REQUEST_DIR="/root/Gemma/received_requests"
export SAVE_REQUESTS="1"

# Search
export SEARCH_BACKENDS="baidu_ai"
export SEARCH_TIMEOUT="60"
export QIANFAN_SEARCH_API_KEY="replace-with-qianfan-key"
export QIANFAN_SEARCH_MODEL="ernie-4.5-turbo-32k"
export QIANFAN_SEARCH_SOURCE="baidu_search_v2"
export QIANFAN_ENABLE_DEEP_SEARCH="0"

# Browser-use / deep read
export AUTO_BROWSER_USE="1"
export BROWSER_USE_MODEL="gemma4-31b-mm"
export BROWSER_USE_MAX_STEPS="12"
export BROWSER_USE_WAIT_BETWEEN_ACTIONS="0.05"
export BROWSER_USE_IDLE_WAIT_SEC="0.2"
export SEARCH_READ_TOP_N="3"
export BROWSER_USE_DISABLE_EXTENSIONS="1"
export ANONYMIZED_TELEMETRY="false"
```

---

## 10. 推荐部署拓扑

```text
个人 PC / Windows 客户端
  ├─ OBS 截图
  ├─ 麦克风轨 / 桌面音频轨
  ├─ 弹幕 WebSocket / 本地 UI
  └─ HTTP OpenAI 兼容请求
          │
          │ 推荐 SSH 隧道: 127.0.0.1:6006 -> 服务器 127.0.0.1:6006
          ▼
H800 服务端 / Linux
  ├─ FastAPI :6006
  ├─ Ollama :11434
  ├─ gemma4-31b-mm
  ├─ gemma4-e4b-mm
  ├─ faster-whisper ASR
  └─ 百度 AI Search / browser-use / Playwright
```
