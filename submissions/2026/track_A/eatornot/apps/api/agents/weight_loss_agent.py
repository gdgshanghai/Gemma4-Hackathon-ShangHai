"""Weight Loss Agent — estimates calorie targets and meal budgets."""

from agents.base import BaseAgent
from models.agent_result import AgentResult
from services.nutrition_calculator import calculate_bmi, calculate_bmr, calculate_tdee, get_daily_calorie_target, get_meal_calorie_budget


class WeightLossAgent(BaseAgent):
    agent_name = "减脂Agent"

    async def run(self, context: dict) -> AgentResult:
        user = context["user"]
        meal_type = context.get("meal_type", "dinner")

        bmi = calculate_bmi(user.weight_kg, user.height_cm)
        bmr = calculate_bmr(user.weight_kg, user.height_cm, user.age, user.sex)
        tdee = calculate_tdee(bmr, user.activity_level)
        daily_target = get_daily_calorie_target(tdee, user.goal.value)
        meal_budget = get_meal_calorie_budget(daily_target, meal_type)

        # Try LLM
        llm_result = await self._try_llm(
            "你是一个减脂顾问。根据用户的BMI、TDEE和目标，推荐热量策略。用中文回答。",
            f"BMI={bmi}，TDEE={tdee}，目标={user.goal.value}，本餐热量预算={meal_budget}千卡",
            {"strategy": "string", "score": 0.5}
        )

        if llm_result:
            reasons = [llm_result.get("strategy", "")]
            score = llm_result.get("score", 0.6 if user.goal.value == "lose_weight" else 0.3)
        else:
            reasons = [f"每日能量消耗：{tdee} 千卡", f"本餐热量预算：{meal_budget} 千卡", "优先选择烤制、低热量选项"]
            score = 0.6 if user.goal.value == "lose_weight" else 0.3

        warnings = ["避免含糖饮料的套餐"] if user.goal.value == "lose_weight" else []

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            decision="approve" if user.goal.value != "gain_muscle" else "neutral",
            reasons=reasons,
            warnings=warnings,
            data={"meal_calorie_budget": meal_budget, "daily_target": daily_target},
        )
