"""FoodProvider 基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Store:
    """门店信息"""
    store_id: str
    name: str
    distance_km: float
    is_open: bool


@dataclass
class FoodItem:
    """菜品信息"""
    name: str
    item_code: str
    category: str
    price: float
    calories: float
    protein: float
    fat: float
    carbohydrate: float
    sodium: float
    tags: list[str]


@dataclass
class ProviderStatus:
    """Provider 状态"""
    name: str
    mode: str  # real / mock / manual
    is_healthy: bool
    message: str


class FoodProvider(ABC):
    """食物提供者抽象接口"""

    @abstractmethod
    def get_name(self) -> str:
        """提供者名称"""
        ...

    @abstractmethod
    def get_mode(self) -> str:
        """提供者模式: real / mock / manual"""
        ...

    @abstractmethod
    async def health_check(self) -> ProviderStatus:
        """健康检查"""
        ...

    @abstractmethod
    async def list_stores(self) -> list[Store]:
        """查询附近门店"""
        ...

    @abstractmethod
    async def list_items(self, category: str = None) -> list[FoodItem]:
        """查询菜单"""
        ...

    @abstractmethod
    async def get_item_detail(self, item_code: str) -> Optional[FoodItem]:
        """查询菜品详情"""
        ...

    @abstractmethod
    async def calculate_price(self, item_codes: list[str]) -> dict:
        """计算价格"""
        ...

    @abstractmethod
    async def create_order_draft(self, item_codes: list[str], store_id: str = None) -> dict:
        """创建订单草稿"""
        ...

    @abstractmethod
    async def confirm_order(self, draft_id: str, confirmed: bool) -> dict:
        """确认订单"""
        ...
