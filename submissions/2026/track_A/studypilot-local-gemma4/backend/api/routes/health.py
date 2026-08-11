"""Local API, SQLite, and LM Studio readiness projection."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.runtime import AppRuntime, get_runtime, get_trace_id
from backend.contracts.api import HealthComponent, HealthResponse, ModelHealthComponent
from backend.orchestration.lm_studio import LMStudioError
from backend.storage.database import connect_database


health_router = APIRouter(tags=["health"])


def _database_health(database_path: Path) -> HealthComponent:
    try:
        connection = connect_database(database_path)
        try:
            row = connection.execute("SELECT 1").fetchone()
            if row is None or int(row[0]) != 1:
                raise sqlite3.DatabaseError("sqlite liveness check failed")
        finally:
            connection.close()
    except sqlite3.Error:
        return HealthComponent(
            status="degraded",
            error_code="sqlite_unavailable",
        )
    return HealthComponent(status="ok", error_code=None)


@health_router.get("/api/v1/health", response_model=HealthResponse)
def get_health(
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> HealthResponse:
    database_component = _database_health(runtime.database_path)
    try:
        metadata = runtime.lm_client.get_model_metadata()
        model_component = ModelHealthComponent(
            status="ok",
            model_id=metadata.id,
            loaded=True,
            tool_use=True,
            quantization=metadata.quantization,
            error_code=None,
        )
    except LMStudioError as error:
        model_component = ModelHealthComponent(
            status="degraded",
            model_id=runtime.lm_client.model_id,
            loaded=False,
            tool_use=False,
            quantization=None,
            error_code=error.code,
        )
    return HealthResponse(
        ready=(database_component.status == "ok" and model_component.status == "ok"),
        trace_id=trace_id,
        api=HealthComponent(status="ok", error_code=None),
        sqlite=database_component,
        model=model_component,
    )
