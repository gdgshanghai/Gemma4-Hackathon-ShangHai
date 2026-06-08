"""订单路由"""

import logging
from fastapi import APIRouter
from models.order import CreateOrderRequest, OrderResponse
from services.order_service import create_order_from_plan

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/order/create", response_model=OrderResponse)
async def create_order(request: CreateOrderRequest):
    """从方案创建订单"""
    logger.info(f"Create order: plan_id={request.plan_id}, items={len(request.items)}")
    result = await create_order_from_plan(request)
    return result
