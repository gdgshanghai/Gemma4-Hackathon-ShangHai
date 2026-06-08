"""Craving Agent — detects emotional eating and manages indulgence."""

from agents.base import BaseAgent
from models.agent_result import AgentResult


class CravingAgent(BaseAgent):
    agent_name = "食欲Agent"

    async def run(self, context: dict) -> AgentResult:
        mood = context.get("mood", "normal")
        user = context["user"]
        memory_service = context.get("memory_service")

        # Detect craving level based on mood
        craving_map = {
            "tired": 0.7,
            "stressed": 0.7,
            "sad": 0.6,
            "normal": 0.4,
            "happy": 0.3,
        }
        craving_score = craving_map.get(mood, 0.4)

        # Check weekly indulgence count
        indulgence_count = 0
        if memory_service:
            indulgence_count = await memory_service.get_indulgence_count_this_week(user.user_id)

        indulgence_remaining = user.weekly_indulgence_allowance - indulgence_count

        # Try LLM
        llm_result = await self._try_llm(
            "你是一个食欲顾问。评估用户的情绪性进食风险，并给出建议。用中文回答。",
            f"情绪状态：{mood}，本周放纵额度已用：{indulgence_count}/{user.weekly_indulgence_allowance}",
            {"assessment": "string", "score": 0.5, "allow_indulgence": True}
        )

        mood_cn = {"tired": "疲惫", "stressed": "压力大", "sad": "心情低落", "normal": "正常", "happy": "开心"}.get(mood, mood)
        if llm_result:
            reasons = [llm_result.get("assessment", "")]
            score = llm_result.get("score", craving_score)
        else:
            reasons = [f"检测到情绪：{mood_cn}", "适度放纵是可以接受的"]
            score = craving_score

        if indulgence_remaining <= 0:
            reasons.append("本周放纵额度已用完")
            score = max(0.2, score - 0.3)

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            decision="approve",
            reasons=reasons,
            data={"mood": mood, "indulgence_remaining": indulgence_remaining},
        )
