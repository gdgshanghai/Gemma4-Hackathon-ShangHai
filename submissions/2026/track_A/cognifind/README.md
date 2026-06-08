# CogniFind — 智能文件搜索与 AI 助手

基于 **Google Gemma 4 E2B（Edge 2B，端侧本地模型）** 的跨平台桌面端 AI 文件搜索助手，深度融合原生函数调用（Native Function Calling）与多模态（Multimodal）能力，实现"搜索即对话"的智能文件交互体验。完全本地运行，数据不出设备。

- **赛道**: A — AI Agent
- **技术栈**: Rust (桌面应用) + Python (AI 调用层) + Gemma 4 (大模型)
- **核心能力**: 原生函数调用 | 多模态理解 | 混合路由 | RAG 增强 | 跨平台热键唤出

---

## 目录

- [环境要求](#环境要求)
- [快速开始](#快速开始)
  - [1. 克隆项目](#1-克隆项目)
  - [2. 安装 Python 依赖](#2-安装-python-依赖)
  - [3. 部署 Gemma 4 推理服务](#3-部署-gemma-4-推理服务)
  - [4. 编译 Rust 桌面应用](#4-编译-rust-桌面应用)
  - [5. 运行](#5-运行)
- [核心源码说明](#核心源码说明)
- [Gemma 4 调用逻辑](#gemma-4-调用逻辑)
- [项目结构](#项目结构)
- [常见问题](#常见问题)

---

## 环境要求

| 组件 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| Python | 3.10 | 3.11+ | AI 调用层 |
| Rust | 1.80+ | 1.83+ | 桌面应用编译 |
| RAM | 8GB | 16GB+ | 模型加载 + 文件索引 |
| 磁盘 | 10GB | 20GB+ | 模型文件 ~4GB（GGUF） |
| GPU | 无需 | 无需 | Gemma 4 E2B 纯 CPU 推理 |

### 操作系统支持

- Windows 10/11 (x86_64)
- macOS 13+ (Apple Silicon / Intel)
- Linux (Ubuntu 22.04+, x86_64)

---

## 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url> cognifind
cd cognifind
```

### 2. 安装 Python 依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r 比赛/requirements.txt
```

### 3. 部署 Gemma 4 推理服务

#### 方式 A：llama.cpp（推荐，纯 CPU 本地推理）

Gemma 4 E2B 专为端侧设计，使用 llama.cpp 在 CPU 上即可高效运行。

```bash
# 克隆并编译 llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
cmake -B build
cmake --build build --config Release

# 下载 Gemma 4 E2B 模型（GGUF 格式）
# 从 Hugging Face 下载量化版本
huggingface-cli download google/gemma-4-2b-it-GGUF --local-dir ./models/gemma-4-e2b

# 启动 OpenAI 兼容 API 服务
./build/bin/llama-server \
    -m ./models/gemma-4-e2b/gemma-4-2b-it-Q4_K_M.gguf \
    --host 0.0.0.0 \
    --port 8000 \
    -c 4096 \
    -t 8
```

#### 方式 B：Ollama（零配置，Mac/Windows 推荐）

```bash
# 安装 Ollama
# Linux/macOS: curl -fsSL https://ollama.com/install.sh | sh
# Windows: https://ollama.com/download

# 拉取 Gemma 4 E2B 模型
ollama pull gemma4:2b

# 启动服务（默认端口 11434）
ollama serve
```

**Ollama 用户注意**：修改 `gemma4_client.py` 中的初始化参数：
```python
client = Gemma4Client(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    model="gemma4:2b",
)
```

#### 方式 C：CogniFind 内置推理（开箱即用）

CogniFind 桌面应用内置了 llama.cpp 推理引擎（`llama_infer.rs`），将 GGUF 模型文件放入 `CogniFind/models/` 目录后，应用会自动加载并推理，无需额外启动任何服务。

```bash
# 下载模型到 CogniFind 模型目录
mkdir -p CogniFind/models
huggingface-cli download google/gemma-4-2b-it-GGUF \
    gemma-4-2b-it-Q4_K_M.gguf \
    --local-dir ./CogniFind/models
```

### 4. 编译 Rust 桌面应用

```bash
# 安装 Rust（如已安装可跳过）
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 编译项目
cargo build --release

# 编译产物位于 target/release/
```

### 5. 运行

```bash
# 启动应用
./target/release/cognifind

# 或直接 cargo run
cargo run --release
```

**使用方式**：
- 双击 `Ctrl` 键唤出全局启动器
- 在搜索框输入问题，AI 将结合本地文件上下文回答
- 支持拖拽图片文件进行多模态理解

---

## 核心源码说明

### `gemma4_client.py` — Gemma 4 核心调用客户端

本文件是从 CogniFind 项目的 Rust 模块重构的 Python 实现，对应以下 Rust 源文件：

| Python 类/方法 | Rust 源文件 | 功能 |
|:---|:---|:---|
| `Gemma4Client` | `external_llm.rs` | OpenAI 兼容 API 调用 |
| `chat_with_tools()` | `engine.rs` | 原生函数调用 Agent 循环 |
| `vision_chat()` | `external_llm.rs` | 多模态 Vision 理解 |
| `build_rag_prompt()` | `rag.rs` | RAG prompt 构建 |
| `chat_with_hybrid_routing()` | `engine.rs` | 五维混合路由决策 |
| `AiService` | `ai_bridge.rs` | 推理生命周期管理 |

#### 快速使用示例

```python
from gemma4_client import Gemma4Client, ToolDefinition, RagContext, AiService

# 1. 初始化客户端
client = Gemma4Client(
    base_url="http://localhost:8000/v1",
    model="gemma-4-2b-it",
    temperature=0.7,
    max_tokens=2048,
)

# 2. 简单问答
answer = client.ask("请解释什么是 MoE 架构")
print(answer)

# 3. 原生函数调用 — 注册工具
def search_files(query: str, path: str = "/") -> list:
    """搜索本地文件"""
    import os, glob
    results = []
    for root, dirs, files in os.walk(path):
        for f in files:
            if query.lower() in f.lower():
                results.append({"name": f, "path": os.path.join(root, f)})
        if len(results) >= 10:
            break
    return results

client.register_tool(ToolDefinition(
    name="search_files",
    description="搜索本地文件，传入关键字和路径",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键字"},
            "path": {"type": "string", "description": "搜索路径，默认 /"},
        },
        "required": ["query"],
    },
    handler=search_files,
))

# 4. Agent 对话（自动调用工具）
response = client.chat_with_tools([
    {"role": "user", "content": "帮我找一下项目里的配置文件"},
])
print(response)

# 5. 多模态 — 图片理解
description = client.describe_image("screenshot.png")
print(description)

# 6. 图文问答
answer = client.ask_with_image("这张图片里有什么错误信息？", "error_screenshot.png")

# 7. RAG 增强问答
ctx = RagContext(
    query="配置文件",
    files=[{"name": "config.toml", "path": "/project/config.toml"}],
    snippets=[{"path": "/project/config.toml", "snippet": "[server]\nhost = \"0.0.0.0\"\nport = 8080"}],
)
prompt = client.build_rag_prompt(ctx, "这个项目的端口号是多少？")
answer = client.ask(prompt)
print(answer)

# 8. 混合路由（自动选择本地/外接模型）
answer = client.chat_with_hybrid_routing(ctx, "分析这个配置文件的网络设置")
print(answer)

# 9. 流式推理
service = AiService(client)
for token in service.submit(ctx, "总结项目的主要功能"):
    print(token, end="", flush=True)
```

---

## Gemma 4 调用逻辑

### 原生函数调用（Native Function Calling）流程

```
用户输入 "帮我找项目里的配置文件"
    │
    ▼
┌─────────────────────────────────────┐
│  System Prompt + 工具定义            │
│  - search_files: 搜索本地文件        │
│  - read_file_content: 读取文件内容   │
│  - get_file_metadata: 获取元信息     │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  Gemma 4 推理                        │
│  → 判断需要调用 search_files         │
│  → 生成 <|tool_call|>               │
│     search_files("配置文件")         │
│     <|tool_call|>                   │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  执行工具 → 返回结果                  │
│  <|tool_result|>                    │
│  [{"name": "config.toml", ...}]     │
│  <|tool_result|>                    │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  Gemma 4 继续推理                    │
│  → "找到了以下配置文件：             │
│     1. config.toml - /project/      │
│     2. settings.json - /project/    │
│     需要我读取哪个文件的内容？"       │
└─────────────────────────────────────┘
```

### 多模态处理流程

```
用户拖入图片文件 screenshot.png
    │
    ▼
┌─────────────────────────────────────────┐
│  image_to_data_uri()                     │
│  → Base64 编码                           │
│  → "data:image/png;base64,iVBORw0KG..." │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  POST /v1/chat/completions               │
│  {                                       │
│    "messages": [{                        │
│      "role": "user",                     │
│      "content": [                        │
│        {"type": "text", "text": "..."},  │
│        {"type": "image_url",             │
│         "image_url": {"url": "data:..."}}│
│      ]                                   │
│    }]                                    │
│  }                                       │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  Gemma 4 处理 <|image|> token            │
│  → 多模态视觉编码器理解图像               │
│  → 生成文本描述/分析结果                  │
└─────────────────────────────────────────┘
```

---

## 项目结构

```
cognifind/
├── 比赛/                          # 比赛提交材料
│   ├── README.md                  # 本文件
│   ├── 技术报告.md                 # 技术报告（模型选型 + 架构设计）
│   ├── requirements.txt           # Python 依赖
│   └── gemma4_client.py           # Gemma 4 核心调用源码
│
├── crates/                        # Rust 核心模块
│   ├── cognifind-ai/              # AI 引擎
│   │   └── src/
│   │       ├── engine.rs          # 推理路由引擎（混合决策）
│   │       ├── external_llm.rs    # 外接 API 调用（Gemma 4）
│   │       ├── rag.rs             # RAG prompt 构建
│   │       ├── audio.rs           # 音频转写
│   │       └── llama_infer.rs     # 本地模型推理
│   ├── cognifind-app/             # 应用服务层
│   │   └── src/
│   │       └── ai_bridge.rs       # AI 桥接服务
│   ├── filemind-ui/               # 前端 UI
│   │   └── src/
│   │       ├── launcher.rs        # 全局启动器
│   │       └── hotkey.rs          # 跨平台热键监听
│   └── cognifind-config/          # 配置管理
│       └── src/
│           └── config.rs          # AI 配置（模型路径、API 地址等）
│
├── src/                           # 应用入口
├── Cargo.toml                     # Rust 项目配置
└── docs/                          # 文档
```

---

## 常见问题

### Q: 没有 GPU 可以运行吗？

完全可以。Gemma 4 E2B 专为纯 CPU 推理设计，普通笔记本（8GB RAM）即可流畅运行，推理速度约 20-30 tokens/s。CogniFind 的核心设计理念就是"零 GPU 门槛"。

### Q: 模型推理太慢怎么办？

1. 使用量化版本（Q4_K_M 推荐），模型更小、推理更快
2. 增加 llama.cpp 的线程数（`-t` 参数）
3. 复杂任务会自动路由到外部大模型（混合路由模式）

### Q: 如何切换模型规格？

修改 `gemma4_client.py` 初始化时的 `model` 参数：
- `gemma-4-2b-it` — E2B 端侧模型（推荐，纯 CPU 运行）
- `gemma-4-4b-it` — 4B 基础模型（需更多内存）
- `gemma-4-26b-it` — 26B MoE（需 GPU）

### Q: 热键唤出延迟高？

热键轮询间隔为 8ms，响应延迟 < 100ms。若延迟异常，检查是否有其他程序占用 `Ctrl` 键。

### Q: 混合路由模式如何配置？

在 CogniFind 设置页面中：
1. 启用"混合模式"
2. 配置本地模型路径（.gguf 文件）
3. 配置外部 API 地址和模型名称

---