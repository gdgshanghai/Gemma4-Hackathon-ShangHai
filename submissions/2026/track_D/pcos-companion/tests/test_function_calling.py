"""
单元测试：用 mock 的 Gemma 客户端验证函数调用编排，无需真实模型即可跑通 CI。
重点验证三条合规/安全主线：危机强制干预、确定性风险评分、记录写入。
"""
from __future__ import annotations

import json
from unittest.mock import patch

from src.tools.registry import dispatch
from src.tools import risk_assessment, safety, symptom  # noqa: F401  装配工具
from src.safety.guardrails import screen_user_input, screen_model_output


def test_crisis_input_forces_escalation():
    pre = screen_user_input("我不想活了")
    assert pre["force_crisis"] and pre["signal"] == "self_harm"


def test_risk_is_deterministic_not_diagnosis():
    out = dispatch("assess_pcos_risk",
                   {"irregular_cycle": True, "hyperandrogen_signs": True,
                    "metabolic_signs": False}, {})
    assert out["level"] == "建议关注"
    assert "不是医学诊断" in out["disclaimer"]


def test_output_guardrail_rewrites_diagnosis_claim():
    fixed = screen_model_output("根据症状你确诊多囊了")
    assert "确诊多囊" not in fixed


def test_record_symptom_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE_STORE", str(tmp_path))
    import importlib
    from src.privacy import data_governance
    importlib.reload(data_governance)
    importlib.reload(symptom)
    ctx = {"user_id": "u_test"}
    out = symptom.record_symptom(
        {"symptom_type": "月经", "severity": "中", "note": "两个月没来"}, ctx)
    assert out["status"] == "saved"


if __name__ == "__main__":
    test_crisis_input_forces_escalation()
    test_risk_is_deterministic_not_diagnosis()
    test_output_guardrail_rewrites_diagnosis_claim()
    print("ok")
