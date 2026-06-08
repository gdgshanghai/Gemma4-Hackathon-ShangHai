# Gemma 4 多模态服务端部署 README

本 README 面向评委或复现实验人员，说明如何把本程序部署到另一台服务器，并通过 OpenAI 兼容接口为客户端提供 Gemma 4 多模态分析服务。

## 1. 功能概览

服务端提供：

- OpenAI 兼容接口：`POST /v1/chat/completions`
- 上传探测接口：`POST /v1/echo_size`
- 传统业务接口：
  - `POST /api/v1/text/summarize`
  - `POST /api/v1/audio/summarize`
  - `POST /api/v1/image/analyze`
- 健康检查：`GET /health`

核心能力：

- Gemma 4 31B 多模态图文联合推理。
- Gemma 4 E4B 音频模型兼容配置。
- faster-whisper 本地 ASR 工具。
- 百度千帆 AI Search、browser-use/Playwright 深读。
- OpenAI 风格 SSE 流式返回。
- 请求落盘与回放测试。

## 2. 推荐硬件环境

本项目当前测试硬件：

- GPU：NVIDIA H800 PCIe
- 显存：约 80GB（`81559 MiB`）
- Driver：580.82.07
- CUDA：13.0
- OS：Linux 5.15.0-161-generic
- 推理引擎：Ollama 0.30.4
- 服务端 Python：Conda 环境 `gemma311`，Python 3.11

当前运行显存参考：

- `gemma4-31b-mm` 常驻约 22~25GB 显存。
- faster-whisper 约占 0.7GB 显存。

最低建议：

- NVIDIA GPU 显存 ≥ 32GB（低并发或更低量化模型）。
- 推荐 48GB~80GB 显存以稳定运行 31B 多模态模型和并发请求。
- CPU 8 核以上，内存 32GB 以上。
- 磁盘预留模型与日志空间，建议 100GB 以上。

## 3. 目录结构

```text
/root/Gemma
├── gemma_api/
│   ├── main.py                    # FastAPI 入口
│   ├── config.py                  # 配置
│   ├── routers/
│   │   ├── openai_compat.py       # OpenAI 兼容与多模态联合推理核心
│   │   ├── text.py
│   │   ├── audio.py
│   │   └── image.py
│   └── services/
│       ├── agent.py               # 工具调用与文本 Agent
│       ├── ollama_client.py       # Ollama 封装
│       ├── search.py              # 百度 AI Search / browser-use
│       ├── deep_read.py           # Playwright 深读
│       └── stt.py                 # faster-whisper ASR 与音频诊断
├── scripts/setup_gemma311_cn.sh   # 国内镜像安装脚本
├── start_gemma_api.sh             # 一键后台启动脚本
├── gguf/Modelfile                 # 31B GGUF 模型配置示例
├── whisper-base/                  # 本地 Whisper 模型目录
├── received_requests/             # 请求落盘目录
├── received_audio/                # 音频落盘目录
├── replay_request.py              # 请求回放工具
├── stress_replay.py               # 并发压测工具
└── TECHNICAL_REPORT.md            # 技术报告
```

## 4. 安装步骤

### 4.1 安装系统依赖

确保服务器已安装：

```bash
apt-get update
apt-get install -y curl git ffmpeg build-essential
```

需要 NVIDIA 驱动、CUDA 运行环境和可用的 `nvidia-smi`。

### 4.2 安装 Ollama

如果服务器未安装 Ollama：

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

国内环境可提前准备 Ollama 安装包并放入服务器。本项目目录中曾使用 `ollama-linux-amd64.tar.zst` 作为离线安装来源。

启动 Ollama：

```bash
ollama serve
```

服务默认监听：

```text
http://127.0.0.1:11434
```

### 4.3 准备 Gemma 4 模型

本服务使用两个模型名：

```bash
export OLLAMA_MODEL=gemma4-31b-mm
export OLLAMA_VISION_MODEL=gemma4-31b-mm
export OLLAMA_AUDIO_MODEL=gemma4-e4b-mm
```

如果使用 GGUF 文件，可参考 `gguf/Modelfile`：

```text
FROM ./gemma-4-31B-it-Q4_K_M.gguf
PARAMETER num_ctx 8192
PARAMETER temperature 1.0
PARAMETER top_k 64
PARAMETER top_p 0.95
```

创建 Ollama 模型示例：

```bash
cd /root/Gemma/gguf
ollama create gemma4-31b-mm -f Modelfile
```

E4B 模型按实际模型文件/Modelfile 创建为：

```bash
ollama create gemma4-e4b-mm -f <E4B_Modelfile>
```

验证模型：

```bash
ollama list
curl http://127.0.0.1:11434/api/ps
```

### 4.4 安装 Python 3.11 环境与依赖

推荐使用项目脚本（已配置国内源）：

```bash
cd /root/Gemma
bash scripts/setup_gemma311_cn.sh
```

该脚本会：

- 创建/复用 Conda 环境 `/root/miniconda3/envs/gemma311`
- 使用清华源安装 Python 依赖
- 使用 npmmirror 下载 Playwright Chromium
- 禁用 browser-use 扩展下载，避免 Google CRX 网络问题

手动安装等价命令：

```bash
conda create -n gemma311 python=3.11 -y
/root/miniconda3/envs/gemma311/bin/pip install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple
/root/miniconda3/envs/gemma311/bin/pip install -r gemma_api/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright /root/miniconda3/envs/gemma311/bin/playwright install chromium
```

### 4.5 安装/准备 Whisper 模型

默认路径：

```text
/root/Gemma/whisper-base
```

如果在线下载不稳定，可在可联网环境下载 faster-whisper base 模型后复制到该目录。启动脚本默认：

```bash
export WHISPER_MODEL=/root/Gemma/whisper-base
export WHISPER_DEVICE=cuda
export WHISPER_COMPUTE=float16
```

若遇到 `libcublas.so.12` 或 cuDNN 缺失，可在 `gemma311` 环境安装 CUDA 12 Python wheel：

```bash
/root/miniconda3/envs/gemma311/bin/pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

启动脚本会将对应库路径加入 `LD_LIBRARY_PATH`。

### 4.6 配置 API Key 与搜索

关键环境变量：

```bash
export GEMMA_API_KEY="<你的服务端API Key>"
export QIANFAN_SEARCH_API_KEY="<百度千帆AI Search API Key>"
export SEARCH_BACKENDS="baidu_ai"
```

也可以把千帆 Key 写入：

```text
/root/Gemma/.qianfan_search_api_key
```

## 5. 一键启动

推荐直接运行：

```bash
cd /root/Gemma
bash start_gemma_api.sh
```

脚本会：

- 设置 Hugging Face 国内镜像
- 设置 Ollama 并发和 KV cache 参数
- 设置模型名
- 设置 browser-use/search 参数
- 设置 CUDA 12 动态库路径
- 确保 Ollama 正在运行
- 后台启动 FastAPI/Uvicorn
- 将日志写入 `gemma_YYYYMMDD_HHMMSS.log`

默认监听：

```text
0.0.0.0:6006
```

## 6. 验证服务

### 6.1 健康检查

```bash
curl http://127.0.0.1:6006/health
```

### 6.2 OpenAI 兼容最小请求

```bash
curl -s -X POST "http://127.0.0.1:6006/v1/chat/completions" \
  -H "Authorization: Bearer $GEMMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"gemma4-31b-mm",
    "messages":[{"role":"user","content":"请用一句话回答：服务是否正常？"}],
    "stream":false
  }'
```

### 6.3 流式请求测试

```bash
curl -N --no-buffer -X POST "http://127.0.0.1:6006/v1/chat/completions" \
  -H "Authorization: Bearer $GEMMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"gemma4-31b-mm",
    "stream":true,
    "messages":[{"role":"user","content":"请输出一个简短中文JSON"}]
  }'
```

### 6.4 上传链路测试

```bash
head -c 580000 /dev/urandom | base64 | \
  curl -s -w "\nclient_total=%{time_total}s\n" \
  -X POST "http://127.0.0.1:6006/v1/echo_size" \
  -H "Authorization: Bearer $GEMMA_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @-
```

## 7. 客户端连接方式

### 7.1 推荐：SSH 隧道

由于 AutoDL `:8443` HTTPS 网关上传速度可能很慢，推荐客户端 PC 使用 SSH 隧道：

```bash
ssh -p <SSH端口> root@<服务器SSH主机> -L 6006:127.0.0.1:6006 -N
```

客户端配置：

```text
BASE_URL=http://127.0.0.1:6006/v1
API_KEY=<GEMMA_API_KEY>
```

### 7.2 自定义服务 URL

也可使用 AutoDL 自定义服务映射到容器内 6006，但需要用 `/v1/echo_size` 测试上传性能。不要误用映射到 Jupyter/其它服务的 `:8443` 端口。

## 8. 联合多模态请求格式

客户端发送 OpenAI 兼容 messages：

```json
{
  "model": "gemma4-31b-mm",
  "stream": true,
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "任务目标：...严格输出JSON..."},
        {"type": "text", "text": "弹幕/统计 JSON：..."},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},
        {"type": "input_audio", "input_audio": {"data": "data:audio/wav;base64,...", "format": "wav"}},
        {"type": "input_audio", "input_audio": {"data": "data:audio/wav;base64,...", "format": "wav"}}
      ]
    }
  ]
}
```

建议客户端：

- 图片使用 JPEG，最长边 1280px 左右。
- 音频尽量使用 mp3/m4a/opus，减少上传体积。
- 业务 UI 只显示 `delta.content`，不要显示 `delta.reasoning`。
- 不要等待完整 JSON 才显示，可先显示原始 content，再解析 JSON。

## 9. 调试与回放

服务端会保存请求：

```text
received_requests/<request_id>.json
received_audio/<request_id>-N.wav
```

回放最近请求：

```bash
python replay_request.py
```

回放指定请求：

```bash
python replay_request.py received_requests/<request_id>.json --stream
```

并发压测：

```bash
python stress_replay.py
```

## 10. 常见问题

### 10.1 客户端 HTTP 200 但 UI 没有内容

检查 SSE 解析：

- 业务只展示 `delta.content`。
- `delta.reasoning` 是模型思考过程，只写 debug，不展示。
- `: connected` / `: keepalive` 是 SSE 心跳，忽略即可。

### 10.2 请求上传很慢

用 `/v1/echo_size` 对比 AutoDL 网关和 SSH 隧道。若网关慢，改用 SSH 隧道。

### 10.3 ASR 报 CUDA/cuBLAS 错误

安装 CUDA 12 运行库 wheel，并确认 `LD_LIBRARY_PATH` 已包含 nvidia/cublas、nvidia/cudnn、nvidia/cuda_nvrtc。

### 10.4 模型只输出 reasoning

这是 Ollama/Gemma OpenAI 兼容层可能出现的字段行为。服务端已尽量屏蔽 reasoning 并要求中文 JSON。若仍发生，建议缩短输入、减少弹幕样例、或降低任务复杂度。
