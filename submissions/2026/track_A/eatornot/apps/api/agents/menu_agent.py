"""Menu Agent — fetches menu data from Provider."""

from agents.base import BaseAgent
from models.agent_result import AgentResult
from providers.factory import get_provider


class MenuAgent(BaseAgent):
    agent_name = "菜单Agent"

    async def run(self, context: dict) -> AgentResult:
        # 获取 Provider
        provider = await get_provider()

        # 通过 Provider 获取数据
        items = await provider.list_items()
        stores = await provider.list_stores()

        # 更新 context
        context["candidates"] = [
            {
                "name": i.name,
                "item_code": i.item_code,
                "category": i.category,
                "price": i.price,
                "calories": i.calories,
                "protein": i.protein,
                "fat": i.fat,
                "carbohydrate": i.carbohydrate,
                "sodium": i.sodium,
                "tags": i.tags,
            }
            for i in items
        ]

        return AgentResult(
            agent_name=self.agent_name,
            score=0.5,
            decision="approve",
            reasons=[f"已加载 {len(items)} 个菜品（{provider.get_mode()}）", f"附近 {len(stores)} 家门店"],
            data={"items_count": len(items), "stores_count": len(stores), "source": provider.get_mode()},
        )
