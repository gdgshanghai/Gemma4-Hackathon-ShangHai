"""QP (Query Pipeline) 两步走 tool-loop（spec §5，核心）。

每一跳统一两步，彻底不在脆弱的 auto 字符串里解析参数：
  step A — auto 跳：service.infer(tool_choice=config 默认 "auto") 返回 FunctionGemma
           content 串；正则抠工具名（名字在第一个 { 之前，铁稳）。无 tool_call → 最终答案。
  step B — forced 跳：service.infer_tool(tool_choice=forced(name))，grammar 约束出干净 JSON 参数。
  step C — executor(args, dal) 执行 + 结果回喂；executor 包在 to_thread 里跑（不阻塞事件
           循环 + 只读连接跨线程安全，D-QP-12）。

公共 API：
  run_qp_query(text, dal, service) -> str   QP 入口：拼场次目录 + system → 跑循环
  run_tool_loop(messages, *, service, dal)  纯循环（可注入 service/dal，便于测试）
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.db.dal import DAL
    from backend.llm.service import LLMService

logger = logging.getLogger(__name__)

_QP_TASK = "query_session"
_MAX_HOPS = 5
_FALLBACK_TEXT = "抱歉，这个问题查询轮数超过上限，没能得出结论。"
# FunctionGemma auto content：<|tool_call>call:NAME{...}（FC spec §3.2）。名字 \w+ 在第一个 { 前。
_TOOL_NAME_RE = re.compile(r"<\|tool_call>call:(\w+)")

# 极简 system prompt（spec §5.5 预算纪律：先按极简跑，不稳才加且每加必量化）。
_QP_SYSTEM = (
    "你是场记查询助手。只回答数据库里查到的事实，不给建议、不做评价。\n"
    "有合适的工具就调工具查；查到结果后用一句话直接回答，不要反复查询。\n"
    "找不到对应记录时直接说没有，禁止编造或用相近的场次/数据顶替。"
)


def _scrape_tool_name(text: str) -> str | None:
    """从 FunctionGemma auto content 抠工具名；无 tool_call 标记返回 None（最终答案）。"""
    if not text:
        return None
    m = _TOOL_NAME_RE.search(text)
    return m.group(1) if m else None


def _run_executor(name: str, args: dict, dal: "DAL") -> dict:
    """同步执行 executor（在 to_thread worker 跑）。错误不抛穿，包成 error 串回喂（spec §5.3）。"""
    from backend.llm.tools import registry  # noqa: PLC0415

    try:
        executor = registry.get_executor(name)
    except KeyError:
        return {"error": f"未知工具 {name!r}"}
    if executor is None:
        return {"error": f"工具 {name!r} 无 executor"}
    try:
        return executor(args, dal)
    except Exception as exc:  # noqa: BLE001  executor 内部异常也包成 error 回喂
        logger.warning("qp executor %s 异常: %r", name, exc)
        return {"error": f"工具执行失败：{exc}"}


async def run_tool_loop(
    messages: list[dict],
    *,
    service: "LLMService",
    dal: "DAL",
    max_hops: int = _MAX_HOPS,
    timeout: float = 30.0,
) -> str:
    """两步走循环：≤max_hops 跳，返回最终自然语言文本。messages 原地追加每跳的 tool 往返。

    异常契约：
    - asyncio.TimeoutError / asyncio.CancelledError 放行给 caller（route 兜底返回友好错误）。
    - step B 取参失败（LookupError/KeyError/JSONDecodeError/TypeError）→ 包成 error 回喂，
      模型下一跳自纠；不抛穿，循环继续。
    - step C executor 错误（_run_executor 内已包）→ 同样回喂，不抛穿。
    """
    for _ in range(max_hops):
        # step A — auto 跳：抠工具名。
        # ✅ Task 7.5 probe 已实证「假设 7」成立：service.infer 在 auto 跳返回 FunctionGemma
        #   content 串（finish_reason=stop，不撞 service 护栏），happy path 即此分支。
        #   （故不需要 infer_message 变体，分诊 A 未触发。）
        # infer 的 TimeoutError 放行给 caller（与 l2_take 约定对齐）。
        text = await service.infer(messages, task_type=_QP_TASK, priority=1, timeout=timeout)
        name = _scrape_tool_name(text)
        if name is None:
            return text  # 模型给的是自然语言最终答案，终止

        # step B — forced 跳：grammar 出干净 JSON 参数
        try:
            tool_call = await service.infer_tool(
                messages,
                task_type=_QP_TASK,
                priority=1,
                timeout=timeout,
                tool_choice={"type": "function", "function": {"name": name}},
            )
            args = json.loads(tool_call["function"]["arguments"])
        except asyncio.TimeoutError:
            raise  # 超时放行给 caller（route 兜底返回友好错误），对齐 l2_take 约定
        except (LookupError, KeyError, json.JSONDecodeError, TypeError) as exc:
            # forced 没拿到干净参数（模型没走 FC / arguments 缺失或非法）→ 当工具失败回喂，模型自纠，不抛穿
            logger.warning("qp forced 跳取参失败 name=%s: %r", name, exc)
            result: dict = {"error": f"工具 {name} 调用失败：参数无法解析，请换种方式或直接回答。"}
        else:
            # step C — 执行（executor 包 to_thread，错误不抛穿）
            result = await asyncio.to_thread(_run_executor, name, args, dal)

        # 回喂（单点，纯文本，Task 7.5 probe 实证定案）：
        # **不**用 OpenAI 风格 assistant{tool_calls}+role=tool——
        # 那会撞这个 GGUF 的 Jinja 模板 `UndefinedError: 'raise_exception' is undefined`（状态相关、不稳）。
        # 改纯文本：assistant 喂 auto 步原始 content（模型自吐的 <|tool_call>...，特殊 token 模型认得），
        # tool 结果用纯文本 user 消息。实测 3 次确定性稳定渲染 + 自然语言收尾、不再无脑调工具。
        messages.append({"role": "assistant", "content": text})
        messages.append(
            {"role": "user", "content": f"工具 {name} 返回：{json.dumps(result, ensure_ascii=False)}"}
        )

    return _FALLBACK_TEXT  # 兜底：正常 1~2 跳收尾，靠 system 防 run-on（spec §5.2）


def _build_scene_catalog(dal: "DAL") -> str:
    """场次目录注入（spec §7.1）：编号 + scene_code + slugline + 顺序号，注入 user/context。"""
    scenes = dal.list_scenes_readonly()
    if not scenes:
        return "（当前项目还没有任何场次记录。）"
    lines = ["当前项目场次目录（顺序号. 编号 ｜ 内外景 地点 时间）："]
    for pos, s in enumerate(scenes, start=1):
        slug = " ".join(
            v for v in (s.get("int_ext"), s.get("location"), s.get("time_of_day")) if v
        )
        lines.append(f"{pos}. {s['scene_code']} ｜ {slug or '（无 slugline）'}")
    lines.append(f"（共 {len(scenes)} 场）")
    return "\n".join(lines)


async def run_qp_query(
    *,
    text: str,
    dal: "DAL",
    service: "LLMService",
    timeout: float = 30.0,
) -> str:
    """QP 入口：拼场次目录 + 极简 system → 跑两步走循环 → 返回自然语言答案。"""
    # 场次目录是同步 SQLite I/O，包 to_thread 不阻塞事件循环（与 step C executor 的 to_thread 一致）。
    catalog = await asyncio.to_thread(_build_scene_catalog, dal)
    messages = [
        {"role": "system", "content": _QP_SYSTEM},
        {"role": "user", "content": f"{catalog}\n\n用户提问：{text}"},
    ]
    return await run_tool_loop(messages, service=service, dal=dal, timeout=timeout)
