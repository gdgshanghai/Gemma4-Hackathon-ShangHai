from __future__ import annotations

import hashlib
import inspect
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier

import pytest

from backend.contracts.family import FamilyWriteContext
from backend.errors import IdempotencyConflictError, VersionConflictError
from backend.storage.database import connect_database, run_migrations
from backend.storage.family_context import FamilyContextRepository


BRIEF_DATE = date(2026, 7, 11)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "school-briefs.db"
    run_migrations(path, backup_dir=tmp_path / "backups")
    return path


@pytest.fixture
def repository(database_path: Path) -> FamilyContextRepository:
    return FamilyContextRepository(database_path)


def _context(
    key: str = "school-secret-key",
    *,
    actor: str = "parent-1",
    role: str = "parent",
    trace_id: str = "trace-school",
) -> FamilyWriteContext:
    return FamilyWriteContext(
        actor=actor,
        role=role,
        trace_id=trace_id,
        idempotency_key=key,
    )


def _append(
    repository: FamilyContextRepository,
    raw_text: str = "",
    *,
    expected_revision: int = 0,
    context: FamilyWriteContext | None = None,
):
    return repository.append_school_brief(
        BRIEF_DATE,
        raw_text,
        expected_revision=expected_revision,
        context=context or _context(),
    )


def _count(connection: sqlite3.Connection, table: str) -> int:
    row = connection.execute(f'SELECT COUNT(*) AS count FROM "{table}"').fetchone()
    assert row is not None
    return int(row["count"])


def test_empty_manual_text_creates_revision_one_and_never_accepts_source_path(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    result = _append(repository)

    assert result.delivery.replayed is False
    assert result.outcome.brief_date == BRIEF_DATE
    assert result.outcome.revision == 1
    assert result.outcome.no_op is False
    assert result.outcome.trace_id == "trace-school"
    assert result.outcome.allowed_actions == ("replace_school_brief",)
    assert result.outcome.record.raw_text == ""
    assert result.outcome.record.source == "manual-paste"
    assert result.outcome.record.revision == 1
    assert result.outcome.record.created_at.tzinfo is not None
    assert result.outcome.record.content_sha256 == hashlib.sha256(b"").hexdigest()
    assert repository.get_latest_school_brief(BRIEF_DATE) == result.outcome.record
    assert repository.list_school_brief_revisions(BRIEF_DATE) == (result.outcome.record,)

    parameters = inspect.signature(repository.append_school_brief).parameters
    assert "source" not in parameters
    assert "source_path" not in parameters
    with connect_database(database_path) as connection:
        row = connection.execute(
            "SELECT source FROM school_brief_revisions"
        ).fetchone()
        assert row is not None
        assert row["source"] == "manual-paste"


def test_changed_content_appends_revision_and_restart_restores_exact_history(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    first = _append(repository, "Mathematics exercise set")
    second = _append(
        repository,
        "Mathematics exercise set\nEnglish reading",
        expected_revision=1,
        context=_context("school-key-2", trace_id="trace-school-2"),
    )

    assert first.outcome.revision == 1
    assert second.outcome.revision == 2
    assert second.outcome.no_op is False
    restarted = FamilyContextRepository(database_path)
    assert restarted.get_latest_school_brief(BRIEF_DATE) == second.outcome.record
    assert restarted.list_school_brief_revisions(BRIEF_DATE) == (
        first.outcome.record,
        second.outcome.record,
    )


def test_school_replay_precedes_revision_check_and_trace_is_not_hashed(
    repository: FamilyContextRepository,
) -> None:
    original = _append(repository, "Manual school text")

    replay = _append(
        repository,
        "Manual school text",
        context=_context("school-secret-key", trace_id="trace-replay"),
    )

    assert replay.delivery.replayed is True
    assert replay.outcome == original.outcome
    assert replay.outcome.trace_id == "trace-school"
    assert repository.list_school_brief_revisions(BRIEF_DATE) == (original.outcome.record,)


@pytest.mark.parametrize(
    "changed",
    [
        {"raw_text": "Changed text"},
        {"expected_revision": 1},
        {"context": _context(actor="parent-2")},
        {"context": _context(role="system")},
    ],
)
def test_school_same_key_changed_request_conflicts_without_key_leak(
    repository: FamilyContextRepository,
    changed: dict[str, object],
) -> None:
    _append(repository, "Original text")

    request: dict[str, object] = {
        "raw_text": "Original text",
        "expected_revision": 0,
        "context": _context(),
    }
    request.update(changed)
    with pytest.raises(IdempotencyConflictError) as captured:
        _append(repository, **request)

    assert "school-secret-key" not in str(captured.value)
    assert hashlib.sha256(b"school-secret-key").hexdigest() not in str(captured.value)
    assert len(repository.list_school_brief_revisions(BRIEF_DATE)) == 1


def test_stale_revision_conflicts_even_when_content_matches(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    original = _append(repository, "Same content")
    _append(
        repository,
        "New content",
        expected_revision=1,
        context=_context("school-key-2"),
    )
    before = _table_counts(database_path)

    with pytest.raises(VersionConflictError) as captured:
        _append(
            repository,
            original.outcome.record.raw_text,
            expected_revision=1,
            context=_context("stale-matching-key"),
        )

    assert captured.value.expected_version == 1
    assert captured.value.actual_version == 2
    assert _table_counts(database_path) == before


def test_same_content_at_current_revision_is_no_op_with_own_idempotent_outcome(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    original = _append(repository, "Same content")

    no_op = _append(
        repository,
        "Same content",
        expected_revision=1,
        context=_context("no-op-key", trace_id="trace-no-op"),
    )

    assert no_op.delivery.replayed is False
    assert no_op.outcome.no_op is True
    assert no_op.outcome.revision == 1
    assert no_op.outcome.record == original.outcome.record
    assert no_op.outcome.trace_id == "trace-no-op"
    with connect_database(database_path) as connection:
        assert _count(connection, "school_brief_revisions") == 1
        assert _count(connection, "idempotency_records") == 2

    replay = _append(
        repository,
        "Same content",
        expected_revision=1,
        context=_context("no-op-key", trace_id="trace-no-op-replay"),
    )
    assert replay.delivery.replayed is True
    assert replay.outcome == no_op.outcome


def test_new_school_workflow_ignores_legacy_school_briefs_table(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    with connect_database(database_path) as connection:
        connection.execute(
            """
            INSERT INTO school_briefs (
                id, brief_date, source_path, content_sha256, raw_text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-school-row",
                BRIEF_DATE.isoformat(),
                "legacy-path",
                "a" * 64,
                "Legacy text must remain isolated",
                "2026-07-11T00:00:00+00:00",
            ),
        )

    assert repository.get_latest_school_brief(BRIEF_DATE) is None
    assert repository.list_school_brief_revisions(BRIEF_DATE) == ()
    created = _append(repository, "Canonical manual text")
    assert created.outcome.revision == 1
    assert created.outcome.record.raw_text == "Canonical manual text"


def test_concurrent_school_writes_allocate_only_one_next_revision(
    repository: FamilyContextRepository,
    database_path: Path,
) -> None:
    _append(repository, "Revision one")
    barrier = Barrier(2)

    def attempt(index: int):
        local = FamilyContextRepository(database_path)
        barrier.wait()
        try:
            return _append(
                local,
                f"Concurrent revision {index}",
                expected_revision=1,
                context=_context(f"concurrent-school-{index}"),
            )
        except VersionConflictError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, VersionConflictError) for result in results) == 1
    revisions = repository.list_school_brief_revisions(BRIEF_DATE)
    assert tuple(item.revision for item in revisions) == (1, 2)


def test_school_write_rolls_back_revision_when_outcome_insert_fails(
    repository: FamilyContextRepository,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.storage import family_context as family_module

    before = _table_counts(database_path)

    def fail_outcome(*args, **kwargs):
        raise RuntimeError("fault before school outcome insert")

    monkeypatch.setattr(family_module, "_insert_school_outcome", fail_outcome)
    with pytest.raises(RuntimeError, match="fault"):
        _append(repository, "Must roll back")

    assert _table_counts(database_path) == before
    assert repository.get_latest_school_brief(BRIEF_DATE) is None


def _table_counts(database_path: Path) -> dict[str, int]:
    with connect_database(database_path) as connection:
        return {
            "school_brief_revisions": _count(connection, "school_brief_revisions"),
            "idempotency_records": _count(connection, "idempotency_records"),
        }
