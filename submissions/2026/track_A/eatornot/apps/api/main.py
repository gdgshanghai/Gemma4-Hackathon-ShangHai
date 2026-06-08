"""EatOrNot API — FastAPI entry point."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import init_db
from api.profile_routes import router as profile_router
from api.recommend_routes import router as recommend_router
from api.chat_routes import router as chat_router
from api.meal_routes import router as meal_router
from api.plan_routes import router as plan_router
from api.dashboard_routes import router as dashboard_router
from api.balance_routes import router as balance_router
from api.draft_routes import router as draft_router
from api.decision_routes import router as decision_router
from api.reminder_routes import router as reminder_router
from api.provider_routes import router as provider_router
from api.demo_routes import router as demo_router
from api.safety_routes import router as safety_router
from api.order_routes import router as order_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} API...")
    logger.info(f"Mock MCP: {settings.USE_MOCK_MCP}")

    # 初始化数据库
    await init_db()
    logger.info("Database initialized")

    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="EatOrNot API",
    description="Multi-agent nutrition & spending companion",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS for frontend
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(profile_router, prefix="/api", tags=["profile"])
app.include_router(recommend_router, prefix="/api", tags=["recommend"])
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(meal_router, prefix="/api", tags=["meal"])
app.include_router(plan_router, prefix="/api", tags=["plan"])
app.include_router(dashboard_router, prefix="/api", tags=["dashboard"])
app.include_router(balance_router, prefix="/api", tags=["balance"])
app.include_router(draft_router, prefix="/api", tags=["draft"])
app.include_router(decision_router, prefix="/api", tags=["decision"])
app.include_router(reminder_router, prefix="/api", tags=["reminder"])
app.include_router(provider_router, prefix="/api", tags=["provider"])
app.include_router(demo_router, prefix="/api", tags=["demo"])
app.include_router(safety_router, prefix="/api", tags=["safety"])
app.include_router(order_router, prefix="/api", tags=["order"])


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "mock_mcp": settings.USE_MOCK_MCP,
    }
