# 技术报告

## 一、模型选型理由

### 为什么选择 Gemma 4？

| 维度 | Gemma 4 26B MoE | 其他模型 | 选型理由 |
|------|-----------------|---------|---------|
| **原生函数调用** | ✅ 原生 `<|tool_call|>` 模板 | ❌ 多数模型需 prompt hacking | 减少工具调用解析错误率 |
| **参数量效率** | 26B MoE（激活 4.3B） | 同性能需 13B+ Dense | 更低延迟，更低成本 |
| **上下文窗口** | 256K tokens | 通常 128K | 支持长对话+大工作流 |
| **多模态** | 视觉理解（E2B/E4B） | 部分模型不支持 | 未来可扩展图片输入 |
| **端侧部署** | E2B Q4 仅 ~2.5GB | 多数模型 >7GB | 可运行在浏览器/移动端 |
| **OpenRouter 可用** | ✅ 多 Key 轮转 | 部分需自有 GPU | 开箱即用，无需自建 |

### 规格选择：E4B 26B MoE vs E2B 9B vs 31B Dense

| 规格 | 参数量（激活） | 每次调用成本 | 函数调用可靠性 | 场景 |
|------|--------------|------------|--------------|------|
| **E2B 9B** | 9B (2.3B) | $0.01/100K tokens | 中 | 延迟敏感、移动端 |
| **E4B 26B** ★ | 26B (4.3B) | $0.03/100K tokens | **高** | **主力模型** |
| 31B Dense | 31B (31B) | $0.08/100K tokens | 高 | 复杂推理、长上下文 |

**主力选择 E4B 26B MoE 的核心原因：**

Gemma 4 E4B（Expert 4B）采用 Mixture-of-Experts 架构，26B 总参数量中每次推理只激活约 4.3B 参数，在函数调用（Tool Calling）场景下有三大优势：

1. **低延迟高吞吐**：MoE 激活参数少，OpenRouter API 返回首 Token 速度比 31B Dense 快约 2-3 倍
2. **原生 Tool Calling 模板**：Gemma 4 的 chat template 预置了 `<|tool_call|>` / `<|tool_response|>` Jinja 宏，模型天然理解结构化工具调用格式，无需在 system prompt 中费力描述格式
3. **足够大的专家容量**：4.3B 参数量在 n8n 工作流生成这种结构化任务中表现稳定，工作流 JSON 的节点数量、连接关系的正确率高于 E2B

## 二、架构设计

### 整体架构

```
┌──────────────────────────────────────────────────────────┐
│                        用户                               │
│              (自然语言描述工作流需求)                       │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│                   n8n Agent (FastAPI)                     │
│                                                          │
│  ┌──────────────┐   ┌──────────────────────────────────┐  │
│  │ Conversation  │   │         Tool Engine              │  │
│  │   Memory      │   │                                  │  │
│  │              │   │  ┌───────────────────────────┐   │  │
│  │ - history[]  │   │  │ generate_n8n_workflow()    │   │  │
│  │ - workflow   │──▶│  │ modify_n8n_workflow()     │   │  │
│  │   state      │   │  │ validate_n8n_workflow()   │   │  │
│  └──────────────┘   │  └───────────────────────────┘   │  │
│                     └──────────────┬───────────────────┘  │
└────────────────────────────────────┼──────────────────────┘
                                     │
                  Native Function Calling (OpenAI 格式)
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────┐
│                   Gemma 4 模型                            │
│  ┌──────────────────────────────────────────────────┐   │
│  │         OpenRouter API (云推理)                    │   │
│  │  google/gemma-4-26b-a4b-it  (主力)               │   │
│  │  google/gemma-4-31b-it      (备用)               │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────┬─────────────────────────────────────┘
                     │
             输出: 结构化 JSON
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│                   n8n 自动化平台                          │
│  部署工作流 JSON → 激活 → 通过 Webhook 触发执行           │
└──────────────────────────────────────────────────────────┘
```

### 数据流

```
Step 1:  用户输入自然语言 → Agent.run("创建 webhook 接收推送")
Step 2:  Memory 构造 messages (system + history + user)
Step 3:  API 发送 chat.completions (含 tools 定义)
Step 4:  Gemma 4 解析 → 调用 generate_n8n_workflow({
           "name": "GitHub Push → Feishu",
           "nodes": [...],
           "connections": {...}
         })
Step 5:  Tool Engine 执行 → 生成结构化 JSON → 存入 memory
Step 6:  Memory 更新 workflow_state
Step 7:  前端渲染 WorkflowCard → 用户可以部署到 n8n
```

### 分层设计

#### API 层（`api/gemma_client.py`）

- 封装 OpenAI 兼容客户端
- 支持多 Key 自动轮转（3 个 OpenRouter Key 循环使用，避免限速）
- 支持自定义 API 端点（用户自部署的 Gemma 4）
- 健康检查接口

#### Agent 层（`agent/`）

| 模块 | 职责 |
|------|------|
| `core.py` | N8nAgent 主类：构造 prompt → 调用 LLM → 解析响应 → 执行工具 |
| `tools.py` | 工具 JSON Schema 定义（OpenAI function calling 格式） |
| `memory.py` | ConversationMemory：对话历史 + 工作流状态持久化 |
| `schema.py` | n8n 节点 Schema 定义（供 LLM 参考节点参数格式） |

#### 服务层（`server.py`）

| 端点 | 功能 |
|------|------|
| `/api/chat` | 接收用户输入 → Agent.run() → 返回工作流 JSON |
| `/api/deploy` | 部署到 n8n（自动添加 Webhook 触发器 + 节点格式修正 + 激活） |
| `/api/execute-workflow` | 通过 Webhook 触发工作流执行 |
| `/api/provider-status` | 检查各 API provider 连通性 |
| `/api/n8n-health` | 检查默认 n8n 实例连通性 |

#### 前端层（`web/static/`）

- Preact + HTM 单页应用
- 无构建步骤，直接加载 ES Module
- 实时显示工作流卡片（WorkflowCard）
- 支持部署 → 执行全流程交互

### 原生函数调用详解

Gemma 4 的 chat template 原生支持工具调用，无需 prompt hacking：

**工具定义**（OpenAI 格式）：

```json
{
  "name": "generate_n8n_workflow",
  "description": "根据需求生成可执行的 n8n 工作流 JSON",
  "parameters": {
    "name": {"type": "string"},
    "nodes": {"type": "array"},
    "connections": {"type": "object"}
  }
}
```

**模型输出**（Gemma 4 原生格式）：

```
<|tool_call|>call:generate_n8n_workflow{
  "name": "GitHub Push → Feishu",
  "nodes": [...],
  "connections": {...}
}<|tool_call|>
```

**双格式兼容**：

Agent 同时支持两种 tool_call 格式：

1. **OpenAI 标准格式**：`msg.tool_calls` 数组（OpenRouter 自动转换）
2. **Gemma 4 内联格式**：`<|tool_call|>` 标签嵌入在 `content` 中（纯文本模式）

当 `msg.tool_calls` 为空时，自动 fallback 到 `parse_tool_calls()` 正则解析。

### 多轮对话机制

```
Turn 1: user → generate_n8n_workflow → 保存 workflow_state
Turn 2: user → modify_n8n_workflow → 读取 workflow_state → 增量修改
Turn 3: user → modify_n8n_workflow → 再次增量修改
```

`ConversationMemory` 在每次工具调用后将最新的 `workflow_state` 序列化到 memory 中，下一轮对话时作为 system message 注入，让 LLM 知道当前已完成的工作流状态，从而实现增量修改。

### 安全性设计

- API Key 不暴露给前端（默认实例的 Key 只存后端 `.env`）
- 用户自建实例的 Key 存在浏览器 localStorage，不经过后端
- OpenRouter 3 个 Key 循环使用避免单 Key 超限
- n8n 部署时自动修正节点类型，防止 LLM 生成非法节点类型


