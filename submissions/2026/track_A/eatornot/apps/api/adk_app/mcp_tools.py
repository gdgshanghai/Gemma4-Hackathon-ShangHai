"""MCP Tools — McDonald's MCP 集成层（支持真实 MCP 和 Mock）"""

import json
import logging
import re
from contextlib import asynccontextmanager
from core.config import get_settings

logger = logging.getLogger(__name__)


def _parse_mcp_response(text: str) -> dict | list | None:
    """解析 MCP 返回的带有 AI 说明的 JSON 数据"""
    try:
        # 尝试直接解析 JSON
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 从文本中提取 JSON
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None


def _parse_csv_items(csv_text: str) -> list[dict]:
    """解析 CSV 格式的菜品数据"""
    items = []
    lines = csv_text.strip().split('\n')

    # 跳过第一行（数量信息 [160]）
    # 第二行是表头
    if len(lines) < 3:
        return items

    header_line = lines[1]
    headers = [h.strip() for h in header_line.replace('{', '').replace('}:', '').split(',')]

    # 解析数据行
    for line in lines[2:]:
        line = line.strip()
        if not line:
            continue

        values = [v.strip() for v in line.split(',')]
        if len(values) >= len(headers):
            item = {}
            for i, header in enumerate(headers):
                value = values[i] if i < len(values) else ''
                # 转换数值类型
                if value == 'null':
                    item[header] = None
                else:
                    try:
                        if '.' in value:
                            item[header] = float(value)
                        else:
                            item[header] = int(value)
                    except ValueError:
                        item[header] = value

            # 转换为标准格式
            product_name = item.get('productName', '')
            if product_name:
                items.append({
                    'name': product_name,
                    'item_code': f'MCD_{len(items)+1:03d}',
                    'category': 'main',
                    'price': 0,  # MCP 不返回价格
                    'calories': item.get('energyKcal', 0),
                    'protein': item.get('protein', 0),
                    'fat': item.get('fat', 0),
                    'carbohydrate': item.get('carbohydrate', 0),
                    'sodium': item.get('sodium', 0),
                    'tags': [],
                })

    return items


@asynccontextmanager
async def _mcp_connection():
    """MCP 连接上下文管理器"""
    settings = get_settings()

    if settings.USE_MOCK_MCP or not settings.MCD_MCP_TOKEN:
        logger.info("Using mock MCP (USE_MOCK_MCP=true or token missing)")
        yield None
        return

    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        url = settings.MCD_MCP_URL
        token = settings.MCD_MCP_TOKEN

        logger.info(f"Connecting to McDonald's MCP: {url}")

        async with streamablehttp_client(url, headers={'Authorization': f'Bearer {token}'}) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.info("Connected to McDonald's MCP successfully")
                yield session

    except Exception as e:
        logger.error(f"Failed to connect to MCP: {e}")
        yield None


async def _call_mcp_tool(tool_name: str, args: dict = None) -> any:
    """调用 MCP 工具并返回解析后的结果"""
    async with _mcp_connection() as session:
        if session is None:
            return None

        try:
            result = await session.call_tool(tool_name, args or {})

            if hasattr(result, 'content') and result.content:
                first = result.content[0]
                if hasattr(first, 'text'):
                    text = first.text

                    # 尝试解析 JSON
                    parsed = _parse_mcp_response(text)
                    if parsed:
                        # 如果是带有 data 字段的响应
                        if isinstance(parsed, dict) and 'data' in parsed:
                            data = parsed['data']
                            if isinstance(data, str) and data.startswith('['):
                                # CSV 格式的数据
                                return _parse_csv_items(data)
                            return data
                        return parsed

                    # 如果是 CSV 格式
                    if text.startswith('[') and '{' in text:
                        return _parse_csv_items(text)

                    return text

            return None

        except Exception as e:
            logger.error(f"MCP {tool_name} error: {e}")
            return None


def _get_mock_provider():
    from services.mcdonalds_provider import get_provider
    return get_provider("mcdonalds")


async def mcd_list_nutrition_foods() -> list[dict]:
    """获取麦当劳菜单（含营养数据）"""
    result = await _call_mcp_tool('list-nutrition-foods')

    if result and isinstance(result, list):
        return result

    # Mock fallback
    provider = _get_mock_provider()
    items = provider.list_items()
    return [
        {
            "name": i.name, "item_code": i.item_code, "category": i.category,
            "price": i.price, "calories": i.calories, "protein": i.protein,
            "fat": i.fat, "carbohydrate": i.carbohydrate, "sodium": i.sodium,
            "tags": i.tags,
        }
        for i in items
    ]


async def mcd_query_nearby_stores() -> list[dict]:
    """查询附近麦当劳门店"""
    result = await _call_mcp_tool('query-nearby-stores')

    if result and isinstance(result, list):
        return result

    # Mock fallback
    provider = _get_mock_provider()
    stores = provider.list_stores()
    return [{"store_id": s.store_id, "name": s.name, "distance_km": s.distance_km, "is_open": s.is_open} for s in stores]


async def mcd_query_meals(category: str = None) -> list[dict]:
    """查询菜品"""
    args = {}
    if category:
        args['category'] = category

    result = await _call_mcp_tool('query-meals', args)

    if result and isinstance(result, list):
        return result

    # Mock fallback
    provider = _get_mock_provider()
    items = provider.list_items(category)
    return [
        {"name": i.name, "item_code": i.item_code, "category": i.category, "price": i.price, "calories": i.calories}
        for i in items
    ]


async def mcd_query_meal_detail(item_code: str) -> dict | None:
    """查询菜品详情"""
    result = await _call_mcp_tool('query-meal-detail', {'item_code': item_code})

    if result and isinstance(result, dict):
        return result

    # Mock fallback
    provider = _get_mock_provider()
    item = provider.get_item_detail(item_code)
    if item:
        return {
            "name": item.name, "item_code": item.item_code, "category": item.category,
            "price": item.price, "calories": item.calories, "protein": item.protein,
            "fat": item.fat, "carbohydrate": item.carbohydrate, "sodium": item.sodium,
            "tags": item.tags,
        }
    return None


async def mcd_calculate_price(item_codes: list[str]) -> dict:
    """计算价格"""
    result = await _call_mcp_tool('calculate-price', {'items': item_codes})

    if result and isinstance(result, dict):
        return result

    # Mock fallback
    provider = _get_mock_provider()
    return provider.calculate_price(item_codes)


async def mcd_create_order(item_codes: list[str], store_id: str = "S001") -> dict:
    """创建订单（需要确认）"""
    result = await _call_mcp_tool('create-order', {
        'items': item_codes,
        'store_id': store_id,
    })

    if result and isinstance(result, dict):
        return result

    # Mock fallback
    provider = _get_mock_provider()
    return provider.create_order(item_codes, store_id)


async def mcd_query_order(order_id: str) -> dict:
    """查询订单状态"""
    result = await _call_mcp_tool('query-order', {'order_id': order_id})

    if result and isinstance(result, dict):
        return result

    # Mock fallback
    return {"order_id": order_id, "status": "simulated", "message": "Mock order"}
