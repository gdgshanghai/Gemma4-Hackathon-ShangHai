# CLAUDE.md - Claude Code 项目指南

## 项目概述

EatOrNot 是一个**多 Agent 饮食决策助手**，帮助用户在"吃什么"这个高频场景中做出平衡健康、预算、情绪的选择。

**核心价值**：不是简单的菜单推荐，而是通过多个专业 Agent 的圆桌辩论，给出有理有据的饮食建议。

## 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 后端框架 | Python + FastAPI | 3.12 / 0.136 |
| 前端框架 | Vue 3 + Vite + TypeScript | 3.5 / 6 / ~5.6 |
| UI 组件 | Tailwind CSS + radix-vue (shadcn-vue) | 4 / latest |
| LLM | Google Gemini API → Gemma 4 31B | gemma-4-31b-it |
| 数据库 | SQLAlchemy + aiosqlite | 2.0 / 0.22 |
| Agent 框架 | Google ADK | 2.1.0 |
| 外部数据 | 麦当劳 MCP | 1.27.2 |

## 项目结构

```
eatornot/
├── apps/
│   ├── api/                          # FastAPI 后端
│   │   ├── main.py                   # 应用入口 (路由注册、CORS、生命周期)
│   │   │
│   │   ├── core/                     # 基础设施
│   │   │   ├── config.py             # pydantic-settings 配置
│   │   │   ├── database.py           # SQLAlchemy async engine
│   │   │   └── llm_client.py         # OpenAI 兼容 LLM 客户端
│   │   │
│   │   ├── agents/                   # Agent 层 (核心决策)
│   │   │   ├── base.py               # BaseAgent 抽象类
│   │   │   ├── orchestrator_agent.py # 智能调度 (关键词→Agent 映射)
│   │   │   ├── supervisor_agent.py   # 方案构建 (调用 Orchestrator + Debate)
│   │   │   ├── debate_engine.py      # 4 阶段圆桌辩论
│   │   │   ├── profile_agent.py      # 用户档案分析
│   │   │   ├── weight_loss_agent.py  # 减脂策略
│   │   │   ├── nutrition_agent.py    # 营养评估
│   │   │   ├── budget_agent.py       # 预算控制
│   │   │   ├── craving_agent.py      # 情绪性进食
│   │   │   ├── time_context_agent.py # 时间压力
│   │   │   ├── safety_agent.py       # 过敏安全
│   │   │   ├── future_simulation_agent.py  # 用餐影响预测
│   │   │   └── reflection_agent.py   # 反思总结
│   │   │
│   │   ├── api/                      # 路由层 (12 个模块)
│   │   │   ├── recommend_routes.py   # 推荐接口
│   │   │   ├── decision_routes.py    # 统一决策入口
│   │   │   ├── plan_routes.py        # 方案精炼 (多轮)
│   │   │   ├── meal_routes.py        # 餐品查询
│   │   │   ├── profile_routes.py     # 用户档案
│   │   │   ├── dashboard_routes.py   # 今日仪表盘
│   │   │   ├── reminder_routes.py    # 饭点提醒
│   │   │   ├── balance_routes.py     # 营养平衡
│   │   │   ├── draft_routes.py       # 订单草稿
│   │   │   ├── chat_routes.py        # 对话交互
│   │   │   ├── safety_routes.py      # 安全检查
│   │   │   └── provider_routes.py    # 数据源切换
│   │   │
│   │   ├── services/                 # 业务服务层
│   │   │   ├── meal_decision_flow.py # Dual-Trigger 统一决策流
│   │   │   ├── memory_service.py     # 饮食习惯长期记忆
│   │   │   ├── auto_draft_service.py # 自动订单草稿
│   │   │   ├── dashboard_service.py  # 今日仪表盘聚合
│   │   │   ├── active_plan_service.py# 活跃方案版本管理
│   │   │   ├── db_service.py         # 用户/餐记录 CRUD
│   │   │   ├── budget_service.py     # 预算计算
│   │   │   ├── nutrition_calculator.py # BMR/TDEE/热量目标
│   │   │   ├── knowledge_service.py  # 知识库查询
│   │   │   ├── rag_knowledge_service.py # RAG 增强检索
│   │   │   ├── reminder_service.py   # 饭点提醒 + 营养缺口
│   │   │   ├── metrics_service.py    # 指标采集
│   │   │   ├── food_provider.py      # Provider 门面
│   │   │   ├── mcdonalds_provider.py # 麦当劳服务封装
│   │   │   ├── demo_service.py       # Demo 模式
│   │   │   ├── conversation_service.py # 对话历史 (内存)
│   │   │   └── mock_mcdonalds_mcp.py # Mock MCP
│   │   │
│   │   ├── models/                   # Pydantic 数据模型
│   │   │   ├── user_profile.py       # 完整用户档案
│   │   │   ├── quick_profile.py      # 快速建档
│   │   │   ├── meal_decision.py      # 决策请求/响应
│   │   │   ├── recommendation.py     # 推荐结果
│   │   │   ├── balance_mode.py       # 三维平衡模型
│   │   │   ├── debate.py             # 辩论结果
│   │   │   ├── active_plan.py        # 活跃方案
│   │   │   ├── meal_record.py        # 用餐记录
│   │   │   ├── agent_result.py       # Agent 输出
│   │   │   └── db_models.py          # SQLAlchemy ORM
│   │   │
│   │   ├── providers/                # 食物数据源抽象
│   │   │   ├── base.py               # FoodProvider 接口
│   │   │   ├── factory.py            # Provider 工厂
│   │   │   ├── mcdonalds_mcp_provider.py # 真实麦当劳 MCP
│   │   │   ├── mock_mcdonalds_provider.py # Mock 数据
│   │   │   └── manual_provider.py    # 手动输入
│   │   │
│   │   ├── adk_app/                  # Google ADK 集成
│   │   │   ├── agent.py              # ADK Agent 定义
│   │   │   ├── mcp_tools.py          # MCP 工具桥接
│   │   │   ├── food_provider_tools.py# 食物查询工具
│   │   │   └── skills_loader.py      # Skills 加载器
│   │   │
│   │   └── data/                     # Mock 数据
│   │       ├── mock_mcdonalds_menu.json
│   │       ├── mock_nutrition_foods.json
│   │       └── demo_user.json
│   │
│   └── web/                          # Vue 3 前端
│       ├── src/
│       │   ├── App.vue               # 主应用 (Tab侧边栏+主内容区)
│       │   ├── main.ts               # 入口
│       │   ├── style.css             # Tailwind 全局样式
│       │   ├── api/client.ts         # API 客户端 (全部后端调用)
│       │   ├── composables/
│       │   │   ├── useAppStore.ts    # 全局状态管理
│       │   │   └── useNotifications.ts # 浏览器通知
│       │   ├── components/           # Vue SFC 组件
│       │   │   ├── ModeSelectionLanding.vue  # 模式选择首页
│       │   │   ├── ProfileOnboardingForm.vue # 完整建档 (3步)
│       │   │   ├── QuickProfileForm.vue      # 快速建档
│       │   │   ├── RoundTableDebate.vue      # 辩论可视化
│       │   │   ├── TodayDashboard.vue        # 今日仪表盘
│       │   │   ├── AutoDraft.vue             # 自动草稿
│       │   │   ├── BalanceMode.vue           # 三维平衡
│       │   │   ├── ReminderCard.vue          # 饭点提醒
│       │   │   ├── ActivePlanPanel.vue       # 方案管理
│       │   │   ├── RecommendationCard.vue    # 推荐卡片
│       │   │   ├── MetricsPanel.vue          # 指标面板
│       │   │   ├── LearningPanel.vue         # 学习进度
│       │   │   ├── SafetyBanner.vue          # 安全警告
│       │   │   ├── ProviderBadge.vue         # 数据源标识
│       │   │   ├── OrderConfirmModal.vue     # 下单确认
│       │   │   ├── FeedbackFormInline.vue    # 用餐反馈
│       │   │   ├── ProfileCard.vue           # 档案卡片
│       │   │   └── ResetButtons.vue          # 重置按钮
│       │   └── components/ui/        # shadcn-vue 基础组件
│       │       ├── Button.vue        # CVA 变体按钮
│       │       ├── Card.vue          # Card 系列
│       │       ├── Badge.vue         # 标签
│       │       ├── Progress.vue      # 进度条 (radix-vue)
│       │       ├── Tabs*.vue         # 标签页 (radix-vue)
│       │       └── Dialog*.vue       # 弹窗 (radix-vue)
│       ├── package.json
│       ├── vite.config.ts
│       └── tsconfig.json
│
├── knowledge/                        # 营养学知识库
│   ├── nutrition.json                # 核心营养数据 (115 条)
│   ├── nutrition_guidelines/         # 膳食指南规则
│   ├── safety/                       # 安全规则 (过敏/极端饮食)
│   └── weight_loss/                  # 减重规则 (BMI/TDEE/热量缺口)
│
├── skills/                           # ADK Skills (5 个)
│   ├── controlled-indulgence-skill/  # 犒劳模式
│   ├── mcdonalds-order-skill/        # 麦当劳下单
│   ├── nutrition-balance-skill/      # 营养平衡
│   ├── spending-control-skill/       # 开销控制
│   └── weight-loss-skill/            # 减重策略
│
└── docs/                             # 项目文档
    ├── architecture.md               # 系统架构
    ├── product_plan.md               # 产品规划
    ├── demo_script.md                # 演示脚本
    ├── judging_story.md              # 评委故事线
    └── troubleshooting.md            # 故障排查
```

## 核心架构

### 请求流程

```
用户输入
    │
    ▼
Route Layer (api/*.py)
    │
    ▼
MealDecisionFlow / RecommendFlow
    │
    ├── 1. 收集上下文 (db_service + dashboard + memory)
    ├── 2. 检测场景 (漏餐/营养缺口/预算超支/深夜)
    ├── 3. 获取习惯记忆 (偏好/回避/预算模式)
    │
    ▼
SupervisorAgent
    │
    ├── OrchestratorAgent (LLM智能调度 → 关键词降级，选 3-5 个 Agent)
    │       │
    │       ▼ asyncio.gather()
    │   [档案] [减脂] [营养] [预算] [食欲] [时间] [安全] [未来]
    │       │
    │       ▼
    │   DebateEngine (4 阶段辩论)
    │       │
    │       ▼
    │   3 个方案: 💪自律 / 💰省钱 / 🍔犒劳
    │
    ▼
AutoDraftService → 订单草稿
    │
    ▼
返回 MealDecisionResponse
```

### 数据源层

```
FoodProvider (接口)
    │
    ├── McDonaldsMCPProvider  → 真实麦当劳 MCP API
    ├── MockMcDonaldsProvider → Mock JSON 数据
    └── ManualProvider        → 用户手动输入
```

Provider 通过 `ProviderFactory` 按配置自动选择，`USE_MOCK_MCP=true` 时降级到 Mock。

### 双模式入口

| 模式 | 触发 | 数据 |
|------|------|------|
| 🏋️ 长期管理 | `ModeSelectionLanding` → `ProfileOnboardingForm` | 身高/体重/目标/预算/过敏/口味 |
| ⚡ 快速选择 | `ModeSelectionLanding` → `QuickProfileForm` | 目标/预算/饥饿感/食欲/心情 |

### 数据持久化

- **用户档案**: `db_service.py` → SQLAlchemy ORM (`db_models.py`)
- **用餐记录**: `db_service.py` → meal_records 表
- **长期记忆**: `memory_service.py` → SQLite (偏好/模式/习惯)
- **活跃方案**: `active_plan_service.py` → SQLite (含版本变更日志)
- **对话历史**: `conversation_service.py` → 内存 (非持久化)

## 关键文件

| 文件 | 说明 |
|------|------|
| `apps/api/main.py` | 应用入口，路由注册，生命周期管理 |
| `apps/api/core/config.py` | 环境变量配置 |
| `apps/api/core/llm_client.py` | LLM 调用 (OpenAI 兼容协议) |
| `apps/api/agents/orchestrator_agent.py` | Agent 智能调度器 |
| `apps/api/agents/supervisor_agent.py` | 方案构建器 |
| `apps/api/agents/debate_engine.py` | 4 阶段圆桌辩论引擎 |
| `apps/api/services/meal_decision_flow.py` | Dual-Trigger 统一决策流 |
| `apps/api/services/memory_service.py` | 饮食习惯长期记忆 |
| `apps/api/services/auto_draft_service.py` | 自动订单草稿 |
| `apps/api/providers/mcdonalds_mcp_provider.py` | 麦当劳 MCP 接入 |
| `apps/api/api/recommend_routes.py` | 推荐接口 |
| `apps/api/api/decision_routes.py` | 统一决策接口 |
| `apps/api/api/plan_routes.py` | 方案精炼接口 |
| `apps/web/src/App.vue` | 前端主应用 (Tab侧边栏+主内容区) |
| `apps/web/src/composables/useAppStore.ts` | 全局状态管理 composable |
| `apps/web/src/api/client.ts` | 前端 API 客户端 |
| `knowledge/nutrition.json` | 营养学知识库 |

## 启动方式

```bash
# 后端
cd apps/api
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000

# 前端 (pnpm)
cd apps/web
pnpm install
pnpm dev
```

前端代理配置在 `apps/web/vite.config.ts`，API 请求自动代理到 `localhost:8000`。

## 环境变量

见 `.env.example`：

- `GEMINI_API_KEY` / `GEMINI_MODEL` — LLM 配置（直连 Gemini API）
- `MCD_MCP_TOKEN` / `MCD_MCP_URL` — 麦当劳 MCP（可选）
- `USE_MOCK_MCP` — 无 MCP 时用 Mock 数据（默认 true）
- `DATABASE_URL` — SQLite 路径
- `DEBUG` — 调试模式

## 协作规范

### Git Flow: GitHub Flow

```
main ────────────────────────────────────────────●
       \              \              \
  feat/xxx       feat/yyy       feat/zzz
        │              │              │
        └──── PR ──────┘──────────────┘
              合并回 main
```

- `main` 永远可运行，禁止直接 push
- 所有开发走 `feat/*` 分支
- 合并走 PR，hackathon 期间可自 merge（建议交叉 review）

### Commit 规范

```
<type>: <描述>
```

| type | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `refactor` | 重构（不改功能） |
| `chore` | 构建/依赖/配置/杂务 |

示例：
```
feat: 添加饭点主动提醒功能
fix: 修复营养计算单位错误
refactor: 拆分 dashboard 服务为独立模块
chore: 升级 vite 到最新版本
```

### 分支命名

```
feat/<简短描述>
```

示例：`feat/ui-redesign`、`feat/proactive-reminder`、`feat/learning-engine`

## 下一步工作

见 `TODO.md`
