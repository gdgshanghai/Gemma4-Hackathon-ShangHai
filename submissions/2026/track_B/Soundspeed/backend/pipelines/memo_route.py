"""入口调度器分类器（块③）：forced 二分类 memo → note | query。

classify_memo 对标 run_np_note 的 forced tool-call 路径，但只取 kind 字段。
设计纪律（spec §3.3）：任何失败 → fail-closed "note"——分类器宕了也绝不能挡掉备注提交。
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.llm.service import LLMService

logger = logging.getLogger(__name__)

_VALID_KINDS = ("note", "query")

_SYSTEM = (
    "你是场记输入分诊器。判断录音师这条输入是要「记录一条备注（note）」"
    "还是「查询场记信息（query）」。\n"
    "- query：想知道/查/问某个事实，如「第一场拍了多少条」「第72场在哪拍」「有几个角色」。\n"
    "- note：对某条素材的评价/好坏/问题/要保要过要废，如「这条过了」「收音有点小」「第三条留着」。"
)


async def classify_memo(
    text: str,
    service: "LLMService",
    *,
    timeout: float = 5.0,
) -> str:
    """forced 二分类 → "note" | "query"。任何异常/超时/畸形 → fail-closed "note"。"""
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": text},
    ]
    try:
        # priority 不显式传：infer_tool 默认从 TASK_CONFIG["memo_route"]["priority"] 取（=1），
        # 让 config 当单一来源，避免两处分裂。
        tool_call = await service.infer_tool(
            messages,
            task_type="memo_route",
            timeout=timeout,
        )
        kind = json.loads(tool_call["function"]["arguments"])["kind"]
    except Exception as exc:  # noqa: BLE001  fail-closed：分类器任何失败都退回 note
        logger.warning("memo 分类失败，fail-closed note: %r", exc)
        return "note"
    if kind not in _VALID_KINDS:
        logger.warning("memo 分类返回非法 kind=%r，fail-closed note", kind)
        return "note"
    return kind
