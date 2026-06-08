"""Time Context Agent — assesses time pressure and recommends speed-oriented choices."""

from agents.base import BaseAgent
from models.agent_result import AgentResult


class TimeContextAgent(BaseAgent):
    agent_name = "时间Agent"

    async def run(self, context: dict) -> AgentResult:
        time_pressure = context.get("time_pressure", "normal")
        meal_type = context.get("meal_type", "dinner")

        # Score based on time pressure
        pressure_map = {
            "high": 0.7,
            "medium": 0.5,
            "normal": 0.4,
            "low": 0.3,
        }
        score = pressure_map.get(time_pressure, 0.4)

        # Try LLM
        llm_result = await self._try_llm(
            "你是一个时间管理顾问。根据时间压力推荐食物选择。用中文回答。",
            f"时间压力：{time_pressure}，餐次：{meal_type}",
            {"recommendation": "string", "score": 0.5}
        )

        pressure_cn = {"high": "紧迫", "medium": "中等", "normal": "正常", "low": "宽松"}.get(time_pressure, time_pressure)
        if llm_result:
            reasons = [llm_result.get("recommendation", "")]
            score = llm_result.get("score", score)
        else:
            reasons = [f"时间压力：{pressure_cn}", "时间紧迫时快餐是合适的选择"]

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            decision="approve",
            reasons=reasons,
            data={"time_pressure": time_pressure, "meal_type": meal_type},
        )
