"""``MissionSpecSubagent`` — produces a mission spec.

Lifted from the legacy ``app.services.agent.create_mission`` plus its
fallback. Behavior is preserved exactly so existing tests pass; the only
structural change is splitting it into a class with ``run``/``fallback``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.llm import LLMProviderError
from app.services.agents.base import (
    MissionContext,
    SubagentError,
    SubagentResult,
    stopwatch,
)
from app.services.agents.llm_io import (
    call_llm_json,
    llm_disabled,
    unwrap_to_required_keys,
)
from app.services.mission_catalog import get_mission_spec
from app.services.role_prompts import get_system_prompt

logger = logging.getLogger(__name__)


_MISSION_SCHEMA_BASE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1, "description": "任务的精炼标题"},
        "description": {"type": "string", "minLength": 1},
        "business_background": {"type": "string", "minLength": 1},
        "objectives": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "2到4个任务目标",
        },
        "delivery_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "2到3个具体、可衡量的技术/业务交付物审计标准",
        },
        "evaluation_criteria": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "3到5个评审标准",
        },
        "recommended_skills": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
        "recommended_resources": {
            "type": "array",
            "items": {"type": "string"},
        },
        "estimated_time": {"type": "string", "minLength": 1},
    },
    "required": [
        "title",
        "description",
        "business_background",
        "objectives",
        "delivery_requirements",
        "evaluation_criteria",
        "recommended_skills",
        "recommended_resources",
        "estimated_time",
    ],
}

TASK_DIRECTION_LABELS = {
    "data-cleaning": "数据清洗",
    "sql-analysis": "SQL 分析",
    "visualization": "可视化报告",
    "bug-fix": "Bug 修复",
    "unit-test": "单元测试",
    "api-design": "API 设计",
}

MISSION_STYLE_LABELS = {
    "ticket": "企业工单",
    "project": "项目委托",
    "interview": "面试实战",
    "feynman": "费曼讲解型",
}

MISSION_STYLE_INSTRUCTIONS = {
    "ticket": "以真实企业工单形式描述，突出问题、限制条件、验收标准。",
    "project": "以项目委托形式描述，突出背景、目标、交付物和业务价值。",
    "interview": "以面试实战形式描述，突出考察点、边界条件和追问。",
    "feynman": (
        "以费曼讲解型任务描述，要求玩家解释关键概念，"
        "但不要激活或声称已经进入系统 Feynman challenge。"
    ),
}


def mission_from_catalog(spec: dict[str, Any]) -> dict[str, Any]:
  """Project a catalog spec into the mission-response payload shape."""
  return {
      "mission_id": spec["id"],
      "title": spec["title"],
      "description": spec["description"],
      "mock_data_url": spec["mock_data_url"],
      "business_background": spec["description"],
      "objectives": spec["delivery_requirements"],
      "delivery_requirements": spec["delivery_requirements"],
      "evaluation_criteria": [
          "Problem understanding is clear",
          "Deliverables are complete",
          "Recommendations are actionable",
      ],
      "recommended_skills": [],
      "recommended_resources": [],
      "estimated_time": "",
  }


def generic_mission_fallback(role_id: str, difficulty: str) -> dict[str, Any]:
  """Hard-coded fallback used when both LLM and catalog lookup fail."""
  return {
      "mission_id": f"mvp_mission_{role_id}_{difficulty}",
      "title": "分析社区论坛用户活跃度下降原因 (Fallback)",
      "description": (
          "由于网络连接原因，触发了备用任务：近期社区论坛日活跃用户数下滑。"
          "请下载原始日志包分析漏斗跌幅最大的环节并提交分析报告。"
      ),
      "mock_data_url": "https://example.com/mock_data/forum_logs_2026.csv",
      "business_background": "近期社区论坛日活跃用户数下滑，需要定位关键流失环节。",
      "objectives": [
          "清洗并核对原始日志中的异常记录",
          "定位漏斗跌幅最大的环节",
          "提出可执行的促活建议",
      ],
      "delivery_requirements": [
          "清晰的数据清洗与归因逻辑",
          "包含至少一张用户流失漏斗图",
          "提出两点具体可行的促活建议",
      ],
      "evaluation_criteria": [
          "Problem understanding is clear",
          "Deliverables are complete",
          "Recommendations are actionable",
      ],
      "recommended_skills": ["数据清洗", "漏斗分析"],
      "recommended_resources": [],
      "estimated_time": "",
  }


class MissionSpecSubagent:
  """Generate a mission spec for ``ctx.role_id`` via LLM."""

  name = "mission.spec"

  async def run(self, ctx: MissionContext) -> SubagentResult[dict[str, Any]]:
    spec = get_mission_spec(ctx.role_id, ctx.task_index)

    if llm_disabled():
      await asyncio.sleep(0.5)
      with stopwatch() as elapsed:
        payload = mission_from_catalog(spec)
      return SubagentResult(payload=payload, elapsed_ms=elapsed())

    system_inst = get_system_prompt(ctx.role_id)
    task_direction_label = TASK_DIRECTION_LABELS.get(
        ctx.task_direction or "", ctx.task_direction or "默认方向",
    )
    mission_style_label = MISSION_STYLE_LABELS.get(
        ctx.mission_style or "", ctx.mission_style or "企业工单",
    )
    style_instruction = MISSION_STYLE_INSTRUCTIONS.get(
        ctx.mission_style or "ticket", MISSION_STYLE_INSTRUCTIONS["ticket"],
    )
    prompt = (
        f"你现在作为职业导师（ID: {ctx.role_id}）。根据以下任务模板为玩家动态生成一个最契合当前进度的实战任务：\n"
        f"任务方向：{task_direction_label}\n"
        f"任务风格：{mission_style_label}\n"
        f"风格要求：{style_instruction}\n"
        f"任务大纲模板：\n"
        f"标题：{spec['title']}\n"
        f"描述：{spec['description']}\n"
        f"参考交付物要求：{', '.join(spec['delivery_requirements'])}\n\n"
        f"请在此模板基础上，结合你的专业性格特点（难度为：{ctx.difficulty}），进行高拟真度的任务情境扩充，"
        f"让玩家感受到沉浸式的职场实战氛围。\n\n"
        "【严格输出格式约束】返回的 JSON 必须是平铺对象，且只能包含以下顶层字段："
        "title (string)、description (string)、business_background (string)、objectives (string[])、"
        "delivery_requirements (string[])、evaluation_criteria (string[])、recommended_skills (string[])、"
        "recommended_resources (string[])、estimated_time (string)。"
        "禁止将这些字段包装在 task / task_config / task_details / context / deliverables 等任何容器中，"
        "禁止额外添加 mission_id / role_id / career_id / status / reward_xp / reward_skills / "
        "mock_data_url / mock_data_filename / feynman_active / role_name / system / from / to / ticket_id 等字段。"
    )

    schema = {
        **_MISSION_SCHEMA_BASE,
        "properties": {
            **_MISSION_SCHEMA_BASE["properties"],
            "description": {
                "type": "string",
                "description": f"任务的详细背景及操作指引。必须参考对应模板：{spec['description']}",
            },
        },
    }

    required_keys = tuple(_MISSION_SCHEMA_BASE["required"])
    with stopwatch() as elapsed:
      try:
        result = await call_llm_json(prompt=prompt, system=system_inst, json_schema=schema)
        logger.debug("mission.spec parsed payload: %s", result)
        unwrapped = unwrap_to_required_keys(result, required_keys)
        if unwrapped is None:
          raise SubagentError(
              f"mission.spec response missing required keys {required_keys}: "
              f"top-level keys were {list(result)}"
          )
        unwrapped["mission_id"] = spec["id"]
        return SubagentResult(payload=unwrapped, elapsed_ms=elapsed())
      except LLMProviderError as e:
        raise SubagentError(f"LLM error: {e}") from e
      except SubagentError:
        raise
      except Exception as e:
        # Catch-all so non-provider failures (SDK / runtime / asyncio) still
        # take the orchestrator's fallback branch instead of becoming 5xx.
        raise SubagentError(f"unexpected error ({type(e).__name__}): {e}") from e

  async def fallback(self, ctx: MissionContext) -> SubagentResult[dict[str, Any]]:
    with stopwatch() as elapsed:
      payload = generic_mission_fallback(ctx.role_id, ctx.difficulty)
    return SubagentResult(payload=payload, used_fallback=True, elapsed_ms=elapsed())


__all__ = [
    "MissionSpecSubagent",
    "mission_from_catalog",
    "generic_mission_fallback",
]
