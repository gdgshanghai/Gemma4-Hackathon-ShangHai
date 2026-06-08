# EatOrNot 架构文档

## 产品定位

**双模式多 Agent 饮食决策助手** — 基于 Google ADK 的智能饮食决策系统

不是麦当劳 MCP 包装器，而是一个完整的营养、预算、情绪管理决策平台。

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户界面层                                │
│                    React + Vite + TypeScript                     │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐    │
│  │ 模式选择    │  │ 档案录入     │  │ 主应用              │    │
│  │ Landing     │  │ Onboarding   │  │ Chat + Plans + Debate│    │
│  └─────────────┘  └──────────────┘  └─────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │ HTTP/JSON
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API 网关层                                │
│                      FastAPI + CORS                              │
│  /api/recommend  /api/plan/refine  /api/order/confirm           │
│  /api/profile    /api/feedback     /api/today/status             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ADK Agent 决策层                             │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Google ADK Root Agent                        │   │
│  │         (eatornot_root_agent, Gemini 2.0 Flash)           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│          ┌───────────────────┼───────────────────┐              │
│          ▼                   ▼                   ▼              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Skills       │  │ FoodProvider │  │ MCP Tools    │         │
│  │ (领域知识)   │  │ (食物数据)   │  │ (外部服务)   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Skills       │  │ Providers    │  │ MCP Server   │
│ /skills/     │  │ McDonald's   │  │ mcp.mcd.cn   │
│              │  │ Meituan      │  │ (or Mock)    │
│              │  │ Manual       │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## 核心概念

### ADK Skill vs MCP

| 维度 | ADK Skill | MCP |
|------|-----------|-----|
| **定义** | 领域知识包 | 外部服务连接器 |
| **内容** | 指令、规则、参考文档 | API 调用、数据查询 |
| **用途** | 指导 Agent 如何推理 | 获取实时外部数据 |
| **加载方式** | 从 `/skills` 目录读取 SKILL.md | 函数调用或 MCPToolset |
| **示例** | 减脂知识、营养规则 | 麦当劳菜单、价格查询 |

**关键区别**：Skill 是被动知识（告诉 Agent 怎么想），MCP 是主动工具（帮 Agent 获取数据）。

### FoodProvider 抽象

麦当劳只是众多食物提供者之一：

```
FoodProvider (抽象接口)
├── McDonaldsProvider    # 麦当劳（Mock 或真实 MCP）
├── MockMeituanProvider  # 美团外卖（Mock）
└── ManualMealProvider   # 手动录入
```

---

## 双模式设计

| 模式 | 入口 | 档案 | 预算追踪 | 历史记录 |
|------|------|------|----------|----------|
| **长期管理** | 完整建档 | 身高/体重/目标/预算/过敏/口味 | ✅ 日/周 | ✅ 保存 |
| **快速选择** | 简易问卷 | 目标/预算/饥饿/嘴馋/心情 | ❌ | ❌ |

### 应用阶段流

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ 模式选择    │────▶│ 档案录入    │────▶│ 主应用      │
│ Landing     │     │ Onboarding  │     │ Chat+Plans  │
└─────────────┘     └─────────────┘     └─────────────┘
       │                                       ▲
       │            ┌─────────────┐            │
       └───────────▶│ 快速问卷    │───────────┘
                    │ QuickForm   │
                    └─────────────┘
```

---

## Agent 架构

### ADK Root Agent

```python
root_agent = Agent(
    name="eatornot_root_agent",
    model="gemini-2.0-flash",
    instruction=SYSTEM_INSTRUCTION,  # 包含所有 Skills 指令
    tools=[
        # FoodProvider 工具
        FunctionTool(search_menu),
        FunctionTool(get_nutrition),
        FunctionTool(calculate_price),
        FunctionTool(create_order_draft),
        FunctionTool(confirm_order),
        # MCP 工具
        FunctionTool(mcd_list_nutrition_foods),
        FunctionTool(mcd_query_nearby_stores),
        FunctionTool(mcd_calculate_price),
        FunctionTool(mcd_create_order),
    ],
)
```

### Skills（领域知识）

```
skills/
├── weight-loss-skill/SKILL.md          # BMI/BMR/TDEE/热量缺口
├── nutrition-balance-skill/SKILL.md    # 营养评估/钠警告
├── controlled-indulgence-skill/SKILL.md # 情绪检测/放纵管理
├── spending-control-skill/SKILL.md     # 预算追踪/性价比
└── mcdonalds-order-skill/SKILL.md      # MCP 使用/下单流程
```

每个 SKILL.md 包含：
- frontmatter（name, description）
- 规则和约束
- 输出指导
- 示例

### 传统 Agent（兼容层）

```
agents/
├── base.py                     # BaseAgent 抽象类
├── supervisor_agent.py         # Supervisor 编排
├── profile_agent.py            # 档案分析
├── weight_loss_agent.py        # 减脂策略
├── nutrition_agent.py          # 营养评估
├── budget_agent.py             # 预算检查
├── craving_agent.py            # 情绪/渴望
├── time_context_agent.py       # 时间压力
├── menu_agent.py               # 菜单获取
├── safety_agent.py             # 安全检查
├── future_simulation_agent.py  # 影响模拟
└── reflection_agent.py         # 反馈学习
```

---

## 数据流

### 推荐流程

```
用户输入: "我想吃麦当劳，我在减肥"
    │
    ▼
POST /api/recommend
    │
    ▼
SupervisorAgent.run(context)
    │
    ├─▶ MenuAgent → 加载菜单数据
    │
    ├─▶ asyncio.gather() 并发运行 8 个 Agent
    │   ├─ ProfileAgent → BMI/BMR/TDEE
    │   ├─ WeightLossAgent → 热量目标
    │   ├─ NutritionAgent → 营养评估
    │   ├─ BudgetAgent → 预算检查
    │   ├─ CravingAgent → 情绪检测
    │   ├─ TimeContextAgent → 时间压力
    │   ├─ SafetyAgent → 安全检查
    │   └─ FutureSimulationAgent → 影响模拟
    │
    ▼
构建 3 个推荐方案
    ├─ 💪 自律减脂餐（按热量排序）
    ├─ 💰 省钱包饱餐（按价格排序）
    └─ 🍔 放纵一下餐（按人气排序）
    │
    ▼
返回 RecommendationResponse
    ├─ plans: [3 个方案]
    ├─ agent_debate: [8 个 AgentResult]
    ├─ summary: 总结
    └─ safety_warnings: 警告
```

### 精炼流程

```
用户: "不要咖啡换成可乐"
    │
    ▼
POST /api/plan/refine
    │
    ▼
解析约束 → 过滤菜品 → 生成新版本
    │
    ▼
ActivePlan v2
    ├─ items: 更新后的菜品
    ├─ change_log: [{version, what_changed, impact}]
    └─ constraints: 用户限制
```

---

## 前端组件

```
components/
├── ModeSelectionLanding.tsx    # 模式选择落地页
├── ProfileOnboardingForm.tsx   # 长期模式建档
├── QuickProfileForm.tsx        # 快速模式问卷
├── ProfileCard.tsx             # 用户档案卡片
├── BudgetBar.tsx               # 预算进度条
├── NutritionBalancePanel.tsx   # 营养平衡面板
├── RecommendationCard.tsx      # 推荐方案卡片
├── ActivePlanPanel.tsx         # 当前方案（版本/精炼）
├── RoundTableDebate.tsx        # 圆桌辩论（4 阶段）
├── ChatMessageList.tsx         # 聊天消息
├── OrderConfirmModal.tsx       # 订单确认弹窗
└── ResetButtons.tsx            # 重置按钮
```

### 圆桌辩论 UI

4 个阶段展示 Agent 讨论过程：

1. **💬 初始意见** — 每个 Agent 独立发表观点
2. **⚡ 发现分歧** — 检测不同意见
3. **🤝 达成妥协** — 各方让步
4. **✅ 最终建议** — 投票表决

---

## API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/demo/profile` | GET | 获取 demo 档案 |
| `/api/profile` | GET/POST | 获取/保存档案 |
| `/api/profile/reset` | POST | 重置档案 |
| `/api/profile/quick` | POST | 快速档案 |
| `/api/recommend` | POST | 获取推荐（支持双模式） |
| `/api/plan/refine` | POST | 精炼方案 |
| `/api/plan/{id}` | GET | 获取方案 |
| `/api/plan/reset` | POST | 重置方案 |
| `/api/order/draft` | POST | 创建订单草稿 |
| `/api/order/confirm` | POST | 确认订单 |
| `/api/meal/record` | POST | 记录用餐 |
| `/api/meal/history` | GET | 用餐历史 |
| `/api/today/status` | GET | 今日状态 |
| `/api/feedback` | POST | 提交反馈 |
| `/api/conversation/reset` | POST | 重置对话 |

---

## 数据模型

### UserProfile

```python
class UserProfile(BaseModel):
    user_id: str
    name: str
    height_cm: float
    weight_kg: float
    age: int
    sex: str
    goal: Goal  # lose_weight/maintain/gain_muscle/save_money/regular_meals
    activity_level: str
    daily_budget: float
    weekly_budget: float
    weekly_indulgence_allowance: int
    taste_preferences: list[str]
    allergies: list[str]
    dislikes: list[str]
    preferred_tone: PreferredTone  # strict_coach/gentle_friend/funny_friend
    onboarding_complete: bool
    mode: str  # long_term/quick
```

### AgentResult

```python
class AgentResult(BaseModel):
    agent_name: str
    score: float  # -1.0 到 1.0
    decision: str  # approve/neutral/reject/warn
    reasons: list[str]
    warnings: list[str]
    data: dict
    # 圆桌辩论字段
    position: str
    objection: str
    concession: str
    final_vote: str
    confidence: float
    evidence: list[str]
```

### ActivePlan

```python
class ActivePlan(BaseModel):
    plan_id: str
    version: int
    items: list[MenuItem]
    nutrition: dict  # calories, protein, fat, carbs, sodium
    price: float
    reasons: list[str]
    tradeoffs: list[str]
    change_log: list[ChangeLogEntry]
    constraints: list[str]
```

---

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| Agent 框架 | Google ADK | 2.1.0 |
| Backend | Python + FastAPI | 3.12, 0.136 |
| Frontend | React + Vite + TypeScript | 19, 6 |
| LLM | Gemini 2.0 Flash | via ADK |
| MCP | McDonald's MCP | Mock fallback |
| 数据库 | SQLite | 待接入 |

---

## 安全约束

- ✅ 不自动下单，必须用户确认
- ✅ 不提供医疗诊断
- ✅ 极端饮食目标会被警告
- ✅ 过敏信息优先检查
- ✅ 不提交密钥到代码库
- ✅ MCP token 缺失时自动使用 Mock 数据
