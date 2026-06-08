# n8n Agent — Gemma 4 Native Function Calling

基于 Google **Gemma 4** 原生函数调用能力，一键生成可执行的 **n8n 工作流 JSON**。

- **赛道**: A (AI Agent)
- **队伍**: fayex
- **模型**: Gemma 4 E4B-it / E2B-it (GGUF Q4_K_M)
- **截止**: 2026-06-08

## 痛点

n8n 工作流的搭建需要手动拖拽配置节点，学习成本高、效率低。本 Agent 通过自然语言对话，自动生成完整可用的 n8n 工作流 JSON，支持多轮修改和验证。

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                        用户                              │
│              (自然语言描述工作流需求)                       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    n8n Agent                             │
│                                                          │
│  ┌──────────────┐   ┌─────────────────────────────────┐  │
│  │ Conversation │   │         Tool Engine              │  │
│  │   Memory     │   │                                  │  │
│  │              │   │  ┌───────────────────────────┐   │  │
│  │ - history[]  │   │  │ generate_n8n_workflow()   │   │  │
│  │ - workflow   │───▶  │ modify_n8n_workflow()     │   │  │
│  │   state      │   │  │ validate_n8n_workflow()   │   │  │
│  └──────────────┘   │  └───────────────────────────┘   │  │
│                     └──────────────┬──────────────────┘  │
└────────────────────────────────────┼─────────────────────┘
                                     │
                  Native Function Calling (OpenAI 格式)
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────┐
│                    Gemma 4 模型                           │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │         llama.cpp / vLLM 推理引擎                 │   │
│  │                                                  │   │
│  │  Gemma 4 E4B-it (主) / E2B-it (备)               │   │
│  │  GGUF Q4_K_M / Safetensors BF16                  │   │
│  │                                                  │   │
│  │  chat template 原生支持:                           │   │
│  │  <|tool|> → <|tool_call|> → <|tool_response|>    │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                                     │
                             输出: 结构化 JSON
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────┐
│                    n8n 平台                              │
│                                                          │
│  导入工作流 JSON → 自动生成可视化节点 → 执行自动化         │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ Webhook  │─▶│   IF     │─▶│ Feishu   │               │
│  │ (trigger)│  │ (filter) │  │ (action) │               │
│  └──────────┘  └──────────┘  └──────────┘               │
└─────────────────────────────────────────────────────────┘
```

## 数据流

```
Step 1:  用户输入 → Agent.run("创建 webhook 接收 push 事件")
Step 2:  Memory 构造 messages (system + history + user)
Step 3:  API 发送 chat.completions (含 tools 定义)
Step 4:  Gemma 4 解析 → 调用 generate_n8n_workflow({
           "name": "GitHub Push → Feishu",
           "nodes": [...],
           "connections": {...}
         })
Step 5:  Tool Engine 执行 → 生成结构化 JSON
Step 6:  Memory 更新 workflow_state
Step 7:  返回结果给用户
```

## Native Function Calling 详解

Gemma 4 的 chat template 原生支持工具调用，无需 prompt hacking：

**工具定义** (OpenAI 格式):
```json
{
  "name": "generate_n8n_workflow",
  "description": "根据需求生成可执行的 n8n 工作流 JSON",
  "parameters": {
    "name": {"type": "string"},
    "nodes": {"type": "array", "items": {"type": "object"}},
    "connections": {"type": "object"}
  }
}
```

**模型输出** (Gemma 4 原生格式):
```
<|tool_call>call:generate_n8n_workflow{name:..., nodes:[...], connections:{...}}<tool_call|>
```

**Memory 机制**:
```
Turn 1: user → generate_n8n_workflow → 保存 workflow_state
Turn 2: user → modify_n8n_workflow → 读取 workflow_state → 增量修改
Turn 3: user → modify_n8n_workflow → 再次增量修改
```

## 模型选型

| 规格 | 参数量 | 量化 | 显存 | 推理框架 | 选型理由 |
|------|--------|------|------|---------|---------|
| **E4B-it** | 4.5B eff | Q4_K_M | ~5GB | llama.cpp | 主力——容量/速度最佳平衡，原生函数调用支持完善 |
| **E2B-it** | 2.3B eff | Q4_K_M | ~3GB | llama.cpp | 备选——端侧部署场景，延迟敏感 |

Gemma 4 的 chat template 预置了完整的 tool_call/tool_response Jinja 宏，这是选择 Gemma 4 而非其他模型的关键理由——无需额外 prompt 工程即可做到可靠的结构化输出。

## 赛道对齐

| 评审标准 (25%权重) | 实现 |
|---|---|
| 架构设计 | agent/core.py + memory.py + tools.py 三层解耦 |
| Gemma 4 特性利用 | 原生 tool_call 模板，非 prompt hacking |
| 文档完善度 | README + run.sh 一键启动 |

## 环境要求

- Python 3.10+
- Ascend 910B4 NPU (32GB) 或 CUDA GPU
- 推荐: llama.cpp + GGUF Q4_K_M (量化)

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 下载模型

```bash
export HF_ENDPOINT=https://hf-mirror.com

# E2B (~3.5GB)
hf download unsloth/gemma-4-E2B-it-GGUF \
  --include "gemma-4-E2B-it-Q4_K_M.gguf" \
  --local-dir models/gemma-4-E2B-it-GGUF

# E4B (~5.4GB，推荐)
hf download unsloth/gemma-4-E4B-it-GGUF \
  --include "gemma-4-E4B-it-Q4_K_M.gguf" \
  --local-dir models/gemma-4-E4B-it-GGUF
```

### 3. 一键启动

```bash
# 服务模式 (推荐开发)
bash scripts/start_llama_server.sh
python3 main.py

# 一键全流程
bash run.sh
```

### 4. 测试

```bash
python3 -c "from api import check_health; print('OK' if check_health() else 'FAIL')"
```

## 功能演示

### 多轮对话示例

| 轮次 | 用户输入 | Agent 动作 |
|------|---------|-----------|
| 1 | "创建 webhook → 飞书通知" | `generate_n8n_workflow` |
| 2 | "加 IF 过滤 main 分支" | `modify_n8n_workflow` |
| 3 | "false 分支加 Slack" | `modify_n8n_workflow` |

### 运行日志

```
[User] 创建一个 webhook 接收 GitHub push 事件，然后发送飞书通知
[Tool Call] generate_n8n_workflow({"name": "GitHub Push → Feishu"})
[Assistant] 已生成工作流，包含 webhook、IF 过滤和飞书三个节点
[User] 在 IF 节点 false 分支加一个 Slack
[Tool Call] modify_n8n_workflow({"operation": "add_node", ...})
```

## 项目结构

```
submissions/2026/A/n8nAgent/
├── README.md              # 本文档（含架构图 + 数据流 + 模型选型）
├── requirements.txt       # 依赖
├── run.sh                 # 一键启动脚本
├── main.py                # Agent 入口
├── agent/
│   ├── core.py            # Agent 核心 (Memory + Tool Calling)
│   ├── tools.py           # n8n 工具定义
│   ├── memory.py          # Conversation Memory
│   └── schema.py          # n8n 节点 schema
├── api/
│   └── gemma_client.py    # OpenAI 兼容 API 客户端
├── examples/
│   └── sample_workflow.json
└── scripts/
    ├── start_llama_server.sh   # llama.cpp 服务
    ├── start_server.sh         # vLLM 服务 (备用)
    └── register_gemma4.py      # vLLM 注册插件
```
