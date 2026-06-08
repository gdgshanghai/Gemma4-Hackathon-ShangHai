"""Provider 工厂 — 统一管理 Provider 选择和降级"""

import logging
from core.config import get_settings
from .base import FoodProvider, ProviderStatus
from .mock_mcdonalds_provider import MockMcDonaldsProvider
from .mcdonalds_mcp_provider import McDonaldsMcpProvider
from .manual_provider import ManualMealProvider

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Provider 工厂 — 统一管理 Provider 选择和降级"""

    def __init__(self):
        self._settings = get_settings()
        self._providers: dict[str, FoodProvider] = {}
        self._active_provider: FoodProvider | None = None
        self._initialized = False

    async def initialize(self):
        """初始化 Provider"""
        if self._initialized:
            return

        # 注册所有 Provider
        self._providers = {
            "mcdonalds_mcp": McDonaldsMcpProvider(),
            "mock_mcdonalds": MockMcDonaldsProvider(),
            "manual": ManualMealProvider(),
        }

        # 选择活跃 Provider
        await self._select_active_provider()
        self._initialized = True

    async def _select_active_provider(self):
        """选择活跃 Provider"""
        settings = self._settings

        # 1. 如果强制使用 Mock
        if settings.USE_MOCK_MCP:
            self._active_provider = self._providers["mock_mcdonalds"]
            logger.info("Provider: Using Mock McDonald's (USE_MOCK_MCP=true)")
            return

        # 2. 尝试使用真实 MCP
        mcp_provider = self._providers["mcdonalds_mcp"]
        status = await mcp_provider.health_check()

        if status.is_healthy:
            self._active_provider = mcp_provider
            logger.info("Provider: Using real McDonald's MCP")
            return

        # 3. 降级到 Mock
        logger.warning(f"Provider: McDonald's MCP unavailable ({status.message}), falling back to Mock")
        self._active_provider = self._providers["mock_mcdonalds"]

    def get_provider(self, name: str = None) -> FoodProvider:
        """获取 Provider"""
        if name:
            return self._providers.get(name, self._active_provider)
        return self._active_provider

    def get_active_provider(self) -> FoodProvider:
        """获取当前活跃 Provider"""
        return self._active_provider

    async def get_status(self) -> dict:
        """获取 Provider 状态"""
        if not self._initialized:
            await self.initialize()

        active = self._active_provider
        mcp_provider = self._providers.get("mcdonalds_mcp")
        mcp_status = await mcp_provider.health_check() if mcp_provider else None

        return {
            "active_provider": active.get_name(),
            "provider_mode": active.get_mode(),
            "fallback_available": True,
            "mcd_mcp_configured": bool(self._settings.MCD_MCP_TOKEN),
            "mcd_mcp_health": "ok" if mcp_status and mcp_status.is_healthy else "unavailable",
            "message": self._get_status_message(active, mcp_status),
        }

    def _get_status_message(self, active: FoodProvider, mcp_status: ProviderStatus | None) -> str:
        """生成状态消息"""
        if active.get_mode() == "real":
            return "Using real McDonald's MCP"
        elif active.get_mode() == "mock":
            if not self._settings.MCD_MCP_TOKEN:
                return "McDonald's MCP token missing, using mock provider for stable demo"
            elif mcp_status and not mcp_status.is_healthy:
                return f"McDonald's MCP unavailable ({mcp_status.message}), using mock provider"
            else:
                return "Using mock McDonald's provider"
        else:
            return "Manual meal provider"


# 全局实例
_provider_factory: ProviderFactory | None = None


async def get_provider_factory() -> ProviderFactory:
    """获取 Provider 工厂实例"""
    global _provider_factory
    if _provider_factory is None:
        _provider_factory = ProviderFactory()
        await _provider_factory.initialize()
    return _provider_factory


async def get_provider(name: str = None) -> FoodProvider:
    """获取 Provider"""
    factory = await get_provider_factory()
    return factory.get_provider(name)
