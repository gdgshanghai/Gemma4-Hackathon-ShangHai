"""Manual Meal Provider — 用户手动录入"""

from typing import Optional
from .base import FoodProvider, Store, FoodItem, ProviderStatus


class ManualMealProvider(FoodProvider):
    """手动录入提供者 — 用于用户自己记录"""

    def get_name(self) -> str:
        return "Manual"

    def get_mode(self) -> str:
        return "manual"

    async def health_check(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.get_name(),
            mode=self.get_mode(),
            is_healthy=True,
            message="Manual provider ready",
        )

    async def list_stores(self) -> list[Store]:
        return []

    async def list_items(self, category: str = None) -> list[FoodItem]:
        return []

    async def get_item_detail(self, item_code: str) -> Optional[FoodItem]:
        return None

    async def calculate_price(self, item_codes: list[str]) -> dict:
        return {"items": [], "total_price": 0}

    async def create_order_draft(self, item_codes: list[str], store_id: str = None) -> dict:
        return {
            "draft_id": "manual",
            "status": "manual",
            "items": [],
            "total_price": 0,
            "is_mock": True,
        }

    async def confirm_order(self, draft_id: str, confirmed: bool) -> dict:
        return {
            "draft_id": draft_id,
            "status": "manual",
            "message": "Manual meal recorded",
            "is_mock": True,
        }
