"""订单服务 — 串联 Provider 下单流程"""

import logging
from providers.factory import get_provider
from models.order import CreateOrderRequest, OrderResponse

logger = logging.getLogger(__name__)


async def create_order_from_plan(request: CreateOrderRequest) -> OrderResponse:
    """从用户选中的方案创建订单"""
    provider = get_provider()

    items = [
        {"productCode": item.product_code, "quantity": item.quantity}
        for item in request.items
    ]

    if hasattr(provider, "create_order"):
        result = await provider.create_order(
            store_code=request.store_code,
            items=items,
            order_type=request.order_type,
        )
        if result.get("success"):
            return OrderResponse(
                success=True,
                order_id=result.get("order_id", ""),
                pay_url=result.get("pay_url", ""),
                status=result.get("status", "pending_payment"),
                total_price=result.get("total_price", 0),
                message=result.get("message", "订单创建成功"),
                is_mock=result.get("is_mock", False),
            )

        logger.warning(f"MCP order failed: {result.get('message')}")
        return OrderResponse(
            success=False,
            status="failed",
            message=result.get("message", "下单服务暂不可用"),
        )

    return OrderResponse(
        success=False,
        status="failed",
        message="当前数据源不支持下单，请前往麦当劳APP下单",
        is_mock=True,
    )
