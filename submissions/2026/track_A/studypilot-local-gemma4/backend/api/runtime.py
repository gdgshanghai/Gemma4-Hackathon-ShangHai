"""Dependency container and request-scoped API accessors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, cast

from fastapi import Header, Request

from backend.config import Settings
from backend.orchestration.lm_studio import LMStudioClient
from backend.services.evening import EveningService
from backend.services.parent_calibration import ParentCalibrationService
from backend.storage.evening_workflow import EveningWorkflowRepository
from backend.storage.family_context import FamilyContextRepository
from backend.storage.run_traces import RunTraceRepository


IdempotencyKeyHeader = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]


@dataclass(frozen=True, slots=True)
class AppRuntime:
    settings: Settings
    database_path: Path
    lm_client: LMStudioClient
    family_repository: FamilyContextRepository
    trace_repository: RunTraceRepository
    parent_service: ParentCalibrationService
    evening_repository: EveningWorkflowRepository
    evening_service: EveningService


def get_runtime(request: Request) -> AppRuntime:
    return cast(AppRuntime, request.app.state.runtime)


def get_trace_id(request: Request) -> str:
    return cast(str, request.state.trace_id)
