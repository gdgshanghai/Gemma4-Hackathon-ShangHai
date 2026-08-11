"""Versioned manual school brief API routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.runtime import (
    AppRuntime,
    IdempotencyKeyHeader,
    get_runtime,
    get_trace_id,
)
from backend.contracts.api import (
    SchoolBriefHistoryEnvelope,
    SchoolBriefReadEnvelope,
    SchoolBriefWriteEnvelope,
    SchoolBriefWriteRequest,
)
from backend.contracts.family import FamilyWriteContext
from backend.errors import NotFoundError


router = APIRouter(prefix="/api/v1/school-briefs", tags=["school-briefs"])


@router.post("", response_model=SchoolBriefWriteEnvelope)
def write_school_brief(
    body: SchoolBriefWriteRequest,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> SchoolBriefWriteEnvelope:
    delivered = runtime.family_repository.append_school_brief(
        body.brief_date,
        body.raw_text,
        expected_revision=body.expected_revision,
        context=FamilyWriteContext(
            actor="local-parent",
            role="parent",
            trace_id=trace_id,
            idempotency_key=idempotency_key,
        ),
    )
    return SchoolBriefWriteEnvelope(
        trace_id=trace_id,
        data=delivered.outcome,
        delivery=delivered.delivery,
    )


@router.get("", response_model=SchoolBriefReadEnvelope)
def get_latest_school_brief(
    brief_date: date,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> SchoolBriefReadEnvelope:
    record = runtime.family_repository.get_latest_school_brief(brief_date)
    if record is None:
        raise NotFoundError("school brief", brief_date.isoformat())
    return SchoolBriefReadEnvelope(trace_id=trace_id, data=record)


@router.get("/revisions", response_model=SchoolBriefHistoryEnvelope)
def get_school_brief_revisions(
    brief_date: date,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> SchoolBriefHistoryEnvelope:
    records = runtime.family_repository.list_school_brief_revisions(brief_date)
    if not records:
        raise NotFoundError("school brief", brief_date.isoformat())
    return SchoolBriefHistoryEnvelope(
        trace_id=trace_id,
        brief_date=brief_date,
        revisions=records,
    )
