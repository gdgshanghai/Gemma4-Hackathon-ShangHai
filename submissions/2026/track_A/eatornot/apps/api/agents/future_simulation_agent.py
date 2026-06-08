"""Future Simulation Agent — simulates effects on today's calorie/budget balance."""

from agents.base import BaseAgent
from models.agent_result import AgentResult
from services.nutrition_calculator import calculate_bmr, calculate_tdee, get_daily_calorie_target


class FutureSimulationAgent(BaseAgent):
    agent_name = "未来模拟Agent"

    async def run(self, context: dict) -> AgentResult:
        user = context["user"]
        budget_service = context.get("budget_service")

        bmr = calculate_bmr(user.weight_kg, user.height_cm, user.age, user.sex)
        tdee = calculate_tdee(bmr, user.activity_level)
        daily_target = get_daily_calorie_target(tdee, user.goal.value)

        # Get today's spending
        today_spent = 0.0
        if budget_service:
            today_spent = await budget_service.get_today_spent(user.user_id)

        remaining_budget = user.daily_budget - today_spent
        remaining_calories = daily_target  # Will be reduced by meal

        # Try LLM
        llm_result = await self._try_llm(
            "你是一个未来规划顾问。模拟现在吃饭对今天剩余时间的影响。用中文回答。",
            f"每日目标：{daily_target}千卡，剩余预算：{remaining_budget}元，餐次：晚餐",
            {"simulation": "string", "score": 0.5}
        )

        if llm_result:
            reasons = [llm_result.get("simulation", "")]
        else:
            reasons = [f"用餐后今日剩余约 {remaining_calories:.0f} 千卡", "后续用餐注意均衡"]

        return AgentResult(
            agent_name=self.agent_name,
            score=0.5,
            decision="approve",
            reasons=reasons,
            data={"remaining_calories": remaining_calories, "remaining_budget": remaining_budget},
        )
