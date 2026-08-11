from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

from backend.contracts.models import (
    EveningSession,
    ObservationEvent,
    SchoolBrief,
    SessionStage,
    Source,
)
from backend.errors import IdempotencyConflictError, NotFoundError, VersionConflictError
from backend.storage.database import connect_database, run_migrations
from backend.storage.repositories import (
    EveningSessionRepository,
    EventRepository,
    IdempotencyRepository,
    SchoolBriefRepository,
)


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "studypilot.db"
    run_migrations(path, backup_dir=tmp_path / "backups")
    return path


def _brief() -> SchoolBrief:
    return SchoolBrief(
        id="brief-1",
        brief_date=date(2026, 7, 11),
        source_path="data/school/2026-07-11.md",
        content_sha256="a" * 64,
        raw_text="Math exercises 1-4",
        created_at=NOW,
    )


def _session(*, session_id: str = "session-1") -> EveningSession:
    return EveningSession(
        id=session_id,
        session_date=date(2026, 7, 11),
        timezone="Asia/Shanghai",
        sleep_time=time(21, 30),
        stage=SessionStage.CREATED,
        version=0,
        available_minutes=180,
        created_at=NOW,
        updated_at=NOW,
    )


def _observation(
    event_id: str,
    *,
    event_type: str,
    offset_minutes: int = 0,
) -> ObservationEvent:
    occurred_at = NOW + timedelta(minutes=offset_minutes)
    return ObservationEvent(
        id=event_id,
        session_id="session-1",
        event_type=event_type,
        source=Source.CHILD,
        payload={"sequence": offset_minutes},
        occurred_at=occurred_at,
        created_at=occurred_at,
    )


def test_school_brief_create_and_read_round_trip(database_path: Path) -> None:
    repository = SchoolBriefRepository(database_path)
    brief = _brief()

    created = repository.create(brief)

    assert created == brief
    assert repository.get(brief.id) == brief
    with pytest.raises(NotFoundError, match="school brief missing"):
        repository.get("missing")


def test_evening_session_create_and_read_round_trip(database_path: Path) -> None:
    repository = EveningSessionRepository(database_path)
    session = _session()

    created = repository.create(session)

    assert created == session
    assert repository.get(session.id) == session


def test_evening_session_round_trips_fractional_sleep_time(
    database_path: Path,
) -> None:
    repository = EveningSessionRepository(database_path)
    session = _session()
    session.sleep_time = time(21, 30, 15, 123_456)

    repository.create(session)

    assert repository.get(session.id) == session


def test_expected_version_update_succeeds_once_and_stale_update_fails(
    database_path: Path,
) -> None:
    repository = EveningSessionRepository(database_path)
    repository.create(_session())

    advanced = repository.advance_version(
        "session-1",
        expected_version=0,
        new_stage=SessionStage.INTAKE_DRAFT,
    )

    assert advanced.version == 1
    assert advanced.stage is SessionStage.INTAKE_DRAFT
    with pytest.raises(VersionConflictError) as error:
        repository.advance_version(
            "session-1",
            expected_version=0,
            new_stage=SessionStage.COVERAGE_PENDING,
        )
    assert error.value.expected_version == 0
    assert error.value.actual_version == 1
    assert repository.get("session-1") == advanced


def test_version_update_distinguishes_missing_session(database_path: Path) -> None:
    repository = EveningSessionRepository(database_path)

    with pytest.raises(NotFoundError, match="evening session missing"):
        repository.advance_version(
            "missing",
            expected_version=0,
            new_stage=SessionStage.INTAKE_DRAFT,
        )


def test_append_only_observation_leaves_earlier_row_unchanged(
    database_path: Path,
) -> None:
    EveningSessionRepository(database_path).create(_session())
    repository = EventRepository(database_path)
    first = _observation("observation-1", event_type="task_reported")
    second = _observation(
        "observation-2",
        event_type="fixed_block_reported",
        offset_minutes=1,
    )

    repository.append_observation(first)
    first_before = repository.list_observations("session-1")[0]
    repository.append_observation(second)

    assert repository.list_observations("session-1") == [first_before, second]
    assert first_before == first
    with connect_database(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE observation_events SET event_type = 'changed' WHERE id = ?",
                (first.id,),
            )


def test_audit_repository_appends_without_update_surface(database_path: Path) -> None:
    EveningSessionRepository(database_path).create(_session())
    repository = EventRepository(database_path)

    stored = repository.append_audit(
        event_id="audit-1",
        session_id="session-1",
        event_type="session_created",
        actor_source=Source.SYSTEM,
        payload={"version": 0},
        trace_id="trace-1",
        occurred_at=NOW,
    )

    assert stored["event_id"] == "audit-1"
    assert stored["payload"] == {"version": 0}
    assert not hasattr(repository, "update_audit")
    assert not hasattr(repository, "delete_audit")


def test_idempotent_same_request_returns_original_stored_json(
    database_path: Path,
) -> None:
    repository = IdempotencyRepository(database_path)
    request_hash = "b" * 64
    original = {"session_id": "session-1", "version": 1}

    assert repository.lookup("create_session", "key-1", request_hash) is None
    assert repository.store(
        "create_session", "key-1", request_hash, original
    ) == original
    replay = repository.store(
        "create_session",
        "key-1",
        request_hash,
        {"session_id": "different", "version": 99},
    )

    assert replay == original
    assert repository.lookup("create_session", "key-1", request_hash) == original
    with connect_database(database_path) as connection:
        count = connection.execute(
            "SELECT count(*) FROM idempotency_records"
        ).fetchone()[0]
    assert count == 1


def test_idempotency_key_reuse_with_different_hash_fails(
    database_path: Path,
) -> None:
    repository = IdempotencyRepository(database_path)
    repository.store(
        "create_session",
        "key-1",
        "b" * 64,
        {"session_id": "session-1"},
    )

    with pytest.raises(IdempotencyConflictError, match="create_session"):
        repository.store(
            "create_session",
            "key-1",
            "c" * 64,
            {"session_id": "session-2"},
        )


def test_same_idempotency_key_is_scoped_by_operation(database_path: Path) -> None:
    repository = IdempotencyRepository(database_path)

    first = repository.store("create_session", "key-1", "b" * 64, {"value": 1})
    second = repository.store("commit_plan", "key-1", "c" * 64, {"value": 2})

    assert first == {"value": 1}
    assert second == {"value": 2}
