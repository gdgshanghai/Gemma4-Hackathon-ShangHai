"""Mock McDonald's Provider — 使用本地 JSON 数据"""

import json
import uuid
from pathlib import Path
from typing import Optional
from .base import FoodProvider, Store, FoodItem, ProviderStatus


class MockMcDonaldsProvider(FoodProvider):
    """Mock McDonald's Provider — 使用本地 JSON 数据"""

    def __init__(self):
        self._data_dir = Path(__file__).parent.parent / "data"
        self._menu_cache: dict | None = None

    def get_name(self) -> str:
        return "Mock McDonald's"

    def get_mode(self) -> str:
        return "mock"

    async def health_check(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.get_name(),
            mode=self.get_mode(),
            is_healthy=True,
            message="Mock provider ready (local JSON data)",
        )

    def _load_menu(self) -> dict:
        """加载菜单数据"""
        if self._menu_cache is None:
            menu_path = self._data_dir / "mock_mcdonalds_menu.json"
            with open(menu_path, "r", encoding="utf-8") as f:
                self._menu_cache = json.load(f)
        return self._menu_cache

    async def list_stores(self) -> list[Store]:
        """查询附近门店"""
        return [
            Store(store_id="S001", name="麦当劳（科技园店）", distance_km=0.8, is_open=True),
            Store(store_id="S002", name="麦当劳（大学城店）", distance_km=1.5, is_open=True),
        ]

    async def list_items(self, category: str = None) -> list[FoodItem]:
        """查询菜单"""
        menu = self._load_menu()
        items = menu.get("items", [])

        if category:
            items = [i for i in items if i.get("category") == category]

        return [self._to_food_item(i) for i in items]

    async def get_item_detail(self, item_code: str) -> Optional[FoodItem]:
        """查询菜品详情"""
        menu = self._load_menu()
        for item in menu.get("items", []):
            if item.get("item_code") == item_code:
                return self._to_food_item(item)
        return None

    async def calculate_price(self, item_codes: list[str]) -> dict:
        """计算价格"""
        menu = self._load_menu()
        items = menu.get("items", [])
        code_map = {i["item_code"]: i for i in items}

        selected = []
        total = 0.0
        for code in item_codes:
            item = code_map.get(code)
            if item:
                selected.append(item)
                total += item["price"]

        return {
            "items": selected,
            "total_price": round(total, 2),
        }

    async def create_order_draft(self, item_codes: list[str], store_id: str = None) -> dict:
        """创建订单草稿"""
        price_info = await self.calculate_price(item_codes)
        return {
            "draft_id": str(uuid.uuid4())[:8],
            "status": "draft",
            "store_id": store_id or "S001",
            "items": price_info["items"],
            "total_price": price_info["total_price"],
            "is_mock": True,
        }

    async def confirm_order(self, draft_id: str, confirmed: bool) -> dict:
        """确认订单"""
        if confirmed:
            return {
                "order_id": f"MOCK-{uuid.uuid4().int % 100000:05d}",
                "status": "simulated",
                "draft_id": draft_id,
                "message": "This is a simulated order (mock provider).",
                "is_mock": True,
            }
        else:
            return {
                "draft_id": draft_id,
                "status": "cancelled",
                "message": "Order cancelled by user.",
            }

    def _to_food_item(self, data: dict) -> FoodItem:
        """将 dict 转换为 FoodItem"""
        return FoodItem(
            name=data.get("name", ""),
            item_code=data.get("item_code", ""),
            category=data.get("category", ""),
            price=data.get("price", 0),
            calories=data.get("calories", 0),
            protein=data.get("protein", 0),
            fat=data.get("fat", 0),
            carbohydrate=data.get("carbohydrate", 0),
            sodium=data.get("sodium", 0),
            tags=data.get("tags", []),
        )
