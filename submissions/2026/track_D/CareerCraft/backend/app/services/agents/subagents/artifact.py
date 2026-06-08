"""``MissionArtifactSubagent`` — produces the downloadable data file.

Stage 2 of the mission pipeline. The LLM returns ``{filename, mime_type,
content}`` constrained by a JSON Schema and a 64 KiB size cap. Fallback
copies a bundled sample file shipped under
``backend/app/data/missions/samples/``.

This subagent is created in PR-2 but not wired into the mission service
until PR-3, when the orchestrator and the new ``mock_data_filename`` ORM
column land together.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.llm import LLMProviderError
from app.core.paths import samples_dir
from app.services.agents.base import (
    MissionContext,
    SubagentError,
    SubagentResult,
    stopwatch,
)
from app.services.agents.llm_io import call_llm_json, llm_disabled
from app.services.role_prompts import get_system_prompt
from app.services.storage.artifact_store import (
    MIME_EXTENSIONS,
    MissionArtifact,
)

logger = logging.getLogger(__name__)


# Hard cap on artifact body size. Beyond this we fall back to a sample to
# bound static-serving cost and protect the frontend renderer.
MAX_CONTENT_BYTES = 64 * 1024


_ARTIFACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "filename": {
            "type": "string",
            "minLength": 1,
            "maxLength": 80,
            "description": "建议的文件名（不含路径）",
        },
        "mime_type": {
            "type": "string",
            "enum": list(MIME_EXTENSIONS.keys()),
            "description": "文件 MIME 类型，必须是白名单内的纯文本类型之一",
        },
        "content": {
            "type": "string",
            "minLength": 1,
            "description": "文件内容（纯文本，不要包裹 markdown 围栏）",
        },
    },
    "required": ["filename", "mime_type", "content"],
}


def _sample_path_for(catalog_mission_id: str) -> Path:
  """Locate the bundled sample file for a catalog mission id.

  The samples directory may hold any extension; we glob by basename.
  """
  base = samples_dir()
  for entry in base.glob(f"{catalog_mission_id}.*"):
    if entry.is_file():
      return entry
  raise FileNotFoundError(
      f"No bundled sample artifact for {catalog_mission_id} under {base}"
  )


def _build_artifact_prompt(ctx: MissionContext) -> str:
  spec = ctx.spec or {}
  reqs = "\n".join(f"- {r}" for r in spec.get("delivery_requirements", []))
  return (
      "请基于以下任务为玩家生成一份**真实可分析**的原始物料文件，文件内容必须能让玩家"
      "据此完成上述交付要求。不要返回 markdown 围栏，不要解释，直接把数据/源码/日志放进 content 字段。\n\n"
      f"任务标题：{spec.get('title', '')}\n"
      f"任务描述：{spec.get('description', '')}\n"
      f"交付要求：\n{reqs}\n\n"
      "选择一种最贴合任务的纯文本格式（CSV/JSON/Markdown/纯文本/Python/日志）。"
      "若是 CSV，至少给 80 行真实样本（含表头），可以包含异常值/空值以匹配清洗类任务。"
      "若是源码，给一个能复现 Bug 或可重构的最小代码片段。"
      "总长度不得超过 60 KB。"
  )


class MissionArtifactSubagent:
  """Generate the downloadable data file accompanying a mission."""

  name = "mission.artifact"

  async def run(self, ctx: MissionContext) -> SubagentResult[MissionArtifact]:
    if llm_disabled():
      raise SubagentError("LLM disabled; using bundled sample")

    if not ctx.spec:
      raise SubagentError("MissionContext.spec is required for artifact stage")

    system_inst = get_system_prompt(ctx.role_id)
    prompt = _build_artifact_prompt(ctx)

    with stopwatch() as elapsed:
      try:
        result = await call_llm_json(
            prompt=prompt, system=system_inst, json_schema=_ARTIFACT_SCHEMA,
        )
      except LLMProviderError as e:
        raise SubagentError(f"LLM error: {e}") from e
      except Exception as e:
        raise SubagentError(f"unexpected error ({type(e).__name__}): {e}") from e

      content = result.get("content")
      mime = result.get("mime_type")
      filename = result.get("filename")
      if not (isinstance(content, str) and isinstance(mime, str) and isinstance(filename, str)):
        raise SubagentError(f"artifact response missing fields: {list(result)}")

      if mime not in MIME_EXTENSIONS:
        raise SubagentError(f"artifact mime_type not in whitelist: {mime!r}")

      if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
        raise SubagentError(
            f"artifact content exceeds {MAX_CONTENT_BYTES} bytes"
        )

      artifact = MissionArtifact(filename=filename, mime_type=mime, content=content)
      return SubagentResult(payload=artifact, elapsed_ms=elapsed())

  async def fallback(self, ctx: MissionContext) -> SubagentResult[MissionArtifact]:
    """Read a bundled sample and wrap it as a ``MissionArtifact``.

    The orchestrator will call ``ArtifactStorage.copy_sample`` on the
    returned payload's ``meta['sample_path']`` rather than re-writing the
    same bytes through ``persist``. This keeps the storage adapter the
    single point that knows about file IO.
    """
    spec = ctx.spec or {}
    catalog_id = spec.get("mission_id") or f"mvp_mission_{ctx.role_id}_1"
    with stopwatch() as elapsed:
      try:
        sample_path = _sample_path_for(catalog_id)
      except FileNotFoundError:
        # Last-resort: synthesize a tiny placeholder so the pipeline never
        # fails outright. The orchestrator will still surface used_fallback.
        artifact = MissionArtifact(
            filename=f"{catalog_id}.txt",
            mime_type="text/plain",
            content="(no sample available)\n",
        )
        return SubagentResult(
            payload=artifact, used_fallback=True, elapsed_ms=elapsed(),
            meta={"sample_path": None},
        )

      mime = _mime_for_extension(sample_path.suffix)
      content = sample_path.read_text(encoding="utf-8", errors="replace")
      artifact = MissionArtifact(
          filename=sample_path.name,
          mime_type=mime,
          content=content,
      )
      return SubagentResult(
          payload=artifact, used_fallback=True, elapsed_ms=elapsed(),
          meta={"sample_path": str(sample_path)},
      )


def _mime_for_extension(ext: str) -> str:
  """Reverse-lookup MIME by extension; default to text/plain."""
  ext = ext.lower()
  for mime, e in MIME_EXTENSIONS.items():
    if e == ext:
      return mime
  return "text/plain"


__all__ = ["MissionArtifactSubagent", "MAX_CONTENT_BYTES"]
