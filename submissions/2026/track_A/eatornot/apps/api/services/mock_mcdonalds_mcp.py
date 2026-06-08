"""Mock McDonald's MCP client — returns data from local JSON when real MCP token is missing."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"
_menu_cache: dict | None = None


def _load_menu() -> dict:
    global _menu_cache
    if _menu_cache is None:
        menu_path = _DATA_DIR / "mock_mcdonalds_menu.json"
        with open(menu_path, "r", encoding="utf-8") as f:
            _menu_cache = json.load(f)
    return _menu_cache


def list_nutrition_foods() -> list[dict]:
    """Return all menu items."""
    return _load_menu()["items"]


def query_nearby_stores() -> list[dict]:
    """Return mock store list."""
    return [
        {"store_id": "S001", "name": "麦当劳（科技园店）", "distance_km": 0.8, "is_open": True},
        {"store_id": "S002", "name": "麦当劳（大学城店）", "distance_km": 1.5, "is_open": True},
    ]


def query_meals(category: str | None = None) -> list[dict]:
    """Query meals, optionally filtered by category."""
    items = _load_menu()["items"]
    if category:
        items = [i for i in items if i["category"] == category]
    return items


def query_meal_detail(item_code: str) -> dict | None:
    """Get detail for a specific item."""
    items = _load_menu()["items"]
    for item in items:
        if item["item_code"] == item_code:
            return item
    return None


def calculate_price(item_codes: list[str]) -> dict:
    """Calculate total price for a list of item codes."""
    items = _load_menu()["items"]
    code_map = {i["item_code"]: i for i in items}
    selected = []
    total = 0.0
    for code in item_codes:
        item = code_map.get(code)
        if item:
            selected.append(item)
            total += item["price"]
    return {"items": selected, "total_price": round(total, 2)}


def create_order(item_codes: list[str], store_id: str = "S001") -> dict:
    """Simulate order creation (mock)."""
    price_info = calculate_price(item_codes)
    return {
        "order_id": f"MOCK-{hash(tuple(item_codes)) % 100000:05d}",
        "status": "simulated",
        "store_id": store_id,
        "items": price_info["items"],
        "total_price": price_info["total_price"],
        "message": "This is a simulated order (no real MCP token).",
        "is_mock": True,
    }
