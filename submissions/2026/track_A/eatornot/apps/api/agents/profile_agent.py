"""Profile Agent — loads user profile and infers dietary constraints."""

from agents.base import BaseAgent
from models.agent_result import AgentResult
from services.nutrition_calculator import calculate_bmi, calculate_bmr, calculate_tdee, get_daily_calorie_target


class ProfileAgent(BaseAgent):
    agent_name = "档案Agent"

    async def run(self, context: dict) -> AgentResult:
        user = context["user"]
        bmi = calculate_bmi(user.weight_kg, user.height_cm)
        bmr = calculate_bmr(user.weight_kg, user.height_cm, user.age, user.sex)
        tdee = calculate_tdee(bmr, user.activity_level)
        daily_target = get_daily_calorie_target(tdee, user.goal.value)

        # Try LLM for richer analysis
        llm_result = await self._try_llm(
            "你是一个营养档案分析师。总结用户的饮食约束和建议。用中文回答。",
            f"用户：年龄={user.age}，性别={user.sex}，BMI={bmi}，TDEE={tdee}，目标={user.goal.value}，过敏={user.allergies}，偏好={user.taste_preferences}",
            {"constraints": ["string"], "recommendations": ["string"]}
        )

        goal_cn = {"lose_weight": "减脂", "maintain": "维持", "gain_muscle": "增肌"}.get(user.goal.value, user.goal.value)
        if llm_result:
            reasons = llm_result.get("constraints", [])
            if not reasons:
                reasons = [f"用户目标：{goal_cn}", f"BMI：{bmi}", f"每日热量目标：{daily_target} 千卡"]
        else:
            reasons = [f"用户目标：{goal_cn}", f"BMI：{bmi}", f"每日热量目标：{daily_target} 千卡"]

        return AgentResult(
            agent_name=self.agent_name,
            score=0.5,
            decision="approve",
            reasons=reasons,
            data={"bmi": bmi, "bmr": bmr, "tdee": tdee, "daily_target": daily_target},
        )
