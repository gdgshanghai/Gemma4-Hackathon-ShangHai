"""Nutrition Agent — evaluates food candidates for nutritional quality."""

from agents.base import BaseAgent
from models.agent_result import AgentResult
from services.nutrition_calculator import evaluate_nutrition


class NutritionAgent(BaseAgent):
    agent_name = "营养Agent"

    async def run(self, context: dict) -> AgentResult:
        candidates = context.get("candidates", [])
        user = context["user"]

        # Score each candidate
        scored = []
        for item in candidates:
            result = evaluate_nutrition(item)
            scored.append((item, result["score"], result["flags"]))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_items = scored[:3]

        # Try LLM for ranking
        llm_result = await self._try_llm(
            "你是一个营养专家。为用户的饮食目标推荐食物。用中文回答。",
            f"候选食物：{[i[0]['name'] for i in top_items]}。用户目标：{user.goal.value}",
            {"ranking": ["string"], "reasons": ["string"]}
        )

        if llm_result:
            reasons = llm_result.get("reasons", [])
            if not reasons:
                reasons = [f"推荐：{', '.join(i[0]['name'] for i in top_items)}"]
        else:
            reasons = [f"推荐：{', '.join(i[0]['name'] for i in top_items)}", "优先选择高蛋白、低钠选项"]

        # Check for high sodium warnings
        warnings = []
        for item, score, flags in top_items:
            if "high_sodium" in flags:
                warnings.append("部分选项钠含量偏高")
                break

        return AgentResult(
            agent_name=self.agent_name,
            score=0.4,
            decision="approve",
            reasons=reasons,
            warnings=warnings,
            data={"top_items": [i[0]["item_code"] for i in top_items]},
        )
