# Agent 智能化 + 半自动下单 设计文档

> 日期: 2026-06-03
> 状态: 已批准
> 分支: feat/ui-and-agent-experience

## 背景

当前 EatOrNot 的 Agent 系统存在以下问题：

1. **OrchestratorAgent**: 纯关键词 dict 匹配（`KEYWORD_AGENT_MAP`），无法理解自然语言
2. **DebateEngine**: 纯算法打分（`score_diff > 0.4 = 冲突`），冲突描述和妥协方案是硬编码模板
3. **SupervisorAgent**: 3 个方案是固定排序（最低卡/最低价/最热门），pros/cons/reason 是硬编码字符串
4. **无下单能力**: 用户选完方案后无法实际下单

## 目标

- Agent 调度从关键词匹配升级为 LLM 理解用户意图
- 辩论过程从算法打分升级为 LLM 生成有逻辑的冲突描述和妥协方案
- 方案生成从固定模板升级为 LLM 智能组合 + 个性化推荐语
- 用户确认方案后 Agent 自动调麦当劳 MCP 下单

## 方案选择

**选定：方案 B — 逐阶段独立 LLM 调用**

| 方案 | LLM 调用 | 延迟 | 复杂度 |
|------|----------|------|--------|
| A: 单次大 Prompt | 1-2 次 | 3-5s | 低 |
| **B: 逐阶段独立** | **3 次** | **5-8s** | **中** |
| C: 流式 LLM | 3-4 次 | 体感快 | 高 |

选择理由：一周开发时间充裕，逐阶段可观测易调试，每步降级独立。

## 设计详情

### Section 1: LLM 驱动的 Orchestrator

**文件**: `agents/orchestrator_agent.py`

改动：
- 新增 `_llm_select_agents()` 方法
  - 输入: 用户消息 + 模式 + 用户背景摘要
  - LLM prompt: 列出 8 个 Agent 的职责描述，要求返回 JSON `{"selected": [...], "reason": "..."}`
  - 快速模式最少选 3 个 Agent，长期模式最少选 4 个
- 现有 `_select_agents()` 重命名为 `_keyword_select()`，作为降级路径
- `run()` 方法中先尝试 LLM，失败则降级到 `_keyword_select()`

降级策略：LLM 失败（无 token / 网络错误 / 返回 fallback）→ 静默降级到关键词匹配

### Section 2: LLM 驱动的 DebateEngine

**文件**: `agents/debate_engine.py`

改动：
- `run()` 方法从同步改为 `async`
- 新增 `_llm_debate()` 方法
  - 输入: 所有 AgentResult + 用户上下文
  - LLM prompt: 把各 Agent 的 name/score/reasons/warnings 传入，要求 LLM 主持 4 阶段辩论
  - 返回 schema: 4 个 stages，每个包含 messages 数组
- 现有 4 个 `_stage_*()` 方法保留，包装为 `_algorithmic_debate()` 作为降级
- `SupervisorAgent` 中 `debate_engine.run()` 调用处加 `await`

LLM Prompt 核心：
```
你是一场饮食决策圆桌辩论的主持人。以下是各专家Agent的分析结果：

[营养Agent]: score=0.4, 理由=..., 警告=...
[预算Agent]: score=0.3, 理由=...
[食欲Agent]: score=0.7, 理由=...

请按4个阶段主持辩论:
1. initial_opinions: 各Agent陈述立场
2. conflicts: 找出真正有逻辑冲突的观点
3. compromise: 提出平衡各方意见的妥协方案
4. final_vote: 各Agent投票并给出理由

返回JSON。
```

降级策略：LLM 失败 → 降级到现有算法辩论

### Section 3: LLM 驱动的方案生成

**文件**: `agents/supervisor_agent.py`

改动：
- 新增 `_llm_build_plans()` 方法
  - 输入: 候选菜品 + 用户档案 + Agent 结果 + 辩论结论
  - LLM prompt: 要求从候选菜品中组合 3 个方案（自律/省钱/犒劳）
  - LLM 返回菜品 name，代码从 candidates 中匹配回完整数据对象
  - pros/cons/reason 由 LLM 生成
  - 营养数值（calories/protein/fat 等）由代码计算，不依赖 LLM 算术
- 现有 `_build_plans()` 重命名为 `_template_build_plans()`，作为降级路径

效果对比：
- 现有: `"最适合您的减脂目标。烤制蛋白 + 零糖饮料，热量最低。"`
- 改造后: `"今天蛋白质摄入偏少，建议选板烤鸡腿堡补充蛋白，搭配零度可乐解馋不增负"`

降级策略：LLM 失败 → 降级到固定模板排序

### Section 4: 半自动下单

**新增文件**:
- `api/order_routes.py`: `POST /api/order/create` 接口
- `services/order_service.py`: 组装订单参数、调 provider、记录订单
- `models/order.py`: 订单请求/响应模型

**改动文件**:
- `providers/mcdonalds_mcp_provider.py`: 新增 `create_order()` 方法
- `main.py`: 注册 order 路由
- 前端 `OrderConfirmModal.tsx`: 选方案后弹确认 → 调下单接口 → 展示支付链接

流程:
```
用户选择方案 → 点"确认下单"
      ↓
POST /api/order/create { plan_id, user_id, store_code }
      ↓
order_service:
  1. 查门店信息
  2. 调 calculate-price 确认价格
  3. 调 create-order 下单
      ↓
返回 { order_id, pay_url, status }
      ↓
前端展示支付链接 / 订单状态
```

降级策略：MCP 不可用 → 返回 `"下单服务暂不可用，请前往麦当劳APP下单"`

**新增 LLM 调用**: 0 次（下单是确定性 API 调用）

## 整体调用链路

```
用户输入 "今天加班好累想吃点好的"
         │
         ▼
┌─ SupervisorAgent.run() ─────────────────────────┐
│                                                   │
│  ① LLM 调度 (OrchestratorAgent)                  │
│     → 选出: craving, nutrition, budget, time_ctx  │
│                                                   │
│  ② 各 Agent 并行跑 (asyncio.gather, 不变)         │
│     → 4个AgentResult                              │
│                                                   │
│  ③ LLM 辩论 (DebateEngine)                       │
│     → 4阶段智能辩论                                │
│                                                   │
│  ④ LLM 方案 (SupervisorAgent)                    │
│     → 3个智能方案 + 个性化 reason                  │
│                                                   │
│  ⚠️ 任何一步 LLM 失败 → 降级到现有算法            │
└───────────────────────────────────────────────────┘
         │
         ▼ 用户选择方案 + 确认下单
┌─ OrderService.create_order_from_plan() ──────────┐
│  ⑤ calculate-price (MCP)                          │
│  ⑥ create-order (MCP)                             │
│  → 返回支付链接                                    │
└───────────────────────────────────────────────────┘
```

**LLM 调用总计**: 3 次（调度 + 辩论 + 方案）

## 改动文件汇总

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `agents/orchestrator_agent.py` | 修改 | 新增 LLM 调度，旧方法保留为降级 |
| `agents/debate_engine.py` | 修改 | run 改 async，新增 LLM 辩论，旧方法保留 |
| `agents/supervisor_agent.py` | 修改 | 新增 LLM 方案生成，旧方法保留 |
| `providers/mcdonalds_mcp_provider.py` | 修改 | 新增 create_order() |
| `api/order_routes.py` | 新建 | POST /api/order/create |
| `services/order_service.py` | 新建 | 下单逻辑 |
| `models/order.py` | 新建 | 订单数据模型 |
| `main.py` | 修改 | 注册 order 路由 |
| 前端 `OrderConfirmModal.tsx` | 修改 | 接入下单流程 |

**不改的文件**:
- 8 个专业 Agent 内部逻辑
- `llm_client.py`
- 所有数据模型（agent_result, debate, recommendation 等）
- API 返回结构

## 预计改动量

- 新增 ~300 行
- 重命名/调整 ~40 行
- 删除 0 行
