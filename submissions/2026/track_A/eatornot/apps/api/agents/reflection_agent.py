"""Reflection Agent — learns from post-meal feedback."""

from agents.base import BaseAgent
from models.agent_result import AgentResult


class ReflectionAgent(BaseAgent):
    agent_name = "反思Agent"

    async def run(self, context: dict) -> AgentResult:
        satisfaction = context.get("satisfaction", 3)
        notes = context.get("notes", "")
        meal_id = context.get("meal_id")
        memory_service = context.get("memory_service")

        # Try LLM for insight generation
        llm_result = await self._try_llm(
            "你是一个营养反思助手。分析这顿饭的反馈，生成洞察。用中文回答。",
            f"满意度：{satisfaction}/5。备注：{notes}",
            {"insight": "string", "adjustment": "string"}
        )

        if llm_result:
            insight = llm_result.get("insight", "")
            adjustment = llm_result.get("adjustment", "none")
        else:
            # Rule-based fallback
            if satisfaction >= 4:
                insight = "用户很满意这餐，下次可以推荐类似选择。"
                adjustment = "none"
            elif satisfaction <= 2:
                insight = "用户不太满意，下次考虑推荐不同的选项。"
                adjustment = "avoid_similar"
            else:
                insight = "反馈中立，没有明显偏好。"
                adjustment = "none"

        # Save to memory
        if memory_service:
            await memory_service.save_feedback("demo-user", meal_id, satisfaction, notes)

        return AgentResult(
            agent_name=self.agent_name,
            score=satisfaction / 5.0,
            decision="approve" if satisfaction >= 3 else "warn",
            reasons=[insight],
            data={"adjustment": adjustment, "satisfaction": satisfaction, "meal_id": meal_id},
        )
