# 技术报告：基于Gemma 4的营养成分以及开销伴随智能体

## 1. 项目定位

**面向程序员的终端饮食智能体** — 利用 Gemma 4 31B Dense 的原生函数调用能力，构建多 Agent 协作系统，实现营养分析、预算控制、习惯学习、自主下单的饮食伴随全流程。

**目标用户**：高强度工作的程序员群体，面临饮食不规律、忘记点餐、情绪性进食、超预算消费等问题。

---

## 2. 模型选型：为什么选择 Gemma 4 31B Dense

| 考量维度 | Gemma 4 31B Dense | 其他方案 |
|---------|-------------------|---------|
| **函数调用能力** | 原生支持 Native Function Calling，JSON 输出稳定 | 需复杂 prompt hack |
| **推理质量** | 31B 参数量足以处理多 Agent 协调、辩论逻辑 | 小模型难以保持多轮对话一致性 |
| **延迟** | Dense 模型推理速度快，适合实时交互 | MoE 模型路由开销不确定 |
| **中文能力** | 对中文营养学知识理解准确 | 部分开源模型中文推理能力不足 |
| **成本** | Google AI Studio 免费额度充足 | 商业 API 成本高 |

**结论**：Gemma 4 31B Dense 在函数调用稳定性、多步推理质量、中文理解能力三个维度上达到了本项目的要求。

### 模型调用方式

```python
# llm_client.py — 通过 OpenAI 兼容协议调用 Gemini API
from openai import AsyncOpenAI

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

client = AsyncOpenAI(
    api_key=settings.GEMINI_API_KEY,
    base_url=GEMINI_BASE_URL,
)

response = await client.chat.completions.create(
    model="gemma-4-31b-it",
    messages=messages,
    temperature=0.3,  # 低温度保证 JSON 输出稳定性
    max_tokens=2048,
)
```

---

## 3. 架构设计

### 3.1 整体架构

```
┌──────────────────────────────────────────────────┐
│                 用户入口 (3 种)                    │
│  🌐 Web (Vue 3)  │  💻 终端 (Skill)  │  🐳 Docker │
└────────┬─────────┴────────┬────────┴──────┬──────┘
         ▼                  ▼               ▼
┌──────────────────────────────────────────────────┐
│              FastAPI 后端                          │
│  ┌─────────────────────────────────────────────┐ │
│  │          MealDecisionFlow                    │ │
│  │  场景检测 → 记忆召回 → Agent 调度 → 辩论    │ │
│  └─────────────────────────────────────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ Agent 层  │ │ Service  │ │ Provider (MCP)   │ │
│  │ 8 Agents  │ │ Memory   │ │ 麦当劳 API       │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
│  ┌─────────────────────────────────────────────┐ │
│  │           SQLite 持久层                       │ │
│  │  用户档案 │ 用餐记录 │ 饮食记忆 │ 活跃方案   │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### 3.2 Agent 编排架构

**核心创新点：LLM 驱动的智能调度 + 4 阶段圆桌辩论**

#### Orchestrator 智能调度

不同于传统 rule-based 路由，Orchestrator 使用 Gemma 4 分析用户意图，动态选择最相关的 3-5 个 Agent：

```python
# orchestrator_agent.py
async def dispatch(self, context: dict) -> list[str]:
    """Gemma 4 分析用户场景，返回需要调度的 Agent 列表"""
    prompt = f"""
    用户场景: {context['user_input']}
    当前时间: {context['time']}
    用户档案: {context['profile_summary']}
    历史记忆: {context['habits']}

    请从以下 Agent 中选择 3-5 个最相关的:
    - profile, weight_loss, nutrition, budget, craving, time_context, safety, future_simulation

    返回 JSON: {{"agents": ["agent1", "agent2", ...], "reasoning": "..."}}
    """
    result = await generate_json(SYSTEM_PROMPT, prompt, schema)
    return result["agents"]
```

#### 4 阶段圆桌辩论 (DebateEngine)

```python
# debate_engine.py — 4 阶段辩论流程
class DebateEngine:
    async def run(self, opinions: dict) -> DebateResult:
        # 第一轮：各 Agent 发表初始意见
        round1 = await self._initial_opinions(opinions)

        # 第二轮：Gemma 4 发现冲突点
        conflicts = await self._discover_conflicts(round1)

        # 第三轮：形成妥协方案（Gemma 4 主持）
        compromises = await self._form_compromises(conflicts)

        # 第四轮：各 Agent 对方案投票
        votes = await self._final_vote(compromises)

        return DebateResult(plans=self._build_plans(votes))
```

**辩论示例**：
- 减脂Agent："建议选热量最低的板烧鸡腿餐，仅 372kcal"
- 预算Agent："但板烧套餐 ¥35 超出单餐预算 ¥25"
- 食欲Agent："用户今天心情低落，需要一定的满足感"
- **妥协**："选择高蛋白低热量的单品组合，控制在 ¥25 内，搭配无糖可乐满足口感"

### 3.3 Agent Memory 实现

```python
# memory_service.py
class MemoryService:
    """
    三层记忆架构：
    1. 短期记忆：当前对话上下文 (ConversationService, 内存)
    2. 中期记忆：用餐记录和偏好反馈 (SQLite, meal_records)
    3. 长期记忆：饮食习惯模式 (SQLite, habit_patterns)
    """

    async def record_meal(self, user_id: str, meal: MealRecord):
        """记录用餐 → 更新偏好权重 → 检测新模式"""
        await self.db.save(meal)
        await self._update_preference_weights(user_id, meal)
        pattern = await self._detect_pattern(user_id)
        if pattern.is_new:
            await self._save_pattern(user_id, pattern)

    async def get_context(self, user_id: str) -> MemoryContext:
        """召回全部记忆上下文，供 Orchestrator 使用"""
        preferences = await self._get_preferences(user_id)
        patterns = await self._get_patterns(user_id)
        recent_meals = await self._get_recent_meals(user_id, days=7)
        return MemoryContext(
            preferences=preferences,      # "偏好高蛋白、辣味"
            patterns=patterns,            # "工作日控制预算，周末放松"
            budget_trend=self._calc_budget_trend(recent_meals),
            nutrition_gaps=self._calc_nutrition_gaps(recent_meals),
        )
```

### 3.4 Tool Calling 实现

通过麦当劳 MCP (Model Context Protocol) 接入真实数据：

```python
# mcdonalds_mcp_provider.py
class McDonaldsMCPProvider(FoodProvider):
    """
    遵循 MCP 协议规范，将麦当劳 API 封装为 Agent 可调用的工具。
    Gemma 4 的 Function Calling 自动选择合适的工具。
    """

    # 工具 1: 搜索菜单
    async def search_menu(self, keyword: str) -> list[Meal]:
        """Gemma 4 生成: search_menu(keyword="鸡腿堡")"""

    # 工具 2: 获取营养数据
    async def get_nutrition(self, product_code: str) -> Nutrition:
        """Gemma 4 生成: get_nutrition(product_code="big_mac")"""

    # 工具 3: 计算价格（含优惠券）
    async def calculate_price(self, items, store_code) -> PriceResult:
        """Gemma 4 生成: calculate_price(items=[...], store_code="12345")"""

    # 工具 4: 创建订单
    async def create_order(self, items, store_code, order_type) -> OrderResult:
        """Gemma 4 生成: create_order(items=[...], store_code="12345", order_type=1)"""
```

---

## 4. Gemma 4 特性利用深度

### 4.1 原生函数调用 (Native Function Calling)

本项目**不只是简单的 Prompt 工程**，而是深度利用了 Gemma 4 的原生 Function Calling：

1. **Orchestrator 调度**：Gemma 4 分析用户场景后，输出结构化 JSON 选择 Agent 组合
2. **Agent 工具选择**：每个 Agent 通过 Function Calling 调用对应的 MCP 工具
3. **辩论主持**：DebateEngine 使用 Gemma 4 分析冲突、提出妥协、主持投票
4. **订单生成**：AutoDraftService 调用 MCP 的 `create_order` 完成闭环

### 4.2 多步规划 (Multi-step Planning)

一次决策流程涉及多个 LLM 调用步骤：

```
Step 1: 场景检测 (1 call)
Step 2: 记忆召回 (0 calls, DB query)
Step 3: Orchestrator 调度 (1 call)
Step 4: 3-5 Agent 并行分析 (3-5 calls)
Step 5: 辩论 - 初始意见 (1 call)
Step 6: 辩论 - 发现冲突 (1 call)
Step 7: 辩论 - 形成妥协 (1 call)
Step 8: 辩论 - 最终投票 (1 call)
Step 9: 方案构建 (1 call)
───────────────────────────────
总计: 10-12 次 LLM 调用/次决策
```

### 4.3 知识库增强

营养学知识库 (115 条) 通过 RAG 检索增强 Agent 的分析：

```python
# knowledge_service.py
async def get_relevant_knowledge(self, query: str) -> list[Knowledge]:
    """从营养学知识库检索相关知识，注入 Agent Prompt"""
```

知识来源：
- 《中国居民膳食指南 (2022)》
- 《中国食物成分表》
- Mifflin-St Jeor 基础代谢公式
- 情绪性进食研究论文

---

## 5. 数据流与持久化

### 5.1 数据模型

| 数据 | 存储方式 | 用途 |
|------|---------|------|
| 用户档案 | SQLAlchemy ORM | 长期管理模式 |
| 用餐记录 | SQLite (meal_records) | 营养追踪、历史回顾 |
| 饮食记忆 | SQLite (habit_patterns) | 偏好学习、模式检测 |
| 活跃方案 | SQLite (active_plans) | 多轮精炼、版本追踪 |
| 对话历史 | 内存 (ConversationService) | 多轮对话上下文 |

### 5.2 Provider 抽象层

```
FoodProvider (接口)
    ├── McDonaldsMCPProvider  → 真实麦当劳 MCP API
    ├── MockMcDonaldsProvider → Mock JSON 数据（无 MCP 时降级）
    └── ManualProvider        → 用户手动输入
```

通过 `ProviderFactory` 按配置自动选择，`USE_MOCK_MCP=true` 时降级到 Mock。

---

## 6. 部署方案

| 方式 | 适用场景 | 说明 |
|------|---------|------|
| Docker Compose | 一键演示 | `docker compose up -d --build` |
| 本地开发 | 开发调试 | uvicorn + pnpm dev |
| Cloudflare Workers | 线上部署 | Workers + D1 + Cron Triggers |
| Claude Code Skill | 终端使用 | meal-order skill 一键点餐 |

---

## 7. 项目亮点总结

1. **深度利用 Gemma 4 原生函数调用**：不是简单的 Prompt 模板，而是 Agent 自主选择工具、多步规划、结构化输出
2. **Agent Memory 持续学习**：记录饮食偏好，检测行为模式，每次决策都融入历史经验
3. **4 阶段圆桌辩论**：多个 Agent 从不同角度分析，发现冲突、形成妥协，给出有理有据的建议
4. **Tool Calling 闭环**：从营养查询到价格计算到自主下单，全流程通过 MCP 工具链完成
5. **面向程序员场景**：终端集成、饭点提醒、预算控制，解决真实痛点
