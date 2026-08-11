from __future__ import annotations

import json

import pytest

from backend.contracts.evening import IntakeDraftTask
from backend.domain.estimate_components import (
    WorkloadBand,
    build_reference_components,
    component_signature,
    reference_minutes,
)


def _task(**values: object) -> IntakeDraftTask:
    payload = {
        "title": "普通作业",
        "subject": "语文",
        "completion_state": "pending",
        **values,
    }
    return IntakeDraftTask.model_validate_json(json.dumps(payload, ensure_ascii=False))


@pytest.mark.parametrize(
    ("task", "expected", "total"),
    [
        (
            _task(
                title="阅读《朝花夕拾》15页并摘录两处，完成一份作文提纲",
                subject="语文",
                completion_state="partial",
                notes="已读5页，还剩10页和两处摘录，作文提纲还没做",
            ),
            [("reading", 20), ("written", 10)],
            30,
        ),
        (
            _task(
                title="完成有理数混合运算12题，订正课堂错题2题",
                subject="数学",
                completion_state="partial",
                notes="已完成前6题，错题还没订正",
            ),
            [("written", 10), ("correction", 5)],
            15,
        ),
        (
            _task(
                title="Unit 2词汇20个，背诵课文一段，完成练习册2页",
                subject="英语",
                completion_state="partial",
                notes="练习册做完1页，词汇和课文背诵都没做",
            ),
            [("recitation", 20), ("written", 10)],
            30,
        ),
        (
            _task(
                title="完成中国早期人类时间轴5个节点",
                subject="历史",
                completion_state="partial",
                notes="完成了一半",
            ),
            [("written", 10)],
            10,
        ),
        (
            _task(
                title="完成经纬网练习8题，订正课堂小测",
                subject="地理",
            ),
            [("map_reading", 20), ("correction", 5)],
            25,
        ),
        (
            _task(
                title="标注显微镜结构图，预习下一课",
                subject="生物",
            ),
            [("written", 5), ("preparation", 10)],
            15,
        ),
        (
            _task(
                title="整理中学生活课堂笔记一页",
                subject="道德与法治",
                completion_state="partial",
                notes="整理了一半",
            ),
            [("written", 10)],
            10,
        ),
    ],
)
def test_busy_thursday_uses_component_reference_baselines(
    task: IntakeDraftTask,
    expected: list[tuple[str, int]],
    total: int,
) -> None:
    components = build_reference_components(task)

    assert [(item.task_type, item.calibrated_minutes) for item in components] == expected
    assert sum(item.calibrated_minutes for item in components) == total
    assert component_signature(components) == "+".join(
        sorted(item.component for item in components)
    )


def test_structured_progress_overrides_total_quantity_in_title() -> None:
    task = _task(
        title="有理数混合运算12题及订正课堂错题",
        subject="数学",
        completion_state="partial",
        total_units=12,
        completed_units=6,
        notes="错题还没订正。",
    )

    components = build_reference_components(task)
    written_questions = next(
        item for item in components if item.component == "written_questions"
    )

    assert written_questions.remaining_quantity == 6
    assert written_questions.reference_minutes == 10


def test_zero_remaining_math_questions_only_keeps_correction_work() -> None:
    task = _task(
        title="有理数混合运算12题及订正课堂错题",
        subject="数学",
        completion_state="partial",
        total_units=12,
        completed_units=12,
        notes="运算题已经完成，错题还没订正。",
    )

    components = build_reference_components(task)

    assert [(item.component, item.reference_minutes) for item in components] == [
        ("correction", 5)
    ]


def test_completed_task_has_no_remaining_components() -> None:
    task = _task(completion_state="completed")

    assert build_reference_components(task) == ()


@pytest.mark.parametrize(
    ("band", "expected"),
    [
        (WorkloadBand.SMALL, 15),
        (WorkloadBand.MEDIUM, 20),
        (WorkloadBand.LARGE, 30),
    ],
)
def test_workload_band_scales_reference_and_rounds_to_five(
    band: WorkloadBand,
    expected: int,
) -> None:
    assert reference_minutes("mathematics", "written", band) == expected
