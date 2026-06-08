# 🍔 基于Gemma 4的营养成分以及开销伴随智能体

> **赛道**: A (AI Agent) | **队伍**: EatOrNot | **模型**: Gemma 4 31B Dense (`gemma-4-31b-it`)
>
> 📹 **演示视频**: [YouTube](https://youtu.be/OXaYEZb2hQ0?si=7MMHgZ6y7A68GSHx) (5 分钟完整功能演示)

## 项目简介

**面向程序员的终端饮食智能体** — 解决高强度工作下饮食不规律的问题。

程序员生活节奏快、压力大，经常忘记点饭、凭情绪暴饮暴食、不知不觉超预算。本智能体通过 **8 个专业 Agent 的圆桌辩论**，自主完成营养分析、预算控制、习惯学习、下单推荐全流程，成为用户的"饮食营养伴随"。

**核心价值**：不是简单的菜单推荐，而是多 Agent 从健康、预算、情绪、安全等维度**辩论后**给出有理有据的饮食建议，并通过 Tool Calling 实现自主下单闭环。

---

## 🎯 Gemma 4 深度利用

### Native Function Calling

本项目的 **核心不是 Prompt 工程**，而是深度利用 Gemma 4 的原生函数调用能力驱动整个 Agent 系统：

```
用户输入 "想吃麦当劳但我在减肥，预算 25"
    │
    ▼ Gemma 4 分析意图 → 选择 Agent 组合
    │
    ├── 🔥 减脂Agent → get_nutrition() → 热量 563kcal，超出目标
    ├── 💰 预算Agent → calculate_price() → ¥42，超出 ¥25 预算
    ├── 🥗 营养Agent → 知识库检索 → 缺少膳食纤维
    └── 🍫 食欲Agent → memory.get_habits() → 用户心情低落需满足感
    │
    ▼ DebateEngine 4 阶段辩论
    │
    💪 自律: 板烧鸡腿堡 + 玉米杯 = 333kcal / ¥22
    💰 省钱: 1+1 随心配 = 490kcal / ¥12.9
    🍔 犒劳: 双层安格斯 = 1003kcal / ¥38（建议明天轻食）
```

### Agent Memory（长期习惯学习）

```python
# 三层记忆架构
短期记忆 → 当前对话上下文（内存）
中期记忆 → 用餐记录 + 偏好反馈（SQLite meal_records）
长期记忆 → 行为模式 + 习惯画像（SQLite habit_patterns）

# 每次决策时召回
[Memory] 召回习惯: 偏好=[辣味, 高蛋白], 回避=[生菜]
[Memory] 检测模式: 工作日倾向控制预算 (置信度 0.85)
[Orchestrator] 基于记忆 → 增加减脂Agent和预算Agent权重
```

### Tool Calling（自主下单闭环）

```python
# 通过麦当劳 MCP (Model Context Protocol) 接入真实 API
search_menu(keyword="鸡腿堡")     # → 营养Agent获取餐品数据
get_nutrition(code="big_mac")     # → 减脂Agent计算热量
calculate_price(items, store)     # → 预算Agent检查是否超支
create_order(items, store, ...)   # → 用户确认后自主下单
```

---

## 🏗️ 核心架构

### 多 Agent 协作 + 4 阶段圆桌辩论

```
MealDecisionFlow (场景检测 + 记忆召回)
    │
    ▼
SupervisorAgent
    ├── OrchestratorAgent (Gemma 4 智能调度 → 选 3-5 个 Agent)
    │       │
    │       ▼ asyncio.gather() 并行分析
    │   [档案] [减脂] [营养] [预算] [食欲] [时间] [安全] [未来模拟]
    │       │
    │       ▼
    │   DebateEngine (4 阶段辩论)
    │       ├── R1: 各 Agent 发表初始意见（基于数据 + 知识库）
    │       ├── R2: Gemma 4 发现冲突（减脂vs食欲、预算vs营养）
    │       ├── R3: 形成妥协方案（Gemma 4 主持）
    │       └── R4: 各 Agent 最终投票（全票/多数通过）
    │       │
    │       ▼
    │   3 个方案: 💪自律 / 💰省钱 / 🍔犒劳
    │
    ▼
AutoDraftService → 自动生成订单草稿（MCP Tool Calling）
```

### Agent 列表

| Agent | 职责 | Function Calling |
|-------|------|------------------|
| 🧑 档案Agent | 分析用户画像 | `get_user_profile` |
| 🔥 减脂Agent | 热量目标 & 减脂策略 | `calculate_tdee` |
| 🥗 营养Agent | 营养素评估 | `get_nutrition` |
| 💰 预算Agent | 预算控制 | `calculate_price` |
| 🍫 食欲Agent | 情绪性进食分析 | 记忆检索 |
| ⏰ 时间Agent | 时间压力评估 | `get_meals` |
| ⚠️ 安全Agent | 过敏 & 饮食安全 | 安全规则匹配 |
| 🔮 未来模拟Agent | 用餐后影响预测 | 热量-预算平衡模型 |

---

## 🚀 快速启动

### 方式 A：Docker 一键启动（推荐，适合评审）

```bash
# 1. 配置环境变量（只需填一个必填项）
cp .env.example .env
# 编辑 .env，将 GEMINI_API_KEY 改为你的 Key

# 2. 一键启动
docker compose up -d --build

# 3. 访问
# 前端: http://localhost:5173
# 后端健康检查: http://localhost:8000/health
```

### 方式 B：本地开发

```bash
# 后端（终端 1）
cd apps/api
pip install -r requirements.txt
cp ../../.env.example ../../.env    # 填入 GEMINI_API_KEY
uvicorn main:app --host 127.0.0.1 --port 8000

# 前端（终端 2）
cd apps/web
pnpm install
pnpm dev
```

访问 http://localhost:5173，Vite 自动代理 `/api` → `localhost:8000`。

### 方式 C：终端点餐（Claude Code Skill）

```powershell
# 1. 安装 skill
.\scripts\claude-setup\install.ps1

# 2. 在 Claude Code 中直接说
帮我点午餐     # → AI 推荐 + 辩论 + 查门店 + 下单
领券           # → 自动领取麦当劳优惠券
```

---

## ⚙️ 环境变量详细配置

复制 `.env.example` 为 `.env` 后按需填写：

```bash
cp .env.example .env
```

### 必填项

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GEMINI_API_KEY` | `""` | **（必填）** Google AI Studio API Key。在 [aistudio.google.com/apikey](https://aistudio.google.com/apikey) 免费获取。项目通过 OpenAI 兼容协议直连 Gemini API 调用 Gemma 4 31B。 |

### LLM 配置（可选）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GEMINI_MODEL` | `gemma-4-31b-it` | Gemma 模型 ID。可选 `gemma-4-12b-it` 等其他 Gemma 4 系列模型 |
| `CF_AIG_TOKEN` | `""` | Cloudflare AI Gateway Token（备用链路）。仅当 Gemini API 直连不可用时配置 |
| `CF_AIG_BASE_URL` | `"https://gateway.ai.cloudflare.com/v1/..."` | CF AI Gateway 地址，配合 `CF_AIG_TOKEN` 使用 |

### 麦当劳 MCP（可选）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MCD_MCP_TOKEN` | `""` | 麦当劳 MCP Token。在 [mcp.mcd.cn](https://mcp.mcd.cn) 获取。**不配置时自动使用 Mock 数据**，项目仍可正常运行（只是菜单和价格为模拟数据） |
| `MCD_MCP_URL` | `https://mcp.mcd.cn` | 麦当劳 MCP 服务地址，一般无需修改 |
| `USE_MOCK_MCP` | `true` | 是否使用 Mock 数据。设为 `false` 且配置了 `MCD_MCP_TOKEN` 时使用真实麦当劳 API |

> 💡 **快速体验**：只需 `GEMINI_API_KEY` 即可启动。麦当劳 MCP 为可选增强，Mock 模式下所有功能均可演示。

### 应用配置（可选）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./eatornot.db` | SQLite 数据库路径。Docker 模式下自动持久化到 `./data/` |
| `APP_NAME` | `EatOrNot` | 应用名称 |
| `DEBUG` | `true` | 调试模式，开启详细日志输出 |
| `CORS_ORIGINS` | `http://localhost:5173,...` | 跨域白名单，逗号分隔。Docker 模式下 nginx 反代无需跨域 |

### Web Push 通知（可选）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VAPID_PUBLIC_KEY` | `""` | VAPID 公钥，用于浏览器推送。生成方式：`npx web-push generate-vapid-keys` |
| `VAPID_PRIVATE_KEY` | `""` | VAPID 私钥 |
| `VAPID_SUBJECT` | `""` | 推送联系人，格式 `mailto:you@example.com` |

---

## 📁 项目结构

```
eatornot/
├── apps/api/                              # FastAPI 后端
│   ├── agents/                            # ★ Agent 层 (核心)
│   │   ├── orchestrator_agent.py          #   Gemma 4 智能调度器 (Function Calling)
│   │   ├── supervisor_agent.py            #   方案构建器 + 辩论编排
│   │   ├── debate_engine.py               #   4 阶段圆桌辩论引擎
│   │   ├── weight_loss_agent.py           #   减脂策略 Agent
│   │   ├── nutrition_agent.py             #   营养评估 Agent
│   │   ├── budget_agent.py                #   预算控制 Agent
│   │   └── ... (共 8 个专业 Agent)
│   ├── services/
│   │   ├── memory_service.py              # ★ Agent Memory (饮食习惯学习)
│   │   ├── meal_decision_flow.py          #   Dual-Trigger 统一决策流
│   │   └── auto_draft_service.py          #   自动订单草稿
│   ├── providers/
│   │   ├── mcdonalds_mcp_provider.py      # ★ Tool Calling (麦当劳 MCP)
│   │   └── mock_mcdonalds_provider.py     #   Mock 降级
│   ├── core/
│   │   └── llm_client.py                  #   Gemma 4 调用 (OpenAI 兼容协议)
│   └── api/                               #   12 个路由模块
├── apps/web/                              # Vue 3 + Vite 6 前端
│   └── src/components/                    #   25+ 组件 (辩论可视化/仪表盘/...)
├── knowledge/                             # 营养学知识库 (115 条)
│   ├── nutrition.json                     #   《中国食物成分表》核心数据
│   ├── nutrition_guidelines/              #   《中国居民膳食指南》规则
│   ├── safety/                            #   过敏原 + 安全规则
│   └── weight_loss/                       #   BMI/TDEE/热量缺口规则
├── skills/                                # Google ADK Skills (5 个)
├── scripts/claude-setup/                  # 终端点餐 Skill 安装
└── docker-compose.yml                     # Docker 一键部署
```

★ = 赛道 A 重点考察文件

---

## 🔍 运行日志（真实 Pipeline）

> 完整日志见 [docs/agent_pipeline.log](docs/agent_pipeline.log) — 赛道 A 要求的 Agent Memory + Tool Calling 运行证明

### ① Memory 加载用户档案

```
INFO [Memory] 加载用户档案: user_id=demo-user, name=小明, goal=lose_weight,
      height=172.0cm, weight=72.0kg, age=24, daily_budget=¥100.0, allergies=[]
```

### ② Function Calling → Orchestrator 智能调度

```
INFO [ToolCalling] Orchestrator 准备调用 LLM Function Calling 选择 Agent
INFO [ToolCalling] 可选工具: ['profile', 'weight_loss', 'nutrition', 'budget',
      'craving', 'time_context', 'safety', 'future_simulation']
INFO [ToolCalling] LLM Function Calling 返回: {selected: ['profile', 'weight_loss',
      'nutrition', 'budget', 'craving', 'time_context'],
      reason: '用户明确提到减脂目标（weight_loss）、预算限制（budget）以及
      疲劳状态（craving, time_context）。在长期模式下，需要结合用户档案（profile）
      和营养均衡分析（nutrition）来评估麦当劳选项。'}
```

### ③ 6 Agent 并行分析

```
INFO [Agent] 减脂Agent: score=0.95 — "建议维持中度热量缺口。本餐603千卡预算在TDEE 2310
      的基础上非常合理（约占每日总预算的25-30%）" | warning: 避免含糖饮料的套餐
INFO [Agent] 预算Agent: score=0.90 — "预算非常充足。剩余43元，足以支付接下来的两餐"
INFO [Agent] 营养Agent: score=0.40 — "美式咖啡热量极低，咖啡因有助于提高基础代谢"
INFO [Agent] 食欲Agent: score=0.20 — "本周放纵额度已严重超标（4/2），建议严格执行健康饮食计划"
```

### ④ 4 阶段圆桌辩论

```
INFO [Debate] Stage 1/4 - 初始意见: 6 位 Agent 陈述立场
INFO [Debate] Stage 2/4 - 发现冲突: 7 条冲突
INFO [Debate] Stage 3/4 - 形成妥协: 综合各方意见
INFO [Debate] Stage 4/4 - 最终投票: 6 票, 结果={approve, warn}
```

### ⑤ 3 个推荐方案

```
INFO [Plan] 💪 自律减脂餐: 板烧鸡腿堡 + 玉米杯 + 美式咖啡 | ¥34.0 | 465kcal | 蛋白27.8g
INFO [Plan] 💰 省钱包饱餐: 猪柳蛋麦满分 + 麦香鸡块 + 零度可乐 | ¥36.5 | 700kcal | 蛋白36.0g
INFO [Plan] 🍔 放纵一下餐: 巨无霸 + 薯条(小) + 零度可乐 | ¥40.5 | 760kcal | 蛋白29.0g
```

---

## 📚 文档

| 文档 | 说明 |
|------|------|
| [技术报告](TECHNICAL_REPORT.md) | 模型选型 (Gemma 4 31B) + 架构设计 + 特性利用深度 |
| [完整运行日志](docs/agent_pipeline.log) | 真实 Pipeline 日志 — Memory + Function Calling + 辩论全过程 |
| [架构文档](docs/architecture.md) | 详细系统架构设计 |
| [演示视频脚本](docs/demo_video_script.md) | 5 分钟 demo 流程 |
| [开发指南](CLAUDE.md) | 项目结构 + 协作规范 |

## License

[MIT](LICENSE)
