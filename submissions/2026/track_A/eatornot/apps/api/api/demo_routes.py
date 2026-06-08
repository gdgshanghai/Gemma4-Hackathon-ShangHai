"""Demo 路由 — 7 天长期伴随模拟"""

from fastapi import APIRouter
from services.demo_service import demo_service
from services.metrics_service import metrics_service

router = APIRouter()


@router.get("/demo/timeline")
async def get_demo_timeline(user_id: str = "demo-user"):
    """获取 7 天 demo 时间线"""
    return await demo_service.get_timeline(user_id)


@router.post("/demo/simulate-week")
async def simulate_week(user_id: str = "demo-user"):
    """模拟 7 天行为"""
    return await demo_service.simulate_week(user_id)


@router.get("/demo/learning")
async def get_learning_points(user_id: str = "demo-user"):
    """获取学习点"""
    points = await demo_service.get_learning_points(user_id)
    return {
        "user_id": user_id,
        "learning_points": points,
        "count": len(points),
    }


@router.get("/demo/metrics")
async def get_demo_metrics(user_id: str = "demo-user"):
    """获取 7 天模拟结果指标"""
    return await metrics_service.get_demo_metrics(user_id)
