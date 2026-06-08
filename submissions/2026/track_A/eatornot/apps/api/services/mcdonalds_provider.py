"""McDonald's Provider — 包装现有 mock_mcdonalds_mcp"""

from services.food_provider import FoodProvider, Store, FoodItem
from services import mock_mcdonalds_mcp as mock


def _to_food_item(data: dict) -> FoodItem:
    """将 dict 转换为 FoodItem，忽略多余字段"""
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


class McDonaldsProvider(FoodProvider):
    """麦当劳提供者"""

    def get_name(self) -> str:
        return "麦当劳"

    def list_stores(self) -> list[Store]:
        stores = mock.query_nearby_stores()
        return [Store(**s) for s in stores]

    def list_items(self, category: str = None) -> list[FoodItem]:
        items = mock.query_meals(category)
        return [_to_food_item(i) for i in items]

    def get_item_detail(self, item_code: str) -> FoodItem | None:
        item = mock.query_meal_detail(item_code)
        if item:
            return _to_food_item(item)
        return None

    def calculate_price(self, item_codes: list[str]) -> dict:
        return mock.calculate_price(item_codes)

    def create_order(self, item_codes: list[str], store_id: str = None) -> dict:
        return mock.create_order(item_codes, store_id or "S001")


class MockMeituanProvider(FoodProvider):
    """美团外卖 Mock 提供者"""

    MOCK_ITEMS = [
        {"name": "黄焖鸡米饭", "item_code": "MT_HUANGMEN", "category": "rice", "price": 22.0,
         "calories": 550, "protein": 25.0, "fat": 18.0, "carbohydrate": 65.0, "sodium": 900, "tags": ["chicken", "rice"]},
        {"name": "麻辣烫", "item_code": "MT_MALATANG", "category": "soup", "price": 28.0,
         "calories": 400, "protein": 15.0, "fat": 20.0, "carbohydrate": 35.0, "sodium": 1200, "tags": ["spicy", "soup"]},
        {"name": "沙县小吃拌面", "item_code": "MT_SHAXIAN", "category": "noodle", "price": 12.0,
         "calories": 380, "protein": 10.0, "fat": 8.0, "carbohydrate": 65.0, "sodium": 600, "tags": ["noodle", "cheap"]},
    ]

    def get_name(self) -> str:
        return "美团外卖"

    def list_stores(self) -> list[Store]:
        return [
            Store(store_id="MT001", name="美团外卖（科技园站）", distance_km=1.0, is_open=True),
        ]

    def list_items(self, category: str = None) -> list[FoodItem]:
        items = self.MOCK_ITEMS
        if category:
            items = [i for i in items if i["category"] == category]
        return [FoodItem(**i) for i in items]

    def get_item_detail(self, item_code: str) -> FoodItem | None:
        for item in self.MOCK_ITEMS:
            if item["item_code"] == item_code:
                return FoodItem(**item)
        return None

    def calculate_price(self, item_codes: list[str]) -> dict:
        code_map = {i["item_code"]: i for i in self.MOCK_ITEMS}
        items = [code_map[c] for c in item_codes if c in code_map]
        total = sum(i["price"] for i in items)
        return {"items": items, "total_price": round(total, 2)}

    def create_order(self, item_codes: list[str], store_id: str = None) -> dict:
        price_info = self.calculate_price(item_codes)
        return {
            "order_id": f"MT-{hash(tuple(item_codes)) % 100000:05d}",
            "status": "simulated",
            "items": price_info["items"],
            "total_price": price_info["total_price"],
            "message": "美团外卖模拟订单",
            "is_mock": True,
        }


class ManualMealProvider(FoodProvider):
    """手动录入提供者 — 用于用户自己记录"""

    def get_name(self) -> str:
        return "手动录入"

    def list_stores(self) -> list[Store]:
        return []

    def list_items(self, category: str = None) -> list[FoodItem]:
        return []

    def get_item_detail(self, item_code: str) -> FoodItem | None:
        return None

    def calculate_price(self, item_codes: list[str]) -> dict:
        return {"items": [], "total_price": 0}

    def create_order(self, item_codes: list[str], store_id: str = None) -> dict:
        return {
            "order_id": "MANUAL",
            "status": "manual",
            "items": [],
            "total_price": 0,
            "message": "手动录入",
            "is_mock": True,
        }


# 全局提供者注册
_providers: dict[str, FoodProvider] = {
    "mcdonalds": McDonaldsProvider(),
    "meituan": MockMeituanProvider(),
    "manual": ManualMealProvider(),
}


def get_provider(name: str) -> FoodProvider:
    return _providers.get(name, _providers["mcdonalds"])


def list_providers() -> list[str]:
    return list(_providers.keys())
