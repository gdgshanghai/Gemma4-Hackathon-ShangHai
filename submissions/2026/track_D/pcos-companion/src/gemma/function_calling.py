"""
原生函数调用编排循环 —— 「她健康」对话引擎的心脏。

流程：
  1. 装好 system prompt（小暖人设）+ 历史 + 本轮用户输入；
  2. 带 tools 调 Gemma 4；模型若决定调用工具，返回结构化 tool_calls；
  3. 本地执行工具，把结果作为 role=tool 追加回上下文；
  4. 再次调模型，直到它给出最终自然语言回复（或达到最大轮次）。
危机干预工具一旦触发 halt_smalltalk，立即收口，优先安全。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import CONFIG, ModelTier
from src.gemma.client import GemmaClient
from src.tools.registry import TOOL_SCHEMAS, dispatch
from src.safety.guardrails import screen_user_input, screen_model_output

# 装配所有工具实现
import src.tools.symptom          # noqa: F401
import src.tools.risk_assessment  # noqa: F401
import src.tools.knowledge        # noqa: F401
import src.tools.clinic           # noqa: F401
import src.tools.safety           # noqa: F401
import src.gemma.multimodal       # noqa: F401

_PERSONA = (Path(__file__).resolve().parents[1]
            / "persona" / "xiaonuan_system_prompt.txt").read_text(encoding="utf-8")


def run_turn(
    user_input: str,
    history: list[dict[str, Any]],
    context: dict[str, Any],
    tier: ModelTier | None = None,
) -> dict[str, Any]:
    """跑完一轮对话，返回 {reply, tool_trace, escalated}。"""
    tier = tier or CONFIG.default_tier

    # 入口安全过滤：危险信号直接走危机工具，不经模型自由发挥
    pre = screen_user_input(user_input)
    if pre.get("force_crisis"):
        result = dispatch("escalate_to_crisis_support",
                          {"signal": pre["signal"]}, context)
        return {"reply": result["guidance"], "tool_trace": [result], "escalated": True}

    client = GemmaClient(tier=tier)
    messages: list[dict[str, Any]] = [{"role": "system", "content": _PERSONA}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_input})

    tool_trace: list[dict[str, Any]] = []
    escalated = False

    try:
        for _ in range(CONFIG.max_tool_iterations):
            resp = client.chat(messages, tools=TOOL_SCHEMAS)
            calls = GemmaClient.extract_tool_calls(resp)

            if not calls:
                reply = GemmaClient.extract_text(resp)
                return {"reply": screen_model_output(reply),
                        "tool_trace": tool_trace, "escalated": escalated}

            # 把助手的工具调用意图记回上下文
            messages.append(resp["choices"][0]["message"])

            for call in calls:
                result = dispatch(call["name"], call["arguments"], context)
                tool_trace.append({"call": call, "result": result})
                if result.get("halt_smalltalk"):
                    escalated = True
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": call["name"],
                    "content": json.dumps(result, ensure_ascii=False),
                })

            if escalated:  # 危机优先收口
                guidance = next((t["result"]["guidance"] for t in tool_trace
                                 if t["result"].get("halt_smalltalk")), "")
                return {"reply": guidance, "tool_trace": tool_trace, "escalated": True}

        # 兜底：达到最大轮次仍未收敛
        final = client.chat(messages)
        return {"reply": screen_model_output(GemmaClient.extract_text(final)),
                "tool_trace": tool_trace, "escalated": escalated}
    finally:
        client.close()
