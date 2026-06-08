"""Base agent class for all EatOrNot agents."""

from abc import ABC, abstractmethod
from models.agent_result import AgentResult
from core.llm_client import generate_json


class BaseAgent(ABC):
    agent_name: str = "BaseAgent"

    @abstractmethod
    async def run(self, context: dict) -> AgentResult:
        """Run the agent with the given context and return structured result."""
        ...

    async def _try_llm(self, system_prompt: str, user_prompt: str, schema_hint: dict) -> dict | None:
        """Attempt LLM call. Returns parsed dict or None on failure."""
        result = await generate_json(system_prompt, user_prompt, schema_hint)
        if result.get("fallback"):
            return None
        return result
