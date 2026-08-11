from __future__ import annotations

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

import pytest

from backend.contracts.family import (
    CalibrationCommitInputReceipt,
    CalibrationCommitInputReceiptResult,
    CalibrationSummary,
    CalibrationState,
    FamilyWriteContext,
    MemoryCategory,
    ObservationEvidenceLevel,
    PendingKind,
    ProfilePatchAction,
    ProfileSnapshot,
    ProposedObservationInput,
    RecoveryDirective,
)
from backend.contracts.models import Source
from backend.errors import (
    CommitCommandInvalidError,
    DraftDigestMismatchError,
    IdempotencyConflictError,
    InvalidTransitionError,
    NotFoundError,
    ProfileProposalInvalidError,
    VersionConflictError,
)
from backend.storage.database import connect_database, run_migrations
from backend.storage.family_context import FamilyContextRepository


NOW_TEXT = "Parent-provided local calibration text"
OBSERVED_AT = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "family-context.db"
    run_migrations(path, backup_dir=tmp_path / "backups")
    return path


@pytest.fixture
def repository(database_path: Path) -> FamilyContextRepository:
    return FamilyContextRepository(database_path)


def _context(
    key: str = "receipt-secret-key",
    *,
    actor: str = "parent-1",
    role: str = "parent",
    trace_id: str = "trace-1",
) -> FamilyWriteContext:
    return FamilyWriteContext(
        actor=actor,
        role=role,
        trace_id=trace_id,
        idempotency_key=key,
    )


def _save_input(
    repository: FamilyContextRepository,
    *,
    calibration_id: str = "calibration-1",
    text: str = NOW_TEXT,
    expected_calibration_version: int = 0,
    expected_profile_version: int = 0,
    context: FamilyWriteContext | None = None,
):
    return repository.save_calibration_input(
        calibration_id,
        text,
        expected_calibration_version=expected_calibration_version,
        expected_profile_version=expected_profile_version,
        context=context or _context(),
    )


def _count(connection: sqlite3.Connection, table: str) -> int:
    row = connection.execute(f'SELECT COUNT(*) AS count FROM "{table}"').fetchone()
    assert row is not None
    return int(row["count"])


def _mark_unavailable(
    repository: FamilyContextRepository,
    receipt_id: str,
    *,
    expected_calibration_version: int = 1,
    error_code: str = "lm_studio_unavailable",
    resume_stage: str = "profile_propose",
    pending_entity_id: str | None = None,
    context: FamilyWriteContext | None = None,
):
    return repository.mark_calibration_model_unavailable(
        "calibration-1",
        receipt_id,
        expected_calibration_version=expected_calibration_version,
        error_code=error_code,
        resume_stage=resume_stage,
        pending_entity_id=pending_entity_id,
        context=context or _context("unavailable-key", trace_id="trace-unavailable"),
    )


def _proposal(**overrides: object) -> ProposedObservationInput:
    payload: dict[str, object] = {
        "action": ProfilePatchAction.ASSERT,
        "category": MemoryCategory.SUBJECT_PERFORMANCE,
        "subject": "Mathematics",
        "task_type": "written",
        "metric": "assessment_level",
        "value_text": "secure",
        "value_number": None,
        "unit": None,
        "confidence": 0.85,
        "sample_count": None,
        "observed_at": OBSERVED_AT,
        "target_event_id": None,
    }
    payload.update(overrides)
    return ProposedObservationInput(**payload)


def _propose(
    repository: FamilyContextRepository,
    receipt_id: str,
    *,
    observations: tuple[ProposedObservationInput, ...] | None = None,
    expected_calibration_version: int = 1,
    context: FamilyWriteContext | None = None,
):
    return repository.propose_profile_patch(
        "calibration-1",
        receipt_id,
        observations or (_proposal(),),
        expected_calibration_version=expected_calibration_version,
        context=context or _context("proposal-key", trace_id="trace-proposal"),
    )


def _pending_draft(repository: FamilyContextRepository, calibration_id: str = "calibration-1"):
    draft = repository.get_calibration_recovery(calibration_id).pending_draft
    assert draft is not None
    return draft


def _commit(
    repository: FamilyContextRepository,
    draft_id: str,
    accepted_operation_ids: tuple[str, ...],
    *,
    calibration_id: str = "calibration-1",
    expected_calibration_version: int = 2,
    draft_digest: str | None = None,
    context: FamilyWriteContext | None = None,
):
    if draft_digest is None:
        with connect_database(repository.database_path) as connection:
            row = connection.execute(
                "SELECT draft_digest FROM calibration_drafts WHERE id = ?",
                (draft_id,),
            ).fetchone()
        assert row is not None
        draft_digest = str(row["draft_digest"])
    return repository.commit_profile_patch(
        calibration_id,
        draft_id,
        accepted_operation_ids,
        draft_digest=draft_digest,
        expected_calibration_version=expected_calibration_version,
        context=context or _context("commit-key", trace_id="trace-commit"),
    )


def _call_commit_boundary(
    repository: FamilyContextRepository,
    method_name: str,
    calibration_id: str,
    draft_id: str,
    accepted_operation_ids: tuple[str, ...],
    *,
    draft_digest: str,
    expected_calibration_version: int,
    context: FamilyWriteContext,
):
    method = getattr(repository, method_name)
    return method(
        calibration_id,
        draft_id,
        accepted_operation_ids,
        draft_digest=draft_digest,
        expected_calibration_version=expected_calibration_version,
        context=context,
    )


def _save_commit_input(
    repository: FamilyContextRepository,
    draft,
    accepted_operation_ids: tuple[str, ...],
    *,
    calibration_id: str = "calibration-1",
    draft_digest: str | None = None,
    expected_calibration_version: int = 2,
    context: FamilyWriteContext | None = None,
):
    return repository.save_profile_commit_input(
        calibration_id,
        draft.id,
        accepted_operation_ids,
        draft_digest=draft_digest or draft.draft_digest,
        expected_calibration_version=expected_calibration_version,
        context=context or _context("commit-http-key-0001", trace_id="trace-command"),
    )


def test_save_calibration_input_persists_receipt_before_inference_and_recovers(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    result = _save_input(repository)

    assert result.replayed is False
    assert result.receipt.calibration_id == "calibration-1"
    assert result.receipt.raw_text == NOW_TEXT
    assert result.receipt.actor == "parent-1"
    assert result.receipt.role == "parent"
    assert result.receipt.created_at.tzinfo is not None

    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.calibration_version == 1
    assert recovery.profile_version == 0
    assert recovery.receipt == result.receipt
    assert recovery.latest_checkpoint.state is CalibrationState.INPUT_SAVED
    assert recovery.latest_checkpoint.calibration_version == 1
    assert recovery.latest_checkpoint.profile_version == 0
    assert recovery.latest_checkpoint.last_stable_calibration_version == 1
    assert recovery.latest_checkpoint.last_stable_profile_version == 0
    assert recovery.latest_checkpoint.input_receipt_id == result.receipt.id
    assert recovery.latest_checkpoint.resume_stage == "profile_propose"
    assert recovery.latest_checkpoint.trace_id == "trace-1"
    assert recovery.pending_draft is None
    assert recovery.pending_draft_result is None
    assert recovery.last_outcome is None
    assert recovery.directive is RecoveryDirective.INITIAL_INFERENCE

    key_hash = hashlib.sha256(b"receipt-secret-key").hexdigest()
    with connect_database(database_path) as connection:
        receipt_row = connection.execute(
            "SELECT operation, key_hash, request_hash, raw_text FROM calibration_turn_receipts"
        ).fetchone()
        assert receipt_row is not None
        assert receipt_row["operation"] == "save_calibration_input"
        assert receipt_row["key_hash"] == key_hash
        assert receipt_row["request_hash"] != key_hash
        assert receipt_row["raw_text"] == NOW_TEXT
        assert _count(connection, "calibration_sessions") == 1
        assert _count(connection, "calibration_turn_receipts") == 1
        assert _count(connection, "calibration_checkpoints") == 1
        assert _count(connection, "profile_versions") == 0
        assert _count(connection, "profile_observation_events") == 0
        assert _count(connection, "idempotency_records") == 0


def test_save_input_replay_precedes_current_version_and_ignores_new_trace(
    repository: FamilyContextRepository,
) -> None:
    original = _save_input(repository)

    replay = _save_input(
        repository,
        context=_context(trace_id="trace-replay"),
    )

    assert replay.replayed is True
    assert replay.receipt == original.receipt
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.calibration_version == 1
    assert recovery.latest_checkpoint.trace_id == "trace-1"


@pytest.mark.parametrize(
    "changed",
    [
        {"text": "different local input"},
        {"expected_calibration_version": 1},
        {"expected_profile_version": 1},
        {"context": _context(actor="parent-2")},
        {"context": _context(role="system")},
    ],
)
def test_save_input_same_key_different_trusted_request_conflicts_without_key_leak(
    repository: FamilyContextRepository,
    changed: dict[str, object],
) -> None:
    _save_input(repository)

    with pytest.raises(IdempotencyConflictError) as captured:
        _save_input(repository, **changed)

    message = str(captured.value)
    assert "receipt-secret-key" not in message
    assert hashlib.sha256(b"receipt-secret-key").hexdigest() not in message
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.calibration_version == 1


def test_save_input_new_key_with_stale_calibration_version_leaves_no_partial_rows(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    _save_input(repository)

    with pytest.raises(VersionConflictError) as captured:
        _save_input(repository, context=_context("new-key"))

    assert captured.value.expected_version == 0
    assert captured.value.actual_version == 1
    with connect_database(database_path) as connection:
        assert _count(connection, "calibration_sessions") == 1
        assert _count(connection, "calibration_turn_receipts") == 1
        assert _count(connection, "calibration_checkpoints") == 1


def test_save_input_checks_profile_version_and_rolls_back_new_aggregate(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    with pytest.raises(VersionConflictError) as captured:
        _save_input(
            repository,
            calibration_id="calibration-stale-profile",
            expected_profile_version=1,
        )

    assert captured.value.entity == "profile"
    assert captured.value.expected_version == 1
    assert captured.value.actual_version == 0
    with connect_database(database_path) as connection:
        assert _count(connection, "calibration_sessions") == 0
        assert _count(connection, "calibration_turn_receipts") == 0
        assert _count(connection, "calibration_checkpoints") == 0


def test_recovery_snapshot_survives_repository_restart(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    original = _save_input(repository)

    restarted = FamilyContextRepository(database_path)
    recovery = restarted.get_calibration_recovery("calibration-1")

    assert recovery.receipt == original.receipt
    assert recovery.directive is RecoveryDirective.INITIAL_INFERENCE
    assert recovery.calibration_version == 1
    assert recovery.profile_version == 0


def test_model_unavailable_persists_sanitized_replayable_checkpoint(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt

    delivered = _mark_unavailable(repository, receipt.id)

    assert delivered.delivery.replayed is False
    assert delivered.outcome.calibration_id == "calibration-1"
    assert delivered.outcome.calibration_version == 2
    assert delivered.outcome.profile_version == 0
    assert delivered.outcome.state is CalibrationState.MODEL_UNAVAILABLE
    assert delivered.outcome.allowed_actions == (
        "retry_last_turn",
        "use_simplified_calibration",
        "abandon_profile_patch",
    )
    assert delivered.outcome.trace_id == "trace-unavailable"
    assert delivered.outcome.data == {
        "error_code": "lm_studio_unavailable",
        "receipt_id": receipt.id,
        "resume_stage": "profile_propose",
        "pending_entity_id": receipt.id,
    }
    assert NOW_TEXT not in delivered.model_dump_json()

    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.directive is RecoveryDirective.EXPLICIT_RETRY_ALLOWED
    assert recovery.calibration_version == 2
    assert recovery.profile_version == 0
    assert recovery.latest_checkpoint.state is CalibrationState.MODEL_UNAVAILABLE
    assert recovery.latest_checkpoint.pending_kind is PendingKind.MODEL_RETRY
    assert recovery.latest_checkpoint.pending_entity_id == receipt.id
    assert recovery.latest_checkpoint.input_receipt_id == receipt.id
    assert recovery.latest_checkpoint.last_stable_calibration_version == 1
    assert recovery.latest_checkpoint.last_stable_profile_version == 0
    assert recovery.last_outcome == delivered.outcome

    key_hash = hashlib.sha256(b"unavailable-key").hexdigest()
    with connect_database(database_path) as connection:
        stored = connection.execute(
            """
            SELECT idempotency_key, response_json
            FROM idempotency_records
            WHERE operation = 'mark_calibration_model_unavailable'
            """
        ).fetchone()
        assert stored is not None
        assert stored["idempotency_key"] == key_hash
        assert "unavailable-key" not in str(stored["response_json"])
        assert NOW_TEXT not in str(stored["response_json"])
        assert _count(connection, "calibration_audit_events") == 1


def test_model_unavailable_replays_before_version_and_trace_checks(
    repository: FamilyContextRepository,
) -> None:
    receipt = _save_input(repository).receipt
    original = _mark_unavailable(repository, receipt.id)

    replay = _mark_unavailable(
        repository,
        receipt.id,
        context=_context("unavailable-key", trace_id="trace-replay"),
    )

    assert replay.delivery.replayed is True
    assert replay.outcome == original.outcome
    assert replay.outcome.trace_id == "trace-unavailable"
    assert repository.get_calibration_recovery("calibration-1").calibration_version == 2


def test_model_unavailable_same_key_changed_error_conflicts_without_key_leak(
    repository: FamilyContextRepository,
) -> None:
    receipt = _save_input(repository).receipt
    _mark_unavailable(repository, receipt.id)

    with pytest.raises(IdempotencyConflictError) as captured:
        _mark_unavailable(repository, receipt.id, error_code="request_timeout")

    assert "unavailable-key" not in str(captured.value)
    assert hashlib.sha256(b"unavailable-key").hexdigest() not in str(captured.value)
    assert repository.get_calibration_recovery("calibration-1").calibration_version == 2


def test_begin_retry_requires_new_key_and_advances_only_calibration_version(
    repository: FamilyContextRepository,
) -> None:
    receipt = _save_input(repository).receipt
    _mark_unavailable(repository, receipt.id)

    delivered = repository.begin_calibration_retry(
        "calibration-1",
        expected_calibration_version=2,
        context=_context("retry-key", trace_id="trace-retry"),
    )

    assert delivered.delivery.replayed is False
    assert delivered.outcome.calibration_version == 3
    assert delivered.outcome.profile_version == 0
    assert delivered.outcome.state is CalibrationState.RETRY_PENDING
    assert delivered.outcome.allowed_actions == ("generate_profile_patch",)
    assert delivered.outcome.data == {
        "receipt_id": receipt.id,
        "recovery_directive": RecoveryDirective.INITIAL_INFERENCE.value,
        "resume_stage": "profile_propose",
        "pending_entity_id": receipt.id,
    }
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.directive is RecoveryDirective.INITIAL_INFERENCE
    assert recovery.latest_checkpoint.pending_kind is PendingKind.MODEL_RETRY
    assert recovery.latest_checkpoint.pending_entity_id == receipt.id
    assert recovery.latest_checkpoint.last_stable_calibration_version == 3
    assert recovery.profile_version == 0


def test_commit_model_unavailable_and_commit_retry_preserve_exact_command(
    repository: FamilyContextRepository,
) -> None:
    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    commit_input = _save_commit_input(
        repository,
        draft,
        (draft.observations[0].operation_id,),
    ).input

    failed = _mark_unavailable(
        repository,
        turn_receipt.id,
        expected_calibration_version=2,
        resume_stage="profile_commit",
        pending_entity_id=commit_input.id,
        context=_context("commit-failure-key", trace_id="trace-commit-failure"),
    )

    assert failed.outcome.calibration_version == 3
    assert failed.outcome.data == {
        "error_code": "lm_studio_unavailable",
        "receipt_id": turn_receipt.id,
        "resume_stage": "profile_commit",
        "pending_entity_id": commit_input.id,
    }
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.latest_checkpoint.state is CalibrationState.MODEL_UNAVAILABLE
    assert recovery.latest_checkpoint.resume_stage == "profile_commit"
    assert recovery.latest_checkpoint.pending_kind is PendingKind.MODEL_RETRY
    assert recovery.latest_checkpoint.pending_entity_id == commit_input.id
    assert recovery.pending_draft == draft
    assert recovery.pending_commit_input == commit_input
    assert recovery.profile_version == 0

    retry = repository.begin_calibration_retry(
        "calibration-1",
        expected_calibration_version=3,
        context=_context("commit-retry-key", trace_id="trace-commit-retry"),
    )

    assert retry.outcome.calibration_version == 4
    assert retry.outcome.data == {
        "receipt_id": turn_receipt.id,
        "recovery_directive": RecoveryDirective.INITIAL_INFERENCE.value,
        "resume_stage": "profile_commit",
        "pending_entity_id": commit_input.id,
    }
    retried = repository.get_calibration_recovery("calibration-1")
    assert retried.latest_checkpoint.resume_stage == "profile_commit"
    assert retried.latest_checkpoint.pending_entity_id == commit_input.id
    assert retried.pending_draft == draft
    assert retried.pending_commit_input == commit_input

    failed_again = _mark_unavailable(
        repository,
        turn_receipt.id,
        expected_calibration_version=4,
        resume_stage="profile_commit",
        pending_entity_id=commit_input.id,
        context=_context(
            "second-commit-failure-key",
            trace_id="trace-second-commit-failure",
        ),
    )
    assert failed_again.outcome.calibration_version == 5
    assert repository.get_calibration_recovery("calibration-1").pending_commit_input == commit_input


@pytest.mark.parametrize(
    ("corruption", "expected_error"),
    [
        ("missing", NotFoundError),
        ("typed_field", ValueError),
        ("outcome_identity", ValueError),
    ],
)
def test_model_unavailable_latest_checkpoint_integrity_failure_rolls_back(
    repository: FamilyContextRepository,
    database_path: Path,
    corruption: str,
    expected_error: type[Exception],
) -> None:
    receipt = _save_input(repository).receipt
    with connect_database(database_path) as connection:
        if corruption == "missing":
            connection.execute("DROP TRIGGER calibration_checkpoints_no_delete")
            connection.execute(
                "DELETE FROM calibration_checkpoints WHERE calibration_id = ?",
                ("calibration-1",),
            )
        elif corruption == "typed_field":
            connection.execute("DROP TRIGGER calibration_checkpoints_no_update")
            connection.execute(
                """
                UPDATE calibration_checkpoints
                SET occurred_at = 'not-a-timestamp'
                WHERE calibration_id = ?
                """,
                ("calibration-1",),
            )
        else:
            connection.execute("DROP TRIGGER calibration_checkpoints_no_update")
            connection.execute(
                """
                UPDATE calibration_checkpoints
                SET outcome_json = ?
                WHERE calibration_id = ?
                """,
                (
                    json.dumps(
                        {
                            "calibration_id": "different-calibration",
                            "calibration_version": 1,
                            "profile_version": 0,
                            "state": "input_saved",
                            "allowed_actions": ["generate_profile_patch"],
                            "trace_id": "trace-corrupt",
                            "data": {},
                        }
                    ),
                    "calibration-1",
                ),
            )
        before_checkpoints = _count(connection, "calibration_checkpoints")
        before_audits = _count(connection, "calibration_audit_events")

    with pytest.raises(expected_error):
        _mark_unavailable(repository, receipt.id)

    with connect_database(database_path) as connection:
        session = connection.execute(
            "SELECT * FROM calibration_sessions WHERE id = ?",
            ("calibration-1",),
        ).fetchone()
        assert session is not None
        assert int(session["calibration_version"]) == 1
        assert int(session["profile_version"]) == 0
        assert session["state"] == CalibrationState.INPUT_SAVED.value
        assert _count(connection, "calibration_checkpoints") == before_checkpoints
        assert _count(connection, "calibration_audit_events") == before_audits
        assert _count(connection, "calibration_drafts") == 0
        assert _count(connection, "profile_observation_events") == 0


def test_proposal_unavailable_rejects_commit_retry_lineage_without_writes(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    commit_input = _save_commit_input(
        repository,
        draft,
        (draft.observations[0].operation_id,),
    ).input
    _mark_unavailable(
        repository,
        turn_receipt.id,
        expected_calibration_version=2,
        resume_stage="profile_commit",
        pending_entity_id=commit_input.id,
        context=_context("commit-failure-key", trace_id="trace-commit-failure"),
    )
    repository.begin_calibration_retry(
        "calibration-1",
        expected_calibration_version=3,
        context=_context("commit-retry-key", trace_id="trace-commit-retry"),
    )
    before = repository.get_calibration_recovery("calibration-1")
    with connect_database(database_path) as connection:
        checkpoint_count = _count(connection, "calibration_checkpoints")
        audit_count = _count(connection, "calibration_audit_events")

    with pytest.raises(InvalidTransitionError):
        _mark_unavailable(
            repository,
            turn_receipt.id,
            expected_calibration_version=4,
            resume_stage="profile_propose",
            context=_context("wrong-lineage-key", trace_id="trace-wrong-lineage"),
        )

    after = repository.get_calibration_recovery("calibration-1")
    assert after == before
    with connect_database(database_path) as connection:
        assert _count(connection, "calibration_checkpoints") == checkpoint_count
        assert _count(connection, "calibration_audit_events") == audit_count
        assert _count(connection, "profile_observation_events") == 0


def test_replayed_retry_outcome_never_overrides_a_later_unavailable_checkpoint(
    repository: FamilyContextRepository,
) -> None:
    receipt = _save_input(repository).receipt
    _mark_unavailable(repository, receipt.id)
    original_retry = repository.begin_calibration_retry(
        "calibration-1",
        expected_calibration_version=2,
        context=_context("retry-key", trace_id="trace-retry"),
    )
    _mark_unavailable(
        repository,
        receipt.id,
        expected_calibration_version=3,
        error_code="request_timeout",
        context=_context("second-unavailable-key", trace_id="trace-unavailable-2"),
    )

    replay = repository.begin_calibration_retry(
        "calibration-1",
        expected_calibration_version=2,
        context=_context("retry-key", trace_id="trace-retry-replay"),
    )
    recovery = repository.get_calibration_recovery("calibration-1")

    assert replay.delivery.replayed is True
    assert replay.outcome == original_retry.outcome
    assert replay.outcome.state is CalibrationState.RETRY_PENDING
    assert recovery.calibration_version == 4
    assert recovery.latest_checkpoint.state is CalibrationState.MODEL_UNAVAILABLE
    assert recovery.directive is RecoveryDirective.EXPLICIT_RETRY_ALLOWED


def test_concurrent_unavailable_attempts_leave_one_complete_outcome(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    barrier = Barrier(2)

    def attempt(index: int):
        local = FamilyContextRepository(database_path)
        barrier.wait()
        try:
            return local.mark_calibration_model_unavailable(
                "calibration-1",
                receipt.id,
                expected_calibration_version=1,
                error_code=f"failure_{index}",
                context=_context(
                    f"concurrent-unavailable-{index}",
                    trace_id=f"trace-concurrent-{index}",
                ),
            )
        except VersionConflictError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, VersionConflictError) for result in results) == 1
    with connect_database(database_path) as connection:
        assert _count(connection, "calibration_checkpoints") == 2
        assert _count(connection, "calibration_audit_events") == 1
        assert _count(connection, "idempotency_records") == 1
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.calibration_version == 2
    assert recovery.latest_checkpoint.state is CalibrationState.MODEL_UNAVAILABLE


def test_proposal_creates_recoverable_draft_without_confirmed_memory(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt

    delivered = _propose(repository, receipt.id)

    assert delivered.delivery.replayed is False
    assert delivered.outcome.calibration_version == 2
    assert delivered.outcome.profile_version == 0
    assert delivered.outcome.state is CalibrationState.NEEDS_CONFIRMATION
    assert delivered.outcome.allowed_actions == (
        "commit_profile_patch",
        "revise_profile_patch",
        "abandon_profile_patch",
    )
    assert delivered.outcome.trace_id == "trace-proposal"
    assert set(delivered.outcome.data) == {
        "base_profile_version",
        "diff_preview",
        "draft_digest",
        "draft_id",
        "proposal_digest",
        "unapplied_notes",
    }
    assert delivered.outcome.data["unapplied_notes"] == []
    assert delivered.outcome.data["base_profile_version"] == 0
    preview = delivered.outcome.data["diff_preview"]
    assert isinstance(preview, list)
    assert len(preview) == 1
    assert preview[0]["value_text"] == "secure"
    assert preview[0]["operation_id"]

    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.directive is RecoveryDirective.RETURN_STORED
    assert recovery.pending_draft is not None
    assert recovery.pending_draft.id == delivered.outcome.data["draft_id"]
    assert recovery.pending_draft.draft_digest == delivered.outcome.data["draft_digest"]
    assert recovery.pending_draft.proposal_digest == delivered.outcome.data["proposal_digest"]
    assert recovery.pending_draft.revises_draft_id is None
    assert recovery.pending_draft_result == delivered.outcome
    assert recovery.last_outcome == delivered.outcome
    assert recovery.latest_checkpoint.pending_kind is PendingKind.PROFILE_PATCH
    assert recovery.latest_checkpoint.pending_entity_id == recovery.pending_draft.id
    assert recovery.latest_checkpoint.last_stable_calibration_version == 2

    with connect_database(database_path) as connection:
        assert _count(connection, "calibration_drafts") == 1
        assert _count(connection, "profile_versions") == 0
        assert _count(connection, "profile_observation_events") == 0
        assert _count(connection, "calibration_commits") == 0


def test_proposal_ids_and_digests_are_deterministic_across_input_order(
    repository: FamilyContextRepository,
) -> None:
    receipt_1 = _save_input(repository).receipt
    first = _propose(
        repository,
        receipt_1.id,
        observations=(
            _proposal(subject="Mathematics", value_text="secure"),
            _proposal(subject="English", value_text="developing"),
        ),
    )
    receipt_2 = repository.save_calibration_input(
        "calibration-2",
        NOW_TEXT,
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_context("receipt-key-2", trace_id="trace-receipt-2"),
    ).receipt
    second = repository.propose_profile_patch(
        "calibration-2",
        receipt_2.id,
        (
            _proposal(subject="English", value_text="developing"),
            _proposal(subject="Mathematics", value_text="secure"),
        ),
        expected_calibration_version=1,
        context=_context("proposal-key-2", trace_id="trace-proposal-2"),
    )

    recovery_1 = repository.get_calibration_recovery("calibration-1")
    recovery_2 = repository.get_calibration_recovery("calibration-2")
    assert recovery_1.pending_draft is not None
    assert recovery_2.pending_draft is not None
    assert recovery_1.pending_draft.proposal_digest == recovery_2.pending_draft.proposal_digest
    assert recovery_1.pending_draft.draft_digest == recovery_2.pending_draft.draft_digest
    assert [item.operation_id for item in recovery_1.pending_draft.observations] == [
        item.operation_id for item in recovery_2.pending_draft.observations
    ]
    assert first.outcome.data["diff_preview"] == second.outcome.data["diff_preview"]


def test_proposal_replays_before_version_and_changed_payload_conflicts(
    repository: FamilyContextRepository,
) -> None:
    receipt = _save_input(repository).receipt
    original = _propose(repository, receipt.id)

    replay = _propose(
        repository,
        receipt.id,
        context=_context("proposal-key", trace_id="trace-proposal-replay"),
    )
    assert replay.delivery.replayed is True
    assert replay.outcome == original.outcome
    assert replay.outcome.trace_id == "trace-proposal"

    with pytest.raises(IdempotencyConflictError):
        _propose(
            repository,
            receipt.id,
            observations=(_proposal(value_text="developing"),),
        )
    assert repository.get_calibration_recovery("calibration-1").calibration_version == 2


def test_second_plain_proposal_cannot_replace_pending_draft_without_revision_lineage(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    original = _pending_draft(repository)
    before = _family_row_counts(database_path)

    with pytest.raises(InvalidTransitionError):
        _propose(
            repository,
            receipt.id,
            observations=(_proposal(value_text="replacement without revision"),),
            expected_calibration_version=2,
            context=_context("second-plain-proposal"),
        )

    assert _family_row_counts(database_path) == before
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.calibration_version == 2
    assert recovery.pending_draft == original


def test_concurrent_different_key_proposals_create_only_one_pending_draft(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    barrier = Barrier(2)

    def attempt(index: int):
        local = FamilyContextRepository(database_path)
        barrier.wait()
        try:
            return local.propose_profile_patch(
                "calibration-1",
                receipt.id,
                (_proposal(value_text=f"level-{index}"),),
                expected_calibration_version=1,
                context=_context(
                    f"concurrent-proposal-{index}",
                    trace_id=f"trace-proposal-{index}",
                ),
            )
        except VersionConflictError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, VersionConflictError) for result in results) == 1
    with connect_database(database_path) as connection:
        assert _count(connection, "calibration_drafts") == 1
        assert _count(connection, "calibration_checkpoints") == 2
        assert _count(connection, "idempotency_records") == 1
        assert _count(connection, "profile_observation_events") == 0


def test_revise_appends_new_draft_and_old_draft_becomes_read_only(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    first = repository.get_calibration_recovery("calibration-1").pending_draft
    assert first is not None

    revised = repository.revise_profile_patch(
        "calibration-1",
        first.id,
        (_proposal(value_text="developing"),),
        expected_calibration_version=2,
        context=_context("revise-key", trace_id="trace-revise"),
    )

    assert revised.outcome.calibration_version == 3
    assert revised.outcome.profile_version == 0
    assert revised.outcome.state is CalibrationState.NEEDS_CONFIRMATION
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.pending_draft is not None
    assert recovery.pending_draft.id != first.id
    assert recovery.pending_draft.revises_draft_id == first.id
    assert recovery.pending_draft.observations[0].value_text == "developing"
    with connect_database(database_path) as connection:
        assert _count(connection, "calibration_drafts") == 2
        assert _count(connection, "profile_observation_events") == 0

    with pytest.raises(InvalidTransitionError) as captured:
        repository.revise_profile_patch(
            "calibration-1",
            first.id,
            (_proposal(value_text="old draft write"),),
            expected_calibration_version=3,
            context=_context("old-revise-key"),
        )
    assert captured.value.current_stage == CalibrationState.NEEDS_CONFIRMATION.value
    assert captured.value.requested_stage == "revise_profile_patch"
    with connect_database(database_path) as connection:
        assert _count(connection, "calibration_drafts") == 2
        assert _count(connection, "idempotency_records") == 2
        assert _count(connection, "profile_observation_events") == 0
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.calibration_version == 3
    assert recovery.profile_version == 0


def test_abandon_pending_patch_advances_calibration_only_and_writes_no_memory(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    pending = repository.get_calibration_recovery("calibration-1").pending_draft
    assert pending is not None

    abandoned = repository.abandon_profile_patch(
        "calibration-1",
        expected_calibration_version=2,
        context=_context("abandon-key", trace_id="trace-abandon"),
    )

    assert abandoned.outcome.calibration_version == 3
    assert abandoned.outcome.profile_version == 0
    assert abandoned.outcome.state is CalibrationState.ABANDONED
    assert abandoned.outcome.allowed_actions == ("start_calibration",)
    assert abandoned.outcome.data == {
        "abandoned_pending_entity_id": pending.id,
        "abandoned_pending_kind": PendingKind.PROFILE_PATCH.value,
    }
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.directive is RecoveryDirective.RETURN_STORED
    assert recovery.pending_draft is None
    assert recovery.latest_checkpoint.pending_kind is None
    assert recovery.latest_checkpoint.pending_entity_id is None
    with connect_database(database_path) as connection:
        assert _count(connection, "calibration_drafts") == 1
        assert _count(connection, "calibration_commits") == 0
        assert _count(connection, "profile_versions") == 0
        assert _count(connection, "profile_observation_events") == 0


@pytest.mark.parametrize("retry_first", [False, True])
def test_abandon_is_available_from_model_failure_and_retry_pending(
    repository: FamilyContextRepository,
    retry_first: bool,
) -> None:
    receipt = _save_input(repository).receipt
    _mark_unavailable(repository, receipt.id)
    expected = 2
    if retry_first:
        repository.begin_calibration_retry(
            "calibration-1",
            expected_calibration_version=2,
            context=_context("retry-before-abandon"),
        )
        expected = 3

    result = repository.abandon_profile_patch(
        "calibration-1",
        expected_calibration_version=expected,
        context=_context("abandon-after-failure"),
    )

    assert result.outcome.state is CalibrationState.ABANDONED
    assert result.outcome.calibration_version == expected + 1
    assert result.outcome.profile_version == 0


def test_commit_atomically_advances_both_versions_and_confirmed_readers(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    operation_id = draft.observations[0].operation_id

    delivered = _commit(repository, draft.id, (operation_id,))

    assert delivered.delivery.replayed is False
    assert delivered.outcome.calibration_version == 3
    assert delivered.outcome.profile_version == 1
    assert delivered.outcome.state is CalibrationState.COMMITTED
    assert delivered.outcome.allowed_actions == ("start_calibration",)
    assert delivered.outcome.trace_id == "trace-commit"
    assert set(delivered.outcome.data) == {
        "accepted_observations",
        "commit",
        "draft_digest",
    }
    commit = delivered.outcome.data["commit"]
    assert commit["calibration_id"] == "calibration-1"
    assert commit["draft_id"] == draft.id
    assert commit["accepted_operation_ids"] == [operation_id]
    assert commit["confirmed_by"] == "parent-1"
    assert commit["profile_version"] == 1
    accepted = delivered.outcome.data["accepted_observations"]
    assert len(accepted) == 1
    assert accepted[0]["operation_id"] == operation_id
    assert accepted[0]["profile_version"] == 1
    assert accepted[0]["canonical_order"] == 0
    assert accepted[0]["source"] == Source.PARENT.value
    assert accepted[0]["evidence_level"] == ObservationEvidenceLevel.PARENT_CONFIRMED.value
    assert accepted[0]["confirmed_by"] == "parent-1"
    assert accepted[0]["id"] != operation_id

    assert repository.get_current_profile_version() == 1
    versions, events = repository.list_profile_history()
    assert len(versions) == 1
    assert versions[0].profile_version == 1
    assert versions[0].commit_id == commit["id"]
    assert versions[0].reason == "parent_confirmed_patch"
    assert len(events) == 1
    assert events[0].id == accepted[0]["id"]
    assert events[0].committed_at == versions[0].committed_at

    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.calibration_version == 3
    assert recovery.profile_version == 1
    assert recovery.latest_checkpoint.state is CalibrationState.COMMITTED
    assert recovery.latest_checkpoint.profile_version == 1
    assert recovery.latest_checkpoint.last_stable_calibration_version == 3
    assert recovery.latest_checkpoint.last_stable_profile_version == 1
    assert recovery.pending_draft is None
    assert recovery.directive is RecoveryDirective.RETURN_STORED
    assert recovery.last_outcome == delivered.outcome

    with connect_database(database_path) as connection:
        assert _count(connection, "calibration_commits") == 1
        assert _count(connection, "profile_versions") == 1
        assert _count(connection, "profile_observation_events") == 1
        assert _count(connection, "calibration_drafts") == 1
        stored_draft = connection.execute(
            "SELECT draft_digest FROM calibration_drafts WHERE id = ?",
            (draft.id,),
        ).fetchone()
        assert stored_draft is not None
        assert stored_draft["draft_digest"] == draft.draft_digest
        stored_event = connection.execute(
            "SELECT operation_id FROM profile_observation_events WHERE id = ?",
            (events[0].id,),
        ).fetchone()
        assert stored_event is not None
        assert stored_event["operation_id"] == operation_id


def test_confirmed_readers_exclude_unconfirmed_drafts_and_survive_restart(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)

    assert repository.get_current_profile_version() == 0
    assert repository.list_profile_history() == ((), ())

    draft = _pending_draft(repository)
    _commit(repository, draft.id, (draft.observations[0].operation_id,))
    restarted = FamilyContextRepository(database_path)

    assert restarted.get_current_profile_version() == 1
    versions, events = restarted.list_profile_history()
    assert tuple(item.profile_version for item in versions) == (1,)
    assert tuple(item.profile_version for item in events) == (1,)


def test_commit_replay_lookup_is_read_only_and_precedes_current_version(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(
        repository,
        receipt.id,
        observations=(
            _proposal(subject="Mathematics"),
            _proposal(subject="English", value_text="developing"),
        ),
    )
    draft = _pending_draft(repository)
    accepted = tuple(item.operation_id for item in draft.observations)
    lookup_context = _context("commit-key", trace_id="trace-lookup")

    before = _family_row_counts(database_path)
    assert (
        repository.lookup_commit_profile_patch(
            "calibration-1",
            draft.id,
            tuple(reversed(accepted)),
            draft_digest=draft.draft_digest,
            expected_calibration_version=2,
            context=lookup_context,
        )
        is None
    )
    assert _family_row_counts(database_path) == before

    original = _commit(repository, draft.id, tuple(reversed(accepted)))
    after_commit = _family_row_counts(database_path)
    replay = repository.lookup_commit_profile_patch(
        "calibration-1",
        draft.id,
        accepted,
        draft_digest=draft.draft_digest,
        expected_calibration_version=2,
        context=_context("commit-key", trace_id="trace-lookup-replay"),
    )

    assert replay is not None
    assert replay.delivery.replayed is True
    assert replay.outcome == original.outcome
    assert replay.outcome.trace_id == "trace-commit"
    assert _family_row_counts(database_path) == after_commit

    with pytest.raises(IdempotencyConflictError):
        repository.lookup_commit_profile_patch(
            "calibration-1",
            draft.id,
            (accepted[0],),
            draft_digest=draft.draft_digest,
            expected_calibration_version=2,
            context=_context("commit-key"),
        )
    assert _family_row_counts(database_path) == after_commit


def test_commit_lookup_includes_digest_and_never_infers_or_mutates(
    repository: FamilyContextRepository,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    context = _context("commit-digest-key", trace_id="trace-commit")

    assert (
        repository.lookup_commit_profile_patch(
            "calibration-1",
            draft.id,
            accepted,
            draft_digest=draft.draft_digest,
            expected_calibration_version=2,
            context=context,
        )
        is None
    )
    committed = repository.commit_profile_patch(
        "calibration-1",
        draft.id,
        accepted,
        draft_digest=draft.draft_digest,
        expected_calibration_version=2,
        context=context,
    )
    replay = repository.lookup_commit_profile_patch(
        "calibration-1",
        draft.id,
        accepted,
        draft_digest=draft.draft_digest,
        expected_calibration_version=2,
        context=context,
    )

    assert replay is not None
    assert replay.outcome == committed.outcome
    assert replay.delivery.replayed is True


@pytest.mark.parametrize(
    "method_name",
    ["lookup_commit_profile_patch", "commit_profile_patch"],
)
def test_commit_digest_identity_conflicts_for_known_key_and_mismatches_for_new_key(
    repository: FamilyContextRepository,
    database_path: Path,
    method_name: str,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    _commit(
        repository,
        draft.id,
        accepted,
        context=_context("digest-established-key"),
    )
    before = _family_row_counts(database_path)

    with pytest.raises(IdempotencyConflictError) as known:
        _call_commit_boundary(
            repository,
            method_name,
            "calibration-1",
            draft.id,
            accepted,
            draft_digest="0" * 64,
            expected_calibration_version=2,
            context=_context("digest-established-key"),
        )
    assert known.value.idempotency_key == "<redacted>"

    with pytest.raises(DraftDigestMismatchError) as fresh:
        _call_commit_boundary(
            repository,
            method_name,
            "calibration-1",
            draft.id,
            accepted,
            draft_digest="0" * 64,
            expected_calibration_version=3,
            context=_context(f"wrong-digest-{method_name}"),
        )
    assert fresh.value.draft_id == draft.id
    assert _family_row_counts(database_path) == before
    assert repository.get_current_profile_version() == 1
    assert repository.get_calibration_recovery("calibration-1").calibration_version == 3


@pytest.mark.parametrize(
    "method_name",
    ["lookup_commit_profile_patch", "commit_profile_patch"],
)
def test_commit_command_invalid_maps_only_new_key_ids_outside_draft(
    repository: FamilyContextRepository,
    database_path: Path,
    method_name: str,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    before = _family_row_counts(database_path)

    with pytest.raises(CommitCommandInvalidError) as captured:
        _call_commit_boundary(
            repository,
            method_name,
            "calibration-1",
            draft.id,
            ("not-in-draft",),
            draft_digest=draft.draft_digest,
            expected_calibration_version=2,
            context=_context(f"new-invalid-{method_name}"),
        )

    assert captured.value.reason_code == "accepted_ids_not_in_draft"
    assert _family_row_counts(database_path) == before
    assert repository.get_current_profile_version() == 0


@pytest.mark.parametrize(
    ("method_name", "invalid_kind"),
    [
        ("lookup_commit_profile_patch", "empty"),
        ("lookup_commit_profile_patch", "duplicate"),
        ("lookup_commit_profile_patch", "outside"),
        ("commit_profile_patch", "empty"),
        ("commit_profile_patch", "duplicate"),
        ("commit_profile_patch", "outside"),
    ],
)
def test_commit_command_invalid_known_key_is_always_sanitized_conflict(
    repository: FamilyContextRepository,
    database_path: Path,
    method_name: str,
    invalid_kind: str,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    context = _context("invalid-canonical-established")
    _commit(repository, draft.id, accepted, context=context)
    invalid = {
        "empty": (),
        "duplicate": accepted * 2,
        "outside": ("not-in-draft",),
    }[invalid_kind]
    before = _family_row_counts(database_path)

    with pytest.raises(IdempotencyConflictError) as captured:
        _call_commit_boundary(
            repository,
            method_name,
            "calibration-1",
            draft.id,
            invalid,
            draft_digest=draft.draft_digest,
            expected_calibration_version=2,
            context=context,
        )

    assert captured.value.idempotency_key == "<redacted>"
    assert _family_row_counts(database_path) == before


@pytest.mark.parametrize(
    "method_name",
    ["lookup_commit_profile_patch", "commit_profile_patch"],
)
def test_commit_command_invalid_does_not_catch_unrelated_value_error(
    repository: FamilyContextRepository,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
) -> None:
    from backend.storage import family_context as family_module

    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    before = _family_row_counts(database_path)

    def fail_canonicalization(*args, **kwargs):
        raise ValueError("unrelated canonicalization programming error")

    monkeypatch.setattr(
        family_module,
        "_canonicalize_accepted_ids",
        fail_canonicalization,
    )
    with pytest.raises(ValueError, match="unrelated canonicalization") as captured:
        _call_commit_boundary(
            repository,
            method_name,
            "calibration-1",
            draft.id,
            (draft.observations[0].operation_id,),
            draft_digest=draft.draft_digest,
            expected_calibration_version=2,
            context=_context(f"unknown-value-error-{method_name}"),
        )

    assert type(captured.value) is ValueError
    assert _family_row_counts(database_path) == before


@pytest.mark.parametrize(
    "method_name",
    ["lookup_commit_profile_patch", "commit_profile_patch"],
)
def test_commit_lookup_missing_and_foreign_drafts_are_indistinguishable(
    repository: FamilyContextRepository,
    database_path: Path,
    method_name: str,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    receipt_2 = repository.save_calibration_input(
        "calibration-2",
        "Second calibration input",
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_context("foreign-receipt"),
    ).receipt
    repository.propose_profile_patch(
        "calibration-2",
        receipt_2.id,
        (_proposal(subject="English"),),
        expected_calibration_version=1,
        context=_context("foreign-proposal"),
    )
    foreign = _pending_draft(repository, "calibration-2")
    before = _family_row_counts(database_path)

    for draft_id, digest in (
        ("missing-draft", "0" * 64),
        (foreign.id, foreign.draft_digest),
    ):
        with pytest.raises(NotFoundError) as captured:
            _call_commit_boundary(
                repository,
                method_name,
                "calibration-1",
                draft_id,
                (foreign.observations[0].operation_id,),
                draft_digest=digest,
                expected_calibration_version=2,
                context=_context(f"missing-foreign-{method_name}-{draft_id}"),
            )
        assert captured.value.entity == "calibration draft"
        assert captured.value.entity_id == draft_id

    repository.save_calibration_input(
        "calibration-without-draft",
        "Input only",
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_context("input-only"),
    )
    with pytest.raises(NotFoundError):
        _call_commit_boundary(
            repository,
            method_name,
            "calibration-without-draft",
            "missing-after-input",
            ("not-in-draft",),
            draft_digest="0" * 64,
            expected_calibration_version=1,
            context=_context(f"input-only-{method_name}"),
        )
    assert _family_row_counts(database_path)["calibration_commits"] == before["calibration_commits"]
    assert repository.get_current_profile_version() == 0


@pytest.mark.parametrize(
    "method_name",
    ["lookup_commit_profile_patch", "commit_profile_patch"],
)
def test_commit_lookup_known_key_mismatch_never_queries_draft(
    repository: FamilyContextRepository,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
) -> None:
    from backend.storage import family_context as family_module

    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    foreign_receipt = repository.save_calibration_input(
        "calibration-2",
        "Foreign replay calibration",
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_context("foreign-replay-receipt"),
    ).receipt
    repository.propose_profile_patch(
        "calibration-2",
        foreign_receipt.id,
        (_proposal(subject="English"),),
        expected_calibration_version=1,
        context=_context("foreign-replay-proposal"),
    )
    foreign_draft = _pending_draft(repository, "calibration-2")
    context = _context("draft-query-established")
    _commit(repository, draft.id, accepted, context=context)
    before = _family_row_counts(database_path)
    calls = 0
    original = family_module._require_draft

    def spy_require_draft(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(family_module, "_require_draft", spy_require_draft)
    for changed_id in ("missing-draft", foreign_draft.id):
        with pytest.raises(IdempotencyConflictError):
            _call_commit_boundary(
                repository,
                method_name,
                "calibration-1",
                changed_id,
                accepted,
                draft_digest=draft.draft_digest,
                expected_calibration_version=2,
                context=context,
            )

    assert calls == 0
    assert _family_row_counts(database_path) == before


@pytest.mark.parametrize(
    ("method_name", "stale_kind"),
    [
        ("lookup_commit_profile_patch", "superseded"),
        ("lookup_commit_profile_patch", "abandoned"),
        ("lookup_commit_profile_patch", "committed"),
        ("commit_profile_patch", "superseded"),
        ("commit_profile_patch", "abandoned"),
        ("commit_profile_patch", "committed"),
    ],
)
def test_commit_lookup_real_noncurrent_draft_is_invalid_transition(
    repository: FamilyContextRepository,
    database_path: Path,
    method_name: str,
    stale_kind: str,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    if stale_kind == "superseded":
        repository.revise_profile_patch(
            "calibration-1",
            draft.id,
            (_proposal(value_text="developing"),),
            expected_calibration_version=2,
            context=_context("make-superseded"),
        )
    elif stale_kind == "abandoned":
        repository.abandon_profile_patch(
            "calibration-1",
            expected_calibration_version=2,
            context=_context("make-abandoned"),
        )
    else:
        _commit(
            repository,
            draft.id,
            accepted,
            context=_context("make-committed"),
        )
    before = _family_row_counts(database_path)

    with pytest.raises(InvalidTransitionError) as captured:
        _call_commit_boundary(
            repository,
            method_name,
            "calibration-1",
            draft.id,
            accepted,
            draft_digest=draft.draft_digest,
            expected_calibration_version=3,
            context=_context(f"stale-{method_name}-{stale_kind}"),
        )

    assert captured.value.requested_stage == "commit_profile_patch"
    assert _family_row_counts(database_path) == before


@pytest.mark.parametrize(
    "corruption",
    [
        "nested_profile_version",
        "accepted_operation_payload",
        "commit_id_link",
        "canonical_order",
        "allowed_actions",
    ],
)
def test_commit_lookup_corrupt_stored_outcome_is_integrity_error(
    repository: FamilyContextRepository,
    database_path: Path,
    corruption: str,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    context = _context("corrupt-commit-outcome")
    _commit(repository, draft.id, accepted, context=context)
    with connect_database(database_path) as connection:
        row = connection.execute(
            """
            SELECT response_json
            FROM idempotency_records
            WHERE operation = 'commit_profile_patch'
            """
        ).fetchone()
        assert row is not None
        stored = json.loads(str(row["response_json"]))
        if corruption == "nested_profile_version":
            stored["outcome"]["data"]["commit"]["profile_version"] = 2
        elif corruption == "accepted_operation_payload":
            stored["outcome"]["data"]["accepted_observations"][0]["operation_id"] = (
                "different-operation"
            )
        elif corruption == "commit_id_link":
            stored["outcome"]["data"]["commit"]["id"] = "different-commit"
        elif corruption == "canonical_order":
            stored["outcome"]["data"]["accepted_observations"][0]["canonical_order"] = 5
        else:
            stored["outcome"]["allowed_actions"] = ["commit_profile_patch"]
        connection.execute(
            """
            UPDATE idempotency_records
            SET response_json = ?
            WHERE operation = 'commit_profile_patch'
            """,
            (json.dumps(stored),),
        )

    with pytest.raises(ValueError) as captured:
        repository.lookup_commit_profile_patch(
            "calibration-1",
            draft.id,
            accepted,
            draft_digest=draft.draft_digest,
            expected_calibration_version=2,
            context=context,
        )

    assert type(captured.value) is ValueError


def test_commit_replay_returns_original_outcome_and_trace_is_not_hashed(
    repository: FamilyContextRepository,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    original = _commit(repository, draft.id, accepted)

    replay = _commit(
        repository,
        draft.id,
        accepted,
        context=_context("commit-key", trace_id="different-trace"),
    )

    assert replay.delivery.replayed is True
    assert replay.outcome == original.outcome
    assert repository.get_current_profile_version() == 1
    assert repository.get_calibration_recovery("calibration-1").calibration_version == 3


@pytest.mark.parametrize(
    ("accepted_selector", "reason_code"),
    [
        (lambda draft: (), None),
        (lambda draft: (draft.observations[0].operation_id,) * 2, None),
        (lambda draft: ("unknown-operation",), "accepted_ids_not_in_draft"),
    ],
)
def test_commit_rejects_empty_duplicate_and_unknown_accepted_ids_without_writes(
    repository: FamilyContextRepository,
    database_path: Path,
    accepted_selector,
    reason_code: str | None,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    before = _family_row_counts(database_path)

    if reason_code is None:
        with pytest.raises(ValueError):
            _commit(repository, draft.id, accepted_selector(draft))
    else:
        with pytest.raises(CommitCommandInvalidError) as captured:
            _commit(repository, draft.id, accepted_selector(draft))
        assert captured.value.reason_code == reason_code

    assert _family_row_counts(database_path) == before
    assert repository.get_current_profile_version() == 0
    assert repository.get_calibration_recovery("calibration-1").calibration_version == 2


def test_accepted_subset_is_committed_in_stored_draft_order(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(
        repository,
        receipt.id,
        observations=(
            _proposal(subject="Mathematics", value_text="secure"),
            _proposal(subject="English", value_text="developing"),
            _proposal(subject="Chinese", value_text="secure"),
        ),
    )
    draft = _pending_draft(repository)
    selected = (draft.observations[2].operation_id, draft.observations[0].operation_id)

    delivered = _commit(repository, draft.id, selected)

    expected = (
        draft.observations[0].operation_id,
        draft.observations[2].operation_id,
    )
    assert tuple(delivered.outcome.data["commit"]["accepted_operation_ids"]) == expected
    _, events = repository.list_profile_history()
    assert tuple(item.canonical_order for item in events) == (0, 1)
    with connect_database(database_path) as connection:
        rows = connection.execute(
            """
            SELECT operation_id
            FROM profile_observation_events
            ORDER BY profile_version, canonical_order
            """
        ).fetchall()
    assert tuple(str(row["operation_id"]) for row in rows) == expected


def test_commit_requires_trusted_parent_role_and_uses_context_actor(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    before = _family_row_counts(database_path)

    with pytest.raises(ValueError, match="parent role"):
        _commit(
            repository,
            draft.id,
            accepted,
            context=_context("non-parent-key", actor="model", role="system"),
        )
    assert _family_row_counts(database_path) == before

    result = _commit(
        repository,
        draft.id,
        accepted,
        context=_context("parent-commit-key", actor="parent-confirmed", role="parent"),
    )
    assert result.outcome.data["commit"]["confirmed_by"] == "parent-confirmed"
    _, events = repository.list_profile_history()
    assert events[0].confirmed_by == "parent-confirmed"


def test_future_dated_evidence_is_rejected_at_commit_without_partial_writes(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(
        repository,
        receipt.id,
        observations=(_proposal(observed_at=datetime(2100, 1, 1, tzinfo=UTC)),),
    )
    draft = _pending_draft(repository)
    before = _family_row_counts(database_path)

    with pytest.raises(ValueError, match="future"):
        _commit(repository, draft.id, (draft.observations[0].operation_id,))

    assert _family_row_counts(database_path) == before
    assert repository.get_current_profile_version() == 0


def test_revised_old_draft_cannot_be_committed_and_leaves_no_writes(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    old_draft = _pending_draft(repository)
    repository.revise_profile_patch(
        "calibration-1",
        old_draft.id,
        (_proposal(value_text="developing"),),
        expected_calibration_version=2,
        context=_context("revise-key"),
    )
    before = _family_row_counts(database_path)

    with pytest.raises(InvalidTransitionError) as captured:
        _commit(
            repository,
            old_draft.id,
            (old_draft.observations[0].operation_id,),
            expected_calibration_version=3,
            context=_context("old-draft-commit"),
        )

    assert captured.value.current_stage == CalibrationState.NEEDS_CONFIRMATION.value
    assert captured.value.requested_stage == "commit_profile_patch"
    assert _family_row_counts(database_path) == before
    assert repository.get_current_profile_version() == 0
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.calibration_version == 3
    assert recovery.profile_version == 0


def test_draft_based_on_old_profile_cannot_commit_after_another_calibration(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt_1 = _save_input(repository).receipt
    _propose(repository, receipt_1.id)
    draft_1 = _pending_draft(repository)

    receipt_2 = repository.save_calibration_input(
        "calibration-2",
        "Second calibration input",
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_context("receipt-2"),
    ).receipt
    repository.propose_profile_patch(
        "calibration-2",
        receipt_2.id,
        (_proposal(subject="English"),),
        expected_calibration_version=1,
        context=_context("proposal-2"),
    )
    draft_2 = _pending_draft(repository, "calibration-2")
    _commit(repository, draft_1.id, (draft_1.observations[0].operation_id,))
    before = _family_row_counts(database_path)

    with pytest.raises(VersionConflictError) as captured:
        _commit(
            repository,
            draft_2.id,
            (draft_2.observations[0].operation_id,),
            calibration_id="calibration-2",
            context=_context("commit-2"),
        )

    assert captured.value.entity == "profile"
    assert captured.value.expected_version == 0
    assert captured.value.actual_version == 1
    assert _family_row_counts(database_path) == before


def test_stale_pending_calibration_can_still_be_abandoned_without_memory_write(
    repository: FamilyContextRepository,
) -> None:
    receipt_1 = _save_input(repository).receipt
    _propose(repository, receipt_1.id)
    draft_1 = _pending_draft(repository)

    receipt_2 = repository.save_calibration_input(
        "calibration-2",
        "Second calibration input",
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_context("receipt-2"),
    ).receipt
    repository.propose_profile_patch(
        "calibration-2",
        receipt_2.id,
        (_proposal(subject="English"),),
        expected_calibration_version=1,
        context=_context("proposal-2"),
    )
    _commit(repository, draft_1.id, (draft_1.observations[0].operation_id,))

    abandoned = repository.abandon_profile_patch(
        "calibration-2",
        expected_calibration_version=2,
        context=_context("abandon-stale-calibration"),
    )

    assert abandoned.outcome.state is CalibrationState.ABANDONED
    assert abandoned.outcome.calibration_version == 3
    assert abandoned.outcome.profile_version == 1
    assert repository.get_current_profile_version() == 1
    versions, events = repository.list_profile_history()
    assert len(versions) == 1
    assert len(events) == 1


def test_concurrent_different_key_commits_mint_one_profile_version(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    barrier = Barrier(2)

    def attempt(index: int):
        local = FamilyContextRepository(database_path)
        barrier.wait()
        try:
            return _commit(
                local,
                draft.id,
                accepted,
                context=_context(f"concurrent-commit-{index}"),
            )
        except VersionConflictError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, VersionConflictError) for result in results) == 1
    assert repository.get_current_profile_version() == 1
    with connect_database(database_path) as connection:
        assert _count(connection, "calibration_commits") == 1
        assert _count(connection, "profile_versions") == 1
        assert _count(connection, "profile_observation_events") == 1
        assert _count(connection, "idempotency_records") == 2


def test_proposal_validates_target_exists_is_active_and_identity_matches(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt_1 = _save_input(repository).receipt
    _propose(repository, receipt_1.id)
    draft_1 = _pending_draft(repository)
    _commit(repository, draft_1.id, (draft_1.observations[0].operation_id,))
    _, events = repository.list_profile_history()
    target = events[0]

    receipt_2 = repository.save_calibration_input(
        "calibration-2",
        "Follow-up calibration",
        expected_calibration_version=0,
        expected_profile_version=1,
        context=_context("receipt-follow-up"),
    ).receipt
    before = _family_row_counts(database_path)
    mismatched = _proposal(
        action=ProfilePatchAction.SUPERSEDE,
        subject="English",
        value_text="developing",
        target_event_id=target.id,
    )
    with pytest.raises(ProfileProposalInvalidError) as mismatched_error:
        repository.propose_profile_patch(
            "calibration-2",
            receipt_2.id,
            (mismatched,),
            expected_calibration_version=1,
            context=_context("mismatched-target"),
        )
    assert mismatched_error.value.reason_code == "broken_identity"
    assert _family_row_counts(database_path) == before

    broken = _proposal(
        action=ProfilePatchAction.REVOKE,
        value_text=None,
        target_event_id="missing-event",
    )
    with pytest.raises(ProfileProposalInvalidError) as broken_error:
        repository.propose_profile_patch(
            "calibration-2",
            receipt_2.id,
            (broken,),
            expected_calibration_version=1,
            context=_context("broken-target"),
        )
    assert broken_error.value.reason_code == "unsupported_target"
    assert _family_row_counts(database_path) == before


@pytest.mark.parametrize(
    ("failure_kind", "reason_code"),
    [
        ("unsupported_target", "unsupported_target"),
        ("broken_identity", "broken_identity"),
    ],
)
def test_proposal_invalid_known_target_failures_are_typed_and_roll_back(
    repository: FamilyContextRepository,
    database_path: Path,
    failure_kind: str,
    reason_code: str,
) -> None:
    target = _commit_initial_assertion(repository)
    receipt = repository.save_calibration_input(
        "calibration-2",
        "Follow-up calibration",
        expected_calibration_version=0,
        expected_profile_version=1,
        context=_context("typed-proposal-receipt"),
    ).receipt
    if failure_kind == "unsupported_target":
        invalid = _proposal(
            action=ProfilePatchAction.REVOKE,
            value_text=None,
            target_event_id="missing-event",
        )
    else:
        invalid = _proposal(
            action=ProfilePatchAction.SUPERSEDE,
            subject="English",
            value_text="developing",
            target_event_id=target.id,
        )
    before = _family_row_counts(database_path)

    with pytest.raises(ProfileProposalInvalidError) as captured:
        repository.propose_profile_patch(
            "calibration-2",
            receipt.id,
            (invalid,),
            expected_calibration_version=1,
            context=_context(f"typed-{failure_kind}"),
        )

    assert captured.value.reason_code == reason_code
    assert _family_row_counts(database_path) == before


@pytest.mark.parametrize(
    ("updates", "reason_code"),
    [
        ({"subject": "hopeless"}, "forbidden_label"),
        (
            {
                "category": MemoryCategory.BEHAVIOR,
                "metric": "assessment_level",
            },
            "invalid_metric_value_relation",
        ),
    ],
)
def test_proposal_invalid_known_contract_failures_are_typed_and_roll_back(
    repository: FamilyContextRepository,
    database_path: Path,
    updates: dict[str, object],
    reason_code: str,
) -> None:
    receipt = _save_input(repository).receipt
    invalid = _proposal().model_copy(update=updates)
    before = _family_row_counts(database_path)

    with pytest.raises(ProfileProposalInvalidError) as captured:
        repository.propose_profile_patch(
            "calibration-1",
            receipt.id,
            (invalid,),
            expected_calibration_version=1,
            context=_context(f"typed-contract-{reason_code}"),
        )

    assert captured.value.reason_code == reason_code
    assert _family_row_counts(database_path) == before


@pytest.mark.parametrize(
    "injected",
    [
        ValueError("unknown proposal value error"),
        sqlite3.OperationalError("injected sqlite failure"),
        RuntimeError("injected programming failure"),
    ],
)
def test_proposal_invalid_unknown_failures_keep_original_type(
    repository: FamilyContextRepository,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    injected: Exception,
) -> None:
    from backend.storage import family_context as family_module

    receipt = _save_input(repository).receipt
    before = _family_row_counts(database_path)

    def fail_validation(*args, **kwargs):
        raise injected

    monkeypatch.setattr(family_module, "_validate_proposed_targets", fail_validation)
    with pytest.raises(type(injected)) as captured:
        _propose(
            repository,
            receipt.id,
            context=_context(f"unknown-proposal-{type(injected).__name__}"),
        )

    assert captured.value is injected
    assert _family_row_counts(database_path) == before


def test_proposal_invalid_classification_never_scans_rendered_input_values(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    receipt = _save_input(repository).receipt
    invalid = _proposal().model_copy(update={"target_event_id": "text metric"})
    before = _family_row_counts(database_path)

    with pytest.raises(ValueError) as captured:
        _propose(
            repository,
            receipt.id,
            observations=(invalid,),
            context=_context("proposal-input-value-marker"),
        )

    assert not isinstance(captured.value, ProfileProposalInvalidError)
    assert _family_row_counts(database_path) == before


def test_commit_rejects_duplicate_target_consumption_before_any_insert(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    target = _commit_initial_assertion(repository)
    receipt = repository.save_calibration_input(
        "calibration-2",
        "Follow-up calibration",
        expected_calibration_version=0,
        expected_profile_version=1,
        context=_context("receipt-follow-up"),
    ).receipt
    supersede = _proposal(
        action=ProfilePatchAction.SUPERSEDE,
        value_text="developing",
        target_event_id=target.id,
    )
    revoke = _proposal(
        action=ProfilePatchAction.REVOKE,
        value_text=None,
        target_event_id=target.id,
    )
    repository.propose_profile_patch(
        "calibration-2",
        receipt.id,
        (supersede, revoke),
        expected_calibration_version=1,
        context=_context("double-target-proposal"),
    )
    draft = _pending_draft(repository, "calibration-2")
    before = _family_row_counts(database_path)

    with pytest.raises(ValueError, match="consumed"):
        _commit(
            repository,
            draft.id,
            tuple(item.operation_id for item in draft.observations),
            calibration_id="calibration-2",
            context=_context("double-target-commit"),
        )

    assert _family_row_counts(database_path) == before
    assert repository.get_current_profile_version() == 1


def test_valid_supersession_is_append_only_and_reader_returns_full_history(
    repository: FamilyContextRepository,
) -> None:
    target = _commit_initial_assertion(repository)
    receipt = repository.save_calibration_input(
        "calibration-2",
        "Follow-up calibration",
        expected_calibration_version=0,
        expected_profile_version=1,
        context=_context("receipt-follow-up"),
    ).receipt
    repository.propose_profile_patch(
        "calibration-2",
        receipt.id,
        (
            _proposal(
                action=ProfilePatchAction.SUPERSEDE,
                value_text="developing",
                target_event_id=target.id,
            ),
        ),
        expected_calibration_version=1,
        context=_context("supersede-proposal"),
    )
    draft = _pending_draft(repository, "calibration-2")
    _commit(
        repository,
        draft.id,
        (draft.observations[0].operation_id,),
        calibration_id="calibration-2",
        context=_context("supersede-commit"),
    )

    assert repository.get_current_profile_version() == 2
    versions, events = repository.list_profile_history()
    assert tuple(item.profile_version for item in versions) == (1, 2)
    assert len(events) == 2
    assert events[0] == target
    assert events[1].action is ProfilePatchAction.SUPERSEDE
    assert events[1].target_event_id == target.id
    capped_versions, capped_events = repository.list_profile_history(1)
    assert capped_versions == (versions[0],)
    assert capped_events == (events[0],)


def test_profile_snapshot_returns_exact_historical_active_observations(
    repository: FamilyContextRepository,
) -> None:
    first_event = _commit_initial_assertion(repository)
    receipt = repository.save_calibration_input(
        "calibration-2",
        "Follow-up calibration",
        expected_calibration_version=0,
        expected_profile_version=1,
        context=_context("snapshot-follow-up-receipt"),
    ).receipt
    repository.propose_profile_patch(
        "calibration-2",
        receipt.id,
        (
            _proposal(
                action=ProfilePatchAction.SUPERSEDE,
                value_text="developing",
                target_event_id=first_event.id,
            ),
        ),
        expected_calibration_version=1,
        context=_context("snapshot-follow-up-proposal"),
    )
    draft = _pending_draft(repository, "calibration-2")
    _commit(
        repository,
        draft.id,
        (draft.observations[0].operation_id,),
        calibration_id="calibration-2",
        context=_context("snapshot-follow-up-commit"),
    )
    _, events = repository.list_profile_history()
    replacement_event = events[-1]

    snapshot_v1 = repository.get_profile_snapshot(1)
    snapshot_v2 = repository.get_profile_snapshot(2)

    assert isinstance(snapshot_v1, ProfileSnapshot)
    assert snapshot_v1.profile_version == 1
    assert {item.id for item in snapshot_v1.active_observations} == {first_event.id}
    assert snapshot_v2.profile_version == 2
    assert first_event.id not in {item.id for item in snapshot_v2.active_observations}
    assert replacement_event.id in {item.id for item in snapshot_v2.active_observations}
    assert repository.get_profile_snapshot(0).active_observations == ()


def test_profile_snapshot_rejects_negative_and_future_versions(
    repository: FamilyContextRepository,
) -> None:
    _commit_initial_assertion(repository)

    with pytest.raises(ValueError, match="non-negative"):
        repository.get_profile_snapshot(-1)
    with pytest.raises(VersionConflictError) as captured:
        repository.get_profile_snapshot(2)

    assert captured.value.entity == "profile"
    assert captured.value.entity_id == "singleton"
    assert captured.value.expected_version == 2
    assert captured.value.actual_version == 1


def test_latest_calibration_summary_is_none_then_returns_exact_checkpoint(
    repository: FamilyContextRepository,
) -> None:
    assert repository.get_latest_calibration_summary() is None
    _save_input(repository)

    summary = repository.get_latest_calibration_summary()

    assert isinstance(summary, CalibrationSummary)
    assert summary.calibration_id == "calibration-1"
    assert summary.calibration_version == 1
    assert summary.profile_version == 0
    assert summary.state is CalibrationState.INPUT_SAVED
    assert summary.occurred_at.tzinfo is not None


def test_commit_rolls_back_all_business_effects_when_outcome_insert_fails(
    repository: FamilyContextRepository,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.storage import family_context as family_module

    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    before = _family_row_counts(database_path)

    def fail_outcome(*args, **kwargs):
        raise RuntimeError("fault before idempotency outcome insert")

    monkeypatch.setattr(family_module, "_insert_idempotency_outcome", fail_outcome)
    with pytest.raises(RuntimeError, match="fault"):
        _commit(repository, draft.id, (draft.observations[0].operation_id,))

    assert _family_row_counts(database_path) == before
    assert repository.get_current_profile_version() == 0
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.calibration_version == 2
    assert recovery.latest_checkpoint.state is CalibrationState.NEEDS_CONFIRMATION


def test_receipt_session_and_checkpoint_roll_back_when_receipt_transaction_fails(
    repository: FamilyContextRepository,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.storage import family_context as family_module

    original = family_module._insert_checkpoint

    def insert_then_fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("fault after receipt checkpoint insert")

    monkeypatch.setattr(family_module, "_insert_checkpoint", insert_then_fail)
    with pytest.raises(RuntimeError, match="fault"):
        _save_input(repository)

    with connect_database(database_path) as connection:
        assert _count(connection, "calibration_sessions") == 0
        assert _count(connection, "calibration_turn_receipts") == 0
        assert _count(connection, "calibration_checkpoints") == 0


def test_unavailable_transition_rolls_back_when_outcome_insert_fails(
    repository: FamilyContextRepository,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.storage import family_context as family_module

    receipt = _save_input(repository).receipt
    before = _family_row_counts(database_path)

    def fail_outcome(*args, **kwargs):
        raise RuntimeError("fault before unavailable outcome insert")

    monkeypatch.setattr(family_module, "_insert_idempotency_outcome", fail_outcome)
    with pytest.raises(RuntimeError, match="fault"):
        _mark_unavailable(repository, receipt.id)

    assert _family_row_counts(database_path) == before
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.calibration_version == 1
    assert recovery.latest_checkpoint.state is CalibrationState.INPUT_SAVED
    assert recovery.directive is RecoveryDirective.INITIAL_INFERENCE


def test_proposal_transition_rolls_back_when_outcome_insert_fails(
    repository: FamilyContextRepository,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.storage import family_context as family_module

    receipt = _save_input(repository).receipt
    before = _family_row_counts(database_path)

    def fail_outcome(*args, **kwargs):
        raise RuntimeError("fault before proposal outcome insert")

    monkeypatch.setattr(family_module, "_insert_idempotency_outcome", fail_outcome)
    with pytest.raises(RuntimeError, match="fault"):
        _propose(repository, receipt.id)

    assert _family_row_counts(database_path) == before
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.calibration_version == 1
    assert recovery.pending_draft is None
    assert recovery.latest_checkpoint.state is CalibrationState.INPUT_SAVED


def test_mutating_delivered_data_cannot_change_stored_idempotent_outcome(
    repository: FamilyContextRepository,
) -> None:
    receipt = _save_input(repository).receipt
    original = _mark_unavailable(repository, receipt.id)
    original.outcome.data["error_code"] = "caller-mutated"

    replay = _mark_unavailable(repository, receipt.id)

    assert replay.delivery.replayed is True
    assert replay.outcome.data["error_code"] == "lm_studio_unavailable"
    assert repository.get_calibration_recovery("calibration-1").last_outcome == replay.outcome


def test_commit_same_key_changed_expected_version_or_actor_conflicts_before_state(
    repository: FamilyContextRepository,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    _commit(repository, draft.id, accepted)

    with pytest.raises(IdempotencyConflictError):
        _commit(
            repository,
            draft.id,
            accepted,
            expected_calibration_version=3,
        )
    with pytest.raises(IdempotencyConflictError):
        _commit(
            repository,
            draft.id,
            accepted,
            context=_context("commit-key", actor="parent-2"),
        )
    assert repository.get_current_profile_version() == 1
    assert repository.get_calibration_recovery("calibration-1").calibration_version == 3


@pytest.mark.parametrize(
    "changed_ids",
    [
        ("unknown-operation",),
        None,
    ],
)
def test_existing_commit_key_with_invalid_changed_ids_is_idempotency_conflict(
    repository: FamilyContextRepository,
    changed_ids: tuple[str, ...] | None,
) -> None:
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    _commit(repository, draft.id, accepted)
    invalid = accepted * 2 if changed_ids is None else changed_ids

    with pytest.raises(IdempotencyConflictError):
        repository.lookup_commit_profile_patch(
            "calibration-1",
            draft.id,
            invalid,
            draft_digest=draft.draft_digest,
            expected_calibration_version=2,
            context=_context("commit-key"),
        )

    assert repository.get_current_profile_version() == 1


def test_commit_input_is_saved_before_model_or_commit_and_audited(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)

    receipt = _save_commit_input(repository, draft, accepted)

    assert isinstance(receipt, CalibrationCommitInputReceiptResult)
    assert isinstance(receipt.input, CalibrationCommitInputReceipt)
    assert receipt.replayed is False
    assert receipt.input.calibration_id == "calibration-1"
    assert receipt.input.draft_id == draft.id
    assert receipt.input.draft_digest == draft.draft_digest
    assert receipt.input.accepted_operation_ids == accepted
    assert receipt.input.actor == "parent-1"
    assert receipt.input.role == "parent"
    assert receipt.input.expected_calibration_version == 2
    assert receipt.input.created_at.tzinfo is not None
    assert repository.get_current_profile_version() == 0
    assert repository.get_calibration_recovery("calibration-1").calibration_version == 2
    with connect_database(database_path) as connection:
        audit = connection.execute(
            "SELECT * FROM calibration_audit_events WHERE id = ?",
            (receipt.input.id,),
        ).fetchone()
        idempotency = connection.execute(
            """
            SELECT idempotency_key, response_json
            FROM idempotency_records
            WHERE operation = 'save_profile_commit_input'
            """
        ).fetchone()
    assert audit is not None
    assert audit["event_type"] == "profile_commit_input_saved"
    assert audit["calibration_id"] == receipt.input.calibration_id
    assert audit["actor"] == receipt.input.actor
    assert audit["role"] == "parent"
    assert audit["occurred_at"] == receipt.input.created_at.isoformat()
    assert audit["created_at"] == receipt.input.created_at.isoformat()
    assert NOW_TEXT not in str(audit["payload_json"])
    assert idempotency is not None
    assert idempotency["idempotency_key"] == hashlib.sha256(b"commit-http-key-0001").hexdigest()
    assert NOW_TEXT not in str(idempotency["response_json"])


def test_commit_input_replay_normalizes_ids_before_draft_lookup(
    repository: FamilyContextRepository,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.storage import family_context as family_module

    turn_receipt = _save_input(repository).receipt
    _propose(
        repository,
        turn_receipt.id,
        observations=(
            _proposal(subject="Mathematics"),
            _proposal(subject="English", value_text="developing"),
        ),
    )
    draft = _pending_draft(repository)
    stored_order = tuple(item.operation_id for item in draft.observations)
    context = _context("commit-input-replay", trace_id="trace-original")
    original = _save_commit_input(
        repository,
        draft,
        tuple(reversed(stored_order)),
        context=context,
    )
    before = _family_row_counts(database_path)
    draft_calls = 0
    original_require_draft = family_module._require_draft

    def spy_require_draft(*args, **kwargs):
        nonlocal draft_calls
        draft_calls += 1
        return original_require_draft(*args, **kwargs)

    monkeypatch.setattr(family_module, "_require_draft", spy_require_draft)
    replay = _save_commit_input(
        repository,
        draft,
        stored_order,
        context=_context("commit-input-replay", trace_id="trace-replay"),
    )

    assert replay is not original
    assert replay.input == original.input
    assert replay.input.accepted_operation_ids == stored_order
    assert replay.replayed is True
    assert draft_calls == 0
    assert _family_row_counts(database_path) == before


@pytest.mark.parametrize(
    "changed_kind",
    [
        "draft",
        "digest",
        "accepted",
        "empty",
        "duplicate",
        "outside",
        "actor",
        "calibration",
        "version",
    ],
)
def test_commit_input_known_key_identity_changes_are_sanitized_conflicts(
    repository: FamilyContextRepository,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_kind: str,
) -> None:
    from backend.storage import family_context as family_module

    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    context = _context("commit-input-known-key")
    _save_commit_input(repository, draft, accepted, context=context)
    before = _family_row_counts(database_path)
    calls = 0
    original = family_module._require_draft

    def spy_require_draft(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(family_module, "_require_draft", spy_require_draft)
    calibration_id = "calibration-1"
    draft_id = draft.id
    draft_digest = draft.draft_digest
    candidate_ids = accepted
    expected_version = 2
    candidate_context = context
    if changed_kind == "draft":
        draft_id = "missing-draft"
    elif changed_kind == "digest":
        draft_digest = "0" * 64
    elif changed_kind == "accepted":
        candidate_ids = ("different-operation",)
    elif changed_kind == "empty":
        candidate_ids = ()
    elif changed_kind == "duplicate":
        candidate_ids = accepted * 2
    elif changed_kind == "outside":
        candidate_ids = ("not-in-draft",)
    elif changed_kind == "actor":
        candidate_context = _context("commit-input-known-key", actor="parent-2")
    elif changed_kind == "calibration":
        calibration_id = "calibration-2"
    else:
        expected_version = 3

    with pytest.raises(IdempotencyConflictError) as captured:
        repository.save_profile_commit_input(
            calibration_id,
            draft_id,
            candidate_ids,
            draft_digest=draft_digest,
            expected_calibration_version=expected_version,
            context=candidate_context,
        )

    assert captured.value.idempotency_key == "<redacted>"
    assert calls == 0
    assert _family_row_counts(database_path) == before


def test_commit_input_non_parent_role_fails_before_database_access(
    repository: FamilyContextRepository,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    before = _family_row_counts(database_path)
    transaction_calls = 0

    def fail_transaction():
        nonlocal transaction_calls
        transaction_calls += 1
        raise AssertionError("transaction must not be opened")

    monkeypatch.setattr(repository, "_transaction", fail_transaction)
    with pytest.raises(ValueError, match="parent role"):
        _save_commit_input(
            repository,
            draft,
            (draft.observations[0].operation_id,),
            context=_context(
                "non-parent-commit-input",
                actor="model",
                role="system",
            ),
        )

    assert transaction_calls == 0
    assert _family_row_counts(database_path) == before


def test_commit_input_new_key_stale_version_and_outside_ids_are_typed(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    before = _family_row_counts(database_path)

    with pytest.raises(VersionConflictError):
        _save_commit_input(
            repository,
            draft,
            accepted,
            expected_calibration_version=1,
            context=_context("commit-input-stale-version"),
        )
    with pytest.raises(CommitCommandInvalidError) as captured:
        _save_commit_input(
            repository,
            draft,
            ("not-in-draft",),
            context=_context("commit-input-outside"),
        )

    assert captured.value.reason_code == "accepted_ids_not_in_draft"
    assert _family_row_counts(database_path) == before


@pytest.mark.parametrize("draft_kind", ["missing", "foreign"])
def test_commit_input_new_key_missing_and_foreign_drafts_are_not_found(
    repository: FamilyContextRepository,
    database_path: Path,
    draft_kind: str,
) -> None:
    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    receipt_2 = repository.save_calibration_input(
        "calibration-2",
        "Foreign calibration",
        expected_calibration_version=0,
        expected_profile_version=0,
        context=_context("commit-input-foreign-receipt"),
    ).receipt
    repository.propose_profile_patch(
        "calibration-2",
        receipt_2.id,
        (_proposal(subject="English"),),
        expected_calibration_version=1,
        context=_context("commit-input-foreign-proposal"),
    )
    foreign = _pending_draft(repository, "calibration-2")
    draft_id = "missing-draft" if draft_kind == "missing" else foreign.id
    digest = "0" * 64 if draft_kind == "missing" else foreign.draft_digest
    before = _family_row_counts(database_path)

    with pytest.raises(NotFoundError) as captured:
        repository.save_profile_commit_input(
            "calibration-1",
            draft_id,
            (foreign.observations[0].operation_id,),
            draft_digest=digest,
            expected_calibration_version=2,
            context=_context(f"commit-input-{draft_kind}"),
        )

    assert captured.value.entity == "calibration draft"
    assert captured.value.entity_id == draft_id
    assert _family_row_counts(database_path) == before


@pytest.mark.parametrize("stale_kind", ["superseded", "abandoned", "committed"])
def test_commit_input_same_calibration_noncurrent_draft_is_invalid_transition(
    repository: FamilyContextRepository,
    database_path: Path,
    stale_kind: str,
) -> None:
    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    if stale_kind == "superseded":
        repository.revise_profile_patch(
            "calibration-1",
            draft.id,
            (_proposal(value_text="developing"),),
            expected_calibration_version=2,
            context=_context("commit-input-supersede"),
        )
    elif stale_kind == "abandoned":
        repository.abandon_profile_patch(
            "calibration-1",
            expected_calibration_version=2,
            context=_context("commit-input-abandon"),
        )
    else:
        _commit(
            repository,
            draft.id,
            accepted,
            context=_context("commit-input-commit"),
        )
    before = _family_row_counts(database_path)

    with pytest.raises(InvalidTransitionError) as captured:
        _save_commit_input(
            repository,
            draft,
            accepted,
            expected_calibration_version=3,
            context=_context(f"commit-input-stale-{stale_kind}"),
        )

    assert captured.value.requested_stage == "save_profile_commit_input"
    assert _family_row_counts(database_path) == before


@pytest.mark.parametrize(
    "injected",
    [
        ValueError("unknown commit input value error"),
        sqlite3.OperationalError("commit input sqlite failure"),
        RuntimeError("commit input programming failure"),
    ],
)
def test_commit_input_unknown_draft_boundary_errors_keep_original_type(
    repository: FamilyContextRepository,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    injected: Exception,
) -> None:
    from backend.storage import family_context as family_module

    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    before = _family_row_counts(database_path)

    def fail_draft(*args, **kwargs):
        raise injected

    monkeypatch.setattr(family_module, "_require_draft", fail_draft)
    with pytest.raises(type(injected)) as captured:
        _save_commit_input(
            repository,
            draft,
            (draft.observations[0].operation_id,),
            context=_context(f"commit-input-unknown-{type(injected).__name__}"),
        )

    assert captured.value is injected
    assert _family_row_counts(database_path) == before


def test_commit_input_corrupt_idempotency_receipt_is_integrity_error(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    context = _context("commit-input-corrupt-replay")
    _save_commit_input(repository, draft, accepted, context=context)
    with connect_database(database_path) as connection:
        connection.execute(
            """
            UPDATE idempotency_records
            SET response_json = '{"malformed":true}'
            WHERE operation = 'save_profile_commit_input'
            """
        )

    with pytest.raises(ValueError) as captured:
        _save_commit_input(repository, draft, accepted, context=context)

    assert not isinstance(captured.value, IdempotencyConflictError)
    assert not isinstance(captured.value, CommitCommandInvalidError)


def test_commit_input_replay_missing_audit_is_integrity_error_not_not_found(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    context = _context("commit-input-missing-audit")
    saved = _save_commit_input(repository, draft, accepted, context=context)
    with connect_database(database_path) as connection:
        connection.execute("DROP TRIGGER calibration_audit_events_no_delete")
        connection.execute(
            "DELETE FROM calibration_audit_events WHERE id = ?",
            (saved.input.id,),
        )

    with pytest.raises(ValueError) as captured:
        _save_commit_input(repository, draft, accepted, context=context)

    assert type(captured.value) is ValueError


def test_commit_input_reader_survives_restart_and_scopes_calibration(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    accepted = (draft.observations[0].operation_id,)
    saved = _save_commit_input(repository, draft, accepted)
    restarted = FamilyContextRepository(database_path)

    assert restarted.get_profile_commit_input("calibration-1", saved.input.id) == saved.input
    with pytest.raises(NotFoundError):
        restarted.get_profile_commit_input("calibration-1", "missing-input")
    with pytest.raises(NotFoundError):
        restarted.get_profile_commit_input("calibration-2", saved.input.id)


@pytest.mark.parametrize(
    "corruption",
    [
        "event_type",
        "actor",
        "role",
        "payload_id",
        "payload_created_at",
        "audit_created_at",
        "duplicate_ids",
        "reordered_ids",
        "malformed_payload",
    ],
)
def test_commit_input_reader_fails_closed_on_corrupt_audit_invariants(
    repository: FamilyContextRepository,
    database_path: Path,
    corruption: str,
) -> None:
    turn_receipt = _save_input(repository).receipt
    _propose(
        repository,
        turn_receipt.id,
        observations=(
            _proposal(subject="Mathematics"),
            _proposal(subject="English", value_text="developing"),
        ),
    )
    draft = _pending_draft(repository)
    accepted = tuple(item.operation_id for item in draft.observations)
    saved = _save_commit_input(repository, draft, accepted)
    with connect_database(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM calibration_audit_events WHERE id = ?",
            (saved.input.id,),
        ).fetchone()
        assert row is not None
        payload = json.loads(str(row["payload_json"]))
        connection.execute("DROP TRIGGER calibration_audit_events_no_update")
        if corruption == "event_type":
            connection.execute(
                "UPDATE calibration_audit_events SET event_type = 'other' WHERE id = ?",
                (saved.input.id,),
            )
        elif corruption == "actor":
            connection.execute(
                "UPDATE calibration_audit_events SET actor = 'parent-2' WHERE id = ?",
                (saved.input.id,),
            )
        elif corruption == "role":
            connection.execute(
                "UPDATE calibration_audit_events SET role = 'system' WHERE id = ?",
                (saved.input.id,),
            )
        elif corruption == "payload_id":
            payload["id"] = "different-input-id"
        elif corruption == "payload_created_at":
            payload["created_at"] = "2026-01-01T00:00:00+00:00"
        elif corruption == "audit_created_at":
            connection.execute(
                "UPDATE calibration_audit_events SET created_at = '2026-01-01T00:00:00+00:00' WHERE id = ?",
                (saved.input.id,),
            )
        elif corruption == "duplicate_ids":
            payload["accepted_operation_ids"] = [accepted[0], accepted[0]]
        elif corruption == "reordered_ids":
            payload["accepted_operation_ids"] = list(reversed(accepted))
        else:
            payload = {"malformed": True}
        if corruption in {
            "payload_id",
            "payload_created_at",
            "duplicate_ids",
            "reordered_ids",
            "malformed_payload",
        }:
            connection.execute(
                "UPDATE calibration_audit_events SET payload_json = ? WHERE id = ?",
                (json.dumps(payload), saved.input.id),
            )

    restarted = FamilyContextRepository(database_path)
    with pytest.raises(ValueError):
        restarted.get_profile_commit_input("calibration-1", saved.input.id)


@pytest.mark.parametrize(
    "state",
    [CalibrationState.MODEL_UNAVAILABLE, CalibrationState.RETRY_PENDING],
)
def test_commit_input_attempt_checkpoint_is_exact_and_recovery_loads_receipt(
    repository: FamilyContextRepository,
    database_path: Path,
    state: CalibrationState,
) -> None:
    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    saved = _save_commit_input(
        repository,
        draft,
        (draft.observations[0].operation_id,),
    )
    assert (
        repository.has_profile_commit_attempt_checkpoint("calibration-1", saved.input.id) is False
    )
    occurred_at = datetime.now(UTC).isoformat()
    with connect_database(database_path) as connection:
        connection.execute(
            """
            INSERT INTO calibration_checkpoints (
                id, calibration_id, calibration_version, profile_version,
                state, resume_stage, pending_kind, pending_entity_id,
                last_stable_calibration_version, last_stable_profile_version,
                input_receipt_id, trace_id, outcome_json, occurred_at
            ) VALUES (?, ?, 3, 0, ?, 'profile_commit', 'model_retry', ?,
                      2, 0, ?, 'trace-checkpoint', NULL, ?)
            """,
            (
                f"checkpoint-{state.value}",
                "calibration-1",
                state.value,
                saved.input.id,
                turn_receipt.id,
                occurred_at,
            ),
        )
        connection.execute(
            """
            UPDATE calibration_sessions
            SET calibration_version = 3, state = ?, pending_kind = 'model_retry',
                pending_entity_id = ?, updated_at = ?
            WHERE id = 'calibration-1'
            """,
            (state.value, saved.input.id, occurred_at),
        )

    assert repository.has_profile_commit_attempt_checkpoint("calibration-1", saved.input.id) is True
    recovery = repository.get_calibration_recovery("calibration-1")
    assert recovery.pending_commit_input == saved.input


def test_commit_input_checkpoint_ignores_other_entity_stage_and_calibration(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    saved = _save_commit_input(
        repository,
        draft,
        (draft.observations[0].operation_id,),
    )
    with connect_database(database_path) as connection:
        connection.execute(
            """
            INSERT INTO calibration_checkpoints (
                id, calibration_id, calibration_version, profile_version,
                state, resume_stage, pending_kind, pending_entity_id,
                last_stable_calibration_version, last_stable_profile_version,
                input_receipt_id, trace_id, outcome_json, occurred_at
            ) VALUES ('wrong-stage', 'calibration-1', 3, 0,
                      'model_unavailable', 'profile_propose', 'model_retry', ?,
                      2, 0, ?, NULL, NULL, ?)
            """,
            (saved.input.id, turn_receipt.id, datetime.now(UTC).isoformat()),
        )
        connection.execute(
            """
            INSERT INTO calibration_checkpoints (
                id, calibration_id, calibration_version, profile_version,
                state, resume_stage, pending_kind, pending_entity_id,
                last_stable_calibration_version, last_stable_profile_version,
                input_receipt_id, trace_id, outcome_json, occurred_at
            ) VALUES ('wrong-entity', 'calibration-1', 4, 0,
                      'retry_pending', 'profile_commit', 'model_retry',
                      'other-input', 2, 0, ?, NULL, NULL, ?)
            """,
            (turn_receipt.id, datetime.now(UTC).isoformat()),
        )

    assert (
        repository.has_profile_commit_attempt_checkpoint("calibration-1", saved.input.id) is False
    )
    assert (
        repository.has_profile_commit_attempt_checkpoint("other-calibration", saved.input.id)
        is False
    )


def test_commit_input_audit_and_idempotency_roll_back_together(
    repository: FamilyContextRepository,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.storage import family_context as family_module

    turn_receipt = _save_input(repository).receipt
    _propose(repository, turn_receipt.id)
    draft = _pending_draft(repository)
    before = _family_row_counts(database_path)

    def fail_outcome(*args, **kwargs):
        raise RuntimeError("fault before commit input outcome insert")

    monkeypatch.setattr(family_module, "_insert_idempotency_outcome", fail_outcome)
    with pytest.raises(RuntimeError, match="commit input outcome"):
        _save_commit_input(
            repository,
            draft,
            (draft.observations[0].operation_id,),
        )

    assert _family_row_counts(database_path) == before


def _family_row_counts(database_path: Path) -> dict[str, int]:
    tables = (
        "calibration_sessions",
        "calibration_turn_receipts",
        "calibration_drafts",
        "calibration_commits",
        "profile_versions",
        "profile_observation_events",
        "calibration_checkpoints",
        "calibration_audit_events",
        "idempotency_records",
    )
    with connect_database(database_path) as connection:
        return {table: _count(connection, table) for table in tables}


def _commit_initial_assertion(repository: FamilyContextRepository):
    receipt = _save_input(repository).receipt
    _propose(repository, receipt.id)
    draft = _pending_draft(repository)
    _commit(repository, draft.id, (draft.observations[0].operation_id,))
    _, events = repository.list_profile_history()
    assert len(events) == 1
    return events[0]
