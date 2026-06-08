"""危机干预 —— 把『安全兜底』做成强制函数，而不是寄望模型自觉。"""
from __future__ import annotations

from typing import Any

from src.config import CONFIG
from src.tools.registry import register


def escalate_to_crisis_support(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    signal = args.get("signal", "severe_other")
    if signal == "self_harm":
        guidance = (
            f"你现在的安全最重要。请立刻联系心理援助热线 {CONFIG.crisis_hotline}，"
            "或拨打 120。我会一直在这里陪你，但这件事需要专业的人来帮你。"
        )
    elif signal == "acute_physical":
        guidance = "你描述的情况比较紧急，建议现在就去急诊或拨打 120，不要拖。"
    else:
        guidance = "这些症状不太寻常，建议尽快就医，让医生当面判断。"
    return {
        "tool": "escalate_to_crisis_support",
        "signal": signal,
        "halt_smalltalk": True,   # 上层据此中止常规闲聊
        "guidance": guidance,
        "hotline": CONFIG.crisis_hotline,
    }


register("escalate_to_crisis_support", escalate_to_crisis_support)
