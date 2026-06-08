"""Budget Service — tracks daily/weekly spending."""

from datetime import datetime, timedelta
from services.db_service import db_service


class BudgetService:
    """Tracks budget usage from meal records."""

    async def get_today_spent(self, user_id: str) -> float:
        """Get total spent today."""
        meals = await db_service.get_today_meals(user_id)
        return sum(m.total_price for m in meals)

    async def get_week_spent(self, user_id: str) -> float:
        """Get total spent this week (last 7 days)."""
        meals = await db_service.get_meals(user_id, days=7)
        return sum(m.total_price for m in meals)

    async def get_remaining_daily(self, user_id: str, daily_budget: float) -> float:
        """Get remaining daily budget."""
        spent = await self.get_today_spent(user_id)
        return max(0, daily_budget - spent)

    async def get_remaining_weekly(self, user_id: str, weekly_budget: float) -> float:
        """Get remaining weekly budget."""
        spent = await self.get_week_spent(user_id)
        return max(0, weekly_budget - spent)

    async def get_today_meals(self, user_id: str) -> list:
        """Get today's meal records."""
        return await db_service.get_today_meals(user_id)
