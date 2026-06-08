"""Budget Agent — checks daily/weekly budget constraints."""

from agents.base import BaseAgent
from models.agent_result import AgentResult


class BudgetAgent(BaseAgent):
    agent_name = "预算Agent"

    async def run(self, context: dict) -> AgentResult:
        user = context["user"]
        candidates = context.get("candidates", [])
        budget_service = context.get("budget_service")

        # Calculate average price from candidates
        avg_price = sum(i["price"] for i in candidates[:5]) / 5 if candidates else 0
        budget_pct = (avg_price / user.daily_budget * 100) if user.daily_budget > 0 else 0

        # Get today's spending if budget service available
        today_spent = 0.0
        if budget_service:
            today_spent = await budget_service.get_today_spent(user.user_id)

        remaining = user.daily_budget - today_spent

        # Try LLM
        llm_result = await self._try_llm(
            "你是一个预算顾问。评估用户的餐饮预算是否充足。用中文回答。",
            f"日预算：{user.daily_budget}元，已花费：{today_spent}元，平均套餐价格：{avg_price:.0f}元",
            {"assessment": "string", "score": 0.5}
        )

        if llm_result:
            reasons = [llm_result.get("assessment", "")]
            score = llm_result.get("score", 0.5 if budget_pct < 60 else 0.2)
        else:
            reasons = [f"平均套餐约 ¥{avg_price:.0f}", f"约占日预算 {budget_pct:.0f}%"]
            score = 0.5 if budget_pct < 60 else 0.2

        warnings = []
        if budget_pct > 60:
            warnings.append("考虑选择小份以节省预算")
        if today_spent > user.daily_budget * 0.8:
            warnings.append("今日预算已用大部分")

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            decision="approve" if budget_pct < 70 else "warn",
            reasons=reasons,
            warnings=warnings,
            data={"avg_price": avg_price, "budget_pct": budget_pct, "today_spent": today_spent, "remaining": remaining},
        )
