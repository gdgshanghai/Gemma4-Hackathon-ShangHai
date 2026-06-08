"""就诊小抄生成 —— 把症状档案 + 主诉转成可带去门诊的清单。"""
from __future__ import annotations

from typing import Any

from src.tools.registry import register
from src.privacy.data_governance import read_profile_events


def generate_clinic_checklist(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    concern = args.get("main_concern", "PCOS 综合管理")
    events = read_profile_events(context["user_id"])
    symptoms = [e for e in events if e.get("kind") == "symptom"]
    periods = [e for e in events if e.get("kind") == "period"]

    bring = ["既往检查报告（性激素六项、B 超、血糖/胰岛素）"]
    if periods:
        bring.append(f"最近 {min(len(periods), 3)} 次月经日期记录")
    if any(s.get("symptom_type") == "血糖" for s in symptoms):
        bring.append("近期空腹血糖/糖耐量结果")

    questions = [
        f"针对我最关心的「{concern}」，目前应该先做哪些检查？",
        "我的情况属于哪种类型（高雄型/胰岛素抵抗型/其他）？",
        "现在需要药物干预吗？如果需要，有哪些选择和注意事项？",
        "生活方式上，最该优先调整的是什么？",
        "下次复查间隔多久，需要复查哪些项目？",
    ]
    return {
        "tool": "generate_clinic_checklist",
        "main_concern": concern,
        "bring_to_clinic": bring,
        "questions_for_doctor": questions,
    }


register("generate_clinic_checklist", generate_clinic_checklist)
