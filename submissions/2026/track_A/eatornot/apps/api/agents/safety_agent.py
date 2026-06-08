"""Safety Agent — checks allergies, extreme dieting, and order safety."""

from agents.base import BaseAgent
from models.agent_result import AgentResult


class SafetyAgent(BaseAgent):
    agent_name = "安全Agent"

    async def run(self, context: dict) -> AgentResult:
        user = context["user"]
        candidates = context.get("candidates", [])

        has_allergies = len(user.allergies) > 0
        warnings = []
        reasons = []

        # Check allergies against menu items
        if has_allergies:
            for item in candidates:
                item_tags = set(item.get("tags", []))
                user_allergies = set(a.lower() for a in user.allergies)
                if item_tags & user_allergies:
                    warnings.append(f"可能的过敏冲突：{item['name']}")
            reasons.append(f"过敏信息：{', '.join(user.allergies)}")
        else:
            reasons.append("未检测到过敏冲突")

        # Check extreme dieting
        if user.goal.value == "lose_weight" and user.weight_kg < 50:
            warnings.append("体重已偏低，建议维持而非继续减重")
            reasons.append("检测到极端减重目标")

        # Try LLM
        llm_result = await self._try_llm(
            "你是一个食品安全顾问。检查过敏风险和极端节食情况。用中文回答。",
            f"过敏原：{user.allergies}，目标：{user.goal.value}，体重：{user.weight_kg}kg",
            {"assessment": "string", "score": 0.5}
        )

        if llm_result:
            reasons = [llm_result.get("assessment", "")] + reasons

        score = 0.8 if not has_allergies else 0.3
        decision = "approve" if not has_allergies else "warn"

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            decision=decision,
            reasons=reasons,
            warnings=warnings,
        )
