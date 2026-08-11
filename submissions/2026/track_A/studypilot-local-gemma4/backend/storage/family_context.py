"""Atomic persistence for calibrated family context and confirmed Memory."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from backend.contracts.calibration_tools import CalibrationEvidenceDetail
from backend.contracts.family import (
    CalibrationCheckpoint,
    CalibrationCommitInputReceipt,
    CalibrationCommitInputReceiptResult,
    CalibrationInputReceiptResult,
    CalibrationRecoverySnapshot,
    CalibrationState,
    CalibrationSummary,
    CalibrationTurnReceipt,
    CalibrationWorkflowResult,
    DeliveredCalibrationResult,
    DeliveryMetadata,
    FamilyWriteContext,
    MemoryCategory,
    MemoryObservation,
    ObservationEvidenceLevel,
    PendingKind,
    ProfileCommit,
    ProfilePatchAction,
    ProfilePatchDraft,
    ProfileSnapshot,
    ProfileVersion,
    ProposedObservation,
    ProposedObservationInput,
    RecoveryDirective,
    DeliveredSchoolBriefResult,
    SchoolBriefRevision,
    SchoolBriefWriteResult,
    normalize_family_text,
)
from backend.contracts.models import Source
from backend.domain.workflow import allowed_actions, validate_calibration_transition
from backend.errors import (
    CommitCommandInvalidError,
    DraftDigestMismatchError,
    IdempotencyConflictError,
    InvalidTransitionError,
    NotFoundError,
    ProfileProposalInvalidError,
    VersionConflictError,
)
from backend.storage.database import connect_database
from backend.services.memory import project_profile


JsonObject = dict[str, Any]
_SAVE_CALIBRATION_INPUT = "save_calibration_input"
_MARK_CALIBRATION_MODEL_UNAVAILABLE = "mark_calibration_model_unavailable"
_BEGIN_CALIBRATION_RETRY = "begin_calibration_retry"
_PROPOSE_PROFILE_PATCH = "propose_profile_patch"
_REVISE_PROFILE_PATCH = "revise_profile_patch"
_ABANDON_PROFILE_PATCH = "abandon_profile_patch"
_COMMIT_PROFILE_PATCH = "commit_profile_patch"
_SAVE_PROFILE_COMMIT_INPUT = "save_profile_commit_input"
_APPEND_SCHOOL_BRIEF = "append_school_brief"
_REDACTED_IDEMPOTENCY_KEY = "<redacted>"


@dataclass(frozen=True, slots=True)
class _CanonicalProposals:
    observations: tuple[ProposedObservation, ...]
    proposal_digest: str
    draft_digest: str


@dataclass(frozen=True, slots=True)
class _ConfirmedOperation:
    operation_id: str
    observation: MemoryObservation


@dataclass(frozen=True, slots=True)
class _CommitCommand:
    calibration_id: str
    draft_id: str
    draft_digest: str
    accepted_operation_ids: tuple[str, ...]
    expected_calibration_version: int
    actor: str
    role: str


@dataclass(frozen=True, slots=True)
class _StoredCommit:
    command: _CommitCommand
    outcome: CalibrationWorkflowResult


class _ProfileProposalValidationError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


class _CommitAcceptanceCanonicalizationError(ValueError):
    """Base for deterministic parent acceptance-shape failures."""


class _CommitAcceptanceEmptyError(_CommitAcceptanceCanonicalizationError):
    pass


class _CommitAcceptanceDuplicateError(_CommitAcceptanceCanonicalizationError):
    pass


class _CommitAcceptanceNotInDraftError(_CommitAcceptanceCanonicalizationError):
    pass


class FamilyContextRepository:
    """Own short SQLite units of work for family context aggregates."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()

    @contextmanager
    def _read_snapshot(self) -> Iterator[sqlite3.Connection]:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN")
            yield connection
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def save_calibration_input(
        self,
        calibration_id: str,
        text: str,
        *,
        expected_calibration_version: int,
        expected_profile_version: int,
        context: FamilyWriteContext,
    ) -> CalibrationInputReceiptResult:
        """Persist raw local evidence before any model inference is attempted."""
        if not calibration_id:
            raise ValueError("calibration_id must be non-empty")
        if expected_calibration_version < 0 or expected_profile_version < 0:
            raise ValueError("expected versions must be non-negative")

        key_hash = _sha256_text(context.idempotency_key)
        request_hash = _canonical_hash(
            {
                "actor": context.actor,
                "role": context.role,
                "calibration_id": calibration_id,
                "expected_calibration_version": expected_calibration_version,
                "expected_profile_version": expected_profile_version,
                "text": text,
            }
        )
        with self._transaction() as connection:
            replay = connection.execute(
                """
                SELECT *
                FROM calibration_turn_receipts
                WHERE operation = ? AND key_hash = ?
                """,
                (_SAVE_CALIBRATION_INPUT, key_hash),
            ).fetchone()
            if replay is not None:
                _verify_request_hash(
                    replay,
                    operation=_SAVE_CALIBRATION_INPUT,
                    request_hash=request_hash,
                )
                return CalibrationInputReceiptResult(
                    receipt=_receipt_from_row(replay),
                    replayed=True,
                )

            profile_version = _current_profile_version(connection)
            if profile_version != expected_profile_version:
                raise VersionConflictError(
                    "profile",
                    "singleton",
                    expected_profile_version,
                    profile_version,
                )

            current_session = connection.execute(
                "SELECT calibration_version FROM calibration_sessions WHERE id = ?",
                (calibration_id,),
            ).fetchone()
            actual_calibration_version = (
                int(current_session["calibration_version"]) if current_session is not None else 0
            )
            if actual_calibration_version != expected_calibration_version:
                raise VersionConflictError(
                    "calibration",
                    calibration_id,
                    expected_calibration_version,
                    actual_calibration_version,
                )
            if current_session is not None:
                raise ValueError("a calibration aggregate accepts one input receipt")

            now = datetime.now(UTC)
            receipt = CalibrationTurnReceipt(
                id=_new_id("receipt"),
                calibration_id=calibration_id,
                actor=context.actor,
                role=context.role,
                content_sha256=_sha256_text(text),
                raw_text=text,
                created_at=now,
            )
            connection.execute(
                """
                INSERT INTO calibration_sessions (
                    id, calibration_version, state, base_profile_version,
                    profile_version, input_receipt_id, pending_kind,
                    pending_entity_id, created_at, updated_at
                ) VALUES (?, 1, ?, ?, ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    calibration_id,
                    CalibrationState.INPUT_SAVED.value,
                    profile_version,
                    profile_version,
                    receipt.id,
                    _iso(now),
                    _iso(now),
                ),
            )
            connection.execute(
                """
                INSERT INTO calibration_turn_receipts (
                    id, calibration_id, operation, key_hash, request_hash,
                    actor, role, content_sha256, raw_text,
                    base_profile_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.id,
                    calibration_id,
                    _SAVE_CALIBRATION_INPUT,
                    key_hash,
                    request_hash,
                    receipt.actor,
                    receipt.role,
                    receipt.content_sha256,
                    receipt.raw_text,
                    profile_version,
                    _iso(now),
                ),
            )
            checkpoint = CalibrationCheckpoint(
                calibration_id=calibration_id,
                calibration_version=1,
                profile_version=profile_version,
                state=CalibrationState.INPUT_SAVED,
                resume_stage="profile_propose",
                pending_kind=None,
                pending_entity_id=None,
                last_stable_calibration_version=1,
                last_stable_profile_version=profile_version,
                input_receipt_id=receipt.id,
                trace_id=context.trace_id,
                occurred_at=now,
            )
            _insert_checkpoint(connection, checkpoint, outcome=None)
            return CalibrationInputReceiptResult(receipt=receipt, replayed=False)

    def get_calibration_recovery(
        self,
        calibration_id: str,
    ) -> CalibrationRecoverySnapshot:
        """Rebuild deterministic recovery state from one coherent DB snapshot."""
        with self._read_snapshot() as connection:
            session = connection.execute(
                "SELECT * FROM calibration_sessions WHERE id = ?",
                (calibration_id,),
            ).fetchone()
            if session is None:
                raise NotFoundError("calibration", calibration_id)

            receipt_id = session["input_receipt_id"]
            receipt_row = connection.execute(
                "SELECT * FROM calibration_turn_receipts WHERE id = ?",
                (receipt_id,),
            ).fetchone()
            if receipt_row is None:
                raise NotFoundError("calibration receipt", str(receipt_id))
            checkpoint_row = connection.execute(
                """
                SELECT *
                FROM calibration_checkpoints
                WHERE calibration_id = ?
                ORDER BY calibration_version DESC
                LIMIT 1
                """,
                (calibration_id,),
            ).fetchone()
            if checkpoint_row is None:
                raise NotFoundError("calibration checkpoint", calibration_id)

            latest_outcome_row = connection.execute(
                """
                SELECT outcome_json
                FROM calibration_checkpoints
                WHERE calibration_id = ? AND outcome_json IS NOT NULL
                ORDER BY calibration_version DESC
                LIMIT 1
                """,
                (calibration_id,),
            ).fetchone()
            last_outcome = (
                _workflow_result_from_json(str(latest_outcome_row["outcome_json"]))
                if latest_outcome_row is not None
                else None
            )
            state = CalibrationState(str(session["state"]))
            directive = _recovery_directive(state)
            pending_draft: ProfilePatchDraft | None = None
            pending_draft_result: CalibrationWorkflowResult | None = None
            pending_commit_input: CalibrationCommitInputReceipt | None = None
            if (
                session["pending_kind"] == PendingKind.PROFILE_PATCH.value
                and session["pending_entity_id"] is not None
            ):
                draft_row = connection.execute(
                    "SELECT * FROM calibration_drafts WHERE id = ?",
                    (str(session["pending_entity_id"]),),
                ).fetchone()
                if draft_row is None:
                    raise NotFoundError(
                        "calibration draft",
                        str(session["pending_entity_id"]),
                    )
                if str(draft_row["calibration_id"]) != calibration_id:
                    raise ValueError("pending draft belongs to another calibration")
                pending_draft = _draft_from_row(draft_row)
                pending_draft_result = _workflow_result_from_json(str(draft_row["result_json"]))
            if (
                str(checkpoint_row["state"])
                in {
                    CalibrationState.MODEL_UNAVAILABLE.value,
                    CalibrationState.RETRY_PENDING.value,
                }
                and checkpoint_row["resume_stage"] == "profile_commit"
                and checkpoint_row["pending_kind"] == PendingKind.MODEL_RETRY.value
                and checkpoint_row["pending_entity_id"] is not None
            ):
                pending_commit_input = _load_profile_commit_input_audit(
                    connection,
                    calibration_id=calibration_id,
                    input_id=str(checkpoint_row["pending_entity_id"]),
                )
                _verify_commit_input_draft_canonicality(
                    connection,
                    pending_commit_input,
                )
                draft_row = _require_draft(
                    connection,
                    calibration_id=calibration_id,
                    draft_id=pending_commit_input.draft_id,
                )
                pending_draft = _draft_from_row(draft_row)
                pending_draft_result = _workflow_result_from_json(str(draft_row["result_json"]))

            return CalibrationRecoverySnapshot(
                calibration_id=calibration_id,
                calibration_version=int(session["calibration_version"]),
                profile_version=int(session["profile_version"]),
                receipt=_receipt_from_row(receipt_row),
                latest_checkpoint=_checkpoint_from_row(checkpoint_row),
                pending_draft=pending_draft,
                pending_draft_result=pending_draft_result,
                pending_commit_input=pending_commit_input,
                last_outcome=last_outcome,
                directive=directive,
            )

    def propose_profile_patch(
        self,
        calibration_id: str,
        receipt_id: str,
        observations: tuple[ProposedObservationInput, ...],
        *,
        expected_calibration_version: int,
        context: FamilyWriteContext,
        unapplied_notes: tuple[str, ...] = (),
        calibration_details: tuple[CalibrationEvidenceDetail, ...] = (),
    ) -> DeliveredCalibrationResult:
        """Store an immutable proposal without changing confirmed profile Memory."""
        _require_non_empty("calibration_id", calibration_id)
        _require_non_empty("receipt_id", receipt_id)
        try:
            canonical = _canonicalize_proposals(observations)
        except _ProfileProposalValidationError as error:
            raise ProfileProposalInvalidError(error.reason_code) from None
        if expected_calibration_version < 0:
            raise ValueError("expected_calibration_version must be non-negative")
        key_hash = _sha256_text(context.idempotency_key)
        request_hash = _profile_patch_request_hash(
            actor=context.actor,
            role=context.role,
            calibration_id=calibration_id,
            receipt_id=receipt_id,
            expected_calibration_version=expected_calibration_version,
            proposal_digest=canonical.proposal_digest,
            revises_draft_id=None,
            unapplied_notes=unapplied_notes,
            calibration_details=calibration_details,
        )

        with self._transaction() as connection:
            replay = _lookup_calibration_outcome(
                connection,
                operation=_PROPOSE_PROFILE_PATCH,
                key_hash=key_hash,
                request_hash=request_hash,
            )
            if replay is not None:
                return replay
            session = _require_session(connection, calibration_id)
            _verify_calibration_version(
                session,
                calibration_id=calibration_id,
                expected_version=expected_calibration_version,
            )
            current_state = CalibrationState(str(session["state"]))
            if current_state not in {
                CalibrationState.INPUT_SAVED,
                CalibrationState.MODEL_UNAVAILABLE,
                CalibrationState.RETRY_PENDING,
            }:
                raise InvalidTransitionError(
                    current_state.value,
                    CalibrationState.NEEDS_CONFIRMATION.value,
                )
            validate_calibration_transition(current_state, CalibrationState.NEEDS_CONFIRMATION)
            if str(session["input_receipt_id"]) != receipt_id:
                raise ValueError("receipt is not current for calibration")
            receipt_row = _require_calibration_receipt(
                connection,
                calibration_id=calibration_id,
                receipt_id=receipt_id,
            )
            profile_version = _verify_receipt_profile_is_current(connection, receipt_row)
            try:
                _validate_proposed_targets(
                    connection,
                    canonical.observations,
                    profile_version=profile_version,
                )
                draft, outcome, checkpoint = _prepare_draft_transition(
                    calibration_id=calibration_id,
                    receipt_id=receipt_id,
                    base_profile_version=profile_version,
                    canonical=canonical,
                    revises_draft_id=None,
                    new_calibration_version=expected_calibration_version + 1,
                    context=context,
                    unapplied_notes=unapplied_notes,
                    calibration_details=calibration_details,
                )
            except _ProfileProposalValidationError as error:
                raise ProfileProposalInvalidError(error.reason_code) from None
            _write_draft_transition(
                connection,
                session=session,
                draft=draft,
                outcome=outcome,
                checkpoint=checkpoint,
                context=context,
                operation=_PROPOSE_PROFILE_PATCH,
                key_hash=key_hash,
                request_hash=request_hash,
                event_type="profile_patch_proposed",
            )
            return DeliveredCalibrationResult(
                outcome=outcome,
                delivery=DeliveryMetadata(replayed=False),
            )

    def revise_profile_patch(
        self,
        calibration_id: str,
        draft_id: str,
        revised_observations: tuple[ProposedObservationInput, ...],
        *,
        expected_calibration_version: int,
        context: FamilyWriteContext,
    ) -> DeliveredCalibrationResult:
        """Append a revised immutable draft and replace only the pending pointer."""
        _require_non_empty("calibration_id", calibration_id)
        _require_non_empty("draft_id", draft_id)
        try:
            canonical = _canonicalize_proposals(revised_observations)
        except _ProfileProposalValidationError as error:
            raise ProfileProposalInvalidError(error.reason_code) from None
        if expected_calibration_version < 0:
            raise ValueError("expected_calibration_version must be non-negative")
        key_hash = _sha256_text(context.idempotency_key)
        request_hash = _profile_patch_request_hash(
            actor=context.actor,
            role=context.role,
            calibration_id=calibration_id,
            receipt_id=None,
            expected_calibration_version=expected_calibration_version,
            proposal_digest=canonical.proposal_digest,
            revises_draft_id=draft_id,
        )

        with self._transaction() as connection:
            replay = _lookup_calibration_outcome(
                connection,
                operation=_REVISE_PROFILE_PATCH,
                key_hash=key_hash,
                request_hash=request_hash,
            )
            if replay is not None:
                return replay
            session = _require_session(connection, calibration_id)
            _verify_calibration_version(
                session,
                calibration_id=calibration_id,
                expected_version=expected_calibration_version,
            )
            current_state = CalibrationState(str(session["state"]))
            validate_calibration_transition(current_state, CalibrationState.NEEDS_CONFIRMATION)
            _verify_current_pending_draft(
                connection,
                session=session,
                calibration_id=calibration_id,
                draft_id=draft_id,
                requested_stage=_REVISE_PROFILE_PATCH,
            )
            old_draft_row = _require_draft(
                connection,
                calibration_id=calibration_id,
                draft_id=draft_id,
            )
            receipt_id = str(old_draft_row["receipt_id"])
            receipt_row = _require_calibration_receipt(
                connection,
                calibration_id=calibration_id,
                receipt_id=receipt_id,
            )
            profile_version = _verify_receipt_profile_is_current(connection, receipt_row)
            if int(old_draft_row["base_profile_version"]) != profile_version:
                raise VersionConflictError(
                    "profile",
                    "singleton",
                    int(old_draft_row["base_profile_version"]),
                    profile_version,
                )
            try:
                _validate_proposed_targets(
                    connection,
                    canonical.observations,
                    profile_version=profile_version,
                )
                draft, outcome, checkpoint = _prepare_draft_transition(
                    calibration_id=calibration_id,
                    receipt_id=receipt_id,
                    base_profile_version=profile_version,
                    canonical=canonical,
                    revises_draft_id=draft_id,
                    new_calibration_version=expected_calibration_version + 1,
                    context=context,
                )
            except _ProfileProposalValidationError as error:
                raise ProfileProposalInvalidError(error.reason_code) from None
            _write_draft_transition(
                connection,
                session=session,
                draft=draft,
                outcome=outcome,
                checkpoint=checkpoint,
                context=context,
                operation=_REVISE_PROFILE_PATCH,
                key_hash=key_hash,
                request_hash=request_hash,
                event_type="profile_patch_revised",
            )
            return DeliveredCalibrationResult(
                outcome=outcome,
                delivery=DeliveryMetadata(replayed=False),
            )

    def abandon_profile_patch(
        self,
        calibration_id: str,
        *,
        expected_calibration_version: int,
        context: FamilyWriteContext,
    ) -> DeliveredCalibrationResult:
        """End a pending calibration without changing confirmed profile Memory."""
        _require_non_empty("calibration_id", calibration_id)
        if expected_calibration_version < 0:
            raise ValueError("expected_calibration_version must be non-negative")
        key_hash = _sha256_text(context.idempotency_key)
        request_hash = _canonical_hash(
            {
                "actor": context.actor,
                "role": context.role,
                "calibration_id": calibration_id,
                "expected_calibration_version": expected_calibration_version,
            }
        )
        with self._transaction() as connection:
            replay = _lookup_calibration_outcome(
                connection,
                operation=_ABANDON_PROFILE_PATCH,
                key_hash=key_hash,
                request_hash=request_hash,
            )
            if replay is not None:
                return replay
            session = _require_session(connection, calibration_id)
            _verify_calibration_version(
                session,
                calibration_id=calibration_id,
                expected_version=expected_calibration_version,
            )
            current_state = CalibrationState(str(session["state"]))
            validate_calibration_transition(current_state, CalibrationState.ABANDONED)
            profile_version = _current_profile_version(connection)
            previous_pending_kind = (
                str(session["pending_kind"]) if session["pending_kind"] is not None else None
            )
            previous_pending_entity = (
                str(session["pending_entity_id"])
                if session["pending_entity_id"] is not None
                else None
            )
            new_calibration_version = expected_calibration_version + 1
            now = datetime.now(UTC)
            connection.execute(
                """
                UPDATE calibration_sessions
                SET calibration_version = ?, state = ?, profile_version = ?,
                    pending_kind = NULL, pending_entity_id = NULL, updated_at = ?
                WHERE id = ? AND calibration_version = ?
                """,
                (
                    new_calibration_version,
                    CalibrationState.ABANDONED.value,
                    profile_version,
                    _iso(now),
                    calibration_id,
                    expected_calibration_version,
                ),
            )
            outcome = CalibrationWorkflowResult(
                calibration_id=calibration_id,
                calibration_version=new_calibration_version,
                profile_version=profile_version,
                state=CalibrationState.ABANDONED,
                allowed_actions=allowed_actions(CalibrationState.ABANDONED),
                trace_id=context.trace_id,
                data={
                    "abandoned_pending_entity_id": previous_pending_entity,
                    "abandoned_pending_kind": previous_pending_kind,
                },
            )
            checkpoint = CalibrationCheckpoint(
                calibration_id=calibration_id,
                calibration_version=new_calibration_version,
                profile_version=profile_version,
                state=CalibrationState.ABANDONED,
                resume_stage=None,
                pending_kind=None,
                pending_entity_id=None,
                last_stable_calibration_version=new_calibration_version,
                last_stable_profile_version=profile_version,
                input_receipt_id=str(session["input_receipt_id"]),
                trace_id=context.trace_id,
                occurred_at=now,
            )
            _insert_checkpoint(connection, checkpoint, outcome=outcome)
            _insert_calibration_audit(
                connection,
                calibration_id=calibration_id,
                event_type="profile_patch_abandoned",
                context=context,
                profile_version=profile_version,
                payload={
                    "pending_entity_id": previous_pending_entity,
                    "pending_kind": previous_pending_kind,
                },
                occurred_at=now,
            )
            _insert_idempotency_outcome(
                connection,
                operation=_ABANDON_PROFILE_PATCH,
                key_hash=key_hash,
                request_hash=request_hash,
                outcome=outcome,
            )
            return DeliveredCalibrationResult(
                outcome=outcome,
                delivery=DeliveryMetadata(replayed=False),
            )

    def save_profile_commit_input(
        self,
        calibration_id: str,
        draft_id: str,
        accepted_operation_ids: tuple[str, ...],
        *,
        draft_digest: str,
        expected_calibration_version: int,
        context: FamilyWriteContext,
    ) -> CalibrationCommitInputReceiptResult:
        """Persist the exact parent-confirmed command before model-backed work."""
        _require_parent_role(context)
        key_hash = _sha256_text(context.idempotency_key)
        with self._transaction() as connection:
            record = _load_idempotency_record(
                connection,
                operation=_SAVE_PROFILE_COMMIT_INPUT,
                key_hash=key_hash,
            )
            if record is not None:
                receipt = _decode_stored_commit_input(connection, record)
                _verify_commit_input_replay_candidate(
                    receipt,
                    calibration_id=calibration_id,
                    draft_id=draft_id,
                    draft_digest=draft_digest,
                    accepted_operation_ids=accepted_operation_ids,
                    expected_calibration_version=expected_calibration_version,
                    context=context,
                )
                return CalibrationCommitInputReceiptResult(
                    input=receipt,
                    replayed=True,
                )

            _require_non_empty("calibration_id", calibration_id)
            _require_non_empty("draft_id", draft_id)
            if expected_calibration_version < 1:
                raise ValueError("expected_calibration_version must be positive")
            try:
                draft_row = _require_draft(
                    connection,
                    calibration_id=calibration_id,
                    draft_id=draft_id,
                )
                draft = _draft_from_row(draft_row)
            except NotFoundError:
                raise
            if draft.draft_digest != draft_digest:
                raise DraftDigestMismatchError(draft.id)
            try:
                accepted_ids = _canonicalize_accepted_ids(
                    draft,
                    accepted_operation_ids,
                )
            except _CommitAcceptanceNotInDraftError:
                raise CommitCommandInvalidError("accepted_ids_not_in_draft") from None
            except _CommitAcceptanceCanonicalizationError:
                raise

            session = _require_session(connection, calibration_id)
            _verify_calibration_version(
                session,
                calibration_id=calibration_id,
                expected_version=expected_calibration_version,
            )
            _verify_current_pending_draft(
                connection,
                session=session,
                calibration_id=calibration_id,
                draft_id=draft_id,
                requested_stage=_SAVE_PROFILE_COMMIT_INPUT,
            )
            profile_version = _current_profile_version(connection)
            now = datetime.now(UTC)
            receipt = CalibrationCommitInputReceipt(
                id=_new_id("commit-input"),
                calibration_id=calibration_id,
                actor=context.actor,
                role="parent",
                expected_calibration_version=expected_calibration_version,
                draft_id=draft_id,
                draft_digest=draft_digest,
                accepted_operation_ids=accepted_ids,
                created_at=now,
            )
            request_hash = _commit_input_request_hash(receipt)
            _insert_profile_commit_input_audit(
                connection,
                receipt=receipt,
                context=context,
                profile_version=profile_version,
            )
            _insert_idempotency_outcome(
                connection,
                operation=_SAVE_PROFILE_COMMIT_INPUT,
                key_hash=key_hash,
                request_hash=request_hash,
                outcome=receipt,
            )
            return CalibrationCommitInputReceiptResult(
                input=receipt,
                replayed=False,
            )

    def get_profile_commit_input(
        self,
        calibration_id: str,
        input_id: str,
    ) -> CalibrationCommitInputReceipt:
        """Load one immutable parent commit command from its exact audit row."""
        with self._read_snapshot() as connection:
            return _require_profile_commit_input(
                connection,
                calibration_id=calibration_id,
                input_id=input_id,
            )

    def has_profile_commit_attempt_checkpoint(
        self,
        calibration_id: str,
        input_id: str,
    ) -> bool:
        """Return whether the exact command receipt reached a retry checkpoint."""
        with self._read_snapshot() as connection:
            row = connection.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM calibration_checkpoints
                    WHERE calibration_id = ?
                      AND pending_entity_id = ?
                      AND resume_stage = 'profile_commit'
                      AND pending_kind = 'model_retry'
                      AND state IN ('model_unavailable', 'retry_pending')
                ) AS found
                """,
                (calibration_id, input_id),
            ).fetchone()
            return row is not None and bool(row["found"])

    def lookup_commit_profile_patch(
        self,
        calibration_id: str,
        draft_id: str,
        accepted_operation_ids: tuple[str, ...],
        *,
        draft_digest: str,
        expected_calibration_version: int,
        context: FamilyWriteContext,
    ) -> DeliveredCalibrationResult | None:
        """Read an exact stored commit outcome without consulting mutable state."""
        key_hash = _sha256_text(context.idempotency_key)
        with self._read_snapshot() as connection:
            record = _load_idempotency_record(
                connection,
                operation=_COMMIT_PROFILE_PATCH,
                key_hash=key_hash,
            )
            if record is not None:
                stored = _decode_stored_commit(record)
                _verify_commit_replay_candidate(
                    stored.command,
                    calibration_id=calibration_id,
                    draft_id=draft_id,
                    draft_digest=draft_digest,
                    accepted_operation_ids=accepted_operation_ids,
                    expected_calibration_version=expected_calibration_version,
                    context=context,
                )
                return DeliveredCalibrationResult(
                    outcome=stored.outcome,
                    delivery=DeliveryMetadata(replayed=True),
                )

            _require_non_empty("calibration_id", calibration_id)
            _require_non_empty("draft_id", draft_id)
            if expected_calibration_version < 0:
                raise ValueError("expected_calibration_version must be non-negative")
            try:
                draft_row = _require_draft(
                    connection,
                    calibration_id=calibration_id,
                    draft_id=draft_id,
                )
                draft = _draft_from_row(draft_row)
            except NotFoundError:
                raise
            if draft.draft_digest != draft_digest:
                raise DraftDigestMismatchError(draft.id)
            try:
                accepted = _canonicalize_accepted_ids(draft, accepted_operation_ids)
            except _CommitAcceptanceNotInDraftError:
                raise CommitCommandInvalidError("accepted_ids_not_in_draft") from None
            except _CommitAcceptanceCanonicalizationError:
                raise
            _require_parent_role(context)
            _commit_request_identity(
                calibration_id=calibration_id,
                draft_id=draft_id,
                draft_digest=draft_digest,
                accepted_operation_ids=accepted,
                expected_calibration_version=expected_calibration_version,
                context=context,
            )
            session = _require_session(connection, calibration_id)
            _verify_calibration_version(
                session,
                calibration_id=calibration_id,
                expected_version=expected_calibration_version,
            )
            _verify_current_pending_draft(
                connection,
                session=session,
                calibration_id=calibration_id,
                draft_id=draft_id,
                requested_stage=_COMMIT_PROFILE_PATCH,
            )
            return None

    def commit_profile_patch(
        self,
        calibration_id: str,
        draft_id: str,
        accepted_operation_ids: tuple[str, ...],
        *,
        draft_digest: str,
        expected_calibration_version: int,
        context: FamilyWriteContext,
    ) -> DeliveredCalibrationResult:
        """Commit a confirmed operation subset and all effects in one transaction."""
        key_hash = _sha256_text(context.idempotency_key)
        with self._transaction() as connection:
            record = _load_idempotency_record(
                connection,
                operation=_COMMIT_PROFILE_PATCH,
                key_hash=key_hash,
            )
            if record is not None:
                stored = _decode_stored_commit(record)
                _verify_commit_replay_candidate(
                    stored.command,
                    calibration_id=calibration_id,
                    draft_id=draft_id,
                    draft_digest=draft_digest,
                    accepted_operation_ids=accepted_operation_ids,
                    expected_calibration_version=expected_calibration_version,
                    context=context,
                )
                return DeliveredCalibrationResult(
                    outcome=stored.outcome,
                    delivery=DeliveryMetadata(replayed=True),
                )

            _require_non_empty("calibration_id", calibration_id)
            _require_non_empty("draft_id", draft_id)
            if expected_calibration_version < 0:
                raise ValueError("expected_calibration_version must be non-negative")
            try:
                draft_row = _require_draft(
                    connection,
                    calibration_id=calibration_id,
                    draft_id=draft_id,
                )
                draft = _draft_from_row(draft_row)
            except NotFoundError:
                raise
            if draft.draft_digest != draft_digest:
                raise DraftDigestMismatchError(draft.id)
            try:
                accepted_ids = _canonicalize_accepted_ids(
                    draft,
                    accepted_operation_ids,
                )
            except _CommitAcceptanceNotInDraftError:
                raise CommitCommandInvalidError("accepted_ids_not_in_draft") from None
            except _CommitAcceptanceCanonicalizationError:
                raise
            _require_parent_role(context)
            key_hash, request_hash = _commit_request_identity(
                calibration_id=calibration_id,
                draft_id=draft_id,
                draft_digest=draft_digest,
                accepted_operation_ids=accepted_ids,
                expected_calibration_version=expected_calibration_version,
                context=context,
            )
            command = _CommitCommand(
                calibration_id=calibration_id,
                draft_id=draft_id,
                draft_digest=draft_digest,
                accepted_operation_ids=accepted_ids,
                expected_calibration_version=expected_calibration_version,
                actor=context.actor,
                role=context.role,
            )

            session = _require_session(connection, calibration_id)
            _verify_calibration_version(
                session,
                calibration_id=calibration_id,
                expected_version=expected_calibration_version,
            )
            _verify_current_pending_draft(
                connection,
                session=session,
                calibration_id=calibration_id,
                draft_id=draft_id,
                requested_stage=_COMMIT_PROFILE_PATCH,
            )
            profile_version = _current_profile_version(connection)
            if draft.base_profile_version != profile_version:
                raise VersionConflictError(
                    "profile",
                    "singleton",
                    draft.base_profile_version,
                    profile_version,
                )
            if int(session["profile_version"]) != profile_version:
                raise VersionConflictError(
                    "profile",
                    "singleton",
                    int(session["profile_version"]),
                    profile_version,
                )

            committed_at = datetime.now(UTC)
            commit_id = _new_id("commit")
            next_profile_version = profile_version + 1
            selected = tuple(
                observation
                for observation in draft.observations
                if observation.operation_id in set(accepted_ids)
            )
            confirmed_operations = _simulate_confirmed_batch(
                connection,
                observations=selected,
                profile_version=next_profile_version,
                commit_id=commit_id,
                confirmed_by=context.actor,
                committed_at=committed_at,
            )
            commit = ProfileCommit(
                id=commit_id,
                calibration_id=calibration_id,
                draft_id=draft_id,
                profile_version=next_profile_version,
                accepted_operation_ids=accepted_ids,
                confirmed_by=context.actor,
                committed_at=committed_at,
            )
            profile_record = ProfileVersion(
                profile_version=next_profile_version,
                commit_id=commit.id,
                reason="parent_confirmed_patch",
                committed_at=committed_at,
            )
            new_calibration_version = expected_calibration_version + 1
            outcome = CalibrationWorkflowResult(
                calibration_id=calibration_id,
                calibration_version=new_calibration_version,
                profile_version=next_profile_version,
                state=CalibrationState.COMMITTED,
                allowed_actions=allowed_actions(CalibrationState.COMMITTED),
                trace_id=context.trace_id,
                data={
                    "accepted_observations": [
                        {
                            "operation_id": item.operation_id,
                            **item.observation.model_dump(mode="json"),
                        }
                        for item in confirmed_operations
                    ],
                    "commit": commit.model_dump(mode="json"),
                    "draft_digest": draft.draft_digest,
                },
            )

            connection.execute(
                """
                INSERT INTO calibration_commits (
                    id, calibration_id, draft_id, resulting_profile_version,
                    accepted_operation_ids_json, confirmed_by, committed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    commit.id,
                    calibration_id,
                    draft_id,
                    next_profile_version,
                    _encode_json(list(accepted_ids)),
                    commit.confirmed_by,
                    _iso(committed_at),
                ),
            )
            connection.execute(
                """
                INSERT INTO profile_versions (
                    profile_version, commit_id, reason, committed_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    profile_record.profile_version,
                    profile_record.commit_id,
                    profile_record.reason,
                    _iso(profile_record.committed_at),
                ),
            )
            for item in confirmed_operations:
                _insert_profile_observation(
                    connection,
                    operation_id=item.operation_id,
                    observation=item.observation,
                )
            cursor = connection.execute(
                """
                UPDATE profile_state
                SET profile_version = ?
                WHERE singleton = 1 AND profile_version = ?
                """,
                (next_profile_version, profile_version),
            )
            if cursor.rowcount != 1:  # pragma: no cover - guarded by write lock
                raise VersionConflictError(
                    "profile",
                    "singleton",
                    profile_version,
                    _current_profile_version(connection),
                )
            connection.execute(
                """
                UPDATE calibration_sessions
                SET calibration_version = ?, state = ?, profile_version = ?,
                    pending_kind = NULL, pending_entity_id = NULL, updated_at = ?
                WHERE id = ? AND calibration_version = ?
                """,
                (
                    new_calibration_version,
                    CalibrationState.COMMITTED.value,
                    next_profile_version,
                    _iso(committed_at),
                    calibration_id,
                    expected_calibration_version,
                ),
            )
            checkpoint = CalibrationCheckpoint(
                calibration_id=calibration_id,
                calibration_version=new_calibration_version,
                profile_version=next_profile_version,
                state=CalibrationState.COMMITTED,
                resume_stage=None,
                pending_kind=None,
                pending_entity_id=None,
                last_stable_calibration_version=new_calibration_version,
                last_stable_profile_version=next_profile_version,
                input_receipt_id=str(session["input_receipt_id"]),
                trace_id=context.trace_id,
                occurred_at=committed_at,
            )
            _insert_checkpoint(connection, checkpoint, outcome=outcome)
            _insert_calibration_audit(
                connection,
                calibration_id=calibration_id,
                event_type="profile_patch_committed",
                context=context,
                profile_version=next_profile_version,
                payload={
                    "accepted_operation_ids": list(accepted_ids),
                    "commit_id": commit.id,
                    "draft_id": draft_id,
                },
                occurred_at=committed_at,
            )
            _insert_commit_idempotency_outcome(
                connection,
                key_hash=key_hash,
                request_hash=request_hash,
                command=command,
                outcome=outcome,
            )
            return DeliveredCalibrationResult(
                outcome=outcome,
                delivery=DeliveryMetadata(replayed=False),
            )

    def get_current_profile_version(self) -> int:
        """Return the confirmed singleton profile counter; zero means no commits."""
        with self._read_snapshot() as connection:
            return _current_profile_version(connection)

    def list_profile_history(
        self,
        up_to_profile_version: int | None = None,
    ) -> tuple[tuple[ProfileVersion, ...], tuple[MemoryObservation, ...]]:
        """Read confirmed version/event history without consulting draft storage."""
        if up_to_profile_version is not None and up_to_profile_version < 0:
            raise ValueError("up_to_profile_version must be non-negative")
        with self._read_snapshot() as connection:
            current = _current_profile_version(connection)
            cap = current if up_to_profile_version is None else min(current, up_to_profile_version)
            return _load_profile_history(connection, up_to_profile_version=cap)

    def get_profile_snapshot(self, profile_version: int) -> ProfileSnapshot:
        """Project confirmed Memory at one exact profile version."""
        if profile_version < 0:
            raise ValueError("profile_version must be non-negative")
        with self._read_snapshot() as connection:
            current = _current_profile_version(connection)
            if profile_version > current:
                raise VersionConflictError(
                    "profile",
                    "singleton",
                    profile_version,
                    current,
                )
            versions, events = _load_profile_history(
                connection,
                up_to_profile_version=profile_version,
            )
            active = (
                project_profile(events, versions, versions[-1].committed_at) if versions else ()
            )
            return ProfileSnapshot(
                profile_version=profile_version,
                active_observations=active,
            )

    def get_latest_calibration_summary(self) -> CalibrationSummary | None:
        """Return the latest exact checkpoint summary across calibrations."""
        with self._read_snapshot() as connection:
            row = connection.execute(
                """
                SELECT calibration_id, calibration_version, profile_version,
                       state, occurred_at
                FROM calibration_checkpoints
                ORDER BY occurred_at DESC, calibration_id DESC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            return CalibrationSummary(
                calibration_id=str(row["calibration_id"]),
                calibration_version=int(row["calibration_version"]),
                profile_version=int(row["profile_version"]),
                state=CalibrationState(str(row["state"])),
                occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
            )

    def append_school_brief(
        self,
        brief_date: date,
        raw_text: str,
        *,
        expected_revision: int,
        context: FamilyWriteContext,
    ) -> DeliveredSchoolBriefResult:
        """Append a manually pasted school brief revision or record a content no-op."""
        if expected_revision < 0:
            raise ValueError("expected_revision must be non-negative")
        key_hash = _sha256_text(context.idempotency_key)
        request_hash = _canonical_hash(
            {
                "actor": context.actor,
                "role": context.role,
                "brief_date": brief_date.isoformat(),
                "expected_revision": expected_revision,
                "raw_text": raw_text,
            }
        )
        with self._transaction() as connection:
            replay = _lookup_school_outcome(
                connection,
                key_hash=key_hash,
                request_hash=request_hash,
            )
            if replay is not None:
                return replay
            current_row = connection.execute(
                """
                SELECT *
                FROM school_brief_revisions
                WHERE brief_date = ?
                ORDER BY revision DESC
                LIMIT 1
                """,
                (brief_date.isoformat(),),
            ).fetchone()
            actual_revision = int(current_row["revision"]) if current_row is not None else 0
            if actual_revision != expected_revision:
                raise VersionConflictError(
                    "school brief",
                    brief_date.isoformat(),
                    expected_revision,
                    actual_revision,
                )
            content_sha256 = _sha256_text(raw_text)
            no_op = current_row is not None and str(current_row["content_sha256"]) == content_sha256
            if no_op:
                record = _school_brief_from_row(current_row)
            else:
                now = datetime.now(UTC)
                record = SchoolBriefRevision(
                    id=_new_id("school-brief"),
                    brief_date=brief_date,
                    revision=actual_revision + 1,
                    content_sha256=content_sha256,
                    raw_text=raw_text,
                    source="manual-paste",
                    created_at=now,
                )
                connection.execute(
                    """
                    INSERT INTO school_brief_revisions (
                        id, brief_date, revision, content_sha256,
                        raw_text, source, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.id,
                        record.brief_date.isoformat(),
                        record.revision,
                        record.content_sha256,
                        record.raw_text,
                        record.source,
                        _iso(record.created_at),
                    ),
                )
            outcome = SchoolBriefWriteResult(
                brief_date=brief_date,
                revision=record.revision,
                record=record,
                trace_id=context.trace_id,
                no_op=no_op,
                allowed_actions=("replace_school_brief",),
            )
            _insert_school_outcome(
                connection,
                key_hash=key_hash,
                request_hash=request_hash,
                outcome=outcome,
            )
            return DeliveredSchoolBriefResult(
                outcome=outcome,
                delivery=DeliveryMetadata(replayed=False),
            )

    def get_latest_school_brief(
        self,
        brief_date: date,
    ) -> SchoolBriefRevision | None:
        """Return the latest canonical manual revision for a school date."""
        with self._read_snapshot() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM school_brief_revisions
                WHERE brief_date = ?
                ORDER BY revision DESC
                LIMIT 1
                """,
                (brief_date.isoformat(),),
            ).fetchone()
            return _school_brief_from_row(row) if row is not None else None

    def list_school_brief_revisions(
        self,
        brief_date: date,
    ) -> tuple[SchoolBriefRevision, ...]:
        """Return exact append-only school brief history for one date."""
        with self._read_snapshot() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM school_brief_revisions
                WHERE brief_date = ?
                ORDER BY revision
                """,
                (brief_date.isoformat(),),
            ).fetchall()
            return tuple(_school_brief_from_row(row) for row in rows)

    def mark_calibration_model_unavailable(
        self,
        calibration_id: str,
        receipt_id: str,
        *,
        expected_calibration_version: int,
        error_code: str,
        resume_stage: str = "profile_propose",
        pending_entity_id: str | None = None,
        context: FamilyWriteContext,
    ) -> DeliveredCalibrationResult:
        """Persist a sanitized failure without automatically retrying inference."""
        _require_non_empty("calibration_id", calibration_id)
        _require_non_empty("receipt_id", receipt_id)
        _require_non_empty("error_code", error_code)
        _require_non_empty("resume_stage", resume_stage)
        if expected_calibration_version < 0:
            raise ValueError("expected_calibration_version must be non-negative")
        if resume_stage not in {"profile_propose", "profile_commit"}:
            raise ValueError("unsupported calibration resume_stage")

        requested_pending_entity_id = (
            receipt_id if resume_stage == "profile_propose" else pending_entity_id
        )

        key_hash = _sha256_text(context.idempotency_key)
        request_hash = _canonical_hash(
            {
                "actor": context.actor,
                "role": context.role,
                "calibration_id": calibration_id,
                "receipt_id": receipt_id,
                "expected_calibration_version": expected_calibration_version,
                "error_code": error_code,
                "resume_stage": resume_stage,
                "pending_entity_id": requested_pending_entity_id,
            }
        )
        with self._transaction() as connection:
            replay = _lookup_calibration_outcome(
                connection,
                operation=_MARK_CALIBRATION_MODEL_UNAVAILABLE,
                key_hash=key_hash,
                request_hash=request_hash,
            )
            if replay is not None:
                return replay

            session = _require_session(connection, calibration_id)
            _verify_calibration_version(
                session,
                calibration_id=calibration_id,
                expected_version=expected_calibration_version,
            )
            current_state = CalibrationState(str(session["state"]))
            if resume_stage == "profile_propose":
                if current_state is CalibrationState.INPUT_SAVED:
                    latest = _require_latest_checkpoint(connection, calibration_id)
                    if (
                        latest.state is not CalibrationState.INPUT_SAVED
                        or latest.resume_stage != "profile_propose"
                        or latest.pending_kind is not None
                        or latest.pending_entity_id is not None
                        or latest.input_receipt_id != receipt_id
                    ):
                        raise InvalidTransitionError(
                            current_state.value,
                            resume_stage,
                        )
                elif current_state is CalibrationState.RETRY_PENDING:
                    latest = _require_latest_checkpoint(connection, calibration_id)
                    if (
                        latest.state is not CalibrationState.RETRY_PENDING
                        or latest.resume_stage != "profile_propose"
                        or latest.pending_kind is not PendingKind.MODEL_RETRY
                        or latest.pending_entity_id != receipt_id
                        or latest.input_receipt_id != receipt_id
                    ):
                        raise InvalidTransitionError(
                            current_state.value,
                            resume_stage,
                        )
                else:
                    raise InvalidTransitionError(current_state.value, resume_stage)
                effective_pending_entity_id = receipt_id
            else:
                if current_state not in {
                    CalibrationState.NEEDS_CONFIRMATION,
                    CalibrationState.RETRY_PENDING,
                }:
                    raise InvalidTransitionError(current_state.value, resume_stage)
                if pending_entity_id is None:
                    raise ValueError("profile_commit recovery requires commit input id")
                commit_input = _require_profile_commit_input(
                    connection,
                    calibration_id=calibration_id,
                    input_id=pending_entity_id,
                )
                _verify_current_pending_draft(
                    connection,
                    session=session,
                    calibration_id=calibration_id,
                    draft_id=commit_input.draft_id,
                    requested_stage=_MARK_CALIBRATION_MODEL_UNAVAILABLE,
                )
                if current_state is CalibrationState.RETRY_PENDING:
                    latest = _require_latest_checkpoint(connection, calibration_id)
                    if (
                        latest.resume_stage != "profile_commit"
                        or latest.pending_kind is not PendingKind.MODEL_RETRY
                        or latest.pending_entity_id != commit_input.id
                    ):
                        raise InvalidTransitionError(current_state.value, resume_stage)
                effective_pending_entity_id = pending_entity_id
            validate_calibration_transition(
                current_state,
                CalibrationState.MODEL_UNAVAILABLE,
            )
            receipt_row = _require_calibration_receipt(
                connection,
                calibration_id=calibration_id,
                receipt_id=receipt_id,
            )
            profile_version = _verify_receipt_profile_is_current(connection, receipt_row)
            new_calibration_version = expected_calibration_version + 1
            now = datetime.now(UTC)
            connection.execute(
                """
                UPDATE calibration_sessions
                SET calibration_version = ?, state = ?, profile_version = ?,
                    pending_kind = ?, pending_entity_id = ?, updated_at = ?
                WHERE id = ? AND calibration_version = ?
                """,
                (
                    new_calibration_version,
                    CalibrationState.MODEL_UNAVAILABLE.value,
                    profile_version,
                    PendingKind.MODEL_RETRY.value,
                    effective_pending_entity_id,
                    _iso(now),
                    calibration_id,
                    expected_calibration_version,
                ),
            )
            outcome = CalibrationWorkflowResult(
                calibration_id=calibration_id,
                calibration_version=new_calibration_version,
                profile_version=profile_version,
                state=CalibrationState.MODEL_UNAVAILABLE,
                allowed_actions=allowed_actions(CalibrationState.MODEL_UNAVAILABLE),
                trace_id=context.trace_id,
                data={
                    "error_code": error_code,
                    "receipt_id": receipt_id,
                    "resume_stage": resume_stage,
                    "pending_entity_id": effective_pending_entity_id,
                },
            )
            checkpoint = CalibrationCheckpoint(
                calibration_id=calibration_id,
                calibration_version=new_calibration_version,
                profile_version=profile_version,
                state=CalibrationState.MODEL_UNAVAILABLE,
                resume_stage=resume_stage,
                pending_kind=PendingKind.MODEL_RETRY,
                pending_entity_id=effective_pending_entity_id,
                last_stable_calibration_version=expected_calibration_version,
                last_stable_profile_version=profile_version,
                input_receipt_id=receipt_id,
                trace_id=context.trace_id,
                occurred_at=now,
            )
            _insert_checkpoint(connection, checkpoint, outcome=outcome)
            _insert_calibration_audit(
                connection,
                calibration_id=calibration_id,
                event_type="calibration_model_unavailable",
                context=context,
                profile_version=profile_version,
                payload={
                    "error_code": error_code,
                    "receipt_id": receipt_id,
                    "resume_stage": resume_stage,
                    "pending_entity_id": effective_pending_entity_id,
                },
                occurred_at=now,
            )
            _insert_idempotency_outcome(
                connection,
                operation=_MARK_CALIBRATION_MODEL_UNAVAILABLE,
                key_hash=key_hash,
                request_hash=request_hash,
                outcome=outcome,
            )
            return DeliveredCalibrationResult(
                outcome=outcome,
                delivery=DeliveryMetadata(replayed=False),
            )

    def begin_calibration_retry(
        self,
        calibration_id: str,
        *,
        expected_calibration_version: int,
        context: FamilyWriteContext,
    ) -> DeliveredCalibrationResult:
        """Record an explicit user-triggered retry before another model attempt."""
        _require_non_empty("calibration_id", calibration_id)
        if expected_calibration_version < 0:
            raise ValueError("expected_calibration_version must be non-negative")

        key_hash = _sha256_text(context.idempotency_key)
        request_hash = _canonical_hash(
            {
                "actor": context.actor,
                "role": context.role,
                "calibration_id": calibration_id,
                "expected_calibration_version": expected_calibration_version,
            }
        )
        with self._transaction() as connection:
            replay = _lookup_calibration_outcome(
                connection,
                operation=_BEGIN_CALIBRATION_RETRY,
                key_hash=key_hash,
                request_hash=request_hash,
            )
            if replay is not None:
                return replay

            session = _require_session(connection, calibration_id)
            _verify_calibration_version(
                session,
                calibration_id=calibration_id,
                expected_version=expected_calibration_version,
            )
            current_state = CalibrationState(str(session["state"]))
            validate_calibration_transition(current_state, CalibrationState.RETRY_PENDING)
            latest = _require_latest_checkpoint(connection, calibration_id)
            if (
                latest.state is not CalibrationState.MODEL_UNAVAILABLE
                or latest.resume_stage not in {"profile_propose", "profile_commit"}
                or latest.pending_kind is not PendingKind.MODEL_RETRY
                or latest.pending_entity_id is None
            ):
                raise InvalidTransitionError(
                    current_state.value,
                    CalibrationState.RETRY_PENDING.value,
                )
            resume_stage = latest.resume_stage
            pending_entity_id = latest.pending_entity_id
            receipt_id = str(session["input_receipt_id"])
            if latest.input_receipt_id != receipt_id:
                raise InvalidTransitionError(
                    current_state.value,
                    CalibrationState.RETRY_PENDING.value,
                )
            receipt_row = _require_calibration_receipt(
                connection,
                calibration_id=calibration_id,
                receipt_id=receipt_id,
            )
            profile_version = _verify_receipt_profile_is_current(connection, receipt_row)
            new_calibration_version = expected_calibration_version + 1
            now = datetime.now(UTC)
            connection.execute(
                """
                UPDATE calibration_sessions
                SET calibration_version = ?, state = ?, profile_version = ?,
                    pending_kind = ?, pending_entity_id = ?, updated_at = ?
                WHERE id = ? AND calibration_version = ?
                """,
                (
                    new_calibration_version,
                    CalibrationState.RETRY_PENDING.value,
                    profile_version,
                    PendingKind.MODEL_RETRY.value,
                    pending_entity_id,
                    _iso(now),
                    calibration_id,
                    expected_calibration_version,
                ),
            )
            outcome = CalibrationWorkflowResult(
                calibration_id=calibration_id,
                calibration_version=new_calibration_version,
                profile_version=profile_version,
                state=CalibrationState.RETRY_PENDING,
                allowed_actions=allowed_actions(CalibrationState.RETRY_PENDING),
                trace_id=context.trace_id,
                data={
                    "receipt_id": receipt_id,
                    "recovery_directive": RecoveryDirective.INITIAL_INFERENCE.value,
                    "resume_stage": resume_stage,
                    "pending_entity_id": pending_entity_id,
                },
            )
            checkpoint = CalibrationCheckpoint(
                calibration_id=calibration_id,
                calibration_version=new_calibration_version,
                profile_version=profile_version,
                state=CalibrationState.RETRY_PENDING,
                resume_stage=resume_stage,
                pending_kind=PendingKind.MODEL_RETRY,
                pending_entity_id=pending_entity_id,
                last_stable_calibration_version=new_calibration_version,
                last_stable_profile_version=profile_version,
                input_receipt_id=receipt_id,
                trace_id=context.trace_id,
                occurred_at=now,
            )
            _insert_checkpoint(connection, checkpoint, outcome=outcome)
            _insert_calibration_audit(
                connection,
                calibration_id=calibration_id,
                event_type="calibration_retry_started",
                context=context,
                profile_version=profile_version,
                payload={
                    "receipt_id": receipt_id,
                    "resume_stage": resume_stage,
                    "pending_entity_id": pending_entity_id,
                },
                occurred_at=now,
            )
            _insert_idempotency_outcome(
                connection,
                operation=_BEGIN_CALIBRATION_RETRY,
                key_hash=key_hash,
                request_hash=request_hash,
                outcome=outcome,
            )
            return DeliveredCalibrationResult(
                outcome=outcome,
                delivery=DeliveryMetadata(replayed=False),
            )


def _known_proposal_contract_reason(error: ValidationError) -> str | None:
    messages: set[str] = set()
    for detail in error.errors(include_url=False, include_input=False):
        context = detail.get("ctx")
        cause = context.get("error") if isinstance(context, Mapping) else None
        message = str(cause) if cause is not None else str(detail["msg"])
        messages.add(message.removeprefix("Value error, "))
    if "structured Memory text contains a permanent label" in messages:
        return "forbidden_label"
    if messages.intersection(
        {
            "metric is not allowed for category",
            "text metric requires non-empty value_text",
            "text metric accepts only value_text",
            "local time metric requires strict HH:MM value_text",
            "local time metric requires only local_time unit",
            "numeric metric requires only value_number",
            "numeric metric is outside its allowed range",
            "numeric metric requires an integer number",
            "numeric metric has an invalid unit",
            "numeric metric requires sample_count >= 1",
            "typical_minutes_low may not exceed typical_minutes_high",
        }
    ):
        return "invalid_metric_value_relation"
    return None


def _canonicalize_proposals(
    observations: tuple[ProposedObservationInput, ...],
) -> _CanonicalProposals:
    if not observations:
        raise ValueError("a profile patch requires at least one observation")
    ordered = sorted(
        enumerate(observations),
        key=lambda item: (
            _encode_json(item[1].model_dump(mode="json")),
            item[0],
        ),
    )
    proposal_payload = [observation.model_dump(mode="json") for _, observation in ordered]
    proposal_digest = _sha256_text(_encode_json(proposal_payload))
    stored: list[ProposedObservation] = []
    for index, (_, observation) in enumerate(ordered):
        operation_digest = _sha256_text(f"{proposal_digest}:{index}")
        try:
            stored.append(
                ProposedObservation(
                    operation_id=f"operation-{operation_digest}",
                    **observation.model_dump(),
                )
            )
        except ValidationError as error:
            reason_code = _known_proposal_contract_reason(error)
            if reason_code is not None:
                raise _ProfileProposalValidationError(reason_code) from None
            raise
    stored_payload = [item.model_dump(mode="json") for item in stored]
    draft_digest = _sha256_text(_encode_json(stored_payload))
    return _CanonicalProposals(
        observations=tuple(stored),
        proposal_digest=proposal_digest,
        draft_digest=draft_digest,
    )


def _canonicalize_accepted_ids(
    draft: ProfilePatchDraft,
    accepted_operation_ids: tuple[str, ...],
) -> tuple[str, ...]:
    if not accepted_operation_ids:
        raise _CommitAcceptanceEmptyError("accepted_operation_ids must be non-empty")
    if len(accepted_operation_ids) != len(set(accepted_operation_ids)):
        raise _CommitAcceptanceDuplicateError("accepted_operation_ids must be unique")
    accepted = set(accepted_operation_ids)
    stored_ids = tuple(item.operation_id for item in draft.observations)
    unknown = accepted.difference(stored_ids)
    if unknown:
        raise _CommitAcceptanceNotInDraftError(
            "accepted_operation_ids must be a subset of the draft"
        )
    return tuple(operation_id for operation_id in stored_ids if operation_id in accepted)


def _commit_request_identity(
    *,
    calibration_id: str,
    draft_id: str,
    draft_digest: str,
    accepted_operation_ids: tuple[str, ...],
    expected_calibration_version: int,
    context: FamilyWriteContext,
) -> tuple[str, str]:
    key_hash = _sha256_text(context.idempotency_key)
    command = _CommitCommand(
        calibration_id=calibration_id,
        draft_id=draft_id,
        draft_digest=draft_digest,
        accepted_operation_ids=accepted_operation_ids,
        expected_calibration_version=expected_calibration_version,
        actor=context.actor,
        role=context.role,
    )
    return key_hash, _canonical_hash(_commit_command_json(command))


def _commit_command_json(command: _CommitCommand) -> JsonObject:
    return {
        "accepted_operation_ids": list(command.accepted_operation_ids),
        "actor": command.actor,
        "role": command.role,
        "calibration_id": command.calibration_id,
        "draft_id": command.draft_id,
        "draft_digest": command.draft_digest,
        "expected_calibration_version": command.expected_calibration_version,
    }


def _commit_input_command(receipt: CalibrationCommitInputReceipt) -> _CommitCommand:
    return _CommitCommand(
        calibration_id=receipt.calibration_id,
        draft_id=receipt.draft_id,
        draft_digest=receipt.draft_digest,
        accepted_operation_ids=receipt.accepted_operation_ids,
        expected_calibration_version=receipt.expected_calibration_version,
        actor=receipt.actor,
        role=receipt.role,
    )


def _commit_input_request_hash(receipt: CalibrationCommitInputReceipt) -> str:
    return _canonical_hash(_commit_command_json(_commit_input_command(receipt)))


def _decode_stored_commit_input(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
) -> CalibrationCommitInputReceipt:
    receipt = CalibrationCommitInputReceipt.model_validate_json(str(row["response_json"]))
    if str(row["request_hash"]) != _commit_input_request_hash(receipt):
        raise ValueError("stored profile commit input hash is inconsistent")
    try:
        audit_receipt = _load_profile_commit_input_audit(
            connection,
            calibration_id=receipt.calibration_id,
            input_id=receipt.id,
        )
    except NotFoundError as error:
        raise ValueError("stored profile commit input audit is missing or mismatched") from error
    if audit_receipt != receipt:
        raise ValueError("stored profile commit input audit is inconsistent")
    return receipt


def _verify_commit_input_replay_candidate(
    stored: CalibrationCommitInputReceipt,
    *,
    calibration_id: str,
    draft_id: str,
    draft_digest: str,
    accepted_operation_ids: tuple[str, ...],
    expected_calibration_version: int,
    context: FamilyWriteContext,
) -> None:
    if (
        not accepted_operation_ids
        or any(type(item) is not str for item in accepted_operation_ids)
        or len(accepted_operation_ids) != len(set(accepted_operation_ids))
        or set(accepted_operation_ids) != set(stored.accepted_operation_ids)
    ):
        raise IdempotencyConflictError(
            _SAVE_PROFILE_COMMIT_INPUT,
            _REDACTED_IDEMPOTENCY_KEY,
        )
    accepted = tuple(
        operation_id
        for operation_id in stored.accepted_operation_ids
        if operation_id in set(accepted_operation_ids)
    )
    candidate = _CommitCommand(
        calibration_id=calibration_id,
        draft_id=draft_id,
        draft_digest=draft_digest,
        accepted_operation_ids=accepted,
        expected_calibration_version=expected_calibration_version,
        actor=context.actor,
        role=context.role,
    )
    if candidate != _commit_input_command(stored):
        raise IdempotencyConflictError(
            _SAVE_PROFILE_COMMIT_INPUT,
            _REDACTED_IDEMPOTENCY_KEY,
        )


def _decode_stored_commit(row: sqlite3.Row) -> _StoredCommit:
    try:
        decoded = json.loads(str(row["response_json"]))
    except json.JSONDecodeError as error:
        raise ValueError("stored commit record is not valid JSON") from error
    if not isinstance(decoded, dict) or set(decoded) != {"command", "outcome"}:
        raise ValueError("stored commit record has an invalid envelope")
    command_json = decoded["command"]
    if not isinstance(command_json, dict) or set(command_json) != {
        "accepted_operation_ids",
        "actor",
        "role",
        "calibration_id",
        "draft_id",
        "draft_digest",
        "expected_calibration_version",
    }:
        raise ValueError("stored commit command has an invalid shape")
    string_fields = (
        "actor",
        "role",
        "calibration_id",
        "draft_id",
        "draft_digest",
    )
    if any(
        type(command_json[field]) is not str or not command_json[field] for field in string_fields
    ):
        raise ValueError("stored commit command has invalid string identity")
    accepted_json = command_json["accepted_operation_ids"]
    if (
        not isinstance(accepted_json, list)
        or not accepted_json
        or any(type(item) is not str or not item for item in accepted_json)
        or len(accepted_json) != len(set(accepted_json))
    ):
        raise ValueError("stored commit command has invalid accepted IDs")
    expected_version = command_json["expected_calibration_version"]
    if type(expected_version) is not int or expected_version < 0:
        raise ValueError("stored commit command has an invalid expected version")
    draft_digest = str(command_json["draft_digest"])
    if len(draft_digest) != 64 or any(
        character not in "0123456789abcdef" for character in draft_digest
    ):
        raise ValueError("stored commit command has an invalid draft digest")
    command = _CommitCommand(
        calibration_id=str(command_json["calibration_id"]),
        draft_id=str(command_json["draft_id"]),
        draft_digest=draft_digest,
        accepted_operation_ids=tuple(str(item) for item in accepted_json),
        expected_calibration_version=expected_version,
        actor=str(command_json["actor"]),
        role=str(command_json["role"]),
    )
    if command.role != "parent":
        raise ValueError("stored commit command has an invalid role")
    if str(row["request_hash"]) != _canonical_hash(_commit_command_json(command)):
        raise ValueError("stored commit command hash is inconsistent")

    outcome_json = decoded["outcome"]
    if not isinstance(outcome_json, dict):
        raise ValueError("stored commit outcome has an invalid shape")
    outcome = CalibrationWorkflowResult.model_validate_json(_encode_json(outcome_json))
    if (
        outcome.calibration_id != command.calibration_id
        or outcome.calibration_version != command.expected_calibration_version + 1
        or outcome.state is not CalibrationState.COMMITTED
        or outcome.allowed_actions != allowed_actions(CalibrationState.COMMITTED)
    ):
        raise ValueError("stored commit outcome identity is inconsistent")
    if set(outcome.data) != {
        "accepted_observations",
        "commit",
        "draft_digest",
    }:
        raise ValueError("stored commit outcome data has an invalid shape")
    commit_json = outcome.data["commit"]
    if not isinstance(commit_json, dict):
        raise ValueError("stored commit payload has an invalid shape")
    commit = ProfileCommit.model_validate_json(_encode_json(commit_json))
    if (
        commit.calibration_id != command.calibration_id
        or commit.draft_id != command.draft_id
        or commit.accepted_operation_ids != command.accepted_operation_ids
        or commit.confirmed_by != command.actor
        or commit.profile_version != outcome.profile_version
        or outcome.data["draft_digest"] != command.draft_digest
    ):
        raise ValueError("stored commit payload identity is inconsistent")
    accepted_observations = outcome.data["accepted_observations"]
    if not isinstance(accepted_observations, list) or len(accepted_observations) != len(
        command.accepted_operation_ids
    ):
        raise ValueError("stored accepted observations have an invalid shape")
    for canonical_order, (operation_id, item) in enumerate(
        zip(
            command.accepted_operation_ids,
            accepted_observations,
            strict=True,
        )
    ):
        if not isinstance(item, dict) or item.get("operation_id") != operation_id:
            raise ValueError("stored accepted observation identity is inconsistent")
        observation_json = dict(item)
        del observation_json["operation_id"]
        observation = MemoryObservation.model_validate_json(_encode_json(observation_json))
        expected_event_id = f"event-{_sha256_text(f'{commit.id}:{operation_id}')}"
        if (
            observation.id != expected_event_id
            or observation.profile_version != commit.profile_version
            or observation.canonical_order != canonical_order
            or observation.confirmed_by != commit.confirmed_by
            or observation.committed_at != commit.committed_at
            or observation.source is not Source.PARENT
            or observation.evidence_level is not ObservationEvidenceLevel.PARENT_CONFIRMED
        ):
            raise ValueError("stored accepted observation provenance is inconsistent")
    return _StoredCommit(command=command, outcome=outcome)


def _verify_commit_replay_candidate(
    stored: _CommitCommand,
    *,
    calibration_id: str,
    draft_id: str,
    draft_digest: str,
    accepted_operation_ids: tuple[str, ...],
    expected_calibration_version: int,
    context: FamilyWriteContext,
) -> None:
    if (
        not accepted_operation_ids
        or any(type(item) is not str for item in accepted_operation_ids)
        or len(accepted_operation_ids) != len(set(accepted_operation_ids))
        or set(accepted_operation_ids) != set(stored.accepted_operation_ids)
    ):
        raise IdempotencyConflictError(
            _COMMIT_PROFILE_PATCH,
            _REDACTED_IDEMPOTENCY_KEY,
        )
    accepted = tuple(
        operation_id
        for operation_id in stored.accepted_operation_ids
        if operation_id in set(accepted_operation_ids)
    )
    candidate = _CommitCommand(
        calibration_id=calibration_id,
        draft_id=draft_id,
        draft_digest=draft_digest,
        accepted_operation_ids=accepted,
        expected_calibration_version=expected_calibration_version,
        actor=context.actor,
        role=context.role,
    )
    if candidate != stored:
        raise IdempotencyConflictError(
            _COMMIT_PROFILE_PATCH,
            _REDACTED_IDEMPOTENCY_KEY,
        )


def _require_parent_role(context: FamilyWriteContext) -> None:
    if context.role != "parent":
        raise ValueError("commit_profile_patch requires the trusted parent role")


def _simulate_confirmed_batch(
    connection: sqlite3.Connection,
    *,
    observations: tuple[ProposedObservation, ...],
    profile_version: int,
    commit_id: str,
    confirmed_by: str,
    committed_at: datetime,
) -> tuple[_ConfirmedOperation, ...]:
    versions, history = _load_profile_history(
        connection,
        up_to_profile_version=profile_version - 1,
    )
    active = {event.id: event for event in project_profile(history, versions, committed_at)}
    consumed_targets: set[str] = set()
    confirmed: list[_ConfirmedOperation] = []
    for canonical_order, proposed in enumerate(observations):
        if proposed.observed_at > committed_at:
            raise ValueError("future-dated observations cannot be committed")
        event_id = f"event-{_sha256_text(f'{commit_id}:{proposed.operation_id}')}"
        event = MemoryObservation(
            id=event_id,
            action=proposed.action,
            category=proposed.category,
            subject=proposed.subject,
            task_type=proposed.task_type,
            metric=proposed.metric,
            value_text=proposed.value_text,
            value_number=proposed.value_number,
            unit=proposed.unit,
            confidence=proposed.confidence,
            sample_count=proposed.sample_count,
            observed_at=proposed.observed_at,
            target_event_id=proposed.target_event_id,
            source=Source.PARENT,
            evidence_level=ObservationEvidenceLevel.PARENT_CONFIRMED,
            confirmed_by=confirmed_by,
            profile_version=profile_version,
            canonical_order=canonical_order,
            committed_at=committed_at,
        )
        if event.action is ProfilePatchAction.ASSERT:
            active[event.id] = event
        else:
            target_id = event.target_event_id
            if target_id is None:  # pragma: no cover - strict contract enforces this
                raise ValueError("non-assert observation requires an active target")
            if target_id in consumed_targets:
                raise ValueError("profile target was consumed more than once")
            target = active.get(target_id)
            if target is None:
                raise ValueError("profile observation requires an active target")
            if _observation_identity(event) != _observation_identity(target):
                raise ValueError("replacement identity does not match target")
            consumed_targets.add(target_id)
            del active[target_id]
            if event.action is ProfilePatchAction.SUPERSEDE:
                active[event.id] = event
        confirmed.append(
            _ConfirmedOperation(
                operation_id=proposed.operation_id,
                observation=event,
            )
        )
    return tuple(confirmed)


def _validate_proposed_targets(
    connection: sqlite3.Connection,
    observations: tuple[ProposedObservation, ...],
    *,
    profile_version: int,
) -> None:
    targeted = tuple(
        observation
        for observation in observations
        if observation.action is not ProfilePatchAction.ASSERT
    )
    if not targeted:
        return
    versions, history = _load_profile_history(
        connection,
        up_to_profile_version=profile_version,
    )
    active = {event.id: event for event in project_profile(history, versions, datetime.now(UTC))}
    for observation in targeted:
        target = active.get(str(observation.target_event_id))
        if target is None:
            raise _ProfileProposalValidationError("unsupported_target")
        if _observation_identity(observation) != _observation_identity(target):
            raise _ProfileProposalValidationError("broken_identity")


def _observation_identity(
    observation: ProposedObservation | MemoryObservation,
) -> tuple[MemoryCategory, str | None, str | None, str]:
    return (
        observation.category,
        normalize_family_text(observation.subject),
        normalize_family_text(observation.task_type),
        observation.metric,
    )


def _profile_patch_request_hash(
    *,
    actor: str,
    role: str,
    calibration_id: str,
    receipt_id: str | None,
    expected_calibration_version: int,
    proposal_digest: str,
    revises_draft_id: str | None,
    unapplied_notes: tuple[str, ...] = (),
    calibration_details: tuple[CalibrationEvidenceDetail, ...] = (),
) -> str:
    return _canonical_hash(
        {
            "actor": actor,
            "role": role,
            "calibration_id": calibration_id,
            "receipt_id": receipt_id,
            "expected_calibration_version": expected_calibration_version,
            "proposal_digest": proposal_digest,
            "revises_draft_id": revises_draft_id,
            "unapplied_notes": list(unapplied_notes),
            "calibration_details": [
                item.model_dump(mode="json") for item in calibration_details
            ],
        }
    )


def _prepare_draft_transition(
    *,
    calibration_id: str,
    receipt_id: str,
    base_profile_version: int,
    canonical: _CanonicalProposals,
    revises_draft_id: str | None,
    new_calibration_version: int,
    context: FamilyWriteContext,
    unapplied_notes: tuple[str, ...] = (),
    calibration_details: tuple[CalibrationEvidenceDetail, ...] = (),
) -> tuple[ProfilePatchDraft, CalibrationWorkflowResult, CalibrationCheckpoint]:
    now = datetime.now(UTC)
    try:
        draft = ProfilePatchDraft(
            id=_new_id("draft"),
            calibration_id=calibration_id,
            receipt_id=receipt_id,
            base_profile_version=base_profile_version,
            proposal_digest=canonical.proposal_digest,
            draft_digest=canonical.draft_digest,
            observations=canonical.observations,
            revises_draft_id=revises_draft_id,
            created_at=now,
        )
    except ValidationError as error:
        reason_code = _known_proposal_contract_reason(error)
        if reason_code is not None:
            raise _ProfileProposalValidationError(reason_code) from None
        raise
    outcome_data: dict[str, Any] = {
        "base_profile_version": base_profile_version,
        "diff_preview": [
            observation.model_dump(mode="json") for observation in draft.observations
        ],
        "draft_digest": draft.draft_digest,
        "draft_id": draft.id,
        "proposal_digest": draft.proposal_digest,
        "unapplied_notes": list(unapplied_notes),
    }
    if calibration_details:
        outcome_data["calibration_details"] = [
            item.model_dump(mode="json") for item in calibration_details
        ]
    outcome = CalibrationWorkflowResult(
        calibration_id=calibration_id,
        calibration_version=new_calibration_version,
        profile_version=base_profile_version,
        state=CalibrationState.NEEDS_CONFIRMATION,
        allowed_actions=allowed_actions(CalibrationState.NEEDS_CONFIRMATION),
        trace_id=context.trace_id,
        data=outcome_data,
    )
    checkpoint = CalibrationCheckpoint(
        calibration_id=calibration_id,
        calibration_version=new_calibration_version,
        profile_version=base_profile_version,
        state=CalibrationState.NEEDS_CONFIRMATION,
        resume_stage="profile_commit",
        pending_kind=PendingKind.PROFILE_PATCH,
        pending_entity_id=draft.id,
        last_stable_calibration_version=new_calibration_version,
        last_stable_profile_version=base_profile_version,
        input_receipt_id=receipt_id,
        trace_id=context.trace_id,
        occurred_at=now,
    )
    return draft, outcome, checkpoint


def _write_draft_transition(
    connection: sqlite3.Connection,
    *,
    session: sqlite3.Row,
    draft: ProfilePatchDraft,
    outcome: CalibrationWorkflowResult,
    checkpoint: CalibrationCheckpoint,
    context: FamilyWriteContext,
    operation: str,
    key_hash: str,
    request_hash: str,
    event_type: str,
) -> None:
    expected_version = int(session["calibration_version"])
    cursor = connection.execute(
        """
        UPDATE calibration_sessions
        SET calibration_version = ?, state = ?, profile_version = ?,
            pending_kind = ?, pending_entity_id = ?, updated_at = ?
        WHERE id = ? AND calibration_version = ?
        """,
        (
            outcome.calibration_version,
            CalibrationState.NEEDS_CONFIRMATION.value,
            outcome.profile_version,
            PendingKind.PROFILE_PATCH.value,
            draft.id,
            _iso(draft.created_at),
            draft.calibration_id,
            expected_version,
        ),
    )
    if cursor.rowcount != 1:  # pragma: no cover - write lock plus prior check
        raise VersionConflictError(
            "calibration",
            draft.calibration_id,
            expected_version,
            outcome.calibration_version,
        )
    connection.execute(
        """
        INSERT INTO calibration_drafts (
            id, calibration_id, receipt_id, base_profile_version,
            proposal_digest, draft_digest, operations_json, result_json,
            revises_draft_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            draft.id,
            draft.calibration_id,
            draft.receipt_id,
            draft.base_profile_version,
            draft.proposal_digest,
            draft.draft_digest,
            _encode_json([item.model_dump(mode="json") for item in draft.observations]),
            _encode_json(outcome.model_dump(mode="json")),
            draft.revises_draft_id,
            _iso(draft.created_at),
        ),
    )
    _insert_checkpoint(connection, checkpoint, outcome=outcome)
    _insert_calibration_audit(
        connection,
        calibration_id=draft.calibration_id,
        event_type=event_type,
        context=context,
        profile_version=draft.base_profile_version,
        payload={
            "draft_digest": draft.draft_digest,
            "draft_id": draft.id,
            "revises_draft_id": draft.revises_draft_id,
        },
        occurred_at=draft.created_at,
    )
    _insert_idempotency_outcome(
        connection,
        operation=operation,
        key_hash=key_hash,
        request_hash=request_hash,
        outcome=outcome,
    )


def _insert_checkpoint(
    connection: sqlite3.Connection,
    checkpoint: CalibrationCheckpoint,
    *,
    outcome: CalibrationWorkflowResult | None,
) -> None:
    connection.execute(
        """
        INSERT INTO calibration_checkpoints (
            id, calibration_id, calibration_version, profile_version, state,
            resume_stage, pending_kind, pending_entity_id,
            last_stable_calibration_version, last_stable_profile_version,
            input_receipt_id, trace_id, outcome_json, occurred_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _new_id("checkpoint"),
            checkpoint.calibration_id,
            checkpoint.calibration_version,
            checkpoint.profile_version,
            checkpoint.state.value,
            checkpoint.resume_stage,
            checkpoint.pending_kind.value if checkpoint.pending_kind is not None else None,
            checkpoint.pending_entity_id,
            checkpoint.last_stable_calibration_version,
            checkpoint.last_stable_profile_version,
            checkpoint.input_receipt_id,
            checkpoint.trace_id,
            _encode_json(outcome.model_dump(mode="json")) if outcome is not None else None,
            _iso(checkpoint.occurred_at),
        ),
    )


def _lookup_calibration_outcome(
    connection: sqlite3.Connection,
    *,
    operation: str,
    key_hash: str,
    request_hash: str,
) -> DeliveredCalibrationResult | None:
    row = connection.execute(
        """
        SELECT request_hash, response_json
        FROM idempotency_records
        WHERE operation = ? AND idempotency_key = ?
        """,
        (operation, key_hash),
    ).fetchone()
    if row is None:
        return None
    _verify_request_hash(row, operation=operation, request_hash=request_hash)
    return DeliveredCalibrationResult(
        outcome=_workflow_result_from_json(str(row["response_json"])),
        delivery=DeliveryMetadata(replayed=True),
    )


def _load_idempotency_record(
    connection: sqlite3.Connection,
    *,
    operation: str,
    key_hash: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT request_hash, response_json
        FROM idempotency_records
        WHERE operation = ? AND idempotency_key = ?
        """,
        (operation, key_hash),
    ).fetchone()


def _lookup_school_outcome(
    connection: sqlite3.Connection,
    *,
    key_hash: str,
    request_hash: str,
) -> DeliveredSchoolBriefResult | None:
    row = connection.execute(
        """
        SELECT request_hash, response_json
        FROM idempotency_records
        WHERE operation = ? AND idempotency_key = ?
        """,
        (_APPEND_SCHOOL_BRIEF, key_hash),
    ).fetchone()
    if row is None:
        return None
    _verify_request_hash(
        row,
        operation=_APPEND_SCHOOL_BRIEF,
        request_hash=request_hash,
    )
    return DeliveredSchoolBriefResult(
        outcome=SchoolBriefWriteResult.model_validate_json(str(row["response_json"])),
        delivery=DeliveryMetadata(replayed=True),
    )


def _insert_idempotency_outcome(
    connection: sqlite3.Connection,
    *,
    operation: str,
    key_hash: str,
    request_hash: str,
    outcome: CalibrationWorkflowResult | CalibrationCommitInputReceipt,
    response_payload: Mapping[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO idempotency_records (
            operation, idempotency_key, request_hash, response_json
        ) VALUES (?, ?, ?, ?)
        """,
        (
            operation,
            key_hash,
            request_hash,
            _encode_json(
                outcome.model_dump(mode="json") if response_payload is None else response_payload
            ),
        ),
    )


def _insert_commit_idempotency_outcome(
    connection: sqlite3.Connection,
    *,
    key_hash: str,
    request_hash: str,
    command: _CommitCommand,
    outcome: CalibrationWorkflowResult,
) -> None:
    _insert_idempotency_outcome(
        connection,
        operation=_COMMIT_PROFILE_PATCH,
        key_hash=key_hash,
        request_hash=request_hash,
        outcome=outcome,
        response_payload={
            "command": _commit_command_json(command),
            "outcome": outcome.model_dump(mode="json"),
        },
    )


def _insert_school_outcome(
    connection: sqlite3.Connection,
    *,
    key_hash: str,
    request_hash: str,
    outcome: SchoolBriefWriteResult,
) -> None:
    connection.execute(
        """
        INSERT INTO idempotency_records (
            operation, idempotency_key, request_hash, response_json
        ) VALUES (?, ?, ?, ?)
        """,
        (
            _APPEND_SCHOOL_BRIEF,
            key_hash,
            request_hash,
            _encode_json(outcome.model_dump(mode="json")),
        ),
    )


def _insert_calibration_audit(
    connection: sqlite3.Connection,
    *,
    calibration_id: str,
    event_type: str,
    context: FamilyWriteContext,
    profile_version: int,
    payload: Mapping[str, Any],
    occurred_at: datetime,
) -> None:
    connection.execute(
        """
        INSERT INTO calibration_audit_events (
            id, calibration_id, event_type, actor, role, profile_version,
            payload_json, trace_id, occurred_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _new_id("audit"),
            calibration_id,
            event_type,
            context.actor,
            context.role,
            profile_version,
            _encode_json(dict(payload)),
            context.trace_id,
            _iso(occurred_at),
            _iso(occurred_at),
        ),
    )


def _insert_profile_commit_input_audit(
    connection: sqlite3.Connection,
    *,
    receipt: CalibrationCommitInputReceipt,
    context: FamilyWriteContext,
    profile_version: int,
) -> None:
    connection.execute(
        """
        INSERT INTO calibration_audit_events (
            id, calibration_id, event_type, actor, role, profile_version,
            payload_json, trace_id, occurred_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            receipt.id,
            receipt.calibration_id,
            "profile_commit_input_saved",
            receipt.actor,
            receipt.role,
            profile_version,
            _encode_json(receipt.model_dump(mode="json")),
            context.trace_id,
            _iso(receipt.created_at),
            _iso(receipt.created_at),
        ),
    )


def _load_profile_history(
    connection: sqlite3.Connection,
    *,
    up_to_profile_version: int,
) -> tuple[tuple[ProfileVersion, ...], tuple[MemoryObservation, ...]]:
    if up_to_profile_version <= 0:
        return (), ()
    version_rows = connection.execute(
        """
        SELECT profile_version, commit_id, reason, committed_at
        FROM profile_versions
        WHERE profile_version <= ?
        ORDER BY profile_version
        """,
        (up_to_profile_version,),
    ).fetchall()
    event_rows = connection.execute(
        """
        SELECT *
        FROM profile_observation_events
        WHERE profile_version <= ?
        ORDER BY profile_version, canonical_order, id
        """,
        (up_to_profile_version,),
    ).fetchall()
    versions = tuple(_profile_version_from_row(row) for row in version_rows)
    events = tuple(_memory_observation_from_row(row) for row in event_rows)
    return versions, events


def _insert_profile_observation(
    connection: sqlite3.Connection,
    *,
    operation_id: str,
    observation: MemoryObservation,
) -> None:
    connection.execute(
        """
        INSERT INTO profile_observation_events (
            id, operation_id, profile_version, canonical_order, action,
            category, subject, task_type, metric, value_text, value_number,
            unit, confidence, sample_count, observed_at, target_event_id,
            source, evidence_level, confirmed_by, committed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            observation.id,
            operation_id,
            observation.profile_version,
            observation.canonical_order,
            observation.action.value,
            observation.category.value,
            observation.subject,
            observation.task_type,
            observation.metric,
            observation.value_text,
            observation.value_number,
            observation.unit,
            observation.confidence,
            observation.sample_count,
            _iso(observation.observed_at),
            observation.target_event_id,
            observation.source.value,
            observation.evidence_level.value,
            observation.confirmed_by,
            _iso(observation.committed_at),
        ),
    )


def _profile_version_from_row(row: sqlite3.Row) -> ProfileVersion:
    return ProfileVersion(
        profile_version=int(row["profile_version"]),
        commit_id=str(row["commit_id"]),
        reason=str(row["reason"]),
        committed_at=datetime.fromisoformat(str(row["committed_at"])),
    )


def _memory_observation_from_row(row: sqlite3.Row) -> MemoryObservation:
    return MemoryObservation(
        id=str(row["id"]),
        action=ProfilePatchAction(str(row["action"])),
        category=MemoryCategory(str(row["category"])),
        subject=str(row["subject"]) if row["subject"] is not None else None,
        task_type=str(row["task_type"]) if row["task_type"] is not None else None,
        metric=str(row["metric"]),
        value_text=str(row["value_text"]) if row["value_text"] is not None else None,
        value_number=(float(row["value_number"]) if row["value_number"] is not None else None),
        unit=str(row["unit"]) if row["unit"] is not None else None,
        confidence=float(row["confidence"]),
        sample_count=int(row["sample_count"]) if row["sample_count"] is not None else None,
        observed_at=datetime.fromisoformat(str(row["observed_at"])),
        target_event_id=(
            str(row["target_event_id"]) if row["target_event_id"] is not None else None
        ),
        source=Source(str(row["source"])),
        evidence_level=ObservationEvidenceLevel(str(row["evidence_level"])),
        confirmed_by=str(row["confirmed_by"]),
        profile_version=int(row["profile_version"]),
        canonical_order=int(row["canonical_order"]),
        committed_at=datetime.fromisoformat(str(row["committed_at"])),
    )


def _receipt_from_row(row: sqlite3.Row) -> CalibrationTurnReceipt:
    return CalibrationTurnReceipt(
        id=str(row["id"]),
        calibration_id=str(row["calibration_id"]),
        actor=str(row["actor"]),
        role=str(row["role"]),
        content_sha256=str(row["content_sha256"]),
        raw_text=str(row["raw_text"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _load_profile_commit_input_audit(
    connection: sqlite3.Connection,
    *,
    calibration_id: str,
    input_id: str,
) -> CalibrationCommitInputReceipt:
    row = connection.execute(
        "SELECT * FROM calibration_audit_events WHERE id = ?",
        (input_id,),
    ).fetchone()
    if row is None or str(row["calibration_id"]) != calibration_id:
        raise NotFoundError("profile commit input", input_id)
    if str(row["event_type"]) != "profile_commit_input_saved":
        raise ValueError("profile commit input audit event type is invalid")
    receipt = CalibrationCommitInputReceipt.model_validate_json(str(row["payload_json"]))
    occurred_at = datetime.fromisoformat(str(row["occurred_at"]))
    audit_created_at = datetime.fromisoformat(str(row["created_at"]))
    if (
        receipt.id != input_id
        or receipt.id != str(row["id"])
        or receipt.calibration_id != calibration_id
        or receipt.calibration_id != str(row["calibration_id"])
        or receipt.actor != str(row["actor"])
        or receipt.role != str(row["role"])
        or receipt.role != "parent"
        or receipt.created_at != occurred_at
        or audit_created_at != occurred_at
    ):
        raise ValueError("profile commit input audit identity is inconsistent")
    return receipt


def _require_profile_commit_input(
    connection: sqlite3.Connection,
    *,
    calibration_id: str,
    input_id: str,
) -> CalibrationCommitInputReceipt:
    receipt = _load_profile_commit_input_audit(
        connection,
        calibration_id=calibration_id,
        input_id=input_id,
    )
    _verify_commit_input_draft_canonicality(connection, receipt)
    return receipt


def _verify_commit_input_draft_canonicality(
    connection: sqlite3.Connection,
    receipt: CalibrationCommitInputReceipt,
) -> None:
    row = connection.execute(
        "SELECT * FROM calibration_drafts WHERE id = ?",
        (receipt.draft_id,),
    ).fetchone()
    if row is None or str(row["calibration_id"]) != receipt.calibration_id:
        raise ValueError("profile commit input draft identity is inconsistent")
    draft = _draft_from_row(row)
    if draft.draft_digest != receipt.draft_digest:
        raise ValueError("profile commit input draft digest is inconsistent")
    try:
        canonical = _canonicalize_accepted_ids(
            draft,
            receipt.accepted_operation_ids,
        )
    except _CommitAcceptanceCanonicalizationError as error:
        raise ValueError("profile commit input accepted IDs are invalid") from error
    if canonical != receipt.accepted_operation_ids:
        raise ValueError("profile commit input accepted IDs are not canonical")


def _school_brief_from_row(row: sqlite3.Row) -> SchoolBriefRevision:
    return SchoolBriefRevision(
        id=str(row["id"]),
        brief_date=date.fromisoformat(str(row["brief_date"])),
        revision=int(row["revision"]),
        content_sha256=str(row["content_sha256"]),
        raw_text=str(row["raw_text"]),
        source="manual-paste",
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _draft_from_row(row: sqlite3.Row) -> ProfilePatchDraft:
    decoded = json.loads(str(row["operations_json"]))
    if not isinstance(decoded, list):
        raise ValueError("stored draft operations must be a list")
    return ProfilePatchDraft(
        id=str(row["id"]),
        calibration_id=str(row["calibration_id"]),
        receipt_id=str(row["receipt_id"]),
        base_profile_version=int(row["base_profile_version"]),
        proposal_digest=str(row["proposal_digest"]),
        draft_digest=str(row["draft_digest"]),
        observations=tuple(
            ProposedObservation.model_validate_json(_encode_json(item)) for item in decoded
        ),
        revises_draft_id=(
            str(row["revises_draft_id"]) if row["revises_draft_id"] is not None else None
        ),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _checkpoint_from_row(row: sqlite3.Row) -> CalibrationCheckpoint:
    pending_kind = row["pending_kind"]
    return CalibrationCheckpoint(
        calibration_id=str(row["calibration_id"]),
        calibration_version=int(row["calibration_version"]),
        profile_version=int(row["profile_version"]),
        state=CalibrationState(str(row["state"])),
        resume_stage=str(row["resume_stage"]) if row["resume_stage"] is not None else None,
        pending_kind=PendingKind(str(pending_kind)) if pending_kind is not None else None,
        pending_entity_id=(
            str(row["pending_entity_id"]) if row["pending_entity_id"] is not None else None
        ),
        last_stable_calibration_version=int(row["last_stable_calibration_version"]),
        last_stable_profile_version=int(row["last_stable_profile_version"]),
        input_receipt_id=(
            str(row["input_receipt_id"]) if row["input_receipt_id"] is not None else None
        ),
        trace_id=str(row["trace_id"]) if row["trace_id"] is not None else None,
        occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
    )


def _require_latest_checkpoint(
    connection: sqlite3.Connection,
    calibration_id: str,
) -> CalibrationCheckpoint:
    _require_non_empty("calibration_id", calibration_id)
    row = connection.execute(
        """
        SELECT *
        FROM calibration_checkpoints
        WHERE calibration_id = ?
        ORDER BY calibration_version DESC
        LIMIT 1
        """,
        (calibration_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("calibration checkpoint", calibration_id)

    checkpoint = _checkpoint_from_row(row)
    if (
        row["id"] is None
        or not str(row["id"]).strip()
        or checkpoint.calibration_id != calibration_id
    ):
        raise ValueError("stored latest checkpoint identity is invalid")

    if row["outcome_json"] is not None:
        outcome = _workflow_result_from_json(str(row["outcome_json"]))
        if (
            outcome.calibration_id != checkpoint.calibration_id
            or outcome.calibration_version != checkpoint.calibration_version
            or outcome.profile_version != checkpoint.profile_version
            or outcome.state is not checkpoint.state
        ):
            raise ValueError("stored latest checkpoint outcome is inconsistent")
    return checkpoint


def _workflow_result_from_json(value: str) -> CalibrationWorkflowResult:
    return CalibrationWorkflowResult.model_validate_json(value)


def _recovery_directive(state: CalibrationState) -> RecoveryDirective:
    if state in {CalibrationState.INPUT_SAVED, CalibrationState.RETRY_PENDING}:
        return RecoveryDirective.INITIAL_INFERENCE
    if state is CalibrationState.MODEL_UNAVAILABLE:
        return RecoveryDirective.EXPLICIT_RETRY_ALLOWED
    return RecoveryDirective.RETURN_STORED


def _current_profile_version(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT profile_version FROM profile_state WHERE singleton = 1"
    ).fetchone()
    if row is None:  # pragma: no cover - guaranteed by migration 0004
        raise NotFoundError("profile state", "singleton")
    return int(row["profile_version"])


def _require_session(
    connection: sqlite3.Connection,
    calibration_id: str,
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM calibration_sessions WHERE id = ?",
        (calibration_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("calibration", calibration_id)
    return row


def _verify_calibration_version(
    session: sqlite3.Row,
    *,
    calibration_id: str,
    expected_version: int,
) -> None:
    actual_version = int(session["calibration_version"])
    if actual_version != expected_version:
        raise VersionConflictError(
            "calibration",
            calibration_id,
            expected_version,
            actual_version,
        )


def _require_calibration_receipt(
    connection: sqlite3.Connection,
    *,
    calibration_id: str,
    receipt_id: str,
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM calibration_turn_receipts WHERE id = ?",
        (receipt_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("calibration receipt", receipt_id)
    if str(row["calibration_id"]) != calibration_id:
        raise ValueError("calibration receipt belongs to another calibration")
    return row


def _require_draft(
    connection: sqlite3.Connection,
    *,
    calibration_id: str,
    draft_id: str,
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM calibration_drafts WHERE id = ?",
        (draft_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("calibration draft", draft_id)
    if str(row["calibration_id"]) != calibration_id:
        raise NotFoundError("calibration draft", draft_id)
    return row


def _verify_current_pending_draft(
    connection: sqlite3.Connection,
    *,
    session: sqlite3.Row,
    calibration_id: str,
    draft_id: str,
    requested_stage: str,
) -> None:
    state = CalibrationState(str(session["state"]))
    latest = _require_latest_checkpoint(connection, calibration_id)
    if state is CalibrationState.NEEDS_CONFIRMATION:
        valid = (
            session["pending_kind"] == PendingKind.PROFILE_PATCH.value
            and session["pending_entity_id"] == draft_id
            and latest.state is CalibrationState.NEEDS_CONFIRMATION
            and latest.pending_kind is PendingKind.PROFILE_PATCH
            and latest.pending_entity_id == draft_id
        )
    elif state is CalibrationState.RETRY_PENDING:
        current_entity = session["pending_entity_id"]
        if (
            session["pending_kind"] != PendingKind.MODEL_RETRY.value
            or current_entity is None
            or latest.state is not CalibrationState.RETRY_PENDING
            or latest.resume_stage != "profile_commit"
            or latest.pending_kind is not PendingKind.MODEL_RETRY
            or latest.pending_entity_id != str(current_entity)
        ):
            valid = False
        else:
            commit_input = _require_profile_commit_input(
                connection,
                calibration_id=calibration_id,
                input_id=str(current_entity),
            )
            valid = commit_input.draft_id == draft_id
    else:
        valid = False
    if not valid:
        raise InvalidTransitionError(state.value, requested_stage)


def _verify_receipt_profile_is_current(
    connection: sqlite3.Connection,
    receipt: sqlite3.Row,
) -> int:
    base_profile_version = int(receipt["base_profile_version"])
    current_profile_version = _current_profile_version(connection)
    if current_profile_version != base_profile_version:
        raise VersionConflictError(
            "profile",
            "singleton",
            base_profile_version,
            current_profile_version,
        )
    return current_profile_version


def _verify_request_hash(
    row: sqlite3.Row,
    *,
    operation: str,
    request_hash: str,
) -> None:
    if str(row["request_hash"]) != request_hash:
        raise IdempotencyConflictError(operation, _REDACTED_IDEMPOTENCY_KEY)


def _require_non_empty(name: str, value: str) -> None:
    if not value:
        raise ValueError(f"{name} must be non-empty")


def _canonical_hash(value: Mapping[str, Any]) -> str:
    return _sha256_text(_encode_json(value))


def _encode_json(value: Mapping[str, Any] | list[Any]) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _iso(value: datetime) -> str:
    return value.isoformat()
