import json
from pathlib import Path

from backend.contracts.evening import SaveIntakeDraftArguments
from backend.domain.family_calibration import RatioObservation
from backend.storage.database import connect_database, run_migrations
from backend.storage.evening_workflow import EveningWorkflowRepository


def _create(repository: EveningWorkflowRepository, day: str, key: str) -> str:
    result = repository.create(
        session_date=day,
        planning_date=day,
        timezone="Asia/Shanghai",
        sleep_time="22:30:00",
        available_minutes=180,
        expected_version=0,
        caller_idempotency_key=key,
        trace_id=f"trace-{key}",
    )
    return str(result["view"]["session_id"])


def test_future_assignment_is_committed_once_and_carried_into_its_evening(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "continuity.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = EveningWorkflowRepository(database_path)
    thursday_id = _create(repository, "2026-10-15", "thursday")
    repository.save_intake_draft(
        session_id=thursday_id,
        arguments=SaveIntakeDraftArguments.model_validate_json(
            json.dumps(
                {
                "tasks": [
                    {
                        "title": "完成数学练习",
                        "subject": "mathematics",
                        "completion_state": "pending",
                        "deadline_text": "明早检查",
                    },
                    {
                        "title": "完成历史时间轴",
                        "subject": "history",
                        "completion_state": "partial",
                        "total_units": 2,
                        "completed_units": 1,
                        "deadline_text": "下周一提交",
                    },
                ]
                },
                ensure_ascii=False,
            )
        ),
        expected_version=1,
        hidden_idempotency_key="draft-thursday",
    )
    confirmed = repository.confirm_inventory(
        session_id=thursday_id,
        expected_version=2,
        profile_version=0,
        parent_high_minutes=[None, None],
        caller_idempotency_key="confirm-thursday",
        trace_id="trace-confirm-thursday",
    )
    inventory = confirmed["view"]["inventory"]
    history = next(task for task in inventory if task["subject"] == "history")
    assert history["planning_bucket"] == "future_scheduled"
    assert history["planned_evening_date"] == "2026-10-17"

    planned = repository.build_plan(
        session_id=thursday_id,
        expected_version=3,
        reason="initial",
        preferred_order=None,
        deadline_risk_task_ids=[],
        caller_idempotency_key="plan-thursday",
        trace_id="trace-plan-thursday",
    )
    plan_id = str(planned["view"]["plan"]["id"])
    committed = repository.commit_plan(
        session_id=thursday_id,
        plan_id=plan_id,
        expected_version=4,
        caller_idempotency_key="commit-thursday",
        trace_id="trace-commit-thursday",
    )
    replay = repository.commit_plan(
        session_id=thursday_id,
        plan_id=plan_id,
        expected_version=4,
        caller_idempotency_key="commit-thursday",
        trace_id="trace-commit-thursday",
    )
    assert replay == committed

    with connect_database(database_path) as connection:
        obligation = connection.execute(
            "SELECT id, planned_evening_date, remaining_percent, status "
            "FROM assignment_obligations WHERE subject = 'history'"
        ).fetchone()
        event_count = connection.execute(
            "SELECT count(*) FROM assignment_schedule_events WHERE assignment_id = ?",
            (obligation["id"],),
        ).fetchone()[0]
    assert obligation["planned_evening_date"] == "2026-10-17"
    assert obligation["remaining_percent"] == 50
    assert obligation["status"] == "open"
    assert event_count == 1

    repository.close(
        session_id=thursday_id,
        expected_version=5,
        unfinished_task_ids=[],
        largest_deviation=None,
        note=None,
        caller_idempotency_key="close-thursday",
        trace_id="trace-close-thursday",
    )

    saturday_id = _create(repository, "2026-10-17", "saturday")
    repository.save_intake_draft(
        session_id=saturday_id,
        arguments=SaveIntakeDraftArguments.model_validate_json(
            json.dumps(
                {
                "tasks": [
                    {
                        "title": "完成周末英语练习",
                        "subject": "english",
                        "completion_state": "pending",
                        "deadline_text": "明早检查",
                    }
                ]
                },
                ensure_ascii=False,
            )
        ),
        expected_version=1,
        hidden_idempotency_key="draft-saturday",
    )
    carried = repository.confirm_inventory(
        session_id=saturday_id,
        expected_version=2,
        profile_version=0,
        parent_high_minutes=[None],
        family_ratio_observations=(
            RatioObservation("history", "written", 1.5, 5),
        ),
        caller_idempotency_key="confirm-saturday",
        trace_id="trace-confirm-saturday",
    )

    carried_history = [
        task for task in carried["view"]["inventory"] if task["subject"] == "history"
    ]
    assert len(carried_history) == 1
    assert carried_history[0]["assignment_id"] == obligation["id"]
    assert carried_history[0]["must_do_tonight"] is True
    assert carried_history[0]["conservative_minutes"] == 15
    assert carried_history[0]["estimate_source"] == "parent_range"


def test_unfinished_task_stays_on_latest_safe_evening_with_deadline_risk(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "unfinished-deadline-risk.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = EveningWorkflowRepository(database_path)
    session_id = _create(repository, "2026-10-15", "unfinished-thursday")
    repository.save_intake_draft(
        session_id=session_id,
        arguments=SaveIntakeDraftArguments.model_validate_json(
            json.dumps(
                {
                "tasks": [
                    {
                        "title": "完成地理经纬网练习",
                        "subject": "geography",
                        "completion_state": "pending",
                        "deadline_text": "明早检查",
                    }
                ]
                },
                ensure_ascii=False,
            )
        ),
        expected_version=1,
        hidden_idempotency_key="draft-unfinished",
    )
    confirmed = repository.confirm_inventory(
        session_id=session_id,
        expected_version=2,
        profile_version=0,
        parent_high_minutes=[None],
        caller_idempotency_key="confirm-unfinished",
        trace_id="trace-confirm-unfinished",
    )
    task_id = str(confirmed["view"]["inventory"][0]["id"])
    planned = repository.build_plan(
        session_id=session_id,
        expected_version=3,
        reason="initial",
        preferred_order=None,
        deadline_risk_task_ids=[],
        caller_idempotency_key="plan-unfinished",
        trace_id="trace-plan-unfinished",
    )
    repository.commit_plan(
        session_id=session_id,
        plan_id=str(planned["view"]["plan"]["id"]),
        expected_version=4,
        caller_idempotency_key="commit-unfinished",
        trace_id="trace-commit-unfinished",
    )

    closed = repository.close(
        session_id=session_id,
        expected_version=5,
        unfinished_task_ids=[task_id],
        largest_deviation=None,
        note="今晚没有做完",
        caller_idempotency_key="close-unfinished",
        trace_id="trace-close-unfinished",
    )

    with connect_database(database_path) as connection:
        obligation = connection.execute(
            "SELECT id, latest_safe_evening, planned_evening_date "
            "FROM assignment_obligations WHERE subject = 'geography'"
        ).fetchone()
        event = connection.execute(
            "SELECT to_evening_date, reason FROM assignment_schedule_events "
            "WHERE assignment_id = ? ORDER BY created_at DESC LIMIT 1",
            (obligation["id"],),
        ).fetchone()

    assert closed["view"]["stage"] == "closed"
    assert obligation["latest_safe_evening"] == "2026-10-15"
    assert obligation["planned_evening_date"] == "2026-10-15"
    assert event["to_evening_date"] == "2026-10-15"
    assert "截止风险" in event["reason"]
