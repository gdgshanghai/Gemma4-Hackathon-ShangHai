# Gemma 4 多模态 API（端口 6006）

## 模型部署（数据盘）

| Ollama 模型 | 文件位置 | 能力 |
|-------------|----------|------|
| **gemma4-31b-mm** | `/root/autodl-tmp/gemma_multimodal/` | 文本、**图像**（31B + mmproj-F16） |
| **gemma4-e4b-mm** | `/root/autodl-tmp/gemma_e4b_mm/` | 文本、图像、**原生音频** |
| **gemma4-31b** | 旧文本-only | 已由 31b-mm 替代 |

- **Ollama 版本**：需 **≥ 0.30.4**（Gemma4 多模态引擎）
- **31B Dense 官方无音频编码器**，音频必须用 E4B-mm

## 三种 API

| 类型 | 路径 | 后端 |
|------|------|------|
| text | `POST /api/v1/text/summarize` | gemma4-31b-mm |
| audio | `POST /api/v1/audio/summarize` | gemma4-e4b-mm 原生 `input_audio`（需真实语音，纯音调无效） |
| image | `POST /api/v1/image/analyze` | gemma4-31b-mm 原生 vision |

## 启动

```bash
# 确保 ollama serve 运行（0.30.4+）
nohup ollama serve > /root/Gemma/ollama_serve.log 2>&1 &

cd /root/Gemma
./start_gemma_api.sh
```

## 示例

```bash
curl http://127.0.0.1:6006/api/v1/examples
curl http://127.0.0.1:6006/docs
```

### 流式输出（SSE）

请求体加 `"stream": true`，使用 `curl -N`：

```bash
curl -N -X POST "http://127.0.0.1:6006/api/v1/text/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "请回答",
    "text": "张雪峰和巧乐兹的关系？",
    "enable_search": true,
    "include_thinking": true,
    "stream": true
  }'
```

事件类型：`status`（阶段状态）· `token`（逐字输出）· `tool_call` · `tool_result` · `thinking_round` · `done`（完整 JSON 结果）。

| phase | 含义 |
|-------|------|
| `thinking` | 31B 首轮推理 |
| `tool_call` | 调用 web_search |
| `search` / `search_done` | 国内搜索 |
| `deep_read` / `deep_read_done` | 深读 Top5 网页 |
| `answering` | 根据检索写最终答案 |
| `answer` | 回答 token 流 |

## 环境变量

| 变量 | 默认 |
|------|------|
| `OLLAMA_MODEL` | `gemma4-31b-mm` |
| `OLLAMA_AUDIO_MODEL` | `gemma4-e4b-mm` |
| `GEMMA_API_PORT` | `6006` |
| `WHISPER_FALLBACK` | `0`（设为 `1` 才在原生音频失败时用 Whisper） |
| `SEARCH_BACKENDS` | `baidu,sogou`（国内默认；可加 `ddg` 作兜底） |
| `ENABLE_BROWSER_USE` | `0`（`1` 时优先 browser-use，失败则降级国内搜索） |
| `BROWSER_USE_MODEL` | 空（建议 `gemma4-e4b-mm`，browser 子任务更快） |
| `BROWSER_USE_MAX_STEPS` | `12` |

### 自动深读 Top5（默认已开启）

模型在 unfamiliar 时会调用 `web_search`，此时自动：

1. 百度/搜狗取前 **5** 条结果  
2. **browser-use** 逐个打开阅读（`AUTO_BROWSER_USE=1`）  
3. 未安装 Playwright 时降级为 HTTP 抓取正文  

```bash
# 国内一键（Python 3.11 + 清华 pip + npmmirror Playwright，跳过 Google 扩展）
bash scripts/setup_gemma311_cn.sh
./start_gemma_api.sh
```

卡住时确认已设 `BROWSER_USE_DISABLE_EXTENSIONS=1`（避免从 Google 下载 uBlock）。
```

| 变量 | 默认 |
|------|------|
| `AUTO_BROWSER_USE` | `1` |
| `SEARCH_READ_TOP_N` | `5` |
| `BROWSER_USE_MAX_STEPS` | `25` |
