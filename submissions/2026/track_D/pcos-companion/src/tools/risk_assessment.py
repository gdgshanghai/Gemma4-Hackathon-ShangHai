"""
PCOS 初步『关注度』评分 —— 确定性规则，绝不交给大模型。

依据鹿特丹标准的三要素（稀发排卵/月经稀发、高雄表现、卵巢多囊样改变）
做*症状层面*的提示性评分。这只是「是否值得就医确认」的信号，
不构成诊断，也不替代医生。把它做成函数而非 prompt，是合规的关键设计：
模型只能"调用"它拿到结果并温柔转述，无法自行"宣布"用户患病。
"""
from __future__ import annotations

from typing import Any

from src.tools.registry import register


def assess_pcos_risk(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    irregular = bool(args.get("irregular_cycle"))
    hyperandrogen = bool(args.get("hyperandrogen_signs"))
    metabolic = bool(args.get("metabolic_signs"))

    score = sum([irregular, hyperandrogen, metabolic])

    if score >= 2:
        level = "建议关注"
        message = (
            "你描述的这些情况里，有几项是 PCOS 比较典型的方向，值得找妇科/内分泌"
            "医生做一次正式评估。这不是诊断，只是说明值得去确认一下。"
        )
    elif score == 1:
        level = "可以留意"
        message = (
            "目前的信息里有一项值得留意，可以先观察记录，"
            "如果持续或加重，再考虑就医。"
        )
    else:
        level = "暂无明显信号"
        message = "目前没有明显的提示信号，保持记录即可。"

    return {
        "tool": "assess_pcos_risk",
        "level": level,
        "matched_factors": {
            "月经稀发/不规律": irregular,
            "高雄表现": hyperandrogen,
            "代谢异常": metabolic,
        },
        "message": message,
        "disclaimer": "本结果由规则评分生成，不是医学诊断，请以医生面诊为准。",
    }


register("assess_pcos_risk", assess_pcos_risk)
