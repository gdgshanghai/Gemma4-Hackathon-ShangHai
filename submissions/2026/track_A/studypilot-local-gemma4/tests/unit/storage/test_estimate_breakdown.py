from __future__ import annotations

import json
from pathlib import Path

from backend.contracts.evening import SaveIntakeDraftArguments
from backend.storage.database import connect_database, run_migrations
from backend.storage.evening_workflow import EveningWorkflowRepository


def test_inventory_persists_busy_thursday_component_baseline(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "component-baseline.db"
    run_migrations(database_path)
    repository = EveningWorkflowRepository(database_path)
    created = repository.create(
        session_date="2026-10-15",
        planning_date="2026-10-15",
        timezone="Asia/Shanghai",
        sleep_time="22:20:00",
        available_minutes=170,
        expected_version=0,
        caller_idempotency_key="create-components",
        trace_id="trace-create-components",
    )
    session_id = str(created["view"]["session_id"])
    repository.save_intake_draft(
        session_id=session_id,
        arguments=SaveIntakeDraftArguments.model_validate_json(
            json.dumps(
                {
                    "tasks": [
                        {
                            "title": "阅读《朝花夕拾》15页并摘录两处，完成一份作文提纲",
                            "subject": "语文",
                            "completion_state": "partial",
                            "notes": "已读5页，还剩10页和两处摘录，作文提纲还没做",
                            "deadline_text": "明早检查",
                        },
                        {
                            "title": "完成有理数混合运算12题，订正课堂错题2题",
                            "subject": "数学",
                            "completion_state": "partial",
                            "notes": "已完成前6题，错题还没订正",
                            "deadline_text": "明早检查",
                        },
                        {
                            "title": "Unit 2词汇20个，背诵课文一段，完成练习册2页",
                            "subject": "英语",
                            "completion_state": "partial",
                            "notes": "练习册做完1页，词汇和课文背诵都没做",
                            "deadline_text": "明早检查",
                        },
                        {
                            "title": "完成中国早期人类时间轴5个节点",
                            "subject": "历史",
                            "completion_state": "partial",
                            "notes": "完成了一半",
                            "deadline_text": "下周一提交",
                        },
                        {
                            "title": "完成经纬网练习8题，订正课堂小测",
                            "subject": "地理",
                            "deadline_text": "明早检查",
                        },
                        {
                            "title": "标注显微镜结构图，预习下一课",
                            "subject": "生物",
                            "deadline_text": "明早检查",
                        },
                        {
                            "title": "整理中学生活课堂笔记一页",
                            "subject": "道德与法治",
                            "completion_state": "partial",
                            "notes": "整理了一半",
                            "deadline_text": "下周一提交",
                        },
                    ]
                },
                ensure_ascii=False,
            )
        ),
        expected_version=1,
        hidden_idempotency_key="draft-components",
    )

    confirmed = repository.confirm_inventory(
        session_id=session_id,
        expected_version=2,
        profile_version=0,
        parent_high_minutes=(None,) * 7,
        caller_idempotency_key="confirm-components",
        trace_id="trace-confirm-components",
    )

    inventory = confirmed["view"]["inventory"]
    assert [task["conservative_minutes"] for task in inventory] == [
        30,
        15,
        30,
        10,
        25,
        15,
        10,
    ]
    assert all(task["estimate_breakdown"] for task in inventory)
    assert all(
        sum(item["calibrated_minutes"] for item in task["estimate_breakdown"])
        == task["conservative_minutes"]
        for task in inventory
    )
    assert all(task["estimate_signature"] for task in inventory)

    with connect_database(database_path) as connection:
        task_rows = connection.execute(
            "SELECT estimate_breakdown_json, estimate_signature FROM task_items"
        ).fetchall()
        obligation_rows = connection.execute(
            "SELECT estimate_breakdown_json, estimate_signature "
            "FROM assignment_obligations"
        ).fetchall()
    assert all(json.loads(row["estimate_breakdown_json"]) for row in task_rows)
    assert all(row["estimate_signature"] for row in task_rows)
    assert all(json.loads(row["estimate_breakdown_json"]) for row in obligation_rows)
    assert all(row["estimate_signature"] for row in obligation_rows)
