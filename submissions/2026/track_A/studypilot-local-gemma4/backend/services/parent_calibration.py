"""Receipt-first orchestration for parent profile calibration workflows."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID, uuid5

from pydantic import ValidationError

from backend.contracts.api import (
    CalibrationAction,
    CalibrationAbandonRequest,
    CalibrationCommitRequest,
    CalibrationCreateRequest,
    CalibrationRecoveryData,
    CalibrationRetryRequest,
    CalibrationSimplifyRequest,
    CalibrationResponseEnvelope,
    CalibrationReviseRequest,
    NarrationStatus,
    ProfilePatchCommitData,
    ProfilePatchProposalData,
)
from backend.contracts.calibration_tools import (
    CalibrationEvidenceDetail,
    ExtractCalibrationEvidenceArgs,
    ProfileToolFailure,
    ProfileToolFailureCode,
    ProfileToolSuccess,
    TrustedProfileCommitCommand,
)
from backend.domain.calibration import (
    compile_duration_evidence,
    describe_duration_evidence,
)
from backend.contracts.family import (
    CalibrationCommitInputReceipt,
    CalibrationCommitInputReceiptResult,
    CalibrationRecoverySnapshot,
    CalibrationState,
    CalibrationWorkflowResult,
    DeliveredCalibrationResult,
    DeliveryMetadata,
    FamilyWriteContext,
    MemoryObservation,
    PendingKind,
    ProfileCommit,
    RecoveryDirective,
    RetryBeginOutcomeData,
)
from backend.errors import (
    CommitCommandInvalidError,
    DraftDigestMismatchError,
    IdempotencyConflictError,
    InvalidTransitionError,
    NotFoundError,
    StudyPilotError,
    VersionConflictError,
)
from backend.domain.workflow import allowed_actions as workflow_allowed_actions
from backend.orchestration.calibration import (
    CalibrationHarnessExecution,
    build_profile_propose_execution,
)
from backend.orchestration.harness import HarnessError
from backend.orchestration.lm_studio import LMStudioClient
from backend.orchestration.tool_registry import (
    WorkflowPhase,
    derive_write_idempotency_key,
)
from backend.storage.family_context import FamilyContextRepository
from backend.storage.run_traces import RunTraceRepository


_CALIBRATION_NAMESPACE = UUID("9c8d2f63-a806-5e76-a9a1-9f927e1f0b42")
_FAILURE_KEY_NAMESPACE = "studypilot.calibration.model-failure.v1"

MODEL_UNAVAILABLE_CODES = frozenset(
    {
        "model_timeout",
        "model_connection_refused",
        "model_transport_error",
        "model_http_error",
        "model_not_found",
        "model_not_loaded",
        "model_tool_use_missing",
    }
)
MODEL_PROTOCOL_CODES = frozenset(
    {
        "malformed_json_response",
        "malformed_response_envelope",
        "malformed_model_metadata",
        "model_output_truncated",
        "model_id_mismatch",
        "missing_choice",
        "malformed_choice",
        "invalid_tool_call",
        "invalid_tool_arguments_type",
        "unsupported_finish_reason",
        "unexpected_tool_calls",
        "required_tool_not_called",
        "tool_schema_invalid",
        "tool_schema_repair_exhausted",
        "multiple_tool_calls",
        "duplicate_tool_call_id",
        "disallowed_tool",
        "repeated_read_limit",
        "model_confirmation_mismatch",
        "proposal_invalid",
    }
)
POST_WRITE_ONLY_CODES = frozenset(
    {
        "idempotency_conflict",
        "tool_loop_limit",
        "empty_final_content",
    }
)
INTERNAL_RUNTIME_CODES = frozenset(
    {
        "invalid_model_base_url",
        "unsupported_model_id",
        "remote_model_host_forbidden",
        "mock_model_forbidden",
        "missing_idempotency_key",
        "tool_handler_failed",
        "tool_result_not_object",
        "tool_result_not_serializable",
        "harness_internal_error",
    }
)


class ParentWorkflowFailureKind(StrEnum):
    NOT_FOUND = "not_found"
    VERSION_CONFLICT = "version_conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    INVALID_TRANSITION = "invalid_transition"
    DRAFT_DIGEST_MISMATCH = "draft_digest_mismatch"
    COMMIT_COMMAND_INVALID = "commit_command_invalid"
    MODEL_PROTOCOL_ERROR = "model_protocol_error"
    MODEL_UNAVAILABLE = "model_unavailable"
    RETRY_LINEAGE_CONFLICT = "retry_lineage_conflict"
    INTERNAL_ERROR = "internal_error"


class InferenceAuthorization(StrEnum):
    INITIAL_REQUEST = "initial_request"
    EXPLICIT_RETRY = "explicit_retry"


@dataclass(frozen=True, slots=True)
class ValidatedRetryLineage:
    calibration_id: str
    baseline_calibration_version: int
    baseline_profile_version: int
    receipt_id: str
    resume_stage: Literal["profile_propose", "profile_commit"]
    pending_entity_id: str
    commit_input: CalibrationCommitInputReceipt | None
    begin_outcome: CalibrationWorkflowResult


@dataclass(frozen=True, slots=True)
class CalibrationWriteTarget:
    phase: WorkflowPhase
    calibration_id: str
    baseline_calibration_version: int
    baseline_profile_version: int
    request_trace_id: str
    receipt_id: str
    commit_input: CalibrationCommitInputReceipt | None = None
    hidden_tool_key: str | None = None

    def __post_init__(self) -> None:
        commit_fields = (self.commit_input, self.hidden_tool_key)
        if self.phase is WorkflowPhase.PROFILE_COMMIT:
            if any(item is None for item in commit_fields):
                raise ValueError("commit target requires commit receipt and hidden key")
        elif self.phase is WorkflowPhase.PROFILE_PROPOSE:
            if any(item is not None for item in commit_fields):
                raise ValueError("proposal target forbids commit-only fields")
        else:
            raise ValueError("calibration target phase is unsupported")

    @classmethod
    def for_proposal(
        cls,
        recovery: CalibrationRecoverySnapshot,
        trace_id: str,
    ) -> Self:
        return cls(
            phase=WorkflowPhase.PROFILE_PROPOSE,
            calibration_id=recovery.calibration_id,
            baseline_calibration_version=recovery.calibration_version,
            baseline_profile_version=recovery.profile_version,
            request_trace_id=trace_id,
            receipt_id=recovery.receipt.id,
        )

    @classmethod
    def for_commit(
        cls,
        recovery: CalibrationRecoverySnapshot,
        commit_input: CalibrationCommitInputReceipt,
        hidden_key: str,
        trace_id: str,
    ) -> Self:
        return cls(
            phase=WorkflowPhase.PROFILE_COMMIT,
            calibration_id=recovery.calibration_id,
            baseline_calibration_version=recovery.calibration_version,
            baseline_profile_version=recovery.profile_version,
            request_trace_id=trace_id,
            receipt_id=commit_input.id,
            commit_input=commit_input,
            hidden_tool_key=hidden_key,
        )


class ParentWorkflowError(StudyPilotError):
    def __init__(
        self,
        kind: ParentWorkflowFailureKind,
        *,
        cause_code: str,
        trace_id: str,
        recovery: CalibrationRecoverySnapshot | None = None,
    ) -> None:
        self.kind = kind
        self.cause_code = cause_code
        self.trace_id = trace_id
        self.recovery = recovery
        super().__init__(kind.value)


def derive_calibration_id(caller_idempotency_key: str) -> str:
    digest = hashlib.sha256(caller_idempotency_key.encode("utf-8")).hexdigest()
    return f"calibration-{uuid5(_CALIBRATION_NAMESPACE, digest)}"


def _parent_context(
    trace_id: str,
    idempotency_key: str,
) -> FamilyWriteContext:
    return FamilyWriteContext(
        actor="local-parent",
        role="parent",
        trace_id=trace_id,
        idempotency_key=idempotency_key,
    )


def _workflow_error_from_terminal_without_recovery(
    terminal: ProfileToolSuccess | ProfileToolFailure | None,
    trace_id: str,
) -> ParentWorkflowError:
    if isinstance(terminal, ProfileToolFailure):
        return _workflow_error_from_tool_failure(
            terminal,
            trace_id,
            recovery=None,
        )
    return ParentWorkflowError(
        ParentWorkflowFailureKind.INTERNAL_ERROR,
        cause_code="missing_typed_terminal_result",
        trace_id=trace_id,
        recovery=None,
    )


def _workflow_error_from_tool_failure(
    terminal: ProfileToolFailure,
    trace_id: str,
    *,
    recovery: CalibrationRecoverySnapshot | None,
) -> ParentWorkflowError:
    kind = {
        ProfileToolFailureCode.NOT_FOUND: ParentWorkflowFailureKind.NOT_FOUND,
        ProfileToolFailureCode.VERSION_CONFLICT: ParentWorkflowFailureKind.VERSION_CONFLICT,
        ProfileToolFailureCode.IDEMPOTENCY_CONFLICT: (
            ParentWorkflowFailureKind.IDEMPOTENCY_CONFLICT
        ),
        ProfileToolFailureCode.INVALID_TRANSITION: (ParentWorkflowFailureKind.INVALID_TRANSITION),
        ProfileToolFailureCode.DRAFT_DIGEST_MISMATCH: (
            ParentWorkflowFailureKind.DRAFT_DIGEST_MISMATCH
        ),
        ProfileToolFailureCode.COMMIT_COMMAND_INVALID: (
            ParentWorkflowFailureKind.COMMIT_COMMAND_INVALID
        ),
        ProfileToolFailureCode.PROPOSAL_INVALID: (ParentWorkflowFailureKind.MODEL_PROTOCOL_ERROR),
        ProfileToolFailureCode.MODEL_CONFIRMATION_MISMATCH: (
            ParentWorkflowFailureKind.MODEL_PROTOCOL_ERROR
        ),
    }[terminal.error.code]
    return ParentWorkflowError(
        kind,
        cause_code=terminal.error.code.value,
        trace_id=trace_id,
        recovery=recovery,
    )


def _classify_harness_code(code: str) -> ParentWorkflowFailureKind:
    if code in MODEL_UNAVAILABLE_CODES:
        return ParentWorkflowFailureKind.MODEL_UNAVAILABLE
    if code in MODEL_PROTOCOL_CODES:
        return ParentWorkflowFailureKind.MODEL_PROTOCOL_ERROR
    return ParentWorkflowFailureKind.INTERNAL_ERROR


def _workflow_error_from_harness(
    error: HarnessError,
    recovery: CalibrationRecoverySnapshot,
) -> ParentWorkflowError:
    return ParentWorkflowError(
        _classify_harness_code(error.code),
        cause_code=error.code,
        trace_id=error.trace_id,
        recovery=recovery,
    )


def _stored_model_failure(
    recovery: CalibrationRecoverySnapshot,
    trace_id: str,
) -> ParentWorkflowError:
    if (
        recovery.latest_checkpoint.state is not CalibrationState.MODEL_UNAVAILABLE
        or recovery.directive is not RecoveryDirective.EXPLICIT_RETRY_ALLOWED
    ):
        return ParentWorkflowError(
            ParentWorkflowFailureKind.INTERNAL_ERROR,
            cause_code="stored_model_failure_state_invalid",
            trace_id=trace_id,
            recovery=None,
        )
    return ParentWorkflowError(
        ParentWorkflowFailureKind.MODEL_UNAVAILABLE,
        cause_code="stored_model_unavailable",
        trace_id=trace_id,
        recovery=recovery,
    )


def _retry_lineage_error(
    recovery: CalibrationRecoverySnapshot,
    trace_id: str,
) -> ParentWorkflowError:
    return ParentWorkflowError(
        ParentWorkflowFailureKind.RETRY_LINEAGE_CONFLICT,
        cause_code="retry_lineage_mismatch",
        trace_id=trace_id,
        recovery=recovery,
    )


def _require_current_retry_pending(
    recovery: CalibrationRecoverySnapshot,
    lineage: ValidatedRetryLineage,
    trace_id: str,
) -> None:
    checkpoint = recovery.latest_checkpoint
    if (
        recovery.calibration_id != lineage.calibration_id
        or recovery.calibration_version != lineage.baseline_calibration_version
        or recovery.profile_version != lineage.baseline_profile_version
        or checkpoint.state is not CalibrationState.RETRY_PENDING
        or checkpoint.resume_stage != lineage.resume_stage
        or checkpoint.pending_kind is not PendingKind.MODEL_RETRY
        or checkpoint.pending_entity_id != lineage.pending_entity_id
        or checkpoint.input_receipt_id != lineage.receipt_id
    ):
        raise _retry_lineage_error(recovery, trace_id)


def _derive_failure_idempotency_key(
    caller_idempotency_key: str,
    resume_stage: str,
) -> str:
    payload = json.dumps(
        {
            "caller_idempotency_key": caller_idempotency_key,
            "namespace": _FAILURE_KEY_NAMESPACE,
            "resume_stage": resume_stage,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_failure_source(
    recovery: CalibrationRecoverySnapshot,
    target: CalibrationWriteTarget,
    resume_stage: Literal["profile_propose", "profile_commit"],
    trace_id: str,
) -> None:
    checkpoint = recovery.latest_checkpoint
    if target.phase is WorkflowPhase.PROFILE_PROPOSE:
        initial_ok = (
            resume_stage == "profile_propose"
            and checkpoint.state is CalibrationState.INPUT_SAVED
            and checkpoint.resume_stage == "profile_propose"
            and checkpoint.pending_kind is None
            and checkpoint.pending_entity_id is None
            and checkpoint.input_receipt_id == target.receipt_id
        )
        retry_ok = (
            resume_stage == "profile_propose"
            and checkpoint.state is CalibrationState.RETRY_PENDING
            and checkpoint.resume_stage == "profile_propose"
            and checkpoint.pending_kind is PendingKind.MODEL_RETRY
            and checkpoint.pending_entity_id == target.receipt_id
            and checkpoint.input_receipt_id == target.receipt_id
        )
        valid = initial_ok or retry_ok
    else:
        commit_input = target.commit_input
        valid = (
            commit_input is not None
            and resume_stage == "profile_commit"
            and checkpoint.state
            in {
                CalibrationState.NEEDS_CONFIRMATION,
                CalibrationState.RETRY_PENDING,
            }
            and (
                checkpoint.state is CalibrationState.NEEDS_CONFIRMATION
                or (
                    checkpoint.resume_stage == "profile_commit"
                    and checkpoint.pending_kind is PendingKind.MODEL_RETRY
                    and checkpoint.pending_entity_id == commit_input.id
                )
            )
        )
    if (
        not valid
        or recovery.calibration_id != target.calibration_id
        or recovery.calibration_version != target.baseline_calibration_version
        or recovery.profile_version != target.baseline_profile_version
    ):
        raise ParentWorkflowError(
            ParentWorkflowFailureKind.VERSION_CONFLICT,
            cause_code="failure_source_conflict",
            trace_id=trace_id,
            recovery=recovery,
        )


class ParentCalibrationService:
    def __init__(
        self,
        *,
        repository: FamilyContextRepository,
        client: LMStudioClient,
        trace_repository: RunTraceRepository,
    ) -> None:
        self.repository = repository
        self.client = client
        self.trace_repository = trace_repository

    def create_calibration(
        self,
        request: CalibrationCreateRequest,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> CalibrationResponseEnvelope:
        calibration_id = derive_calibration_id(caller_idempotency_key)
        receipt_result = self.repository.save_calibration_input(
            calibration_id,
            request.text,
            expected_calibration_version=request.expected_calibration_version,
            expected_profile_version=request.expected_profile_version,
            context=_parent_context(trace_id, caller_idempotency_key),
        )
        recovery = self.repository.get_calibration_recovery(calibration_id)
        return self._continue_from_recovery(
            recovery,
            authorization=InferenceAuthorization.INITIAL_REQUEST,
            initial_commit_input=None,
            caller_idempotency_key=caller_idempotency_key,
            trace_id=trace_id,
            delivery_replayed=receipt_result.replayed,
        )

    def commit_calibration(
        self,
        calibration_id: str,
        request: CalibrationCommitRequest,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> CalibrationResponseEnvelope:
        hidden_key = derive_write_idempotency_key(
            caller_idempotency_key,
            WorkflowPhase.PROFILE_COMMIT,
            "commit_profile_patch",
        )
        replay = self.repository.lookup_commit_profile_patch(
            calibration_id,
            request.draft_id,
            request.accepted_operation_ids,
            draft_digest=request.draft_digest,
            expected_calibration_version=request.expected_calibration_version,
            context=_parent_context(trace_id, hidden_key),
        )
        if replay is not None:
            recovery = self.repository.get_calibration_recovery(calibration_id)
            if recovery.last_outcome != replay.outcome:
                raise ParentWorkflowError(
                    ParentWorkflowFailureKind.IDEMPOTENCY_CONFLICT,
                    cause_code="exact_commit_replay_not_current",
                    trace_id=trace_id,
                    recovery=recovery,
                )
            return _present_recovery(
                recovery,
                delivery_replayed=True,
                narration=None,
                narration_status=NarrationStatus.NOT_REQUESTED,
                request_trace_id=trace_id,
            )

        recovery = self.repository.get_calibration_recovery(calibration_id)
        if recovery.calibration_version != request.expected_calibration_version:
            raise VersionConflictError(
                "calibration",
                calibration_id,
                request.expected_calibration_version,
                recovery.calibration_version,
            )
        if (
            recovery.latest_checkpoint.state is not CalibrationState.NEEDS_CONFIRMATION
            or recovery.pending_draft is None
            or recovery.pending_draft.id != request.draft_id
        ):
            raise InvalidTransitionError(
                recovery.latest_checkpoint.state.value,
                WorkflowPhase.PROFILE_COMMIT.value,
            )
        if recovery.pending_draft.draft_digest != request.draft_digest:
            raise DraftDigestMismatchError(request.draft_id)

        commit_input = self.repository.save_profile_commit_input(
            calibration_id,
            request.draft_id,
            request.accepted_operation_ids,
            draft_digest=request.draft_digest,
            expected_calibration_version=request.expected_calibration_version,
            context=_parent_context(trace_id, caller_idempotency_key),
        )
        recovery = self.repository.get_calibration_recovery(calibration_id)
        command = TrustedProfileCommitCommand(
            calibration_id=commit_input.input.calibration_id,
            expected_calibration_version=recovery.calibration_version,
            draft_id=commit_input.input.draft_id,
            draft_digest=commit_input.input.draft_digest,
            accepted_operation_ids=commit_input.input.accepted_operation_ids,
        )
        if command.expected_calibration_version != (
            commit_input.input.expected_calibration_version
        ):
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INVALID_TRANSITION,
                cause_code="commit_receipt_baseline_changed",
                trace_id=trace_id,
                recovery=recovery,
            )
        return self._continue_from_recovery(
            recovery,
            authorization=InferenceAuthorization.INITIAL_REQUEST,
            initial_commit_input=commit_input,
            caller_idempotency_key=caller_idempotency_key,
            trace_id=trace_id,
            delivery_replayed=commit_input.replayed,
        )

    def get_calibration(
        self,
        calibration_id: str,
        *,
        trace_id: str,
    ) -> CalibrationResponseEnvelope:
        recovery = self.repository.get_calibration_recovery(calibration_id)
        return _present_recovery(
            recovery,
            delivery_replayed=True,
            narration=None,
            narration_status=NarrationStatus.NOT_REQUESTED,
            request_trace_id=trace_id,
        )

    def simplify_calibration(
        self,
        calibration_id: str,
        request: CalibrationSimplifyRequest,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> CalibrationResponseEnvelope:
        recovery = self.repository.get_calibration_recovery(calibration_id)
        evidence = ExtractCalibrationEvidenceArgs(
            duration_groups=tuple(
                {
                    "subject": group.subject,
                    "task_type": group.task_type,
                    "workload_band": group.workload_band,
                    "minutes": (group.conservative_minutes,),
                }
                for group in request.duration_groups
            )
        )
        observations = compile_duration_evidence(
            evidence,
            recovery.receipt,
            self.repository.get_profile_snapshot(recovery.profile_version),
        )
        delivered = self.repository.propose_profile_patch(
            calibration_id,
            recovery.receipt.id,
            observations,
            expected_calibration_version=request.expected_calibration_version,
            context=_parent_context(trace_id, caller_idempotency_key),
            calibration_details=describe_duration_evidence(evidence),
        )
        fresh = self.repository.get_calibration_recovery(calibration_id)
        if fresh.last_outcome != delivered.outcome:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INTERNAL_ERROR,
                cause_code="simplified_outcome_not_current",
                trace_id=trace_id,
                recovery=None,
            )
        return _present_recovery(
            fresh,
            delivery_replayed=delivered.delivery.replayed,
            narration=None,
            narration_status=NarrationStatus.NOT_REQUESTED,
            request_trace_id=trace_id,
        )

    def retry_calibration(
        self,
        calibration_id: str,
        request: CalibrationRetryRequest,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> CalibrationResponseEnvelope:
        begin_result = self.repository.begin_calibration_retry(
            calibration_id,
            expected_calibration_version=request.expected_calibration_version,
            context=_parent_context(trace_id, caller_idempotency_key),
        )
        recovery = self.repository.get_calibration_recovery(calibration_id)
        return self._continue_from_recovery(
            recovery,
            authorization=InferenceAuthorization.EXPLICIT_RETRY,
            retry_begin_result=begin_result,
            initial_commit_input=None,
            caller_idempotency_key=caller_idempotency_key,
            trace_id=trace_id,
            delivery_replayed=begin_result.delivery.replayed,
        )

    def revise_calibration(
        self,
        calibration_id: str,
        request: CalibrationReviseRequest,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> CalibrationResponseEnvelope:
        delivered = self.repository.revise_profile_patch(
            calibration_id,
            request.draft_id,
            request.revised_observations,
            expected_calibration_version=request.expected_calibration_version,
            context=_parent_context(trace_id, caller_idempotency_key),
        )
        recovery = self.repository.get_calibration_recovery(calibration_id)
        if recovery.last_outcome != delivered.outcome:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INTERNAL_ERROR,
                cause_code="revised_outcome_not_current",
                trace_id=trace_id,
                recovery=None,
            )
        return _present_recovery(
            recovery,
            delivery_replayed=delivered.delivery.replayed,
            narration=None,
            narration_status=NarrationStatus.NOT_REQUESTED,
            request_trace_id=trace_id,
        )

    def abandon_calibration(
        self,
        calibration_id: str,
        request: CalibrationAbandonRequest,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> CalibrationResponseEnvelope:
        delivered = self.repository.abandon_profile_patch(
            calibration_id,
            expected_calibration_version=request.expected_calibration_version,
            context=_parent_context(trace_id, caller_idempotency_key),
        )
        recovery = self.repository.get_calibration_recovery(calibration_id)
        if recovery.last_outcome != delivered.outcome:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INTERNAL_ERROR,
                cause_code="abandoned_outcome_not_current",
                trace_id=trace_id,
                recovery=None,
            )
        return _present_recovery(
            recovery,
            delivery_replayed=delivered.delivery.replayed,
            narration=None,
            narration_status=NarrationStatus.NOT_REQUESTED,
            request_trace_id=trace_id,
        )

    def _continue_from_recovery(
        self,
        recovery: CalibrationRecoverySnapshot,
        *,
        authorization: InferenceAuthorization,
        retry_begin_result: DeliveredCalibrationResult | None = None,
        initial_commit_input: CalibrationCommitInputReceiptResult | None,
        caller_idempotency_key: str,
        trace_id: str,
        delivery_replayed: bool,
    ) -> CalibrationResponseEnvelope:
        if authorization is InferenceAuthorization.INITIAL_REQUEST:
            if retry_begin_result is not None:
                raise ParentWorkflowError(
                    ParentWorkflowFailureKind.INVALID_TRANSITION,
                    cause_code="initial_request_rejects_retry_result",
                    trace_id=trace_id,
                    recovery=recovery,
                )
            return self._continue_initial_from_recovery(
                recovery,
                initial_commit_input=initial_commit_input,
                caller_idempotency_key=caller_idempotency_key,
                trace_id=trace_id,
                delivery_replayed=delivery_replayed,
            )
        if (
            authorization is not InferenceAuthorization.EXPLICIT_RETRY
            or initial_commit_input is not None
        ):
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.RETRY_LINEAGE_CONFLICT,
                cause_code="retry_authorization_invalid",
                trace_id=trace_id,
                recovery=recovery,
            )
        if retry_begin_result is None:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.RETRY_LINEAGE_CONFLICT,
                cause_code="retry_begin_result_required",
                trace_id=trace_id,
                recovery=recovery,
            )
        lineage = self._validate_retry_begin_lineage(
            retry_begin_result,
            recovery,
            trace_id=trace_id,
        )
        stored_retry_outcome = self._verify_retry_lineage_against_current(
            recovery,
            lineage,
            caller_idempotency_key=caller_idempotency_key,
            trace_id=trace_id,
        )
        match recovery.directive:
            case RecoveryDirective.RETURN_STORED:
                if stored_retry_outcome is None:
                    raise ParentWorkflowError(
                        ParentWorkflowFailureKind.RETRY_LINEAGE_CONFLICT,
                        cause_code="retry_lineage_mismatch",
                        trace_id=trace_id,
                        recovery=recovery,
                    )
                return _present_recovery(
                    recovery,
                    delivery_replayed=True,
                    narration=None,
                    narration_status=NarrationStatus.NOT_REQUESTED,
                    request_trace_id=trace_id,
                )
            case RecoveryDirective.EXPLICIT_RETRY_ALLOWED:
                raise _stored_model_failure(recovery, trace_id)
            case RecoveryDirective.INITIAL_INFERENCE:
                _require_current_retry_pending(recovery, lineage, trace_id)
                if lineage.resume_stage == "profile_propose":
                    return self._infer_proposal(
                        recovery,
                        caller_idempotency_key=caller_idempotency_key,
                        trace_id=trace_id,
                    )
                if lineage.commit_input is None:
                    raise ParentWorkflowError(
                        ParentWorkflowFailureKind.RETRY_LINEAGE_CONFLICT,
                        cause_code="retry_commit_input_missing",
                        trace_id=trace_id,
                        recovery=recovery,
                    )
                hidden_key = derive_write_idempotency_key(
                    caller_idempotency_key,
                    WorkflowPhase.PROFILE_COMMIT,
                    "commit_profile_patch",
                )
                command = TrustedProfileCommitCommand(
                    calibration_id=recovery.calibration_id,
                    expected_calibration_version=recovery.calibration_version,
                    draft_id=lineage.commit_input.draft_id,
                    draft_digest=lineage.commit_input.draft_digest,
                    accepted_operation_ids=lineage.commit_input.accepted_operation_ids,
                )
                return self._infer_commit(
                    recovery,
                    command,
                    commit_input=lineage.commit_input,
                    hidden_key=hidden_key,
                    caller_idempotency_key=caller_idempotency_key,
                    trace_id=trace_id,
                )
            case _:
                raise ParentWorkflowError(
                    ParentWorkflowFailureKind.RETRY_LINEAGE_CONFLICT,
                    cause_code="retry_recovery_directive_not_supported",
                    trace_id=trace_id,
                    recovery=recovery,
                )

    def _continue_initial_from_recovery(
        self,
        recovery: CalibrationRecoverySnapshot,
        *,
        initial_commit_input: CalibrationCommitInputReceiptResult | None,
        caller_idempotency_key: str,
        trace_id: str,
        delivery_replayed: bool,
    ) -> CalibrationResponseEnvelope:
        if initial_commit_input is not None:
            accepted_ids = frozenset(initial_commit_input.input.accepted_operation_ids)
            if (
                recovery.latest_checkpoint.state is not CalibrationState.NEEDS_CONFIRMATION
                or recovery.directive is not RecoveryDirective.RETURN_STORED
                or recovery.pending_draft is None
                or initial_commit_input.input.calibration_id != recovery.calibration_id
                or initial_commit_input.input.expected_calibration_version
                != recovery.calibration_version
                or initial_commit_input.input.draft_id != recovery.pending_draft.id
                or initial_commit_input.input.draft_digest != recovery.pending_draft.draft_digest
                or initial_commit_input.input.accepted_operation_ids
                != tuple(
                    item.operation_id
                    for item in recovery.pending_draft.observations
                    if item.operation_id in accepted_ids
                )
                or self.repository.has_profile_commit_attempt_checkpoint(
                    recovery.calibration_id,
                    initial_commit_input.input.id,
                )
            ):
                raise ParentWorkflowError(
                    ParentWorkflowFailureKind.INVALID_TRANSITION,
                    cause_code="initial_commit_input_not_authorized",
                    trace_id=trace_id,
                    recovery=recovery,
                )
            hidden_key = derive_write_idempotency_key(
                caller_idempotency_key,
                WorkflowPhase.PROFILE_COMMIT,
                "commit_profile_patch",
            )
            exact_commit = self.repository.lookup_commit_profile_patch(
                recovery.calibration_id,
                initial_commit_input.input.draft_id,
                initial_commit_input.input.accepted_operation_ids,
                draft_digest=initial_commit_input.input.draft_digest,
                expected_calibration_version=recovery.calibration_version,
                context=_parent_context(trace_id, hidden_key),
            )
            if exact_commit is not None:
                fresh = self.repository.get_calibration_recovery(recovery.calibration_id)
                if fresh.last_outcome != exact_commit.outcome:
                    raise ParentWorkflowError(
                        ParentWorkflowFailureKind.INTERNAL_ERROR,
                        cause_code="exact_commit_outcome_not_current",
                        trace_id=trace_id,
                        recovery=None,
                    )
                return _present_recovery(
                    fresh,
                    delivery_replayed=True,
                    narration=None,
                    narration_status=NarrationStatus.NOT_REQUESTED,
                    request_trace_id=trace_id,
                )
            return self._infer_commit(
                recovery,
                TrustedProfileCommitCommand(
                    calibration_id=recovery.calibration_id,
                    expected_calibration_version=recovery.calibration_version,
                    draft_id=initial_commit_input.input.draft_id,
                    draft_digest=initial_commit_input.input.draft_digest,
                    accepted_operation_ids=(initial_commit_input.input.accepted_operation_ids),
                ),
                commit_input=initial_commit_input.input,
                hidden_key=hidden_key,
                caller_idempotency_key=caller_idempotency_key,
                trace_id=trace_id,
            )

        match recovery.directive:
            case RecoveryDirective.RETURN_STORED:
                return _present_recovery(
                    recovery,
                    delivery_replayed=delivery_replayed,
                    narration=None,
                    narration_status=NarrationStatus.NOT_REQUESTED,
                    request_trace_id=trace_id,
                )
            case RecoveryDirective.EXPLICIT_RETRY_ALLOWED:
                raise _stored_model_failure(recovery, trace_id)
            case RecoveryDirective.INITIAL_INFERENCE:
                if (
                    recovery.latest_checkpoint.state is not CalibrationState.INPUT_SAVED
                    or recovery.latest_checkpoint.resume_stage != "profile_propose"
                ):
                    raise ParentWorkflowError(
                        ParentWorkflowFailureKind.INVALID_TRANSITION,
                        cause_code="initial_request_cannot_resume_retry",
                        trace_id=trace_id,
                        recovery=recovery,
                    )
                return self._infer_proposal(
                    recovery,
                    caller_idempotency_key=caller_idempotency_key,
                    trace_id=trace_id,
                )
            case _:
                raise ParentWorkflowError(
                    ParentWorkflowFailureKind.INVALID_TRANSITION,
                    cause_code="initial_recovery_directive_not_supported",
                    trace_id=trace_id,
                    recovery=recovery,
                )

    def _validate_retry_begin_lineage(
        self,
        begin_result: DeliveredCalibrationResult,
        recovery: CalibrationRecoverySnapshot,
        *,
        trace_id: str,
    ) -> ValidatedRetryLineage:
        outcome = begin_result.outcome
        try:
            data = RetryBeginOutcomeData.model_validate(outcome.data)
        except ValidationError:
            raise _retry_lineage_error(recovery, trace_id) from None
        if (
            outcome.calibration_id != recovery.calibration_id
            or outcome.state is not CalibrationState.RETRY_PENDING
            or outcome.allowed_actions != workflow_allowed_actions(CalibrationState.RETRY_PENDING)
            or data.receipt_id != recovery.receipt.id
        ):
            raise _retry_lineage_error(recovery, trace_id)

        commit_input: CalibrationCommitInputReceipt | None = None
        if data.resume_stage == "profile_propose":
            if data.pending_entity_id != data.receipt_id:
                raise _retry_lineage_error(recovery, trace_id)
        else:
            try:
                commit_input = self.repository.get_profile_commit_input(
                    recovery.calibration_id,
                    data.pending_entity_id,
                )
            except (StudyPilotError, ValueError):
                raise _retry_lineage_error(recovery, trace_id) from None
            if (
                commit_input.calibration_id != recovery.calibration_id
                or commit_input.actor != "local-parent"
                or commit_input.role != "parent"
                or commit_input.expected_calibration_version >= outcome.calibration_version
            ):
                raise _retry_lineage_error(recovery, trace_id)
        return ValidatedRetryLineage(
            calibration_id=outcome.calibration_id,
            baseline_calibration_version=outcome.calibration_version,
            baseline_profile_version=outcome.profile_version,
            receipt_id=data.receipt_id,
            resume_stage=data.resume_stage,
            pending_entity_id=data.pending_entity_id,
            commit_input=commit_input,
            begin_outcome=outcome,
        )

    def _verify_retry_lineage_against_current(
        self,
        recovery: CalibrationRecoverySnapshot,
        lineage: ValidatedRetryLineage,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> CalibrationWorkflowResult | None:
        checkpoint = recovery.latest_checkpoint
        checkpoint_identity = (
            checkpoint.resume_stage == lineage.resume_stage
            and checkpoint.pending_kind is PendingKind.MODEL_RETRY
            and checkpoint.pending_entity_id == lineage.pending_entity_id
            and checkpoint.input_receipt_id == lineage.receipt_id
        )
        if recovery.latest_checkpoint.state is CalibrationState.RETRY_PENDING:
            if (
                recovery.calibration_version == lineage.baseline_calibration_version
                and recovery.profile_version == lineage.baseline_profile_version
                and checkpoint.calibration_version == lineage.baseline_calibration_version
                and checkpoint.profile_version == lineage.baseline_profile_version
                and checkpoint_identity
                and recovery.last_outcome == lineage.begin_outcome
            ):
                return None
            raise _retry_lineage_error(recovery, trace_id)

        if recovery.latest_checkpoint.state is CalibrationState.MODEL_UNAVAILABLE:
            if (
                recovery.calibration_version == lineage.baseline_calibration_version + 1
                and recovery.profile_version == lineage.baseline_profile_version
                and checkpoint.calibration_version == lineage.baseline_calibration_version + 1
                and checkpoint.profile_version == lineage.baseline_profile_version
                and checkpoint_identity
            ):
                return None
            raise _retry_lineage_error(recovery, trace_id)

        if lineage.resume_stage == "profile_propose":
            last_outcome = recovery.last_outcome
            valid = (
                recovery.latest_checkpoint.state is CalibrationState.NEEDS_CONFIRMATION
                and recovery.calibration_version == lineage.baseline_calibration_version + 1
                and recovery.profile_version == lineage.baseline_profile_version
                and recovery.pending_draft is not None
                and recovery.pending_draft.receipt_id == lineage.receipt_id
                and recovery.pending_draft_result is not None
                and recovery.pending_draft_result == last_outcome
                and last_outcome is not None
                and last_outcome.calibration_id == lineage.calibration_id
                and last_outcome.calibration_version == lineage.baseline_calibration_version + 1
                and last_outcome.profile_version == lineage.baseline_profile_version
                and last_outcome.state is CalibrationState.NEEDS_CONFIRMATION
            )
            if valid:
                return last_outcome
            raise _retry_lineage_error(recovery, trace_id)

        commit_input = lineage.commit_input
        if commit_input is None:
            raise _retry_lineage_error(recovery, trace_id)
        hidden_key = derive_write_idempotency_key(
            caller_idempotency_key,
            WorkflowPhase.PROFILE_COMMIT,
            "commit_profile_patch",
        )
        try:
            exact = self.repository.lookup_commit_profile_patch(
                lineage.calibration_id,
                commit_input.draft_id,
                commit_input.accepted_operation_ids,
                draft_digest=commit_input.draft_digest,
                expected_calibration_version=lineage.baseline_calibration_version,
                context=_parent_context(trace_id, hidden_key),
            )
        except (StudyPilotError, ValueError):
            raise _retry_lineage_error(recovery, trace_id) from None
        if (
            exact is None
            or recovery.latest_checkpoint.state is not CalibrationState.COMMITTED
            or recovery.calibration_version != lineage.baseline_calibration_version + 1
            or recovery.profile_version != lineage.baseline_profile_version + 1
            or recovery.last_outcome != exact.outcome
        ):
            raise _retry_lineage_error(recovery, trace_id)
        return exact.outcome

    def _lookup_exact_success_target(
        self,
        target: CalibrationWriteTarget,
        recovery: CalibrationRecoverySnapshot,
        *,
        terminal_success: ProfileToolSuccess | None,
    ) -> CalibrationRecoverySnapshot | None:
        if target.phase is WorkflowPhase.PROFILE_PROPOSE:
            if terminal_success is None:
                return None
            _verify_success_target(terminal_success, recovery, target)
            return recovery

        commit_input = target.commit_input
        hidden_key = target.hidden_tool_key
        if commit_input is None or hidden_key is None:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INTERNAL_ERROR,
                cause_code="commit_target_fields_missing",
                trace_id=target.request_trace_id,
                recovery=None,
            )
        stored_input = self.repository.get_profile_commit_input(
            target.calibration_id,
            target.receipt_id,
        )
        exact = self.repository.lookup_commit_profile_patch(
            target.calibration_id,
            commit_input.draft_id,
            commit_input.accepted_operation_ids,
            draft_digest=commit_input.draft_digest,
            expected_calibration_version=target.baseline_calibration_version,
            context=_parent_context(
                target.request_trace_id,
                hidden_key,
            ),
        )
        if exact is None:
            return None
        valid = (
            stored_input == commit_input
            and recovery.calibration_id == target.calibration_id
            and recovery.calibration_version == target.baseline_calibration_version + 1
            and recovery.profile_version == target.baseline_profile_version + 1
            and recovery.latest_checkpoint.state is CalibrationState.COMMITTED
            and recovery.pending_draft is None
            and recovery.pending_draft_result is None
            and recovery.last_outcome == exact.outcome
        )
        if terminal_success is not None:
            _verify_success_target(terminal_success, recovery, target)
            valid = valid and exact.outcome == terminal_success.outcome
        if not valid:
            return None
        return recovery

    def _persist_model_failure_or_read_exact_target(
        self,
        recovery: CalibrationRecoverySnapshot,
        *,
        target: CalibrationWriteTarget,
        error_code: str,
        resume_stage: Literal["profile_propose", "profile_commit"],
        caller_idempotency_key: str,
        trace_id: str,
        terminal_success: ProfileToolSuccess | None = None,
    ) -> CalibrationRecoverySnapshot:
        _require_failure_source(recovery, target, resume_stage, trace_id)
        try:
            delivered = self.repository.mark_calibration_model_unavailable(
                target.calibration_id,
                recovery.receipt.id,
                expected_calibration_version=recovery.calibration_version,
                error_code=error_code,
                resume_stage=resume_stage,
                pending_entity_id=(
                    target.commit_input.id if target.commit_input is not None else None
                ),
                context=_parent_context(
                    trace_id,
                    _derive_failure_idempotency_key(
                        caller_idempotency_key,
                        resume_stage,
                    ),
                ),
            )
        except (VersionConflictError, IdempotencyConflictError) as error:
            fresh = self.repository.get_calibration_recovery(target.calibration_id)
            exact = self._lookup_exact_success_target(
                target,
                fresh,
                terminal_success=terminal_success,
            )
            if exact is not None:
                return exact
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.VERSION_CONFLICT,
                cause_code="failure_source_conflict",
                trace_id=trace_id,
                recovery=fresh,
            ) from error
        except NotFoundError as error:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.NOT_FOUND,
                cause_code="not_found",
                trace_id=trace_id,
                recovery=None,
            ) from error
        except InvalidTransitionError as error:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INVALID_TRANSITION,
                cause_code="invalid_transition",
                trace_id=trace_id,
                recovery=None,
            ) from error
        except ValueError as error:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INTERNAL_ERROR,
                cause_code="failure_persistence_integrity_error",
                trace_id=trace_id,
                recovery=None,
            ) from error

        fresh = self.repository.get_calibration_recovery(target.calibration_id)
        if fresh.last_outcome != delivered.outcome:
            exact = self._lookup_exact_success_target(
                target,
                fresh,
                terminal_success=terminal_success,
            )
            if exact is not None:
                return exact
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.VERSION_CONFLICT,
                cause_code="failure_source_conflict",
                trace_id=trace_id,
                recovery=fresh,
            )
        return fresh

    def _infer_proposal(
        self,
        recovery: CalibrationRecoverySnapshot,
        *,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> CalibrationResponseEnvelope:
        profile_snapshot = self.repository.get_profile_snapshot(recovery.profile_version)
        execution = build_profile_propose_execution(
            repository=self.repository,
            recovery=recovery,
            profile_snapshot=profile_snapshot,
            client=self.client,
            trace_repository=self.trace_repository,
            caller_idempotency_key=caller_idempotency_key,
            trace_id=trace_id,
        )
        return self._run_and_reconcile(
            execution,
            calibration_id=recovery.calibration_id,
            caller_idempotency_key=caller_idempotency_key,
            resume_stage="profile_propose",
            target=CalibrationWriteTarget.for_proposal(recovery, trace_id),
        )

    def _infer_commit(
        self,
        recovery: CalibrationRecoverySnapshot,
        command: TrustedProfileCommitCommand,
        *,
        commit_input: CalibrationCommitInputReceipt,
        hidden_key: str,
        caller_idempotency_key: str,
        trace_id: str,
    ) -> CalibrationResponseEnvelope:
        del caller_idempotency_key
        if (
            command.calibration_id != recovery.calibration_id
            or command.expected_calibration_version != recovery.calibration_version
            or command.draft_id != commit_input.draft_id
            or command.draft_digest != commit_input.draft_digest
            or command.accepted_operation_ids != commit_input.accepted_operation_ids
        ):
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.COMMIT_COMMAND_INVALID,
                cause_code="commit_command_invalid",
                trace_id=trace_id,
                recovery=recovery,
            )
        try:
            delivered = self.repository.commit_profile_patch(
                command.calibration_id,
                command.draft_id,
                command.accepted_operation_ids,
                draft_digest=command.draft_digest,
                expected_calibration_version=command.expected_calibration_version,
                context=_parent_context(trace_id, hidden_key),
            )
        except DraftDigestMismatchError as error:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.DRAFT_DIGEST_MISMATCH,
                cause_code="draft_digest_mismatch",
                trace_id=trace_id,
                recovery=None,
            ) from error
        except CommitCommandInvalidError as error:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.COMMIT_COMMAND_INVALID,
                cause_code="commit_command_invalid",
                trace_id=trace_id,
                recovery=None,
            ) from error
        fresh = self.repository.get_calibration_recovery(command.calibration_id)
        if fresh.last_outcome != delivered.outcome:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INTERNAL_ERROR,
                cause_code="committed_outcome_not_current",
                trace_id=trace_id,
                recovery=None,
            )
        return _present_recovery(
            fresh,
            delivery_replayed=delivered.delivery.replayed,
            narration=None,
            narration_status=NarrationStatus.NOT_REQUESTED,
            request_trace_id=trace_id,
        )

    def _run_and_reconcile(
        self,
        execution: CalibrationHarnessExecution,
        *,
        calibration_id: str,
        caller_idempotency_key: str,
        resume_stage: Literal["profile_propose", "profile_commit"],
        target: CalibrationWriteTarget,
    ) -> CalibrationResponseEnvelope:
        if (
            calibration_id != target.calibration_id
            or execution.request.session_id != target.calibration_id
            or execution.request.idempotency_key != caller_idempotency_key
            or execution.request.workflow_phase is not target.phase
            or resume_stage != target.phase.value
        ):
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INTERNAL_ERROR,
                cause_code="execution_target_mismatch",
                trace_id=execution.request.trace_id,
                recovery=None,
            )
        try:
            harness_result = execution.harness.run(execution.request)
        except HarnessError as error:
            recovery = self.repository.get_calibration_recovery(calibration_id)
            successful = execution.invocation.successful_business_result
            if successful is not None:
                exact_success = self._lookup_exact_success_target(
                    target,
                    recovery,
                    terminal_success=successful,
                )
                if exact_success is None:
                    raise ParentWorkflowError(
                        ParentWorkflowFailureKind.INTERNAL_ERROR,
                        cause_code="successful_write_target_mismatch",
                        trace_id=error.trace_id,
                        recovery=None,
                    ) from error
                return _present_recovery(
                    exact_success,
                    delivery_replayed=successful.delivery.replayed,
                    narration=None,
                    narration_status=NarrationStatus.UNAVAILABLE,
                    request_trace_id=error.trace_id,
                )

            exact_success = self._lookup_exact_success_target(
                target,
                recovery,
                terminal_success=None,
            )
            if exact_success is not None:
                return _present_recovery(
                    exact_success,
                    delivery_replayed=True,
                    narration=None,
                    narration_status=NarrationStatus.UNAVAILABLE,
                    request_trace_id=error.trace_id,
                )

            if execution.invocation.unexpected_handler_failure:
                raise ParentWorkflowError(
                    ParentWorkflowFailureKind.INTERNAL_ERROR,
                    cause_code="tool_handler_failed",
                    trace_id=error.trace_id,
                    recovery=None,
                ) from error

            terminal = execution.invocation.terminal_result
            if isinstance(terminal, ProfileToolFailure):
                if terminal.error.code in {
                    ProfileToolFailureCode.PROPOSAL_INVALID,
                    ProfileToolFailureCode.MODEL_CONFIRMATION_MISMATCH,
                }:
                    failed = self._persist_model_failure_or_read_exact_target(
                        recovery,
                        target=target,
                        error_code=terminal.error.code.value,
                        resume_stage=resume_stage,
                        caller_idempotency_key=caller_idempotency_key,
                        trace_id=error.trace_id,
                    )
                    if failed.latest_checkpoint.state in {
                        CalibrationState.NEEDS_CONFIRMATION,
                        CalibrationState.COMMITTED,
                    }:
                        return _present_recovery(
                            failed,
                            delivery_replayed=True,
                            narration=None,
                            narration_status=NarrationStatus.UNAVAILABLE,
                            request_trace_id=error.trace_id,
                        )
                    raise _workflow_error_from_tool_failure(
                        terminal,
                        error.trace_id,
                        recovery=failed,
                    )
                raise _workflow_error_from_tool_failure(
                    terminal,
                    error.trace_id,
                    recovery=None,
                )

            if error.code in POST_WRITE_ONLY_CODES:
                raise ParentWorkflowError(
                    ParentWorkflowFailureKind.INTERNAL_ERROR,
                    cause_code="post_write_code_without_verified_write",
                    trace_id=error.trace_id,
                    recovery=None,
                ) from error

            failure_kind = _classify_harness_code(error.code)
            if failure_kind is ParentWorkflowFailureKind.INTERNAL_ERROR:
                raise ParentWorkflowError(
                    failure_kind,
                    cause_code=error.code,
                    trace_id=error.trace_id,
                    recovery=None,
                ) from error
            failed = self._persist_model_failure_or_read_exact_target(
                recovery,
                target=target,
                error_code=error.code,
                resume_stage=resume_stage,
                caller_idempotency_key=caller_idempotency_key,
                trace_id=error.trace_id,
            )
            if failed.latest_checkpoint.state in {
                CalibrationState.NEEDS_CONFIRMATION,
                CalibrationState.COMMITTED,
            }:
                return _present_recovery(
                    failed,
                    delivery_replayed=True,
                    narration=None,
                    narration_status=NarrationStatus.UNAVAILABLE,
                    request_trace_id=error.trace_id,
                )
            raise _workflow_error_from_harness(error, failed)

        successful = execution.invocation.successful_business_result
        terminal = execution.invocation.terminal_result
        if successful is not None:
            fresh = self.repository.get_calibration_recovery(target.calibration_id)
            exact_success = self._lookup_exact_success_target(
                target,
                fresh,
                terminal_success=successful,
            )
            if exact_success is None:
                raise ParentWorkflowError(
                    ParentWorkflowFailureKind.INTERNAL_ERROR,
                    cause_code="successful_write_target_mismatch",
                    trace_id=execution.request.trace_id,
                    recovery=None,
                )
            if terminal == successful:
                narration = (
                    harness_result.final_content
                    if harness_result.final_content.strip()
                    else None
                )
                return _present_recovery(
                    exact_success,
                    delivery_replayed=successful.delivery.replayed,
                    narration=narration,
                    narration_status=(
                        NarrationStatus.AVAILABLE
                        if narration is not None
                        else NarrationStatus.NOT_REQUESTED
                    ),
                    request_trace_id=execution.request.trace_id,
                )
            return _present_recovery(
                exact_success,
                delivery_replayed=successful.delivery.replayed,
                narration=None,
                narration_status=NarrationStatus.UNAVAILABLE,
                request_trace_id=execution.request.trace_id,
            )

        if isinstance(terminal, ProfileToolFailure):
            if terminal.error.code in {
                ProfileToolFailureCode.PROPOSAL_INVALID,
                ProfileToolFailureCode.MODEL_CONFIRMATION_MISMATCH,
            }:
                failed = self._persist_model_failure_or_read_exact_target(
                    self.repository.get_calibration_recovery(calibration_id),
                    target=target,
                    error_code=terminal.error.code.value,
                    resume_stage=resume_stage,
                    caller_idempotency_key=caller_idempotency_key,
                    trace_id=execution.request.trace_id,
                )
                if failed.latest_checkpoint.state in {
                    CalibrationState.NEEDS_CONFIRMATION,
                    CalibrationState.COMMITTED,
                }:
                    return _present_recovery(
                        failed,
                        delivery_replayed=True,
                        narration=None,
                        narration_status=NarrationStatus.UNAVAILABLE,
                        request_trace_id=execution.request.trace_id,
                    )
                raise _workflow_error_from_tool_failure(
                    terminal,
                    execution.request.trace_id,
                    recovery=failed,
                )
            raise _workflow_error_from_tool_failure(
                terminal,
                execution.request.trace_id,
                recovery=None,
            )
        raise ParentWorkflowError(
            ParentWorkflowFailureKind.INTERNAL_ERROR,
            cause_code="missing_successful_business_result",
            trace_id=execution.request.trace_id,
            recovery=None,
        )

    def _verify_exact_commit_target(
        self,
        terminal: ProfileToolSuccess,
        recovery: CalibrationRecoverySnapshot,
        target: CalibrationWriteTarget,
    ) -> None:
        if target.commit_input is None or target.hidden_tool_key is None:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INTERNAL_ERROR,
                cause_code="commit_target_fields_missing",
                trace_id=target.request_trace_id,
                recovery=None,
            )
        stored_input = self.repository.get_profile_commit_input(
            target.calibration_id,
            target.receipt_id,
        )
        exact = self.repository.lookup_commit_profile_patch(
            target.calibration_id,
            target.commit_input.draft_id,
            target.commit_input.accepted_operation_ids,
            draft_digest=target.commit_input.draft_digest,
            expected_calibration_version=target.baseline_calibration_version,
            context=_parent_context(
                target.request_trace_id,
                target.hidden_tool_key,
            ),
        )
        if (
            stored_input != target.commit_input
            or exact is None
            or exact.outcome != terminal.outcome
            or recovery.last_outcome != exact.outcome
        ):
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INTERNAL_ERROR,
                cause_code="exact_commit_target_mismatch",
                trace_id=target.request_trace_id,
                recovery=None,
            )


def _present_recovery(
    recovery: CalibrationRecoverySnapshot,
    *,
    delivery_replayed: bool,
    narration: str | None,
    narration_status: NarrationStatus,
    request_trace_id: str,
) -> CalibrationResponseEnvelope:
    stage = recovery.latest_checkpoint.state
    if stage is CalibrationState.NEEDS_CONFIRMATION:
        if recovery.pending_draft is None:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INTERNAL_ERROR,
                cause_code="proposal_draft_missing",
                trace_id=request_trace_id,
                recovery=None,
            )
        data = ProfilePatchProposalData(
            draft=recovery.pending_draft,
            diff_preview=recovery.pending_draft.observations,
            narration=narration,
            narration_status=narration_status,
            unapplied_notes=_proposal_unapplied_notes(recovery),
            calibration_details=_proposal_calibration_details(recovery),
        )
    elif stage is CalibrationState.COMMITTED:
        outcome = recovery.last_outcome
        if outcome is None:
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INTERNAL_ERROR,
                cause_code="commit_outcome_missing",
                trace_id=request_trace_id,
                recovery=None,
            )
        try:
            if set(outcome.data) != {
                "accepted_observations",
                "commit",
                "draft_digest",
            }:
                raise ValueError("stored commit fields are not exact")
            raw_commit = outcome.data["commit"]
            raw_accepted = outcome.data["accepted_observations"]
            if not isinstance(raw_commit, dict) or not isinstance(raw_accepted, list):
                raise TypeError("stored commit structures have invalid types")
            commit = ProfileCommit.model_validate_json(
                json.dumps(raw_commit, separators=(",", ":"), sort_keys=True)
            )
            operation_ids: list[str] = []
            observations: list[MemoryObservation] = []
            for item in raw_accepted:
                if not isinstance(item, dict) or type(item.get("operation_id")) is not str:
                    raise TypeError("stored accepted observation is invalid")
                operation_ids.append(item["operation_id"])
                observation_data = {
                    key: value for key, value in item.items() if key != "operation_id"
                }
                observations.append(
                    MemoryObservation.model_validate_json(
                        json.dumps(
                            observation_data,
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                    )
                )
            if tuple(operation_ids) != commit.accepted_operation_ids:
                raise ValueError("stored accepted operations do not match commit")
            draft_digest = outcome.data["draft_digest"]
            if type(draft_digest) is not str:
                raise TypeError("stored draft digest is invalid")
            data = ProfilePatchCommitData(
                commit=commit,
                draft_digest=draft_digest,
                accepted_operation_ids=commit.accepted_operation_ids,
                observation_event_ids=tuple(item.id for item in observations),
                narration=narration,
                narration_status=narration_status,
            )
        except (KeyError, TypeError, ValueError):
            raise ParentWorkflowError(
                ParentWorkflowFailureKind.INTERNAL_ERROR,
                cause_code="stored_commit_outcome_invalid",
                trace_id=request_trace_id,
                recovery=None,
            ) from None
    elif stage in {
        CalibrationState.INPUT_SAVED,
        CalibrationState.MODEL_UNAVAILABLE,
        CalibrationState.RETRY_PENDING,
        CalibrationState.ABANDONED,
    }:
        checkpoint = recovery.latest_checkpoint
        data = CalibrationRecoveryData(
            input_receipt_id=recovery.receipt.id,
            resume_stage=checkpoint.resume_stage,
            pending_kind=checkpoint.pending_kind,
            pending_entity_id=checkpoint.pending_entity_id,
            failure_code=_project_failure_code(recovery),
        )
    else:
        raise ParentWorkflowError(
            ParentWorkflowFailureKind.INTERNAL_ERROR,
            cause_code="stored_presentation_state_unsupported",
            trace_id=request_trace_id,
            recovery=None,
        )
    return CalibrationResponseEnvelope(
        calibration_id=recovery.calibration_id,
        calibration_version=recovery.calibration_version,
        profile_version=recovery.profile_version,
        stage=stage,
        allowed_actions=tuple(
            CalibrationAction(action) for action in workflow_allowed_actions(stage)
        ),
        trace_id=request_trace_id,
        data=data,
        delivery=DeliveryMetadata(replayed=delivery_replayed),
    )


def _proposal_unapplied_notes(
    recovery: CalibrationRecoverySnapshot,
) -> tuple[str, ...]:
    result = recovery.pending_draft_result
    if result is None:
        return ()
    raw = result.data.get("unapplied_notes", [])
    if not isinstance(raw, list) or not all(type(item) is str for item in raw):
        return ()
    return tuple(raw)


def _proposal_calibration_details(
    recovery: CalibrationRecoverySnapshot,
) -> tuple[CalibrationEvidenceDetail, ...]:
    result = recovery.pending_draft_result
    if result is None:
        return ()
    raw = result.data.get("calibration_details", [])
    if not isinstance(raw, list):
        return ()
    try:
        return tuple(
            CalibrationEvidenceDetail.model_validate_json(
                json.dumps(item, separators=(",", ":"), sort_keys=True)
            )
            for item in raw
        )
    except (TypeError, ValidationError):
        return ()


def _project_failure_code(recovery: CalibrationRecoverySnapshot) -> str | None:
    checkpoint = recovery.latest_checkpoint
    outcome = recovery.last_outcome
    if (
        checkpoint.state is not CalibrationState.MODEL_UNAVAILABLE
        or outcome is None
        or outcome.calibration_version != checkpoint.calibration_version
        or outcome.state is not CalibrationState.MODEL_UNAVAILABLE
    ):
        return None
    value = outcome.data.get("error_code")
    return value if type(value) is str and value else None


def _verify_success_target(
    terminal: ProfileToolSuccess,
    recovery: CalibrationRecoverySnapshot,
    target: CalibrationWriteTarget,
) -> None:
    common = (
        recovery.calibration_id == target.calibration_id
        and recovery.calibration_version == target.baseline_calibration_version + 1
        and recovery.last_outcome == terminal.outcome
    )
    if target.phase is WorkflowPhase.PROFILE_PROPOSE:
        valid = (
            common
            and terminal.operation == "profile_patch_proposed"
            and recovery.profile_version == target.baseline_profile_version
            and recovery.latest_checkpoint.state is CalibrationState.NEEDS_CONFIRMATION
            and recovery.pending_draft is not None
            and recovery.pending_draft.receipt_id == target.receipt_id
            and recovery.pending_draft_result == terminal.outcome
        )
    elif target.phase is WorkflowPhase.PROFILE_COMMIT:
        valid = (
            common
            and terminal.operation == "profile_patch_committed"
            and recovery.profile_version == target.baseline_profile_version + 1
            and recovery.latest_checkpoint.state is CalibrationState.COMMITTED
            and recovery.pending_draft is None
            and recovery.pending_draft_result is None
        )
    else:
        valid = False
    if valid and not terminal.delivery.replayed:
        valid = terminal.outcome.trace_id == target.request_trace_id
    if not valid:
        raise ParentWorkflowError(
            ParentWorkflowFailureKind.INTERNAL_ERROR,
            cause_code="successful_write_target_mismatch",
            trace_id=target.request_trace_id,
            recovery=None,
        )
