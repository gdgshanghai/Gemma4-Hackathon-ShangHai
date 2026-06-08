"""Orchestrator Agent — 智能调度器，根据用户输入决定需要调用哪些 Agent"""

import asyncio
import logging
from agents.base import BaseAgent
from agents.profile_agent import ProfileAgent
from agents.weight_loss_agent import WeightLossAgent
from agents.nutrition_agent import NutritionAgent
from agents.budget_agent import BudgetAgent
from agents.craving_agent import CravingAgent
from agents.time_context_agent import TimeContextAgent
from agents.menu_agent import MenuAgent
from agents.safety_agent import SafetyAgent
from agents.future_simulation_agent import FutureSimulationAgent
from models.agent_result import AgentResult

logger = logging.getLogger(__name__)

# Agent 注册表
AGENT_REGISTRY = {
    "profile": ProfileAgent,
    "weight_loss": WeightLossAgent,
    "nutrition": NutritionAgent,
    "budget": BudgetAgent,
    "craving": CravingAgent,
    "time_context": TimeContextAgent,
    "safety": SafetyAgent,
    "future_simulation": FutureSimulationAgent,
}

# 关键词 → Agent 映射
KEYWORD_AGENT_MAP = {
    # 预算相关
    "预算": ["budget", "nutrition"],
    "便宜": ["budget", "nutrition"],
    "省钱": ["budget"],
    "花了多少": ["budget"],
    "budget": ["budget"],

    # 减脂相关
    "减脂": ["weight_loss", "nutrition", "profile"],
    "减肥": ["weight_loss", "nutrition", "profile"],
    "热量": ["weight_loss", "nutrition"],
    "卡路里": ["weight_loss", "nutrition"],
    "低卡": ["weight_loss", "nutrition"],

    # 情绪/食欲相关
    "累": ["craving", "time_context"],
    "疲惫": ["craving", "time_context"],
    "压力": ["craving"],
    "心情": ["craving"],
    "馋": ["craving"],
    "想吃": ["craving", "nutrition"],
    "饿": ["craving", "nutrition"],

    # 安全相关
    "过敏": ["safety"],
    "不要": ["safety"],
    "忌口": ["safety"],

    # 时间相关
    "赶时间": ["time_context"],
    "快": ["time_context"],
    "急": ["time_context"],
}

# 默认 Agent 组合（最少要跑的）
DEFAULT_AGENTS = ["profile", "menu"]


class OrchestratorAgent(BaseAgent):
    """智能调度器：分析用户输入，动态选择需要运行的 Agent"""

    agent_name = "Orchestrator Agent"

    async def run(self, context: dict) -> dict:
        """
        分析用户输入，决定需要运行哪些 Agent，然后并行执行。

        Returns:
            dict: {
                "selected_agents": list[str],  # 选中的 Agent 名称
                "results": list[AgentResult],   # Agent 执行结果
                "reason": str,                  # 选择原因
            }
        """
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

        # 3. 始终包含 MenuAgent（获取菜品数据）
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

    def _keyword_select(self, message: str, mode: str) -> list[str]:
        """根据用户消息和模式选择需要的 Agent"""
        selected = set(DEFAULT_AGENTS)

        # 快速模式：只跑核心 Agent
        if mode == "quick":
            selected.update(["nutrition", "budget", "craving"])
            return list(selected)

        # 长期模式：根据关键词动态选择
        matched_agents = set()
        for keyword, agents in KEYWORD_AGENT_MAP.items():
            if keyword in message:
                matched_agents.update(agents)

        if matched_agents:
            selected.update(matched_agents)
        else:
            # 没有匹配到关键词，默认跑全套（但排除不必要的）
            selected.update([
                "profile",
                "nutrition",
                "budget",
                "craving",
                "safety",
            ])

        return list(selected)

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
            for fallback in ["nutrition", "budget", "craving", "profile", "safety"]:
                if fallback not in valid:
                    valid.append(fallback)
                if len(valid) >= min_agents:
                    break

        return valid, result.get("reason", "LLM 调度选择")

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

    def _build_reason(self, message: str, selected: list[str]) -> str:
        """构建选择原因的可读描述"""
        reasons = []

        if "budget" in selected:
            if any(kw in message for kw in ["预算", "便宜", "省钱"]):
                reasons.append("检测到预算相关需求")
            else:
                reasons.append("检查预算约束")

        if "weight_loss" in selected:
            reasons.append("检测到减脂/热量相关需求")

        if "craving" in selected:
            if any(kw in message for kw in ["累", "疲惫", "压力"]):
                reasons.append("检测到情绪状态，评估食欲")
            else:
                reasons.append("评估食欲和情绪")

        if "safety" in selected:
            reasons.append("检查过敏/安全信息")

        if "time_context" in selected:
            reasons.append("考虑时间压力")

        if not reasons:
            reasons.append("进行全面分析")

        return "；".join(reasons)
