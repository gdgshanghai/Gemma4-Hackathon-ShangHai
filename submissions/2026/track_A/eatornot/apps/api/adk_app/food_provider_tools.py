"""FoodProvider Tools — 食物提供者工具层"""

import logging
from services.mcdonalds_provider import get_provider, list_providers

logger = logging.getLogger(__name__)


async def search_menu(provider: str = "mcdonalds", query: str = "", category: str = None) -> dict:
    """
    搜索菜单

    Args:
        provider: 提供者名称 (mcdonalds/meituan/manual)
        query: 搜索关键词
        category: 分类过滤

    Returns:
        菜品列表
    """
    p = get_provider(provider)
    items = p.list_items(category)

    # 关键词过滤
    if query:
        items = [i for i in items if query.lower() in i.name.lower() or query.lower() in str(i.tags).lower()]

    return {
        "provider": p.get_name(),
        "items": [
            {
                "name": i.name, "item_code": i.item_code, "category": i.category,
                "price": i.price, "calories": i.calories, "protein": i.protein,
                "fat": i.fat, "carbohydrate": i.carbohydrate, "sodium": i.sodium,
                "tags": i.tags,
            }
            for i in items
        ],
    }


async def get_nutrition(provider: str = "mcdonalds", item_codes: list[str] = None) -> dict:
    """
    获取营养数据

    Args:
        provider: 提供者名称
        item_codes: 菜品代码列表

    Returns:
        营养数据
    """
    if not item_codes:
        return {"items": [], "total": {}}

    p = get_provider(provider)
    items = []
    for code in item_codes:
        item = p.get_item_detail(code)
        if item:
            items.append({
                "name": item.name, "item_code": item.item_code,
                "calories": item.calories, "protein": item.protein,
                "fat": item.fat, "carbohydrate": item.carbohydrate, "sodium": item.sodium,
            })

    total = {
        "calories": sum(i["calories"] for i in items),
        "protein": sum(i["protein"] for i in items),
        "fat": sum(i["fat"] for i in items),
        "carbohydrate": sum(i["carbohydrate"] for i in items),
        "sodium": sum(i["sodium"] for i in items),
    }

    return {"items": items, "total": total}


async def calculate_price(provider: str = "mcdonalds", item_codes: list[str] = None) -> dict:
    """
    计算价格

    Args:
        provider: 提供者名称
        item_codes: 菜品代码列表

    Returns:
        价格信息
    """
    if not item_codes:
        return {"items": [], "total_price": 0}

    p = get_provider(provider)
    result = p.calculate_price(item_codes)
    return result


async def create_order_draft(provider: str = "mcdonalds", item_codes: list[str] = None, store_id: str = None) -> dict:
    """
    创建订单草稿

    Args:
        provider: 提供者名称
        item_codes: 菜品代码列表
        store_id: 门店 ID

    Returns:
        订单草稿
    """
    if not item_codes:
        return {"error": "No items specified"}

    p = get_provider(provider)
    result = p.create_order(item_codes, store_id)
    return result


async def confirm_order(provider: str = "mcdonalds", order_id: str = "", confirmed: bool = False) -> dict:
    """
    确认订单

    Args:
        provider: 提供者名称
        order_id: 订单 ID
        confirmed: 是否确认

    Returns:
        确认结果
    """
    if not confirmed:
        return {"status": "cancelled", "message": "用户取消订单"}

    # 模拟确认
    return {
        "order_id": order_id,
        "status": "confirmed",
        "message": f"订单 {order_id} 已确认",
        "is_mock": True,
    }
