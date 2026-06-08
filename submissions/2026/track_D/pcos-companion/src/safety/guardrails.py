"""输入/输出安全护栏 —— 危机词强制干预 + 输出红线兜底。"""
from __future__ import annotations

import re

_SELF_HARM = ["不想活", "自杀", "活不下去", "结束自己", "伤害自己", "想死"]
_ACUTE = ["大量出血", "剧烈腹痛", "晕倒", "昏迷", "视力模糊", "剧烈头痛"]

# 输出红线：模型若越界，做最小化纠正
_FORBIDDEN_OUTPUT = [
    (re.compile(r"你(确诊|得了|患有|就是)多囊"), "你描述的情况值得找医生确认一下"),
    (re.compile(r"建议你服用[\u4e00-\u9fff A-Za-z0-9\-]+"), "用药请和医生讨论"),
]


def screen_user_input(text: str) -> dict:
    if any(k in text for k in _SELF_HARM):
        return {"force_crisis": True, "signal": "self_harm"}
    if any(k in text for k in _ACUTE):
        return {"force_crisis": True, "signal": "acute_physical"}
    return {"force_crisis": False}


def screen_model_output(text: str) -> str:
    for pattern, replacement in _FORBIDDEN_OUTPUT:
        text = pattern.sub(replacement, text)
    if "仅供参考" not in text and ("吃" in text or "建议" in text):
        text += "\n\n（以上仅供参考，不替代医嘱。）"
    return text
