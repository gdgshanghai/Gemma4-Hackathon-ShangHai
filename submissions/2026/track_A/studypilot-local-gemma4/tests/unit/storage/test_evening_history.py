from __future__ import annotations

from pathlib import Path

from backend.contracts.evening import (
    IntakeDraftTask,
    SaveIntakeDraftArguments,
)
from backend.storage.database import run_migrations
from backend.storage.evening_workflow import EveningWorkflowRepository


def _store_outcome(
    repository: EveningWorkflowRepository,
    *,
    session_id: str,
    task_id: str,
    actual_minutes: int,
    stage: str,
) -> None:
    with repository._transaction() as connection:
        connection.execute(
            "UPDATE evening_sessions SET stage = ? WHERE id = ?",
            (stage, session_id),
        )
        connection.execute(
            """
            INSERT INTO task_outcomes (
                id, session_id, task_id, completion_state, actual_minutes
            ) VALUES (?, ?, ?, 'completed', ?)
            """,
            (f"outcome-{task_id}", session_id, task_id, actual_minutes),
        )


def _create_confirmed_task(
    repository: EveningWorkflowRepository,
    *,
    key: str,
    session_date: str,
    subject: str,
    task_type: str,
) -> tuple[str, dict[str, object]]:
    created = repository.create(
        session_date=session_date,
        timezone="Asia/Shanghai",
        sleep_time="22:30:00",
        available_minutes=180,
        expected_version=0,
        caller_idempotency_key=f"{key}-create",
        trace_id=f"{key}-create-trace",
    )
    session_id = str(created["view"]["session_id"])
    repository.save_intake_draft(
        session_id=session_id,
        arguments=SaveIntakeDraftArguments(
            tasks=[
                IntakeDraftTask(
                    title=f"{task_type} 练习册",
                    subject=subject,
                    child_estimate_minutes=20,
                )
            ]
        ),
        expected_version=1,
        hidden_idempotency_key=f"{key}-draft",
    )
    confirmed = repository.confirm_inventory(
        session_id=session_id,
        expected_version=2,
        profile_version=0,
        parent_high_minutes=(None,),
        caller_idempotency_key=f"{key}-confirm",
        trace_id=f"{key}-confirm-trace",
    )
    return session_id, confirmed["view"]["inventory"][0]


def test_three_exact_signature_samples_change_the_next_matching_estimate(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evening-history.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = EveningWorkflowRepository(database_path)
    for index, (session_date, actual_minutes) in enumerate(
        (("2026-07-10", 40), ("2026-07-11", 45), ("2026-07-12", 50)),
        start=1,
    ):
        session_id, task = _create_confirmed_task(
            repository,
            key=f"history-night-{index}",
            session_date=session_date,
            subject="mathematics",
            task_type="written",
        )
        _store_outcome(
            repository,
            session_id=session_id,
            task_id=str(task["id"]),
            actual_minutes=actual_minutes,
            stage="closed",
        )

    _, target_task = _create_confirmed_task(
        repository,
        key="target-night",
        session_date="2026-07-13",
        subject="mathematics",
        task_type="written",
    )

    assert target_task["conservative_minutes"] == 50
    assert target_task["estimate_source"] == "history_p80"
    assert target_task["estimate_confidence"] == "medium"


def test_history_uses_only_authoritative_closed_earlier_evenings(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "filtered-history.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = EveningWorkflowRepository(database_path)

    for index, (session_date, actual_minutes) in enumerate(
        (("2026-07-08", 40), ("2026-07-09", 45), ("2026-07-10", 50)),
        start=1,
    ):
        valid_session_id, valid_task = _create_confirmed_task(
            repository,
            key=f"valid-history-{index}",
            session_date=session_date,
            subject="mathematics",
            task_type="written",
        )
        _store_outcome(
            repository,
            session_id=valid_session_id,
            task_id=str(valid_task["id"]),
            actual_minutes=actual_minutes,
            stage="closed",
        )

    incomplete_session_id, incomplete_task = _create_confirmed_task(
        repository,
        key="incomplete-history",
        session_date="2026-07-11",
        subject="mathematics",
        task_type="written",
    )
    _store_outcome(
        repository,
        session_id=incomplete_session_id,
        task_id=str(incomplete_task["id"]),
        actual_minutes=120,
        stage="inventory_confirmed",
    )

    future_session_id, future_task = _create_confirmed_task(
        repository,
        key="future-history",
        session_date="2026-07-14",
        subject="mathematics",
        task_type="written",
    )
    _store_outcome(
        repository,
        session_id=future_session_id,
        task_id=str(future_task["id"]),
        actual_minutes=200,
        stage="closed",
    )

    with repository._transaction() as connection:
        connection.execute(
            """
            INSERT INTO evening_sessions (
                id, session_date, timezone, sleep_time, stage, version,
                available_minutes, created_at, updated_at
            ) VALUES (
                'legacy-duplicate', '2026-07-10', 'Asia/Shanghai', '22:30',
                'closed', 3, 180, '2026-07-10T23:00:00+08:00',
                '2026-07-10T23:00:00+08:00'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO task_items (
                id, session_id, title, subject, task_type, source,
                completion_state, estimated_minutes, conservative_minutes,
                priority
            ) VALUES (
                'legacy-task', 'legacy-duplicate', 'Legacy duplicate',
                'mathematics', 'written', 'child', 'pending', 20, 20, 1
            )
            """
        )
        connection.execute(
            """
            INSERT INTO task_outcomes (
                id, session_id, task_id, completion_state, actual_minutes
            ) VALUES (
                'legacy-outcome', 'legacy-duplicate', 'legacy-task',
                'completed', 99
            )
            """
        )

    _, target_task = _create_confirmed_task(
        repository,
        key="target-night",
        session_date="2026-07-13",
        subject="mathematics",
        task_type="written",
    )

    assert target_task["conservative_minutes"] == 50
    assert target_task["estimate_source"] == "history_p80"
