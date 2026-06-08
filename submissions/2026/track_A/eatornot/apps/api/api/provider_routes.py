"""Provider 状态路由"""

from fastapi import APIRouter
from providers.factory import get_provider_factory

router = APIRouter()


@router.get("/provider/status")
async def get_provider_status():
    """获取当前 Provider 状态

    返回：
    - active_provider: 当前活跃的 Provider 名称
    - provider_mode: real / mock / manual
    - fallback_available: 是否有降级方案
    - mcd_mcp_configured: 是否配置了 MCP token
    - mcd_mcp_health: MCP 服务健康状态
    - message: 状态说明
    """
    factory = await get_provider_factory()
    return await factory.get_status()
