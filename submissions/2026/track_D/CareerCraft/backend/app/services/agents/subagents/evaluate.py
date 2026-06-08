"""``SubmissionEvaluateSubagent`` — produces a structured peer review.

Lifted verbatim from the legacy ``app.services.agent.evaluate_submission``
plus its two fallbacks. Behavior is preserved so existing tests pass.

Career-aware whitelist filtering of ``experience_gains`` lives in the
orchestrator (or the legacy ``services/eval.py``) -- not here -- because
that is a persistence/policy concern, not an LLM concern.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.llm import LLMProviderError
from app.services.agents.base import (
    EvaluationContext,
    SubagentError,
    SubagentResult,
    stopwatch,
)
from app.services.agents.llm_io import call_llm_json, llm_disabled

logger = logging.getLogger(__name__)


def build_eval_schema(career_id: str) -> dict[str, Any]:
  """Build the LLM JSON Schema for an evaluation response.

  ``experience_gains`` is constrained to the legal skill-id set for
  ``career_id`` via ``additionalProperties: false`` plus per-key int props.
  """
  from app.services.skill_catalog import allowed_skills_for
  allowed = sorted(allowed_skills_for(career_id))
  return {
      "type": "object",
      "properties": {
          "status": {
              "type": "string",
              "enum": ["success", "fail"],
              "description": "要么是 'success'，要么是 'fail'",
          },
          "feedback": {
              "type": "string",
              "description": "极其符合你身份语气和头衔设定的结构化、有深度的中肯点评",
          },
          "experience_gains": {
              "type": "object",
              "description": "分配给用户的技能经验。键名必须是预设技能ID之一，数值为经验点（通常5至15）",
              "properties": {k: {"type": "integer", "minimum": 0} for k in allowed},
              "additionalProperties": False,
          },
          "trigger_feynman_challenge": {
              "type": "boolean",
              "description": "是否决定触发费曼挑战（追问理论名词）",
          },
          "feynman_question": {
              "type": ["string", "null"],
              "description": "要求用户用大白话或通俗类比解释的技术/数据分析名词。如果未触发，设为null",
          },
      },
      "required": [
          "status",
          "feedback",
          "experience_gains",
          "trigger_feynman_challenge",
          "feynman_question",
      ],
  }


_DATA_ANALYST_OFFLINE: dict[str, Any] = {
    "status": "success",
    "feedback": (
        "成果评审成功！问题拆解非常清晰，清洗逻辑合理地处理了异常空值，"
        "漏斗图准确定位了转化过程中的注册流失高点。建议的促活促成方案可行性极强，"
        "恭喜你，这是一份合格的专家报告！"
    ),
    "experience_gains": {
        "skill_data_cleaning": 10,
        "skill_exploratory_analysis": 5,
        "skill_business_insight": 5,
    },
    "trigger_feynman_challenge": True,
    "feynman_question": (
        "你在报告中提到了次日留存分组。请尝试用最简单、大白话的语言向没有技术背景的"
        "市场部同事解释，到底什么是次日留存率？"
    ),
}

_SOFTWARE_ENGINEER_OFFLINE: dict[str, Any] = {
    "status": "success",
    "feedback": (
        "代码评审通过：测试用例完整复现了 Bug 场景，修复点准确命中根因，"
        "命名与异常处理符合规范。继续保持这种「先复现、再修复」的工程纪律。"
    ),
    "experience_gains": {
        "skill_debugging": 10,
        "skill_unit_testing": 5,
        "skill_code_quality": 5,
    },
    "trigger_feynman_challenge": True,
    "feynman_question": (
        "你在 PR 描述里提到「单元测试」。请用大白话向非技术同事解释一下，"
        "为什么写测试反而能让我们写代码更快？"
    ),
}


def eval_offline_fallback(career_id: str) -> dict[str, Any]:
  if career_id == "career_software_engineer":
    return dict(_SOFTWARE_ENGINEER_OFFLINE)
  return dict(_DATA_ANALYST_OFFLINE)


def eval_error_fallback(career_id: str) -> dict[str, Any]:
  if career_id == "career_software_engineer":
    return {
        "status": "success",
        "feedback": "【离线仿真评审】定位准、修复稳，工程纪律到位，继续保持。",
        "experience_gains": {
            "skill_debugging": 8,
            "skill_unit_testing": 5,
            "skill_code_quality": 5,
        },
        "trigger_feynman_challenge": True,
        "feynman_question": "请你简要解释下，什么是单元测试？为什么它能显著降低回归成本？",
    }
  return {
      "status": "success",
      "feedback": "【离线仿真评审】问题拆解很到位，分析报告框架标准。恭喜你通过评审并点亮经验增长！",
      "experience_gains": {
          "skill_data_cleaning": 8,
          "skill_exploratory_analysis": 5,
          "skill_business_insight": 5,
      },
      "trigger_feynman_challenge": True,
      "feynman_question": "请你简要解释下，什么是数据清洗？为什么它通常占据数据分析师 70% 的工作量？",
  }


class SubmissionEvaluateSubagent:
  """LLM peer-review producing the evaluation payload."""

  name = "submission.evaluate"

  async def run(self, ctx: EvaluationContext) -> SubagentResult[dict[str, Any]]:
    if llm_disabled():
      await asyncio.sleep(0.5)
      with stopwatch() as elapsed:
        payload = eval_offline_fallback(ctx.career_id)
      return SubagentResult(payload=payload, elapsed_ms=elapsed())

    from app.services.skill_catalog import allowed_skills_for

    # Cap submission size to bound prompt tokens and reduce upstream latency.
    max_chars = 6000
    trimmed = ctx.submission_text
    if len(ctx.submission_text) > max_chars:
      trimmed = ctx.submission_text[:max_chars] + "\n...<truncated>"
      logger.info(
          "Truncated submission_text from %d to %d chars before LLM eval",
          len(ctx.submission_text), max_chars,
      )

    allowed_keys = sorted(allowed_skills_for(ctx.career_id))
    system_inst = (
        "你是一名极具角色感的职业导师 / 评审。"
        "评审语气和用词必须极其符合你的导师身份设定（冷静严谨 / 数据驱动），"
        "可合理引用对应正/负面头衔（如「人形代码注释生成器」「熵增对抗者」「混元形意代码掌门」等）"
        "进行鼓励或鞭策。仅输出符合 JSON Schema 的结构化评审数据，不要任何额外解释。"
    )

    excerpt_block = ""
    if ctx.artifact_excerpt:
      excerpt_block = (
          "\n物料文件（节选，前 8KB）：\n"
          "------\n"
          f"{ctx.artifact_excerpt}\n"
          "------\n"
      )

    prompt = (
        f"任务背景说明：{ctx.mission_description}\n"
        f"{excerpt_block}"
        f"用户提交成果：{trimmed}\n\n"
        "请针对用户的交付成果进行专业、详尽的技术或业务评审。"
        f"experience_gains 的键名只能是 {allowed_keys} 中的一个或多个。"
    )

    schema = build_eval_schema(ctx.career_id)
    with stopwatch() as elapsed:
      try:
        result = await call_llm_json(
            prompt=prompt, system=system_inst, json_schema=schema,
        )
        return SubagentResult(payload=result, elapsed_ms=elapsed())
      except LLMProviderError as e:
        raise SubagentError(f"LLM error: {e}") from e
      except Exception as e:
        raise SubagentError(f"unexpected error ({type(e).__name__}): {e}") from e

  async def fallback(self, ctx: EvaluationContext) -> SubagentResult[dict[str, Any]]:
    with stopwatch() as elapsed:
      payload = eval_error_fallback(ctx.career_id)
    return SubagentResult(payload=payload, used_fallback=True, elapsed_ms=elapsed())


__all__ = [
    "SubmissionEvaluateSubagent",
    "build_eval_schema",
    "eval_offline_fallback",
    "eval_error_fallback",
]
