from datetime import date

from backend.domain.deadlines import resolve_deadline


PLANNING_DATE = date(2026, 10, 12)  # Monday


def test_tomorrow_morning_is_required_on_the_planning_evening() -> None:
    result = resolve_deadline("明早检查", PLANNING_DATE, "Asia/Shanghai")

    assert result.due_at.isoformat() == "2026-10-13T08:00:00+08:00"
    assert result.latest_safe_evening == PLANNING_DATE
    assert result.must_do_tonight is True


def test_friday_submission_from_monday_is_scheduled_for_wednesday() -> None:
    result = resolve_deadline("周五提交", PLANNING_DATE, "Asia/Shanghai")

    assert result.due_at.date() == date(2026, 10, 16)
    assert result.latest_safe_evening == date(2026, 10, 15)
    assert result.planned_evening_date == date(2026, 10, 14)
    assert result.must_do_tonight is False


def test_next_monday_submission_receives_a_future_evening() -> None:
    result = resolve_deadline("下周一提交", PLANNING_DATE, "Asia/Shanghai")

    assert result.due_at.date() == date(2026, 10, 19)
    assert result.latest_safe_evening == date(2026, 10, 18)
    assert result.planned_evening_date == date(2026, 10, 17)
    assert result.must_do_tonight is False


def test_unknown_school_deadline_stays_required_without_inventing_a_date() -> None:
    result = resolve_deadline("老师之后会通知", PLANNING_DATE, "Asia/Shanghai")

    assert result.due_at is None
    assert result.latest_safe_evening is None
    assert result.planned_evening_date is None
    assert result.must_do_tonight is True
    assert result.display_label == "截止未说明，按今晚必做"
