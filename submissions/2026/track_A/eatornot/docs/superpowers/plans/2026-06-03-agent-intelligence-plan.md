# Agent 智能化 + 半自动下单 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Agent 系统从关键词/算法升级为 LLM 驱动，并新增半自动下单能力。

**Architecture:** 逐阶段独立 LLM 调用（调度→辩论→方案），每步独立降级到现有逻辑。下单通过麦当劳 MCP Provider 走真实 API。

**Tech Stack:** Python 3.12 / FastAPI / OpenAI-compatible LLM client / 麦当劳 MCP / React + TypeScript

---

## Task 1: LLM 驱动的 Orchestrator

**Files:**
- Modify: `apps/api/agents/orchestrator_agent.py`

- [ ] **Step 1: 重命名现有 `_select_agents` 为 `_keyword_select`**

在 `orchestrator_agent.py` 中，将第 120 行的 `def _select_agents` 方法重命名为 `def _keyword_select`，内容不变：

```python
def _keyword_select(self, message: str, mode: str) -> list[str]:
    """根据用户消息和模式选择需要的 Agent (关键词降级)"""
    # ... 原有 _select_agents 的全部代码不变 ...
```

- [ ] **Step 2: 新增 `_llm_select_agents` 方法**

在 `OrchestratorAgent` 类中新增以下方法（放在 `_keyword_select` 之后）：

```python
async def _llm_select_agents(self, message: str, mode: str, user_context: str) -> tuple[list[str], str] | None:
    """用 LLM 理解用户意图，选择需要的 Agent。失败返回 None。"""
    from core.llm_client import generate_json

    agent_descriptions = {
        "profile": "用户档案分析 — 根据身高体重目标等档案评估",
        "weight_loss": "减脂策略 — 热量缺口、减重方案",
        "nutrition": "营养评估 — 营养素均衡、微量元素",
        "budget": "预算控制 — 开销策略、性价比",
        "craving": "情绪性进食 — 情绪状态、食欲管理",
        "time_context": "时间压力 — 用餐时间、出餐速度",
        "safety": "过敏安全 — 过敏原、饮食禁忌",
        "future_simulation": "用餐影响预测 — 这次吃的长期影响",
    }

    min_agents = 3 if mode == "quick" else 4

    system_prompt = f"""你是饮食决策助手调度器。根据用户输入判断需要哪些专家Agent参与分析。

可选 Agent:
{chr(10).join(f'- {k}: {v}' for k, v in agent_descriptions.items())}

规则:
1. menu Agent 始终包含，不需要你选择
2. {'快速' if mode == 'quick' else '长期'}模式下最少选 {min_agents} 个 Agent
3. 根据用户意图选择最相关的 Agent，宁多勿少
4. 返回 JSON"""

    user_prompt = f"用户输入: {message}\n模式: {mode}\n用户背景: {user_context}"

    result = await generate_json(
        system_prompt,
        user_prompt,
        {"selected": ["agent_name1", "agent_name2"], "reason": "选择原因一句话"},
    )

    if result.get("fallback") or "selected" not in result:
        return None

    selected = result["selected"]
    # 校验: 过滤无效名称，保底补齐
    valid = [s for s in selected if s in AGENT_REGISTRY]
    if len(valid) < min_agents:
        # 补充默认 Agent
        for fallback in ["nutrition", "budget", "craving", "profile", "safety"]:
            if fallback not in valid:
                valid.append(fallback)
            if len(valid) >= min_agents:
                break

    return valid, result.get("reason", "LLM 调度选择")

```

- [ ] **Step 3: 新增 `_build_user_context` 辅助方法**

```python
def _build_user_context(self, context: dict) -> str:
    """从 context 中提取用户背景摘要给 LLM"""
    parts = []
    user = context.get("user")
    if user:
        goal_map = {"lose_weight": "减脂", "maintain": "维持", "gain_muscle": "增肌"}
        parts.append(f"目标: {goal_map.get(user.goal.value, user.goal.value)}")
        if hasattr(user, "daily_budget") and user.daily_budget:
            parts.append(f"日预算: {user.daily_budget}元")
        if hasattr(user, "allergies") and user.allergies:
            parts.append(f"过敏: {','.join(user.allergies)}")
    mood = context.get("mood")
    if mood and mood != "normal":
        parts.append(f"情绪: {mood}")
    return "；".join(parts) if parts else "无特殊背景"
```

- [ ] **Step 4: 改写 `run()` 方法，串联 LLM 调度和降级**

替换 `OrchestratorAgent.run()` 方法体：

```python
async def run(self, context: dict) -> dict:
    message = context.get("message", "").lower()
    mode = context.get("mode", "long_term")
    user_context = self._build_user_context(context)

    # 1. 尝试 LLM 调度
    selected = None
    reason = ""
    llm_result = await self._llm_select_agents(message, mode, user_context)
    if llm_result:
        selected, reason = llm_result
        logger.info(f"LLM selected agents: {selected} — {reason}")
    else:
        # 2. 降级到关键词匹配
        selected = self._keyword_select(message, mode)
        reason = self._build_reason(message, selected) + "（降级模式）"
        logger.info(f"Keyword fallback agents: {selected}")

    # 3. 始终包含 MenuAgent
    if "menu" not in selected:
        selected.insert(0, "menu")

    # 4. 并行运行选中的 Agent
    agents = []
    agent_names = []
    for name in selected:
        if name == "menu":
            agents.append(MenuAgent())
        elif name in AGENT_REGISTRY:
            agents.append(AGENT_REGISTRY[name]())
        agent_names.append(name)

    results = await asyncio.gather(*(a.run(context) for a in agents))

    return {
        "selected_agents": agent_names,
        "results": list(results),
        "reason": reason,
    }
```

- [ ] **Step 5: 手动验证**

启动后端后用 curl 测试：

```bash
# 测试 LLM 调度（需要 CF_AIG_TOKEN）
curl -X POST http://localhost:8001/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo-user","message":"今天加班好累想吃点好的犒劳自己","mode":"long_term"}'
```

检查返回的 `agent_debate` 中 Agent 名称和 reason 是否合理。无 token 时应降级到关键词匹配。

- [ ] **Step 6: 提交**

```bash
git add apps/api/agents/orchestrator_agent.py
git commit -m "feat: OrchestratorAgent LLM 调度，关键词降级"
```

---

## Task 2: LLM 驱动的 DebateEngine

**Files:**
- Modify: `apps/api/agents/debate_engine.py`

- [ ] **Step 1: 将现有 `run()` 及 4 个 `_stage_*` 方法包装为 `_algorithmic_debate`**

在 `DebateEngine` 类中，将现有 `run()` 方法重命名为 `_algorithmic_debate`：

```python
def _algorithmic_debate(self, agent_results: list[AgentResult], context: dict) -> DebateResult:
    """算法辩论（降级路径）"""
    debate_id = str(uuid.uuid4())[:8]
    stage1 = self._stage_initial_opinions(agent_results)
    stage2 = self._stage_conflicts(agent_results)
    stage3 = self._stage_compromise(agent_results, context)
    stage4 = self._stage_final_vote(agent_results, stage3)
    return DebateResult(debate_id=debate_id, stages=[stage1, stage2, stage3, stage4])
```

原有的 4 个 `_stage_*` 方法和 `_build_position`、`_get_evidence`、`_build_conflict_reason`、`_build_compromise` 全部保留不动。

- [ ] **Step 2: 新增 `_llm_debate` 方法**

```python
async def _llm_debate(self, agent_results: list[AgentResult], context: dict) -> DebateResult | None:
    """用 LLM 生成 4 阶段辩论。失败返回 None。"""
    from core.llm_client import generate_json

    # 过滤掉菜单Agent
    filtered = [r for r in agent_results if r.agent_name != "菜单Agent"]

    # 构建 Agent 摘要
    agent_summaries = []
    for r in filtered:
        summary = f"[{r.agent_name}]: 评分={r.score:.1f}, 立场={r.reasons[0] if r.reasons else '无'}"
        if r.warnings:
            summary += f", 警告={r.warnings[0]}"
        agent_summaries.append(summary)

    user = context.get("user")
    goal_map = {"lose_weight": "减脂", "maintain": "维持", "gain_muscle": "增肌"}
    user_desc = ""
    if user:
        user_desc = f"用户目标: {goal_map.get(user.goal.value, user.goal.value)}, 日预算: {getattr(user, 'daily_budget', '未知')}元"

    system_prompt = """你是一场饮食决策圆桌辩论的主持人。你要根据各专家Agent的分析结果，模拟一场真实的辩论。

辩论规则:
1. initial_opinions: 每个Agent陈述自己的立场和理由
2. conflicts: 找出Agent之间真正有逻辑冲突的观点（不只是分数差异，而是理念冲突）
3. compromise: 主持人提出一个平衡各方意见的妥协方案
4. final_vote: 每个Agent对妥协方案投票(approve/warn/reject)并说明理由

要求:
- 辩论内容要有逻辑，像真实的专家讨论
- 冲突描述要具体（"营养师担心热量超标，但心理顾问认为用户需要情绪安慰"）
- 妥协方案要平衡，不是简单折中
- 每个Agent的发言要符合其专业角色
- 返回合法JSON"""

    user_prompt = f"""专家分析结果:
{chr(10).join(agent_summaries)}

{user_desc}

请主持这场辩论，返回JSON。"""

    schema = {
        "stages": [
            {
                "stage": "initial_opinions",
                "messages": [{"agent": "name", "position": "立场陈述", "confidence": 0.8}]
            },
            {
                "stage": "conflicts",
                "messages": [{"agent": "name", "conflict_with": "name", "reason": "冲突原因", "confidence": 0.6}]
            },
            {
                "stage": "compromise",
                "messages": [{"agent": "调度Agent", "position": "妥协方案", "accepted_by": ["name1", "name2"], "confidence": 0.7}]
            },
            {
                "stage": "final_vote",
                "messages": [{"agent": "name", "vote": "approve", "warning": "可选警告", "confidence": 0.8}]
            }
        ]
    }

    result = await generate_json(system_prompt, user_prompt, schema)

    if result.get("fallback") or "stages" not in result:
        return None

    # 将 LLM 返回转为 DebateResult
    try:
        stages = []
        for s in result["stages"]:
            from models.debate import DebateMessage, DebateStage
            messages = []
            for m in s.get("messages", []):
                messages.append(DebateMessage(
                    agent=m.get("agent", ""),
                    position=m.get("position", ""),
                    confidence=m.get("confidence", 0.5),
                    conflict_with=m.get("conflict_with"),
                    reason=m.get("reason"),
                    vote=m.get("vote"),
                    warning=m.get("warning"),
                    accepted_by=m.get("accepted_by", []),
                    evidence=[],
                ))
            stage_names = {
                "initial_opinions": "第一轮：各Agent初始判断",
                "conflicts": "第二轮：发现冲突",
                "compromise": "第三轮：形成妥协",
                "final_vote": "第四轮：最终投票",
            }
            stages.append(DebateStage(
                stage=s.get("stage", ""),
                title=stage_names.get(s.get("stage", ""), s.get("stage", "")),
                messages=messages,
            ))

        return DebateResult(
            debate_id=str(uuid.uuid4())[:8],
            stages=stages,
        )
    except Exception as e:
        logger.error(f"Failed to parse LLM debate result: {e}")
        return None
```

- [ ] **Step 3: 新增 `run()` 入口，串联 LLM 和降级**

```python
async def run(self, agent_results: list[AgentResult], context: dict) -> DebateResult:
    """运行完整辩论流程（LLM优先，算法降级）"""
    # 尝试 LLM 辩论
    llm_result = await self._llm_debate(agent_results, context)
    if llm_result:
        logger.info(f"LLM debate completed: {llm_result.debate_id}")
        return llm_result

    # 降级到算法辩论
    logger.info("Falling back to algorithmic debate")
    return self._algorithmic_debate(agent_results, context)
```

- [ ] **Step 4: 手动验证**

```bash
curl -X POST http://localhost:8001/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo-user","message":"想吃炸鸡但又在减肥","mode":"long_term"}'
```

检查返回 `debate.stages` 中各 stage 的 messages 是否有具体内容（而非模板文字）。

- [ ] **Step 5: 提交**

```bash
git add apps/api/agents/debate_engine.py
git commit -m "feat: DebateEngine LLM 辩论，算法降级"
```

---

## Task 3: 修复 DebateEngine async 调用链

**Files:**
- Modify: `apps/api/agents/supervisor_agent.py` (第 32 行)

- [ ] **Step 1: 在 SupervisorAgent 中加 await**

`supervisor_agent.py` 第 32 行：

```python
# 改前:
debate_result = debate_engine.run(agent_debate, context)

# 改后:
debate_result = await debate_engine.run(agent_debate, context)
```

- [ ] **Step 2: 全局搜索其他 debate_engine.run 调用**

```bash
grep -rn "debate_engine\.run\|DebateEngine.*run" apps/api/
```

确保所有调用处都有 `await`。如果其他路由也直接调用 DebateEngine，同样加 `await`。

- [ ] **Step 3: 提交**

```bash
git add apps/api/agents/supervisor_agent.py
git commit -m "fix: DebateEngine.run() 改为 async，调用处加 await"
```

---

## Task 4: LLM 驱动的方案生成

**Files:**
- Modify: `apps/api/agents/supervisor_agent.py`

- [ ] **Step 1: 重命名现有 `_build_plans` 为 `_template_build_plans`**

将第 64 行的 `def _build_plans` 重命名为 `def _template_build_plans`，内部代码不变。

- [ ] **Step 2: 新增辅助方法 `_summarize_agents` 和 `_summarize_debate`**

```python
def _summarize_agents(self, agent_results: list[AgentResult]) -> str:
    """汇总各 Agent 的分析结果"""
    parts = []
    for r in agent_results:
        if r.agent_name == "菜单Agent":
            continue
        reason = r.reasons[0] if r.reasons else "无具体建议"
        parts.append(f"{r.agent_name}(评分{r.score:.1f}): {reason}")
    return "；".join(parts)

def _summarize_debate(self, debate_result) -> str:
    """汇总辩论结论"""
    if not debate_result or not debate_result.stages:
        return "无辩论结果"
    # 取妥协阶段的结论
    for stage in debate_result.stages:
        if stage.stage == "compromise" and stage.messages:
            return stage.messages[0].position
    # 取最终投票
    for stage in debate_result.stages:
        if stage.stage == "final_vote" and stage.messages:
            votes = [f"{m.agent}={m.vote}" for m in stage.messages]
            return "投票结果: " + ", ".join(votes)
    return "辩论已完成"
```

- [ ] **Step 3: 新增 `_llm_build_plans` 方法**

```python
async def _llm_build_plans(self, candidates: list, user, agent_results: list[AgentResult], debate_result, context: dict) -> list[RecommendationPlan] | None:
    """用 LLM 智能组合 3 个方案。失败返回 None。"""
    from core.llm_client import generate_json

    agent_summary = self._summarize_agents(agent_results)
    debate_summary = self._summarize_debate(debate_result)

    # 精简菜品信息给 LLM
    items_brief = []
    for c in candidates:
        items_brief.append({
            "name": c.get("name", ""),
            "price": c.get("price", 0),
            "calories": c.get("calories", 0),
            "protein": c.get("protein", 0),
            "category": c.get("category", ""),
        })

    goal_map = {"lose_weight": "减脂", "maintain": "维持", "gain_muscle": "增肌"}
    bmr = calculate_bmr(user.weight_kg, user.height_cm, user.age, user.sex)
    tdee = calculate_tdee(bmr, user.activity_level)
    daily_target = get_daily_calorie_target(tdee, user.goal.value)

    system_prompt = """你是饮食方案设计师。根据专家辩论结果，从候选菜品中为用户组合3个方案。

方案要求:
1. "自律减脂餐"(disciplined): 优先满足健康/减脂目标，选热量低、蛋白高的组合
2. "省钱管饱餐"(budget_friendly): 优先满足预算约束，选性价比高的组合
3. "放纵犒劳餐"(controlled_indulgence): 优先满足情绪/食欲需求，但要给出控制建议

每个方案选2-3个菜品(必须来自候选列表中的name)，给出2-3条优缺点，和一句有说服力的推荐语（像营养师面对面跟你说的话，个性化、有温度）。

返回合法JSON。"""

    user_prompt = f"""候选菜品: {items_brief}
用户档案: 目标={goal_map.get(user.goal.value, user.goal.value)}, 日预算={user.daily_budget}元, 日热量目标={daily_target:.0f}kcal
专家建议: {agent_summary}
辩论结论: {debate_summary}"""

    schema = {
        "plans": [
            {
                "mode": "disciplined|budget_friendly|controlled_indulgence",
                "items": ["菜品name1", "菜品name2"],
                "pros": ["优点1", "优点2"],
                "cons": ["缺点1"],
                "final_reason": "一句个性化推荐语"
            }
        ]
    }

    result = await generate_json(system_prompt, user_prompt, schema)

    if result.get("fallback") or "plans" not in result:
        return None

    try:
        plans = []
        for p in result["plans"]:
            # 从 candidates 中匹配 LLM 返回的菜品 name
            matched_items = []
            for name in p.get("items", []):
                for c in candidates:
                    if c.get("name") == name and c not in matched_items:
                        matched_items.append(c)
                        break

            if not matched_items:
                continue  # LLM 返回了不存在的菜品，跳过这个方案

            mi = [MenuItem(
                name=c["name"],
                item_code=c["item_code"],
                category=c.get("category", ""),
                price=c["price"],
                calories=c["calories"],
                protein=c.get("protein", 0),
                fat=c.get("fat", 0),
                carbohydrate=c.get("carbohydrate", 0),
                sodium=c.get("sodium", 0),
                tags=c.get("tags", []),
            ) for c in matched_items]

            total_price = sum(i.price for i in mi)
            total_cal = sum(i.calories for i in mi)

            mode = p.get("mode", "disciplined")
            title_map = {
                "disciplined": "💪 自律减脂餐",
                "budget_friendly": "💰 省钱包饱餐",
                "controlled_indulgence": "🍔 放纵一下餐",
            }

            plans.append(RecommendationPlan(
                id=str(uuid.uuid4())[:8],
                title=title_map.get(mode, mode),
                mode=mode,
                items=mi,
                estimated_price=round(total_price, 2),
                estimated_calories=round(total_cal, 0),
                protein=round(sum(i.protein for i in mi), 1),
                fat=round(sum(i.fat for i in mi), 1),
                carbohydrate=round(sum(i.carbohydrate for i in mi), 1),
                sodium=round(sum(i.sodium for i in mi), 0),
                budget_impact=f"占日预算 {total_price / user.daily_budget * 100:.0f}%" if user.daily_budget > 0 else "N/A",
                calorie_impact=f"占日目标 {total_cal / daily_target * 100:.0f}%" if daily_target > 0 else "N/A",
                indulgence_impact="消耗1次本周放纵额度" if mode == "controlled_indulgence" else "不消耗放纵额度",
                pros=p.get("pros", []),
                cons=p.get("cons", []),
                safety_warnings=[],
                final_reason=p.get("final_reason", ""),
                agent_votes=[],
            ))

        if len(plans) < 3:
            return None  # 方案不足 3 个，降级

        return plans
    except Exception as e:
        logger.error(f"Failed to parse LLM plans: {e}")
        return None
```

- [ ] **Step 4: 改写 SupervisorAgent.run() 中的方案生成调用**

在 `SupervisorAgent.run()` 方法中，找到这一行（约第 36 行）：

```python
# 改前:
plans = self._build_plans(context.get("candidates", []), context["user"], agent_debate, context)

# 改后:
llm_plans = await self._llm_build_plans(context.get("candidates", []), context["user"], agent_debate, debate_result, context)
if llm_plans:
    plans = llm_plans
else:
    plans = self._template_build_plans(context.get("candidates", []), context["user"], agent_debate, context)
```

- [ ] **Step 5: 手动验证**

```bash
curl -X POST http://localhost:8001/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo-user","message":"想吃炸鸡但又在减肥，预算只有30","mode":"long_term"}'
```

检查返回 3 个 plans 的 `final_reason` 是否个性化（不是硬编码模板）。

- [ ] **Step 6: 提交**

```bash
git add apps/api/agents/supervisor_agent.py
git commit -m "feat: SupervisorAgent LLM 方案生成，模板降级"
```

---

## Task 5: 订单数据模型

**Files:**
- Create: `apps/api/models/order.py`

- [ ] **Step 1: 创建订单请求/响应模型**

创建 `apps/api/models/order.py`：

```python
"""订单相关数据模型"""

from pydantic import BaseModel, Field
from typing import Optional


class OrderItem(BaseModel):
    """订单中的单个菜品"""
    product_code: str
    product_name: str = ""
    quantity: int = 1
    price: float = 0
    calories: float = 0


class CreateOrderRequest(BaseModel):
    """创建订单请求"""
    user_id: str = "demo-user"
    plan_id: str
    items: list[OrderItem]
    store_code: str = "S001"
    order_type: int = 1  # 1=到店, 2=外送


class OrderResponse(BaseModel):
    """订单响应"""
    success: bool
    order_id: str = ""
    pay_url: str = ""
    status: str = ""  # pending_payment / confirmed / failed
    total_price: float = 0
    message: str = ""
    is_mock: bool = False
```

- [ ] **Step 2: 提交**

```bash
git add apps/api/models/order.py
git commit -m "feat: 订单数据模型 (OrderItem/CreateOrderRequest/OrderResponse)"
```

---

## Task 6: OrderService + Provider 下单方法

**Files:**
- Create: `apps/api/services/order_service.py`
- Modify: `apps/api/providers/mcdonalds_mcp_provider.py`

- [ ] **Step 1: 在 McDonaldsMcpProvider 中新增 `create_order` 方法**

在 `providers/mcdonalds_mcp_provider.py` 的 `McDonaldsMcpProvider` 类中，`confirm_order` 方法之后新增：

```python
async def create_order(self, store_code: str, items: list[dict], order_type: int = 1, take_way_code: str = None) -> dict:
    """通过 MCP 创建真实订单

    Args:
        store_code: 门店编码
        items: [{"productCode": "xxx", "quantity": 1}, ...]
        order_type: 1=到店, 2=外送
        take_way_code: 取餐方式编码
    """
    try:
        # 先计算价格确认
        price_result = await self._call_mcp_tool("calculate-price", {
            "items": items,
            "storeCode": store_code,
            "orderType": order_type,
        })

        if not price_result or price_result.get("error"):
            return {"success": False, "message": "价格计算失败，无法下单"}

        # 从价格结果中获取 take_way_code
        if not take_way_code and isinstance(price_result, dict):
            take_ways = price_result.get("takeWayList", [])
            if take_ways:
                take_way_code = take_ways[0].get("code", "DINE_IN")

        # 创建订单
        order_args = {
            "items": items,
            "storeCode": store_code,
            "orderType": order_type,
        }
        if take_way_code:
            order_args["takeWayCode"] = take_way_code

        order_result = await self._call_mcp_tool("create-order", order_args)

        if order_result and isinstance(order_result, dict):
            return {
                "success": True,
                "order_id": order_result.get("orderId", str(uuid.uuid4())[:8]),
                "pay_url": order_result.get("payUrl", ""),
                "status": "pending_payment",
                "total_price": order_result.get("totalPrice", 0),
                "message": "订单创建成功",
                "is_mock": False,
            }

        return {"success": False, "message": "MCP 未返回有效订单结果"}

    except Exception as e:
        logger.error(f"create_order error: {e}")
        return {"success": False, "message": f"下单失败: {str(e)}"}
```

- [ ] **Step 2: 创建 OrderService**

创建 `apps/api/services/order_service.py`：

```python
"""订单服务 — 串联 Provider 下单流程"""

import logging
from providers.factory import get_provider
from models.order import CreateOrderRequest, OrderResponse

logger = logging.getLogger(__name__)


async def create_order_from_plan(request: CreateOrderRequest) -> OrderResponse:
    """从用户选中的方案创建订单

    流程:
    1. 获取 Provider
    2. 组装 MCP 下单参数
    3. 调 Provider.create_order
    4. 返回订单结果
    """
    provider = get_provider()

    # 组装菜品参数
    items = [
        {"productCode": item.product_code, "quantity": item.quantity}
        for item in request.items
    ]

    # 尝试真实下单
    if hasattr(provider, "create_order"):
        result = await provider.create_order(
            store_code=request.store_code,
            items=items,
            order_type=request.order_type,
        )
        if result.get("success"):
            return OrderResponse(
                success=True,
                order_id=result.get("order_id", ""),
                pay_url=result.get("pay_url", ""),
                status=result.get("status", "pending_payment"),
                total_price=result.get("total_price", 0),
                message=result.get("message", "订单创建成功"),
                is_mock=result.get("is_mock", False),
            )

        # MCP 下单失败
        logger.warning(f"MCP order failed: {result.get('message')}")
        return OrderResponse(
            success=False,
            status="failed",
            message=result.get("message", "下单服务暂不可用"),
        )

    # Provider 不支持下单
    return OrderResponse(
        success=False,
        status="failed",
        message="当前数据源不支持下单，请前往麦当劳APP下单",
        is_mock=True,
    )
```

- [ ] **Step 3: 检查 providers/factory.py 是否有 `get_provider` 函数**

```bash
grep -n "def get_provider" apps/api/providers/factory.py
```

如果函数名不同（比如 `create_provider`），在 `order_service.py` 中调整 import。

- [ ] **Step 4: 提交**

```bash
git add apps/api/services/order_service.py apps/api/providers/mcdonalds_mcp_provider.py
git commit -m "feat: OrderService + McDonaldsMcpProvider.create_order"
```

---

## Task 7: 订单 API 路由 + 注册

**Files:**
- Create: `apps/api/api/order_routes.py`
- Modify: `apps/api/main.py`

- [ ] **Step 1: 创建订单路由**

创建 `apps/api/api/order_routes.py`：

```python
"""订单路由"""

import logging
from fastapi import APIRouter, HTTPException
from models.order import CreateOrderRequest, OrderResponse
from services.order_service import create_order_from_plan

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/order/create", response_model=OrderResponse)
async def create_order(request: CreateOrderRequest):
    """从方案创建订单"""
    logger.info(f"Create order: plan_id={request.plan_id}, items={len(request.items)}")

    result = await create_order_from_plan(request)
    return result
```

- [ ] **Step 2: 在 main.py 中注册路由**

在 `main.py` 的 import 区域（第 22 行后）新增：

```python
from api.order_routes import router as order_router
```

在路由注册区域（第 72 行后）新增：

```python
app.include_router(order_router, prefix="/api", tags=["order"])
```

- [ ] **Step 3: 手动验证**

```bash
# 启动后端后测试
curl -X POST http://localhost:8001/api/order/create \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo-user","plan_id":"test123","items":[{"product_code":"MCD_001","product_name":"巨无霸","quantity":1,"price":25,"calories":387}],"store_code":"S001"}'
```

应返回 `{"success":false/false,...}` 而不是 404。

- [ ] **Step 4: 提交**

```bash
git add apps/api/api/order_routes.py apps/api/main.py
git commit -m "feat: POST /api/order/create 订单路由"
```

---

## Task 8: 前端下单流程集成

**Files:**
- Modify: `apps/web/src/api/client.ts`
- Modify: `apps/web/src/components/OrderConfirmModal.tsx`

- [ ] **Step 1: 在 client.ts 新增下单接口**

在 `apps/web/src/api/client.ts` 末尾新增：

```typescript
export interface OrderResponse {
  success: boolean
  order_id: string
  pay_url: string
  status: string
  total_price: number
  message: string
  is_mock: boolean
}

export async function createOrder(plan: RecommendationPlan, storeCode: string = 'S001'): Promise<OrderResponse> {
  const res = await fetch(`${BASE}/api/order/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: 'demo-user',
      plan_id: plan.id,
      items: plan.items.map(item => ({
        product_code: item.item_code,
        product_name: item.name,
        quantity: 1,
        price: item.price,
        calories: item.calories,
      })),
      store_code: storeCode,
      order_type: 1,
    }),
  })
  return res.json()
}
```

- [ ] **Step 2: 改造 OrderConfirmModal**

替换 `apps/web/src/components/OrderConfirmModal.tsx` 全部内容：

```tsx
import { useState } from 'react'
import { createOrder, type RecommendationPlan } from '../api/client'

export function OrderConfirmModal({
  plan,
  onClose,
  onOrderComplete,
}: {
  plan: RecommendationPlan
  onClose: () => void
  onOrderComplete: (result: { success: boolean; message: string }) => void
}) {
  const [loading, setLoading] = useState(false)
  const [storeCode, setStoreCode] = useState('S001')

  const handleConfirm = async () => {
    setLoading(true)
    try {
      const result = await createOrder(plan, storeCode)
      onOrderComplete(result)
    } catch (err) {
      onOrderComplete({ success: false, message: '下单请求失败' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>📋 确认订单</h2>
        <div className="modal-items">
          {plan.items.map((item, i) => (
            <div key={i} className="modal-item">
              <span>{item.name}</span>
              <span>¥{item.price.toFixed(0)} / {item.calories}kcal</span>
            </div>
          ))}
        </div>
        <div className="modal-summary">
          <div>总计: ¥{plan.estimated_price.toFixed(0)}</div>
          <div>总热量: {plan.estimated_calories.toFixed(0)} 千卡</div>
          <div>预算影响: {plan.budget_impact}</div>
        </div>
        <div className="modal-store">
          <label>门店编码: </label>
          <input
            value={storeCode}
            onChange={(e) => setStoreCode(e.target.value)}
            placeholder="S001"
          />
        </div>
        {plan.safety_warnings.length > 0 && (
          <div className="modal-warnings">
            {plan.safety_warnings.map((w, i) => <div key={i}>⚠️ {w}</div>)}
          </div>
        )}
        <div className="modal-actions">
          <button className="btn-cancel" onClick={onClose} disabled={loading}>取消</button>
          <button className="btn-confirm" onClick={handleConfirm} disabled={loading}>
            {loading ? '下单中...' : '确认下单'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 检查 App.tsx 中 OrderConfirmModal 的调用方式**

```bash
grep -n "OrderConfirmModal" apps/web/src/App.tsx
```

如果 App.tsx 中 `onConfirm` prop 的处理只是 `confirmOrder(plan)` 调用旧接口，需要更新为新的回调签名 `onOrderComplete`。具体改动视 App.tsx 中的使用方式而定。

- [ ] **Step 4: 前端构建验证**

```bash
cd apps/web && npm run build
```

确保无 TypeScript 编译错误。

- [ ] **Step 5: 提交**

```bash
git add apps/web/src/api/client.ts apps/web/src/components/OrderConfirmModal.tsx
git commit -m "feat: 前端下单流程集成 (createOrder + OrderConfirmModal 改造)"
```

---

## Task 9: 全链路集成验证 + 最终提交

- [ ] **Step 1: 启动后端和前端**

```bash
cd apps/api && uvicorn main:app --host 127.0.0.1 --port 8001 &
cd apps/web && npm run dev
```

- [ ] **Step 2: 完整流程测试**

在浏览器 http://localhost:5173 中：
1. 选择长期模式 → 完整建档
2. 输入 "今天加班好累想吃点好的" → 检查辩论是否有 LLM 生成的内容
3. 选择一个方案 → 检查 final_reason 是否个性化
4. 点确认下单 → 检查是否弹出 OrderConfirmModal 并正确调用 API

- [ ] **Step 3: 降级测试**

临时清空 `CF_AIG_TOKEN`，重启后端，重复上述流程。应降级到关键词/算法模式，无报错。

- [ ] **Step 4: 最终提交并推送**

```bash
git push origin feat/ui-and-agent-experience
```

如果一切正常，可以创建 PR 合并到 main。

---

## 依赖关系

```
Task 1 (Orchestrator) ──┐
                         ├─→ Task 4 (Supervisor 方案) ─→ Task 9 (集成验证)
Task 2 (DebateEngine) ──┤        ↑
                         │        │
Task 3 (async fix) ─────┘        │
                                  │
Task 5 (Order模型) ─→ Task 6 (OrderService) ─→ Task 7 (Route) ─→ Task 8 (前端) ─┘
```

Task 1-3 可并行执行。Task 5-7 可并行执行。Task 4 依赖 1-3。Task 8 依赖 7。
