"""FastAPI application factory for the local StudyPilot backend."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response

from backend.api.errors import register_exception_handlers, unknown_exception_handler
from backend.api.routes.health import health_router
from backend.api.routes.demo import router as demo_router
from backend.api.routes.evenings import router as evenings_router
from backend.api.routes.parent import parent_router
from backend.api.routes.school_briefs import router as school_briefs_router
from backend.api.runtime import AppRuntime
from backend.config import Settings
from backend.orchestration.lm_studio import LMStudioClient
from backend.orchestration.evening import EveningIntakeOrchestrator
from backend.services.evening import EveningService
from backend.services.parent_calibration import ParentCalibrationService
from backend.storage.database import run_migrations
from backend.storage.evening_workflow import EveningWorkflowRepository
from backend.storage.family_context import FamilyContextRepository
from backend.storage.run_traces import RunTraceRepository


async def _trace_request(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    trace_id = f"trace-{uuid4()}"
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response


async def _dispatch_unknown_exception(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    try:
        return await call_next(request)
    except Exception as error:
        return await unknown_exception_handler(request, error)


def create_app(
    settings: Settings,
    *,
    database_path: str | Path | None = None,
    lm_client: LMStudioClient | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Create the local API without starting a network listener."""
    selected_database_path = database_path if database_path is not None else settings.database_path
    resolved_database_path = Path(selected_database_path).expanduser().resolve()
    runtime_clock = clock if clock is not None else lambda: datetime.now(UTC)
    business_zone = ZoneInfo(settings.timezone)

    def business_today() -> date:
        now = runtime_clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("application clock must return a timezone-aware datetime")
        return now.astimezone(business_zone).date()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        run_migrations(resolved_database_path)
        runtime_client = (
            lm_client if lm_client is not None else LMStudioClient.from_settings(settings)
        )
        family_repository = FamilyContextRepository(resolved_database_path)
        evening_repository = EveningWorkflowRepository(
            resolved_database_path,
            current_date=business_today,
        )
        trace_repository = RunTraceRepository(resolved_database_path)
        app.state.runtime = AppRuntime(
            settings=settings,
            database_path=resolved_database_path,
            lm_client=runtime_client,
            family_repository=family_repository,
            trace_repository=trace_repository,
            parent_service=ParentCalibrationService(
                repository=family_repository,
                client=runtime_client,
                trace_repository=trace_repository,
            ),
            evening_repository=evening_repository,
            evening_service=EveningService(
                repository=evening_repository,
                family_repository=family_repository,
                current_date=business_today,
                timezone=settings.timezone,
                intake_orchestrator=EveningIntakeOrchestrator(
                    client=runtime_client,
                    repository=evening_repository,
                    trace_repository=trace_repository,
                ),
            ),
        )
        yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(demo_router)
    app.include_router(evenings_router)
    app.include_router(parent_router)
    app.include_router(school_briefs_router)
    register_exception_handlers(app)
    app.middleware("http")(_dispatch_unknown_exception)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:8041",
            "http://localhost:8041",
            "http://127.0.0.1:8042",
            "http://localhost:8042",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )
    app.middleware("http")(_trace_request)
    return app
