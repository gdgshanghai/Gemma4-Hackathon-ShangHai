from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.contracts.models import Source, TaskCompletionState, TaskItem
from backend.domain.estimation import (
    EstimateEvidence,
    EstimateResult,
    conservative_estimate,
    estimation_key,
)


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)


def _task(
    *,
    subject: str | None = "mathematics",
    task_type: str | None = "written",
    child_estimate_minutes: int | None = None,
    remaining_percent: int = 100,
) -> TaskItem:
    return TaskItem(
        id="task-1",
        session_id="session-1",
        title="Homework",
        subject=subject,
        task_type=task_type,
        source=Source.SCHOOL,
        completion_state=TaskCompletionState.PENDING,
        estimated_minutes=0,
        conservative_minutes=0,
        priority=0,
        must_do_tonight=True,
        child_estimate_minutes=child_estimate_minutes,
        estimate_source="domain_default",
        estimate_confidence="low",
        avoidance_score=0,
        preference_score=0,
        remaining_percent=remaining_percent,
        created_at=NOW,
        updated_at=NOW,
    )


def test_three_positive_history_samples_use_nearest_rank_p80() -> None:
    evidence = EstimateEvidence(
        history_minutes=(10, 20, 30, 40, 50),
        parent_high_minutes=99,
    )

    result = conservative_estimate(_task(child_estimate_minutes=15), evidence, False)

    assert result == EstimateResult(
        minutes=40,
        source="history_p80",
        confidence="medium",
        sample_count=5,
    )


def test_six_history_samples_raise_confidence_to_high() -> None:
    evidence = EstimateEvidence(
        history_minutes=(10, 20, 30, 40, 50, 60),
        parent_high_minutes=None,
    )

    result = conservative_estimate(_task(), evidence, False)

    assert result.minutes == 50
    assert result.confidence == "high"
    assert result.sample_count == 6


def test_one_overrun_sample_conservatively_raises_the_next_estimate() -> None:
    evidence = EstimateEvidence(
        history_minutes=(50,),
        parent_high_minutes=None,
    )

    result = conservative_estimate(
        _task(child_estimate_minutes=20),
        evidence,
        adaptation_mode=True,
    )

    assert result == EstimateResult(
        minutes=50,
        source="history_p80",
        confidence="low",
        sample_count=1,
    )


def test_partial_parent_estimate_scales_to_remaining_work_and_rounds_to_five() -> None:
    result = conservative_estimate(
        _task(remaining_percent=50),
        EstimateEvidence(history_minutes=(), parent_high_minutes=34),
        adaptation_mode=True,
    )

    assert result.minutes == 20
    assert result.source == "parent_range"


def test_explicit_child_minutes_already_describe_remaining_work() -> None:
    result = conservative_estimate(
        _task(child_estimate_minutes=15, remaining_percent=50),
        EstimateEvidence(history_minutes=(), parent_high_minutes=None),
        adaptation_mode=True,
    )

    assert result.minutes == 15
    assert result.source == "child_adjusted"


def test_completed_task_has_zero_remaining_minutes() -> None:
    result = conservative_estimate(
        _task(remaining_percent=0),
        EstimateEvidence(history_minutes=(), parent_high_minutes=34),
        adaptation_mode=True,
    )

    assert result.minutes == 0


def test_fewer_than_three_positive_samples_fall_back_to_parent_high() -> None:
    evidence = EstimateEvidence(
        history_minutes=(0, -5, 12, 18),
        parent_high_minutes=42,
    )

    result = conservative_estimate(_task(child_estimate_minutes=10), evidence, False)

    assert result == EstimateResult(
        minutes=42,
        source="parent_range",
        confidence="medium",
        sample_count=2,
    )


def test_child_estimate_is_used_as_explicit_remaining_minutes() -> None:
    result = conservative_estimate(
        _task(child_estimate_minutes=21),
        EstimateEvidence(history_minutes=(), parent_high_minutes=None),
        False,
    )

    assert result == EstimateResult(
        minutes=21,
        source="child_adjusted",
        confidence="low",
        sample_count=0,
    )


@pytest.mark.parametrize(
    ("subject", "task_type", "expected"),
    [
        ("  MATH  ", " WRITTEN ", 30),
        ("Chinese", "written", 25),
        ("ENGLISH", "written", 20),
        ("mathematics", "recitation", 15),
        ("mathematics", "correction", 10),
        ("mathematics", "reading", 20),
        ("mathematics", "preparation", 10),
        ("数学", "书面", 30),
        ("语文", "背诵", 15),
        ("英语", "订正", 10),
        ("道德与法治", "阅读", 20),
        ("历史", "背诵", 15),
        ("地理", "预习", 10),
        ("生物", "准备材料", 10),
        ("science", "experiment", 20),
        (None, None, 20),
    ],
)
def test_domain_defaults_are_explicit_and_normalized(
    subject: str | None,
    task_type: str | None,
    expected: int,
) -> None:
    result = conservative_estimate(
        _task(subject=subject, task_type=task_type),
        EstimateEvidence(history_minutes=(), parent_high_minutes=None),
        False,
    )

    assert result.minutes == expected
    assert result.source == "domain_default"
    assert result.confidence == "low"


def test_adaptation_mode_does_not_expand_individual_tasks() -> None:
    result = conservative_estimate(
        _task(child_estimate_minutes=10),
        EstimateEvidence(history_minutes=(), parent_high_minutes=None),
        True,
    )

    assert result.minutes == 10
    assert result.source == "child_adjusted"


def test_adaptation_mode_does_not_increase_history_result() -> None:
    evidence = EstimateEvidence(
        history_minutes=(10, 20, 30),
        parent_high_minutes=None,
    )

    result = conservative_estimate(_task(), evidence, True)

    assert result.minutes == 30
    assert result.source == "history_p80"


@pytest.mark.parametrize(
    "evidence",
    [
        EstimateEvidence(history_minutes=(1, 1, 1), parent_high_minutes=None),
        EstimateEvidence(history_minutes=(), parent_high_minutes=0),
    ],
)
def test_estimates_have_a_five_minute_minimum(evidence: EstimateEvidence) -> None:
    result = conservative_estimate(_task(), evidence, False)

    assert result.minutes == 5


def test_non_integer_and_boolean_history_values_are_ignored() -> None:
    evidence = EstimateEvidence(
        history_minutes=(10, True, 20.5, 30),  # type: ignore[arg-type]
        parent_high_minutes=35,
    )

    result = conservative_estimate(_task(), evidence, False)

    assert result.source == "parent_range"
    assert result.sample_count == 2
    assert result.minutes == 35


@pytest.mark.parametrize(
    ("subject", "task_type", "title", "expected"),
    [
        ("数学", None, "有理数混合运算12题", ("mathematics", "written")),
        ("英语", None, "Unit 2词汇背诵", ("english", "recitation")),
        ("地理", None, "经纬网读图练习", ("geography", "map_reading")),
        ("语文", None, "阅读《朝花夕拾》", ("chinese", "reading")),
        ("生物", None, "预习下一课", ("biology", "preparation")),
        ("数学", None, "订正课堂错题", ("mathematics", "correction")),
    ],
)
def test_estimation_key_infers_canonical_task_type_from_title(
    subject: str,
    task_type: str | None,
    title: str,
    expected: tuple[str, str],
) -> None:
    assert estimation_key(subject, task_type, title=title) == expected


def test_busy_thursday_defaults_keep_full_and_tonight_workload_realistic() -> None:
    specifications = [
        ("语文阅读10页并摘录", "chinese", "reading", 67, True),
        ("完成作文提纲", "chinese", "written", 100, True),
        ("有理数混合运算12题", "mathematics", "written", 50, True),
        ("订正课堂错题2题", "mathematics", "correction", 100, True),
        ("Unit 2词汇20个", "english", "recitation", 100, True),
        ("背诵课文一段", "english", "recitation", 100, True),
        ("完成练习册2页", "english", "written", 50, True),
        ("历史时间轴5个节点", "history", "written", 50, False),
        ("经纬网练习8题", "geography", "map_reading", 100, True),
        ("订正地理课堂小测", "geography", "correction", 100, True),
        ("标注显微镜结构图", "biology", "written", 100, True),
        ("预习下一课", "biology", "preparation", 100, True),
        ("整理道法课堂笔记一页", "civics", "written", 50, False),
    ]
    estimates = [
        conservative_estimate(
            _task_with_title(title, subject, task_type, remaining),
            EstimateEvidence(history_minutes=(), parent_high_minutes=None),
            adaptation_mode=False,
        ).minutes
        for title, subject, task_type, remaining, _ in specifications
    ]
    tonight = sum(
        minutes
        for minutes, (*_, required) in zip(estimates, specifications, strict=True)
        if required
    )

    assert sum(estimates) == 155
    assert tonight == 135


def _task_with_title(
    title: str,
    subject: str,
    task_type: str,
    remaining_percent: int,
) -> TaskItem:
    task = _task(
        subject=subject,
        task_type=task_type,
        remaining_percent=remaining_percent,
    )
    task.title = title
    return task
