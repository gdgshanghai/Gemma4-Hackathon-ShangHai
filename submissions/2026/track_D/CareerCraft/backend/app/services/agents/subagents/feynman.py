"""``FeynmanReviewSubagent`` — short-form review of a Feynman explanation.

Lifted from the inline LLM call inside ``app/api/v1/user.py`` so the
endpoint can later switch to a uniform orchestrator. Behavior preserved.
"""

from __future__ import annotations

import asyncio

from app.core.llm import LLMProviderError
from app.services.agents.base import (
    FeynmanContext,
    SubagentError,
    SubagentResult,
    stopwatch,
)
from app.services.agents.llm_io import call_llm, llm_disabled


_OFFLINE_FEEDBACK = (
    "【费曼挑战通关！】你的大白话解释生动有趣、通俗形象，完全避开了晦涩的学术黑话。"
    "用如此生活化的类比说清该技术定义，说明你确实已经融会贯通，完成了知识自主重构的深度闭环！"
)

_ERROR_FEEDBACK = (
    "很好的大白话解释！证明你确实已经融会贯通，完成了自我转述的深度学习闭环。"
)


class FeynmanReviewSubagent:
  """Produce the short feedback string shown after a Feynman challenge."""

  name = "feynman.review"

  async def run(self, ctx: FeynmanContext) -> SubagentResult[str]:
    if llm_disabled():
      await asyncio.sleep(0.5)
      with stopwatch() as elapsed:
        pass
      return SubagentResult(payload=_OFFLINE_FEEDBACK, elapsed_ms=elapsed())

    prompt = (
        f"费曼挑战问题：{ctx.question}\n"
        f"用户通俗化的回答：{ctx.answer}\n\n"
        "请作为一个温柔专业的导师进行中肯评价。判定用户的解释是否准确通俗，避开了学术术语？"
        "字数在100字左右，给出极富人情味与学术自豪感的评价。"
    )
    with stopwatch() as elapsed:
      try:
        text = await call_llm(
            prompt=prompt,
            system="你现在是一个专业的AI职业导师。",
        )
        return SubagentResult(payload=text, elapsed_ms=elapsed())
      except LLMProviderError as e:
        raise SubagentError(f"LLM error: {e}") from e
      except Exception as e:
        raise SubagentError(f"unexpected error ({type(e).__name__}): {e}") from e

  async def fallback(self, ctx: FeynmanContext) -> SubagentResult[str]:
    with stopwatch() as elapsed:
      pass
    return SubagentResult(payload=_ERROR_FEEDBACK, used_fallback=True, elapsed_ms=elapsed())


__all__ = ["FeynmanReviewSubagent"]
