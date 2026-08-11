"""Child-facing evening workflow routes."""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BeforeValidator

from backend.api.runtime import (
    AppRuntime,
    IdempotencyKeyHeader,
    get_runtime,
    get_trace_id,
)
from backend.contracts.evening import (
    EveningCloseRequest,
    EveningCommitRequest,
    EveningConfirmRequest,
    EveningCreateRequest,
    EveningIntakeRequest,
    EveningPlanRequest,
    EveningResponse,
    EveningTimeBoundaryRequest,
)


def _validate_create_json_body(value: Any) -> Any:
    if isinstance(value, EveningCreateRequest):
        return value
    if not isinstance(value, dict):
        return value
    return EveningCreateRequest.model_validate_json(json.dumps(value))


EveningCreateHttpBody = Annotated[
    EveningCreateRequest,
    BeforeValidator(_validate_create_json_body),
]


def _validate_time_boundary_json_body(value: Any) -> Any:
    if isinstance(value, EveningTimeBoundaryRequest):
        return value
    if not isinstance(value, dict):
        return value
    return EveningTimeBoundaryRequest.model_validate_json(json.dumps(value))


EveningTimeBoundaryHttpBody = Annotated[
    EveningTimeBoundaryRequest,
    BeforeValidator(_validate_time_boundary_json_body),
]


router = APIRouter(prefix="/api/v1/evenings", tags=["evenings"])


@router.post("", response_model=EveningResponse)
def create_evening(
    body: EveningCreateHttpBody,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> EveningResponse:
    return runtime.evening_service.create(
        body,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )


@router.get("/latest", response_model=EveningResponse)
def get_latest_evening(
    session_date: date,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> EveningResponse:
    return runtime.evening_service.get_latest(session_date, trace_id=trace_id)


@router.get("/today", response_model=EveningResponse)
def get_today_evening(
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> EveningResponse:
    return runtime.evening_service.get_today(trace_id=trace_id)


@router.get("/{session_id}", response_model=EveningResponse)
def get_evening(
    session_id: str,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> EveningResponse:
    return runtime.evening_service.get(session_id, trace_id=trace_id)


@router.put("/{session_id}/time-boundary", response_model=EveningResponse)
def update_evening_time_boundary(
    session_id: str,
    body: EveningTimeBoundaryHttpBody,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> EveningResponse:
    return runtime.evening_service.update_time_boundary(
        session_id,
        body,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )


@router.post("/{session_id}/intake-turns", response_model=EveningResponse)
def add_intake_turn(
    session_id: str,
    body: EveningIntakeRequest,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> EveningResponse:
    return runtime.evening_service.intake(
        session_id,
        body,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )


@router.post("/{session_id}/inventory/confirm", response_model=EveningResponse)
def confirm_inventory(
    session_id: str,
    body: EveningConfirmRequest,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> EveningResponse:
    return runtime.evening_service.confirm(
        session_id,
        body,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )


@router.post("/{session_id}/plans", response_model=EveningResponse)
def build_evening_plan(
    session_id: str,
    body: EveningPlanRequest,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> EveningResponse:
    return runtime.evening_service.plan(
        session_id,
        body,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )


@router.post("/{session_id}/plans/{plan_id}/commit", response_model=EveningResponse)
def commit_evening_plan(
    session_id: str,
    plan_id: str,
    body: EveningCommitRequest,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> EveningResponse:
    return runtime.evening_service.commit(
        session_id,
        plan_id,
        body,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )


@router.post("/{session_id}/close-turns", response_model=EveningResponse)
def close_evening(
    session_id: str,
    body: EveningCloseRequest,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> EveningResponse:
    return runtime.evening_service.close(
        session_id,
        body,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )
