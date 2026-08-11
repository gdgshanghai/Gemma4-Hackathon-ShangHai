"""Shared parent-facing read router."""

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
from backend.contracts.api import (
    CalibrationAbandonRequest,
    CalibrationCommitRequest,
    CalibrationCreateRequest,
    CalibrationResponseEnvelope,
    CalibrationRetryRequest,
    CalibrationSimplifyRequest,
    CalibrationReviseRequest,
    WeeklySummaryResponse,
)
from backend.services.weekly_summary import build_weekly_summary


def _validate_commit_json_body(value: Any) -> Any:
    if isinstance(value, CalibrationCommitRequest):
        return value
    if not isinstance(value, dict):
        return value
    return CalibrationCommitRequest.model_validate_json(json.dumps(value))


def _validate_revise_json_body(value: Any) -> Any:
    if isinstance(value, CalibrationReviseRequest):
        return value
    if not isinstance(value, dict):
        return value
    return CalibrationReviseRequest.model_validate_json(json.dumps(value))


def _validate_simplify_json_body(value: Any) -> Any:
    if isinstance(value, CalibrationSimplifyRequest):
        return value
    if not isinstance(value, dict):
        return value
    return CalibrationSimplifyRequest.model_validate_json(json.dumps(value))


CalibrationCommitHttpBody = Annotated[
    CalibrationCommitRequest,
    BeforeValidator(_validate_commit_json_body),
]
CalibrationReviseHttpBody = Annotated[
    CalibrationReviseRequest,
    BeforeValidator(_validate_revise_json_body),
]
CalibrationSimplifyHttpBody = Annotated[
    CalibrationSimplifyRequest,
    BeforeValidator(_validate_simplify_json_body),
]


parent_router = APIRouter(
    prefix="/api/v1/parent",
    tags=["parent"],
)


@parent_router.get("/weekly-summary", response_model=WeeklySummaryResponse)
def get_weekly_summary(
    week_start: date,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> WeeklySummaryResponse:
    return WeeklySummaryResponse(
        trace_id=trace_id,
        data=build_weekly_summary(
            runtime.family_repository,
            week_start,
        ),
    )


@parent_router.post(
    "/calibrations",
    response_model=CalibrationResponseEnvelope,
)
def create_calibration(
    body: CalibrationCreateRequest,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> CalibrationResponseEnvelope:
    return runtime.parent_service.create_calibration(
        body,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )


@parent_router.get(
    "/calibrations/{calibration_id}",
    response_model=CalibrationResponseEnvelope,
)
def get_calibration(
    calibration_id: str,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> CalibrationResponseEnvelope:
    return runtime.parent_service.get_calibration(
        calibration_id,
        trace_id=trace_id,
    )


@parent_router.post(
    "/calibrations/{calibration_id}/retry",
    response_model=CalibrationResponseEnvelope,
)
def retry_calibration(
    calibration_id: str,
    body: CalibrationRetryRequest,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> CalibrationResponseEnvelope:
    return runtime.parent_service.retry_calibration(
        calibration_id,
        body,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )


@parent_router.post(
    "/calibrations/{calibration_id}/simplify",
    response_model=CalibrationResponseEnvelope,
)
def simplify_calibration(
    calibration_id: str,
    body: CalibrationSimplifyHttpBody,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> CalibrationResponseEnvelope:
    return runtime.parent_service.simplify_calibration(
        calibration_id,
        body,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )


@parent_router.post(
    "/calibrations/{calibration_id}/commit",
    response_model=CalibrationResponseEnvelope,
)
def commit_calibration(
    calibration_id: str,
    body: CalibrationCommitHttpBody,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> CalibrationResponseEnvelope:
    return runtime.parent_service.commit_calibration(
        calibration_id,
        body,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )


@parent_router.post(
    "/calibrations/{calibration_id}/revise",
    response_model=CalibrationResponseEnvelope,
)
def revise_calibration(
    calibration_id: str,
    body: CalibrationReviseHttpBody,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> CalibrationResponseEnvelope:
    return runtime.parent_service.revise_calibration(
        calibration_id,
        body,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )


@parent_router.post(
    "/calibrations/{calibration_id}/abandon",
    response_model=CalibrationResponseEnvelope,
)
def abandon_calibration(
    calibration_id: str,
    body: CalibrationAbandonRequest,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> CalibrationResponseEnvelope:
    return runtime.parent_service.abandon_calibration(
        calibration_id,
        body,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )
