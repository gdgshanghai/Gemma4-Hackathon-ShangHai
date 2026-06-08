"""
零依赖 GPU 的本地演示：用一个模拟 Gemma 4 函数调用响应的假客户端，
跑通完整的「原生函数调用编排循环」，方便评委在没有显卡时也能看到效果。

真实运行时把 USE_MOCK 关掉即可对接 Ollama / vLLM 上的 Gemma 4。
"""
from __future__ import annotations

import json
from unittest.mock import patch

from src.gemma import function_calling
from src.config import ModelTier

# —— 模拟 Gemma 4 在不同输入下的「原生函数调用」决策 ——
_SCRIPT = {
    "我月经两个月没来了，好焦虑": [
        {"id": "c1", "name": "record_symptom",
         "args": {"symptom_type": "月经", "severity": "中", "note": "两个月没来，焦虑"}},
    ],
    "我去年血糖偏高，痘痘也一直反复": [
        {"id": "c2", "name": "assess_pcos_risk",
         "args": {"irregular_cycle": True, "hyperandrogen_signs": True, "metabolic_signs": True}},
    ],
    "下周要看妇科，我该问什么": [
        {"id": "c3", "name": "generate_clinic_checklist",
         "args": {"main_concern": "确认情况是否严重、要不要吃药"}},
    ],
}
_FINAL_TEXT = {
    "record_symptom": "记下了，两个月没来确实会让人焦虑 😔 先别慌，要不要我帮你看看是否值得去医院确认一下？（仅供参考，不替代医嘱。）",
    "assess_pcos_risk": "你说的这几项里有几个是 PCOS 比较典型的方向，值得找医生正式评估一下——这不是诊断，只是说明值得去确认。需要我帮你列个就诊小抄吗？",
    "generate_clinic_checklist": "帮你准备好「就诊小抄」啦：带上既往报告和最近的月经记录，到时候照着问医生就行 🌸 这些仅供参考，具体以医生为准。",
}


class FakeResp:
    @staticmethod
    def with_calls(calls):
        return {"choices": [{"message": {"role": "assistant", "content": None,
                "tool_calls": [{"id": c["id"], "type": "function",
                "function": {"name": c["name"], "arguments": json.dumps(c["args"])}}
                for c in calls]}}]}

    @staticmethod
    def with_text(text):
        return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def fake_chat(self, messages, tools=None, tool_choice="auto"):
    last_user = next((m["content"] for m in reversed(messages)
                      if m["role"] == "user"), "")
    if tools and last_user in _SCRIPT and not any(m["role"] == "tool" for m in messages):
        return FakeResp.with_calls(_SCRIPT[last_user])
    last_tool = next((m["name"] for m in reversed(messages)
                      if m["role"] == "tool"), None)
    return FakeResp.with_text(_FINAL_TEXT.get(last_tool, "我在听，你慢慢说 🌸"))


def main():
    with patch("src.gemma.client.GemmaClient.chat", fake_chat):
        ctx = {"user_id": "demo_user", "vision_consent": False, "image_path": None}
        for line in _SCRIPT:
            print(f"\n💬 用户：{line}")
            out = function_calling.run_turn(line, [], ctx, tier=ModelTier.EDGE)
            tools_used = [t["call"]["name"] for t in out["tool_trace"]]
            print(f"🔧 触发函数调用：{tools_used}")
            print(f"🌸 小暖：{out['reply']}")

        print("\n💬 用户：我最近总觉得活不下去")
        out = function_calling.run_turn("我最近总觉得活不下去", [], ctx)
        print(f"🚨 危机干预触发：escalated={out['escalated']}")
        print(f"🌸 小暖：{out['reply']}")


if __name__ == "__main__":
    main()
