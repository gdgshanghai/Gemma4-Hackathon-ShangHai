"""症状记录 / 月经日志 —— 写入用户本地（自托管）健康档案。"""
from __future__ import annotations

from datetime import date
from typing import Any

from src.tools.registry import register
from src.privacy.data_governance import write_profile_event


def record_symptom(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    event = {
        "kind": "symptom",
        "symptom_type": args.get("symptom_type", "其他"),
        "severity": args.get("severity", "中"),
        "note": args.get("note", ""),
    }
    write_profile_event(context["user_id"], event)
    return {"tool": "record_symptom", "status": "saved", "saved": event}


def log_menstrual_period(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    start = args.get("start_date") or date.today().isoformat()
    event = {"kind": "period", "start_date": start, "flow_level": args.get("flow_level")}
    cycle_days = _estimate_cycle(context["user_id"], start)
    write_profile_event(context["user_id"], event)
    return {"tool": "log_menstrual_period", "status": "saved",
            "saved": event, "estimated_cycle_days": cycle_days}


def _estimate_cycle(user_id: str, latest_start: str) -> int | None:
    """与上一条月经记录相减，估算周期天数（仅示意）。"""
    from src.privacy.data_governance import read_profile_events
    periods = [e for e in read_profile_events(user_id) if e.get("kind") == "period"]
    if not periods:
        return None
    try:
        prev = date.fromisoformat(periods[-1]["start_date"])
        cur = date.fromisoformat(latest_start)
        return (cur - prev).days
    except (KeyError, ValueError):
        return None


register("record_symptom", record_symptom)
register("log_menstrual_period", log_menstrual_period)
