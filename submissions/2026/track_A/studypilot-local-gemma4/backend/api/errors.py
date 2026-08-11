"""Sanitized HTTP error projection for the local API boundary."""

from __future__ import annotations

from typing import Literal, cast
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from backend.contracts.api import (
    ApiErrorCode,
    ApiErrorDetail,
    ErrorEnvelope,
    ModelRecoveryData,
    ValidationIssue,
)
from backend.contracts.family import CalibrationState, PendingKind
from backend.errors import (
    CommitCommandInvalidError,
    DraftDigestMismatchError,
    IdempotencyConflictError,
    InvalidTransitionError,
    NotFoundError,
    ProfileProposalInvalidError,
    VersionConflictError,
)
from backend.services.parent_calibration import (
    ParentWorkflowError,
    ParentWorkflowFailureKind,
    _project_failure_code,
)
from backend.services.evening import EveningModelUnavailableError


ERROR_STATUS = {
    ApiErrorCode.SCHEMA_INVALID: 422,
    ApiErrorCode.NOT_FOUND: 404,
    ApiErrorCode.METHOD_NOT_ALLOWED: 405,
    ApiErrorCode.VERSION_CONFLICT: 409,
    ApiErrorCode.IDEMPOTENCY_CONFLICT: 409,
    ApiErrorCode.INVALID_TRANSITION: 409,
    ApiErrorCode.DRAFT_DIGEST_MISMATCH: 409,
    ApiErrorCode.COMMIT_COMMAND_INVALID: 409,
    ApiErrorCode.PROFILE_PROPOSAL_INVALID: 409,
    ApiErrorCode.RETRY_LINEAGE_CONFLICT: 409,
    ApiErrorCode.MODEL_PROTOCOL_ERROR: 502,
    ApiErrorCode.MODEL_UNAVAILABLE: 503,
    ApiErrorCode.INTERNAL_ERROR: 500,
}

ERROR_MESSAGES = {
    ApiErrorCode.SCHEMA_INVALID: "Request schema is invalid.",
    ApiErrorCode.NOT_FOUND: "The requested resource was not found.",
    ApiErrorCode.METHOD_NOT_ALLOWED: "The requested method is not allowed.",
    ApiErrorCode.VERSION_CONFLICT: "The resource version conflicts with the current state.",
    ApiErrorCode.IDEMPOTENCY_CONFLICT: ("The idempotency key conflicts with a previous request."),
    ApiErrorCode.INVALID_TRANSITION: "The requested transition is not allowed.",
    ApiErrorCode.DRAFT_DIGEST_MISMATCH: ("The draft no longer matches the stored version."),
    ApiErrorCode.COMMIT_COMMAND_INVALID: "The commit command is invalid.",
    ApiErrorCode.PROFILE_PROPOSAL_INVALID: "The profile proposal is invalid.",
    ApiErrorCode.RETRY_LINEAGE_CONFLICT: (
        "The retry request conflicts with the stored recovery state."
    ),
    ApiErrorCode.MODEL_PROTOCOL_ERROR: "The model response could not be validated.",
    ApiErrorCode.MODEL_UNAVAILABLE: "The model is temporarily unavailable.",
    ApiErrorCode.INTERNAL_ERROR: "An internal error occurred.",
}


def _error_response(
    request: Request,
    status_code: int,
    detail: ApiErrorDetail,
    recovery: ModelRecoveryData | None = None,
) -> JSONResponse:
    state_trace_id = getattr(request.state, "trace_id", None)
    trace_id = (
        state_trace_id
        if isinstance(state_trace_id, str) and state_trace_id.strip()
        else f"trace-{uuid4()}"
    )
    request.state.trace_id = trace_id
    envelope = ErrorEnvelope(
        error=detail,
        trace_id=trace_id,
        recovery=recovery,
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json"),
        headers={"X-Trace-Id": trace_id},
    )


def _fixed_error_response(
    request: Request,
    code: ApiErrorCode,
    *,
    recovery: ModelRecoveryData | None = None,
) -> JSONResponse:
    return _error_response(
        request,
        ERROR_STATUS[code],
        ApiErrorDetail(code=code, message=ERROR_MESSAGES[code]),
        recovery,
    )


async def request_validation_error_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    try:
        validation_errors = error.errors(include_url=False)
    except TypeError:
        validation_errors = error.errors()
    issues = tuple(
        ValidationIssue(
            location=tuple(item["loc"]),
            type=str(item["type"]),
        )
        for item in validation_errors
    )
    detail = ApiErrorDetail(
        code=ApiErrorCode.SCHEMA_INVALID,
        message=ERROR_MESSAGES[ApiErrorCode.SCHEMA_INVALID],
        issues=issues,
    )
    return _error_response(
        request,
        ERROR_STATUS[ApiErrorCode.SCHEMA_INVALID],
        detail,
    )


async def starlette_http_error_handler(
    request: Request,
    error: StarletteHTTPException,
) -> JSONResponse:
    code = {
        404: ApiErrorCode.NOT_FOUND,
        405: ApiErrorCode.METHOD_NOT_ALLOWED,
    }.get(error.status_code, ApiErrorCode.INTERNAL_ERROR)
    return _fixed_error_response(request, code)


async def not_found_error_handler(
    request: Request,
    _error: NotFoundError,
) -> JSONResponse:
    return _fixed_error_response(request, ApiErrorCode.NOT_FOUND)


async def version_conflict_error_handler(
    request: Request,
    _error: VersionConflictError,
) -> JSONResponse:
    return _fixed_error_response(request, ApiErrorCode.VERSION_CONFLICT)


async def idempotency_conflict_error_handler(
    request: Request,
    _error: IdempotencyConflictError,
) -> JSONResponse:
    return _fixed_error_response(request, ApiErrorCode.IDEMPOTENCY_CONFLICT)


async def invalid_transition_error_handler(
    request: Request,
    _error: InvalidTransitionError,
) -> JSONResponse:
    return _fixed_error_response(request, ApiErrorCode.INVALID_TRANSITION)


async def draft_digest_mismatch_error_handler(
    request: Request,
    _error: DraftDigestMismatchError,
) -> JSONResponse:
    return _fixed_error_response(request, ApiErrorCode.DRAFT_DIGEST_MISMATCH)


async def commit_command_invalid_error_handler(
    request: Request,
    _error: CommitCommandInvalidError,
) -> JSONResponse:
    return _fixed_error_response(request, ApiErrorCode.COMMIT_COMMAND_INVALID)


async def profile_proposal_invalid_error_handler(
    request: Request,
    _error: ProfileProposalInvalidError,
) -> JSONResponse:
    return _fixed_error_response(request, ApiErrorCode.PROFILE_PROPOSAL_INVALID)


def _project_model_recovery(error: ParentWorkflowError) -> ModelRecoveryData | None:
    recovery = error.recovery
    if recovery is None:
        return None
    checkpoint = recovery.latest_checkpoint
    if (
        checkpoint.state is not CalibrationState.MODEL_UNAVAILABLE
        or checkpoint.pending_kind is not PendingKind.MODEL_RETRY
        or checkpoint.calibration_id != recovery.calibration_id
        or checkpoint.calibration_version != recovery.calibration_version
        or checkpoint.profile_version != recovery.profile_version
    ):
        raise ValueError("invalid model recovery snapshot")
    return ModelRecoveryData(
        calibration_id=recovery.calibration_id,
        calibration_version=recovery.calibration_version,
        profile_version=recovery.profile_version,
        stage=CalibrationState.MODEL_UNAVAILABLE,
        allowed_actions=(
            "retry_last_turn",
            "use_simplified_calibration",
            "abandon_profile_patch",
        ),
        resume_stage=cast(
            Literal["profile_propose", "profile_commit"],
            checkpoint.resume_stage,
        ),
        pending_kind=PendingKind.MODEL_RETRY,
        pending_entity_id=cast(str, checkpoint.pending_entity_id),
        input_receipt_id=recovery.receipt.id,
        input_saved=True,
        failure_code=_project_failure_code(recovery),
    )


async def parent_workflow_error_handler(
    request: Request,
    error: ParentWorkflowError,
) -> JSONResponse:
    code = ApiErrorCode(error.kind.value)
    recovery = None
    if error.kind is ParentWorkflowFailureKind.MODEL_UNAVAILABLE:
        try:
            recovery = _project_model_recovery(error)
        except (AttributeError, TypeError, ValueError):
            return _fixed_error_response(request, ApiErrorCode.INTERNAL_ERROR)
    return _fixed_error_response(request, code, recovery=recovery)


async def evening_model_unavailable_error_handler(
    request: Request,
    error: EveningModelUnavailableError,
) -> JSONResponse:
    content = error.response.model_dump(mode="json")
    content["error"] = ApiErrorDetail(
        code=ApiErrorCode.MODEL_UNAVAILABLE,
        message=ERROR_MESSAGES[ApiErrorCode.MODEL_UNAVAILABLE],
    ).model_dump(mode="json")
    return JSONResponse(
        status_code=ERROR_STATUS[ApiErrorCode.MODEL_UNAVAILABLE],
        content=content,
        headers={"X-Trace-Id": error.response.trace_id},
    )


async def unknown_exception_handler(
    request: Request,
    _error: Exception,
) -> JSONResponse:
    code = ApiErrorCode.INTERNAL_ERROR
    return _error_response(
        request,
        ERROR_STATUS[code],
        ApiErrorDetail(code=code, message=ERROR_MESSAGES[code]),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_error_handler)
    app.add_exception_handler(NotFoundError, not_found_error_handler)
    app.add_exception_handler(VersionConflictError, version_conflict_error_handler)
    app.add_exception_handler(IdempotencyConflictError, idempotency_conflict_error_handler)
    app.add_exception_handler(InvalidTransitionError, invalid_transition_error_handler)
    app.add_exception_handler(DraftDigestMismatchError, draft_digest_mismatch_error_handler)
    app.add_exception_handler(CommitCommandInvalidError, commit_command_invalid_error_handler)
    app.add_exception_handler(ProfileProposalInvalidError, profile_proposal_invalid_error_handler)
    app.add_exception_handler(ParentWorkflowError, parent_workflow_error_handler)
    app.add_exception_handler(
        EveningModelUnavailableError,
        evening_model_unavailable_error_handler,
    )
    app.add_exception_handler(Exception, unknown_exception_handler)
