from fastapi import APIRouter

from app.api.v1.debug.routes import router as debug_router
from app.api.v1.jobs.routes import router as jobs_router
from app.api.v1.live.routes import router as live_router

router = APIRouter(prefix="/api/v1", tags=["pptx"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


router.include_router(debug_router)
router.include_router(jobs_router)
router.include_router(live_router)
