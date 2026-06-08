"""McDonald's MCP Provider — 使用真实麦当劳 MCP API"""

import uuid
import logging
from typing import Optional
from core.config import get_settings
from .base import FoodProvider, Store, FoodItem, ProviderStatus

logger = logging.getLogger(__name__)


class McDonaldsMcpProvider(FoodProvider):
    """McDonald's MCP Provider — 使用真实麦当劳 MCP API"""

    def __init__(self):
        self._settings = get_settings()

    def get_name(self) -> str:
        return "McDonald's MCP"

    def get_mode(self) -> str:
        return "real"

    async def health_check(self) -> ProviderStatus:
        """检查 MCP 服务是否可用"""
        if not self._settings.MCD_MCP_TOKEN:
            return ProviderStatus(
                name=self.get_name(),
                mode=self.get_mode(),
                is_healthy=False,
                message="MCD_MCP_TOKEN not configured",
            )

        try:
            items = await self._call_mcp_tool("list-nutrition-foods")
            if items and len(items) > 0:
                return ProviderStatus(
                    name=self.get_name(),
                    mode=self.get_mode(),
                    is_healthy=True,
                    message=f"McDonald's MCP connected ({len(items)} items)",
                )
            else:
                return ProviderStatus(
                    name=self.get_name(),
                    mode=self.get_mode(),
                    is_healthy=False,
                    message="McDonald's MCP returned empty response",
                )
        except Exception as e:
            return ProviderStatus(
                name=self.get_name(),
                mode=self.get_mode(),
                is_healthy=False,
                message=f"McDonald's MCP error: {str(e)}",
            )

    async def list_stores(self, city: str = "南京", keyword: str = "麦当劳") -> list[Store]:
        """查询附近门店"""
        try:
            result = await self._call_mcp_tool("query-nearby-stores", {
                "beType": 1,
                "searchType": 2,
                "city": city,
                "keyword": keyword,
            })
            if result and isinstance(result, list):
                stores = []
                for s in result:
                    if isinstance(s, dict):
                        stores.append(Store(
                            store_id=str(s.get("storeCode", s.get("store_id", ""))),
                            name=s.get("storeName", s.get("name", "")),
                            distance_km=s.get("distance", s.get("distance_km", 0)),
                            is_open=s.get("isOpen", s.get("is_open", True)),
                        ))
                if stores:
                    return stores
        except Exception as e:
            logger.error(f"MCP list_stores error: {e}")

        # Fallback
        return [
            Store(store_id="S001", name="麦当劳（科技园店）", distance_km=0.8, is_open=True),
        ]

    async def list_items(self, category: str = None) -> list[FoodItem]:
        """查询菜单 — 优先使用 query-meals（含价格），降级到 list-nutrition-foods"""
        try:
            # 优先用 query-meals 获取完整菜单（含价格）
            items = await self.query_meals(store_code="S001", order_type=1, be_type=1)
            if items and len(items) > 0:
                if category:
                    items = [i for i in items if i.category == category]
                return items
        except Exception as e:
            logger.warning(f"query-meals failed, trying list-nutrition-foods: {e}")

        # 降级到 list-nutrition-foods（只有营养数据，无价格）
        try:
            result = await self._call_mcp_tool("list-nutrition-foods")
            items_data = self._extract_items_data(result)

            if items_data and len(items_data) > 0:
                items = [self._to_food_item(i) for i in items_data]
                if category:
                    items = [i for i in items if i.category == category]
                return items
            else:
                logger.warning("MCP returned empty list, falling back to mock")
                return await self._fallback_to_mock(category)
        except Exception as e:
            logger.error(f"MCP list_items error: {e}")
            return await self._fallback_to_mock(category)

    async def query_meals(self, store_code: str = "S001", order_type: int = 1, be_type: int = 1) -> list[FoodItem]:
        """按门店+订单类型查询菜单 (MCP query-meals)"""
        result = await self._call_mcp_tool("query-meals", {
            "storeCode": store_code,
            "orderType": order_type,
            "beType": be_type,
        })

        items_data = self._extract_items_data(result)
        if items_data:
            return [self._to_food_item(i) for i in items_data]
        return []

    async def _fallback_to_mock(self, category: str = None) -> list[FoodItem]:
        """降级到 Mock 数据"""
        logger.warning("Falling back to Mock data because MCP returned empty or failed")
        from .mock_mcdonalds_provider import MockMcDonaldsProvider
        mock = MockMcDonaldsProvider()
        return await mock.list_items(category)

    async def get_item_detail(self, item_code: str) -> Optional[FoodItem]:
        """查询菜品详情"""
        try:
            result = await self._call_mcp_tool("query-meal-detail", {
                "code": item_code,
                "storeCode": "S001",
                "orderType": 1,
                "beType": 1,
            })
            if result and isinstance(result, dict):
                return self._to_food_item(result)
        except Exception as e:
            logger.error(f"MCP get_item_detail error: {e}")

        return None

    async def calculate_price(self, item_codes: list[str]) -> dict:
        """计算价格"""
        try:
            # 将 item_codes 转为 MCP 需要的格式
            items = [{"productCode": code, "quantity": 1} for code in item_codes]
            result = await self._call_mcp_tool("calculate-price", {
                "items": items,
                "storeCode": "S001",
                "orderType": 1,
                "beType": 1,
            })
            if result and isinstance(result, dict):
                return result
        except Exception as e:
            logger.error(f"MCP calculate_price error: {e}")

        return {"items": [], "total_price": 0}

    async def create_order_draft(self, item_codes: list[str], store_id: str = None) -> dict:
        """创建订单草稿"""
        try:
            items = [{"productCode": code, "quantity": 1} for code in item_codes]
            result = await self._call_mcp_tool("create-order", {
                "items": items,
                "storeCode": store_id or "S001",
                "orderType": 1,
                "beType": 1,
            })
            if result and isinstance(result, dict):
                return {
                    "draft_id": str(uuid.uuid4())[:8],
                    "status": "draft",
                    "items": result.get("items", []),
                    "total_price": result.get("total_price", 0),
                    "is_mock": False,
                }
        except Exception as e:
            logger.error(f"MCP create_order_draft error: {e}")

        return {"draft_id": "", "status": "error", "message": "MCP order creation failed"}

    async def confirm_order(self, draft_id: str, confirmed: bool) -> dict:
        """确认订单"""
        if confirmed:
            try:
                result = await self._call_mcp_tool("create-order", {"draft_id": draft_id})
                if result and isinstance(result, dict):
                    return {
                        "order_id": result.get("order_id", ""),
                        "status": "confirmed",
                        "draft_id": draft_id,
                        "message": "Order confirmed via McDonald's MCP",
                        "is_mock": False,
                    }
            except Exception as e:
                logger.error(f"MCP confirm_order error: {e}")

        return {
            "draft_id": draft_id,
            "status": "cancelled",
            "message": "Order cancelled by user.",
        }

    async def create_order(self, store_code: str, items: list[dict], order_type: int = 1, take_way_code: str = None) -> dict:
        """通过 MCP 创建真实订单"""
        try:
            # 先计算价格确认
            price_result = await self._call_mcp_tool("calculate-price", {
                "items": items,
                "storeCode": store_code,
                "orderType": order_type,
                "beType": 1,
            })

            if not price_result or price_result.get("error"):
                return {"success": False, "message": "价格计算失败，无法下单"}

            # 从价格结果中获取 take_way_code
            if not take_way_code and isinstance(price_result, dict):
                take_ways = price_result.get("takeWayList", [])
                if take_ways:
                    take_way_code = take_ways[0].get("code", "DINE_IN")

            # 创建订单
            order_args = {
                "items": items,
                "storeCode": store_code,
                "orderType": order_type,
                "beType": 1,
            }
            if take_way_code:
                order_args["takeWayCode"] = take_way_code

            order_result = await self._call_mcp_tool("create-order", order_args)

            if order_result and isinstance(order_result, dict):
                return {
                    "success": True,
                    "order_id": order_result.get("orderId", str(uuid.uuid4())[:8]),
                    "pay_url": order_result.get("payUrl", ""),
                    "status": "pending_payment",
                    "total_price": order_result.get("totalPrice", 0),
                    "message": "订单创建成功",
                    "is_mock": False,
                }

            return {"success": False, "message": "MCP 未返回有效订单结果"}

        except Exception as e:
            logger.error(f"create_order error: {e}")
            return {"success": False, "message": f"下单失败: {str(e)}"}

    async def _call_mcp_tool(self, tool_name: str, args: dict = None) -> any:
        """调用 MCP 工具"""
        import json
        import re
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        url = self._settings.MCD_MCP_URL
        token = self._settings.MCD_MCP_TOKEN

        async with streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"}) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args or {})

                if hasattr(result, "content") and result.content:
                    first = result.content[0]
                    if hasattr(first, "text"):
                        text = first.text

                        # 尝试直接解析 JSON
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            pass

                        # 尝试从文本中提取 JSON
                        json_match = re.search(r'\{.*\}', text, re.DOTALL)
                        if json_match:
                            try:
                                return json.loads(json_match.group())
                            except json.JSONDecodeError:
                                pass

                        # 如果是 CSV 格式的数据
                        if text.startswith('[') and '{' in text:
                            return self._parse_csv_items(text)

                        return text

                return None

    def _extract_items_data(self, result) -> list[dict]:
        """从 MCP 响应中提取菜品数据列表"""
        if not result:
            return []
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # 尝试常见嵌套结构
            for key in ("data", "items", "foods", "meals"):
                data = result.get(key)
                if isinstance(data, list):
                    return data
                elif isinstance(data, str):
                    parsed = self._parse_csv_items(data)
                    if parsed:
                        return parsed
            # 如果响应本身包含菜品字段
            if result.get("productName") or result.get("name"):
                return [result]
        if isinstance(result, str):
            return self._parse_csv_items(result)
        return []

    def _parse_csv_items(self, csv_text: str) -> list[dict]:
        """解析 CSV 格式的菜品数据"""
        import re
        items = []
        lines = csv_text.strip().split('\n')

        if len(lines) < 2:
            return items

        header_line = lines[0]
        header_match = re.search(r'\{(.+?)\}', header_line)
        if not header_match:
            return items

        headers = [h.strip() for h in header_match.group(1).split(',')]

        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            values = [v.strip() for v in line.split(',')]
            if len(values) >= len(headers):
                item = {}
                for i, header in enumerate(headers):
                    value = values[i] if i < len(values) else ''
                    if value == 'null' or value == '':
                        item[header] = None
                    else:
                        try:
                            if '.' in value:
                                item[header] = float(value)
                            else:
                                item[header] = int(value)
                        except ValueError:
                            item[header] = value

                product_name = item.get('productName', '')
                if product_name and product_name != 'null':
                    items.append({
                        'name': product_name,
                        'item_code': f'MCD_{len(items)+1:03d}',
                        'category': 'main',
                        'price': 0,
                        'calories': item.get('energyKcal', 0) or 0,
                        'protein': item.get('protein', 0) or 0,
                        'fat': item.get('fat', 0) or 0,
                        'carbohydrate': item.get('carbohydrate', 0) or 0,
                        'sodium': item.get('sodium', 0) or 0,
                        'tags': [],
                    })

        return items

    def _to_food_item(self, data: dict) -> FoodItem:
        """将 dict 转换为 FoodItem — 兼容真实 MCP 和 Mock 两种字段名"""
        # 真实 MCP 返回 productName/productCode/price(分)
        # Mock 返回 name/item_code/price(元)
        name = data.get("productName", data.get("name", ""))
        item_code = str(data.get("productCode", data.get("item_code", "")))
        price_raw = data.get("price", 0) or 0
        # 真实 MCP 价格单位是分，需要除以 100；Mock 直接是元
        # 判断依据：价格 > 100 认为是分
        price = price_raw / 100 if price_raw > 100 else price_raw

        return FoodItem(
            name=name,
            item_code=item_code,
            category=data.get("category", "main"),
            price=round(price, 2),
            calories=data.get("calories", data.get("energyKcal", 0)) or 0,
            protein=data.get("protein", 0) or 0,
            fat=data.get("fat", 0) or 0,
            carbohydrate=data.get("carbohydrate", 0) or 0,
            sodium=data.get("sodium", 0) or 0,
            tags=data.get("tags", []),
        )
