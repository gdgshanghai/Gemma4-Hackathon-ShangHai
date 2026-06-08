"""FoodProvider 抽象接口"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Store:
    store_id: str
    name: str
    distance_km: float
    is_open: bool


@dataclass
class FoodItem:
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


class FoodProvider(ABC):
    """食物提供者抽象接口"""

    @abstractmethod
    def get_name(self) -> str:
        """提供者名称"""
        ...

    @abstractmethod
    def list_stores(self) -> list[Store]:
        """查询附近门店"""
        ...

    @abstractmethod
    def list_items(self, category: str = None) -> list[FoodItem]:
        """查询菜单"""
        ...

    @abstractmethod
    def get_item_detail(self, item_code: str) -> FoodItem | None:
        """查询菜品详情"""
        ...

    @abstractmethod
    def calculate_price(self, item_codes: list[str]) -> dict:
        """计算价格"""
        ...

    @abstractmethod
    def create_order(self, item_codes: list[str], store_id: str = None) -> dict:
        """创建订单"""
        ...
