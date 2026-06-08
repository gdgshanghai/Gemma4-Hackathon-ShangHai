"""订单相关数据模型"""

from pydantic import BaseModel, Field
from typing import Optional


class OrderItem(BaseModel):
    """订单中的单个菜品"""
    product_code: str
    product_name: str = ""
    quantity: int = 1
    price: float = 0
    calories: float = 0


class CreateOrderRequest(BaseModel):
    """创建订单请求"""
    user_id: str = "demo-user"
    plan_id: str
    items: list[OrderItem]
    store_code: str = "S001"
    order_type: int = 1  # 1=到店, 2=外送


class OrderResponse(BaseModel):
    """订单响应"""
    success: bool
    order_id: str = ""
    pay_url: str = ""
    status: str = ""  # pending_payment / confirmed / failed
    total_price: float = 0
    message: str = ""
    is_mock: bool = False
