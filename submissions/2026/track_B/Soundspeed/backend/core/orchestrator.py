"""Orchestrator：同步 pub/sub 事件分发中心。

内置 handler（asr.final.ch1 / asr.final.ch2）在构造时通过 subscribe 注册，
直接写入 DAL transcript_segments 表。
任一 handler 抛异常时记 ERROR 日志并继续调用剩余 handler，不向 publish 调用方传播。

工厂函数 create_orchestrator 支持依赖注入（llm_service / l2_runner），
供 1.H take handler 使用。老签名 Orchestrator(dal, session) 零改动。
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from backend.core.events import (
    ASR_FINAL_CH1,
    ASR_FINAL_CH2,
    LLM_STATUS,
    NOTE_FAILED,
    NOTE_PROCESSED,
    TAKE_CHANGED,
    TAKE_END,
    TAKE_PROCESSING,
    TAKE_START,
    AsrFinalPayload,
    LlmStatusPayload,
    NoteFailedPayload,
    NoteProcessedPayload,
    TakeChangedPayload,
    TakeEndPayload,
    TakeProcessingPayload,
    TakeStartPayload,
)
from backend.core.session import SessionState
from backend.db.dal import DAL

Handler = Callable[[object], None]

# NP note 类别里直接映射到 take.status（= UI Mark）的三类：场记口播「过/保/不好」即打 Mark。
# 与 take.status 枚举同值（pass/ng/keep）；note/issue 不在内，不碰状态。tbd 只作初始态，note 不产出。
_STATUS_CATEGORIES = frozenset({"pass", "ng", "keep"})

logger = logging.getLogger(__name__)


@dataclass
class Dependencies:
    """Orchestrator 可选外部依赖，用于 1.H take handler。

    llm_service: LLMService 实例，注入到 l2_runner / np_runner / voice_runner。
    l2_runner: 异步可调用，签名 (L2Input, LLMService) -> Awaitable[L2Output]。
    np_runner: 异步可调用，签名 (NPInput, LLMService) -> Awaitable[NPOutput]。
    voice_runner: 异步可调用，签名 (NPInput, bytes, LLMService) -> Awaitable[NPOutput]（语音 NP，4.J）。
    diarization_backfill: DiarizationBackfill 实例（可选）；提供时 L2 gate 到回填完成后。
    """

    llm_service: Any = field(default=None)
    l2_runner: Any = field(default=None)
    np_runner: Any = field(default=None)
    voice_runner: Any = field(default=None)
    diarization_backfill: Any = field(default=None)


class Orchestrator:
    """同步事件总线，持有 DAL 与 SessionState，内置 ASR segment handler。"""

    def __init__(
        self,
        dal: DAL,
        session: SessionState | None = None,
        *,
        llm_service: Any = None,
        l2_runner: Any = None,
        np_runner: Any = None,
        voice_runner: Any = None,
        diarization_backfill: Any = None,
    ) -> None:
        self.dal = dal
        self.session: SessionState = session if session is not None else SessionState()
        self._deps = Dependencies(
            llm_service=llm_service,
            l2_runner=l2_runner,
            np_runner=np_runner,
            voice_runner=voice_runner,
            diarization_backfill=diarization_backfill,
        )
        self._handlers: dict[str, list[Handler]] = {}
        self._l2_task: asyncio.Task[None] | None = None  # 最近一次 L2 后台 task，供测试 await
        self._np_task: asyncio.Task[None] | None = None  # 最近一次 NP 后台 task，供测试 await
        self._register_builtin_handlers()

    def subscribe(self, event_type: str, handler: Handler) -> None:
        """注册 event_type 的 handler，同一 event_type 可注册多个，按 subscribe 顺序调用。"""
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event_type: str, payload: object) -> None:
        """发布事件，逐个同步调用已注册 handler。

        handler 抛异常时记 ERROR 日志 + 继续后续 handler，不向调用方传播。
        未注册的 event_type 为 no-op。
        """
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(payload)
            except Exception:
                logger.exception("handler error for event %r", event_type)

    def _register_builtin_handlers(self) -> None:
        """注册内置 handler（asr.final.ch1 / asr.final.ch2 / take.start / take.end）。"""
        self.subscribe(
            ASR_FINAL_CH1,
            lambda p: self._on_asr_final(p, ch=1, force_speaker_none=False),
        )
        self.subscribe(
            ASR_FINAL_CH2,
            lambda p: self._on_asr_final(p, ch=2, force_speaker_none=True),
        )
        self.subscribe(TAKE_START, self._on_take_start)
        self.subscribe(TAKE_END, self._on_take_end)

    def _resolve_take_id(self, payload_take_id: int | None, event_label: str) -> int | None:
        """payload.take_id 优先用，None 时回退 session.take_id。

        payload 与 session 都非 None 且不匹配时记 warning（跨 take 边界迟到 segment），仍按 payload 写库。
        """
        session_take_id = self.session.take_id
        if payload_take_id is None:
            return session_take_id

        if session_take_id is not None and payload_take_id != session_take_id:
            logger.warning(
                "%s: payload.take_id=%d != session.take_id=%d, using payload (cross-take boundary)",
                event_label,
                payload_take_id,
                session_take_id,
            )
        return payload_take_id

    def _take_status(self, take_id: int) -> str:
        """读 take 当前 status（用户录音中 Mark 的结果），取不到回退 'tbd'。

        take.end 与 L2 完成的 take.changed 都用它取真实 status，避免写死 'tbd'
        把用户 Mark 冲掉（停录后状态回退 bug）。
        """
        take = self.dal.get_take(take_id)
        return take.status if take is not None else "tbd"

    def _on_asr_final(
        self,
        payload: object,
        *,
        ch: int,
        force_speaker_none: bool,
    ) -> None:
        """处理 asr.final.chN 事件：take_active 时写 transcript_segments。

        ch1 保留 payload.speaker；ch2 强制 speaker=None（diarization 只跑 ch1）。
        """
        assert isinstance(payload, AsrFinalPayload)
        event_label = f"asr.final.ch{ch}"
        if not self.session.take_active:
            logger.debug("%s: take inactive, skipping segment write", event_label)
            return

        target_take_id = self._resolve_take_id(payload.take_id, event_label)
        if target_take_id is None:
            return

        self.dal.insert_segment(
            take_id=target_take_id,
            ch=ch,
            speaker=None if force_speaker_none else payload.speaker,
            text=payload.text,
            start_frame=payload.start_frame,
            end_frame=payload.end_frame,
        )

    def _on_take_start(self, payload: object) -> None:
        """处理 take.start 事件：写 DAL + 更新 SessionState + publish take.changed。"""
        assert isinstance(payload, TakeStartPayload)

        scene_id = payload.scene_id
        # P1 #2：先同步 session.scene_id，确保 take.end 时 scene_id 已就绪
        self.session.activate_scene(scene_id)

        # shot=None 时归一为 ''（v4 NOT NULL DEFAULT ''，DeepSeek #2 注）
        shot = payload.shot if payload.shot is not None else ""

        # take_number：payload 带显式号（用户手动指定待录号）→ 用它；None → dal 内部自动 MAX+1。
        # start_take 在写事务内解析号位冲突，返回最终 (take_id, take_number)，无需 read-back。
        take_id, take_number = self.dal.start_take(
            scene_id=scene_id,
            shot=shot,
            start_ts=payload.start_ts,
            take_number=payload.take_number,
        )
        # 挂本 take 在场演员（diarization 回填匹配范围）；无则空关联（全匿名说话人N）
        if payload.speaker_ids:
            self.dal.set_take_speakers(take_id, list(payload.speaker_ids))
        self.session.take_start(
            take_id=take_id,
            take_number=take_number,
            start_ts=payload.start_ts,
            shot=shot,
        )

        self.publish(
            TAKE_CHANGED,
            TakeChangedPayload(
                take_id=take_id,
                scene_id=scene_id,
                take_number=take_number,
                status="tbd",
                script_diff=None,
            ),
        )

    def _on_take_end(self, payload: object) -> None:
        """处理 take.end 事件：写 DAL + publish take.changed（同步）+ fire-and-forget L2。

        同步阶段 publish 第一次 take.changed（script_diff=None）。
        异步阶段 L2 完成后（或失败后）publish 第二次。
        """
        assert isinstance(payload, TakeEndPayload)

        take_id = self.session.take_id
        if take_id is None:
            logger.warning("take.end: session.take_id is None, skipping")
            return

        self.session.take_end()
        # end_take 只标记结束，不碰 status/script_diff/notes（preserve-on-None）：用户录音中 Mark 的
        # status 与（将来接线的）memo notes 都原样保留，不会被停录冲掉。status 单独读出来只为下方
        # take.changed 广播给前端。
        self.dal.end_take(take_id=take_id, end_ts=payload.end_ts)
        status = self._take_status(take_id)

        # 第一次 publish（同步，script_diff=None）：带真实 status，不写死 tbd
        self.publish(
            TAKE_CHANGED,
            TakeChangedPayload(
                take_id=take_id,
                scene_id=self.session.scene_id or 0,
                take_number=self.session.take_number,
                status=status,
                script_diff=None,
            ),
        )

        # P1 #1：deps 检查在 get_running_loop 之前——无 LLM 依赖且无 diarization 时降级跳过
        has_l2 = self._deps.llm_service is not None and self._deps.l2_runner is not None
        has_backfill = self._deps.diarization_backfill is not None
        if not has_l2 and not has_backfill:
            return

        # fire-and-forget（需要 event loop）
        loop = asyncio.get_running_loop()  # 无 loop 时抛 RuntimeError，不降级

        # P2 #1：闭包绑定 scene_id/take_number，避免 session 被后续 take 覆盖
        scene_id = self.session.scene_id or 0
        take_number = self.session.take_number

        if has_backfill:
            # Diarization 回填链：buffer→engine→registry→align→DAL→L2
            # L2 gate 在回填完成后触发（DiarizationBackfill.run 内部调用 l2_trigger）
            backfill = self._deps.diarization_backfill
            backfill._l2_trigger = (
                self._run_l2_async if has_l2 else None
            )
            self._l2_task = loop.create_task(
                backfill.run(take_id, scene_id, take_number)
            )
            self._l2_task.add_done_callback(
                lambda t: self._l2_done_callback(t, take_id=take_id, scene_id=scene_id, take_number=take_number)
            )
        else:
            # 无 diarization，直接触发 L2（原有逻辑）
            self._l2_task = loop.create_task(self._run_l2_async(take_id, scene_id, take_number))
            self._l2_task.add_done_callback(
                lambda t: self._l2_done_callback(t, take_id=take_id, scene_id=scene_id, take_number=take_number)
            )

    @staticmethod
    def _truncate_script_lines(lines: list[dict], max_chars: int = 1000) -> list[dict]:
        """截断 script_lines 使总字符数不超过 max_chars。

        保留前 N 行（剧本按行号顺序，靠前的行优先）。
        """
        result: list[dict] = []
        accumulated = 0
        for item in lines:
            text_len = len(item.get("text", ""))
            if accumulated + text_len > max_chars:
                break
            result.append(item)
            accumulated += text_len
        return result

    @staticmethod
    def _assemble_previous_notes(
        takes: list[Any],
        current_take_id: int,
        max_count: int = 5,
        max_total_chars: int = 800,
    ) -> list[str]:
        """从历史 take 提取 script_diff_summary，限制最近 max_count 条且总字符 ≤ max_total_chars。

        takes 假设按 take_number ASC 排序，取最后 max_count 条历史 take（排除当前 take）。
        """
        # 排除当前 take，取最近 max_count 条（ASC 顺序下取尾部）
        history = [t for t in takes if t.take_id != current_take_id]
        recent = history[-max_count:]

        notes: list[str] = []
        total_chars = 0
        for t in recent:
            if not (t.script_diff and isinstance(t.script_diff, dict)):
                continue
            summary = t.script_diff.get("script_diff_summary")
            if not summary:
                continue
            summary_str = str(summary)
            if total_chars + len(summary_str) > max_total_chars:
                break
            notes.append(summary_str)
            total_chars += len(summary_str)
        return notes

    async def _run_l2_async(self, take_id: int, scene_id: int, take_number: int) -> None:
        """后台异步 L2 Pipeline：组装 L2Input → 调 l2_runner → 写库 → publish take.changed。

        scene_id / take_number 由 caller 闭包传入（P2 #1 race condition 防护）。
        L2ParseError / asyncio.TimeoutError 等异常不在此捕获，传到 task.exception() 由 callback 处理。

        llm.status 发射顺序（前端 chip 状态）：
          模型不在本地 → downloading → ensure_model_ready（HF 下载）→ loading/running → idle
          模型已在本地 →                                              loading/running → idle
        """
        from backend.pipelines.l2_take import L2Input

        # 前端 Live 框状态条：正在生成场记摘要（Gemma L2）
        self.publish(
            TAKE_PROCESSING,
            TakeProcessingPayload(take_id=take_id, scene_id=scene_id, phase="summarizing"),
        )

        svc = self._deps.llm_service

        # 模型缺失时：发 downloading + await ensure_model_ready（触发下载，在 worker thread）。
        # getattr 兜底：MagicMock stub 默认 model_present truthy → 跳过此分支，既有测试不受影响。
        if svc is not None and not getattr(svc, "model_present", True):
            self.publish(
                LLM_STATUS,
                LlmStatusPayload(state="downloading", task_type="l2_take", take_id=take_id),
            )
            await svc.ensure_model_ready()

        # 起手发射 llm.status：model_loaded=False → loading（首次权重加载），否则 running。
        # getattr 兜底：stub / 非标准服务对象不一定有 model_loaded 属性，缺失视为已加载。
        _state = (
            "loading"
            if not getattr(svc, "model_loaded", True)
            else "running"
        )
        self.publish(
            LLM_STATUS,
            LlmStatusPayload(state=_state, task_type="l2_take", take_id=take_id),
        )

        # 收集 ch1 转录记录
        segments = self.dal.list_segments(take_id, ch=1)
        transcript_segments = [
            {
                "segment_id": s.segment_id,
                "speaker": s.speaker,
                "text": s.text,
                "start_frame": s.start_frame,
                "end_frame": s.end_frame,
            }
            for s in segments
        ]

        # 收集剧本行（P2 #2：截断到 1000 字符）
        script_lines: list[dict] = []
        script_info = self.dal.get_latest_script(scene_id)
        if script_info is not None:
            raw_lines = self.dal.list_script_lines(script_info["script_id"])
            script_lines = self._truncate_script_lines(raw_lines)

        # 从历史 take 提取 previous_notes（P2 #3：限 5 条 / 800 字符）
        history = self.dal.list_takes(scene_id)
        previous_notes = self._assemble_previous_notes(history, current_take_id=take_id)

        input_data = L2Input(
            take_id=take_id,
            scene_id=scene_id,
            take_number=take_number,
            transcript_segments=transcript_segments,
            script_lines=script_lines,
            previous_notes=previous_notes,
        )

        l2_output = await self._deps.l2_runner(input_data, self._deps.llm_service)

        # 写库：script_diff（juxtaposition = 并置文档，缺口③；前端两列对照直接读它）
        script_diff_dict = {
            "script_diff_summary": l2_output.script_diff_summary,
            "line_matches": [asdict(m) for m in l2_output.line_matches],
            "corrected_segments": [asdict(cs) for cs in l2_output.corrected_segments],
            "juxtaposition": [asdict(j) for j in l2_output.juxtaposition],
        }
        self.dal.update_take_l2_output(take_id, script_diff_dict)

        # 写库：take_line_matches（需要 line_no → line_id 映射）
        line_no_to_id: dict[int, int] = {
            ln["line_no"]: ln["line_id"] for ln in script_lines
        }
        matches_for_dal: list[dict] = []
        for m in l2_output.line_matches:
            if m.line_no == -1:
                continue  # insertion，跳过（DAL 会再过滤，双重保险）
            line_id = line_no_to_id.get(m.line_no)
            if line_id is None:
                logger.warning(
                    "_run_l2_async: line_no=%d not found in script_lines, skipping",
                    m.line_no,
                )
                continue
            matches_for_dal.append(
                {"line_no": m.line_no, "line_id": line_id, "diff_type": m.diff_type, "detail": m.detail}
            )
        if matches_for_dal:
            self.dal.insert_take_line_matches(take_id, matches_for_dal)

        # 第二次 publish（含 script_diff）；用闭包参数保持与 L2Input 一致。
        # status 读库真实值，保留用户 Mark（写死 tbd 会在 L2 完成后二次冲掉 Mark）。
        self.publish(
            TAKE_CHANGED,
            TakeChangedPayload(
                take_id=take_id,
                scene_id=scene_id,
                take_number=take_number,
                status=self._take_status(take_id),
                script_diff=script_diff_dict,
            ),
        )

    def _l2_done_callback(
        self, task: Any, *, take_id: int, scene_id: int, take_number: int
    ) -> None:
        """L2 task done callback：发 idle + 失败时 log + publish 降级 take.changed。

        codex P8：idle 统一在此发，成功 / 失败 / 取消三条路径均发一次，消除双发歧义。
        cancelled 路径：shutdown 时 loop 取消 task，broadcast 会 no-op（loop 已停），
          发 idle 是防御性保证——若未来在未停 loop 时取消，前端也能回到 idle。
        成功路径：_run_l2_async 已 publish 第二次 take.changed，callback 只发 idle。
        失败路径：记 WARNING + publish idle + publish 降级 take.changed（script_diff=None）。

        take_id / scene_id / take_number 由 add_done_callback lambda 闭包绑定，
        避免 session 被后续 take.start 覆盖（race condition 防护）。
        """
        # 无论成功 / 失败 / 取消，先发 idle（所有路径都经过此处）
        self.publish(
            LLM_STATUS,
            LlmStatusPayload(state="idle", task_type="l2_take", take_id=take_id),
        )
        if task.cancelled():
            return  # 取消路径：idle 已发，不取 exception（会抛 CancelledError）
        exc = task.exception()
        if exc is None:
            # 成功路径，_run_l2_async 已处理 take.changed；通知前端状态条收尾
            self.publish(
                TAKE_PROCESSING,
                TakeProcessingPayload(take_id=take_id, scene_id=scene_id, phase="done"),
            )
            return
        logger.warning("L2 pipeline failed for task, publishing degraded take.changed: %r", exc)
        # 降级 publish 也带真实 status，保留用户 Mark（不写死 tbd）
        self.publish(
            TAKE_PROCESSING,
            TakeProcessingPayload(
                take_id=take_id, scene_id=scene_id, phase="error",
                detail=f"摘要生成失败：{exc}",
            ),
        )
        self.publish(
            TAKE_CHANGED,
            TakeChangedPayload(
                take_id=take_id,
                scene_id=scene_id,
                take_number=take_number,
                status=self._take_status(take_id),
                script_diff=None,
            ),
        )

    def run_np_async(
        self, raw_text: str, parsed_category: str, ts: float, client_id: str | None = None
    ) -> None:
        """fire-and-forget 文本 NP Pipeline：归置 note 到正确的 take。

        在 event loop 内调用，创建后台 Task + done callback。
        与 L2 流程对齐：runner 由 create_orchestrator 注入，callback 处理错误与 idle。
        client_id：前端乐观 pending 的去重键，透传到 note.processed 供精确移除。
        """
        loop = asyncio.get_running_loop()
        task = loop.create_task(self._run_np_async(raw_text, parsed_category, ts, client_id))
        task.add_done_callback(
            lambda t: self._np_done_callback(t, label=f"text={raw_text[:80]!r}")
        )
        self._np_task = task

    def run_np_voice_async(
        self, audio: bytes, ts: float, client_id: str | None = None
    ) -> None:
        """fire-and-forget 语音 NP Pipeline（4.J）：浏览器麦 WAV → 多模态 Gemma 归置 → 写库 → WS。

        与 run_np_async 对称：音频经 voice_runner（带 audio 字节）进同一单实例（_lock+priority 串行）。
        client_id 透传链与文本一致。
        """
        loop = asyncio.get_running_loop()
        task = loop.create_task(self._run_np_voice_async(audio, ts, client_id))
        task.add_done_callback(
            lambda t: self._np_done_callback(t, label=f"audio({len(audio)}B)")
        )
        self._np_task = task

    async def _emit_np_status_preamble(self, svc: Any) -> None:
        """NP 模型状态前导（文本/语音共用）。

        llm.status 发射顺序（前端 chip 状态，与 L2 对齐）：
          模型不在本地 → downloading → ensure_model_ready → loading/running
          模型已在本地 → loading/running
        """
        if not getattr(svc, "model_present", True):
            self.publish(
                LLM_STATUS,
                LlmStatusPayload(state="downloading", task_type="note_struct", take_id=None),
            )
            await svc.ensure_model_ready()
        _state = "loading" if not getattr(svc, "model_loaded", True) else "running"
        self.publish(
            LLM_STATUS,
            LlmStatusPayload(state=_state, task_type="note_struct", take_id=None),
        )

    def _build_np_input(self, raw_text: str, parsed_category: str, ts: float) -> Any:
        """组装 NPInput（4.H 带完整 场-镜-次；文本/语音共用）。

        语音路径无文字：raw_text 传 ''、parsed_category 传占位 'note'（voice runner 不读这两项，
        正文/类别由模型从音频听+判）。
        """
        from backend.pipelines.np_note import NPInput  # noqa: PLC0415

        scene_id = self.session.scene_id
        current_take_id = self.session.take_id if self.session.take_active else None

        # scene_id → scene_code 映射（一次查询，替代循环内 N+1 的 list_scenes）
        scene_code_by_id = {
            s.get("scene_id"): s.get("scene_code", "") for s in self.dal.list_scenes()
        }

        take_context: list[dict] = []
        if scene_id is not None:
            takes = self.dal.list_takes(scene_id)
            recent = [t for t in takes if t.take_id != current_take_id][-10:]
            for t in recent:
                summary = ""
                if t.script_diff and isinstance(t.script_diff, dict):
                    summary = t.script_diff.get("script_diff_summary", "") or ""
                take_context.append({
                    "take_id": t.take_id,
                    "scene_code": scene_code_by_id.get(t.scene_id, ""),
                    "shot": t.shot,
                    "take_number": t.take_number,
                    "summary": summary,
                })

        return NPInput(
            raw_text=raw_text,
            parsed_category=parsed_category,
            current_scene_id=scene_id,
            current_take_id=current_take_id,
            take_context=take_context,
            ts=ts,
            current_scene_code=(
                scene_code_by_id.get(scene_id) if scene_id is not None else None
            ),
            current_shot=self.session.shot if current_take_id is not None else None,
            current_take_number=(
                self.session.take_number if current_take_id is not None else None
            ),
        )

    async def _finalize_np(
        self,
        run_awaitable: Any,
        *,
        ts: float,
        client_id: str | None,
        raw_text_override: str | None,
    ) -> None:
        """await runner → insert_note → publish（文本/语音共用，含 4.I 失败兜底）。

        raw_text_override：文本路径传原始文字；语音路径传 None → 存模型转写正文（§8）。
        机制可检测的三类失败（parse/timeout/FK）→ 发 note.failed（带 client_id），前端转失败态；
        未知异常上抛交 _np_done_callback 记 WARNING + idle。
        """
        from backend.llm.errors import ModelUnavailableError  # noqa: PLC0415
        from backend.pipelines.np_note import NPParseError  # noqa: PLC0415

        try:
            output = await run_awaitable
            stored_raw = raw_text_override if raw_text_override is not None else output.content
            event_id = self.dal.insert_note(
                take_id=output.take_id,
                category=output.category,
                content=output.content,
                raw_text=stored_raw,
                ts=ts,
            )
        except Exception as exc:
            # 失败原因在产生地确定（typed domain error），这里只做干净映射，不靠宽泛内建异常类型反推。
            if isinstance(exc, NPParseError):
                reason = "parse_error"
            elif isinstance(exc, asyncio.TimeoutError):
                reason = "timeout"
            elif isinstance(exc, sqlite3.IntegrityError):
                reason = "take_not_found"  # 归到不存在的 take_id，insert_note 撞 FK
            elif isinstance(exc, ModelUnavailableError):
                # 多模态模型不可用（mmproj 缺失/下载失败 → 退纯文本；或 mtmd 自检失败）。
                # 必须发 note.failed，否则前端 pending 永久卡（复活 4.I 的 bug）。
                reason = "model_unavailable"
            else:
                raise  # 真正未知失败：保留安全网，交 done_callback 处理
            logger.warning(
                "NP Pipeline failed (%s) [client_id=%s]: %s", reason, client_id, exc
            )
            self.publish(
                NOTE_FAILED,
                NoteFailedPayload(reason=reason, ts=ts, client_id=client_id),
            )
            return

        # note 已 durable 落库 → 无条件发 note.processed 解除 pending：与「note 已保存」绑定，
        # 不被后续 Mark 副作用回退（否则 Mark 抛非 typed 异常会留孤儿 pending，复活 4.I 的 bug）。
        self.publish(
            NOTE_PROCESSED,
            NoteProcessedPayload(
                event_id=event_id,
                take_id=output.take_id,
                category=output.category,
                content=output.content,
                ts=ts,
                client_id=client_id,
            ),
        )

        # pass/ng/keep 类别把该 take 标成对应 status（= UI Mark）+ 广播 take.changed；note/issue 不动。
        # Mark 是 note 落库后的独立副作用——失败只记日志，绝不回退已发的 note.processed。
        if output.category in _STATUS_CATEGORIES:
            try:
                self.dal.set_take_status(output.take_id, output.category)
                take = self.dal.get_take(output.take_id)
                if take is not None:
                    self.publish(
                        TAKE_CHANGED,
                        TakeChangedPayload(
                            take_id=take.take_id,
                            scene_id=take.scene_id,
                            take_number=take.take_number,
                            status=take.status,
                            script_diff=take.script_diff,
                        ),
                    )
            except Exception as exc:
                logger.warning(
                    "NP take Mark failed after note stored [client_id=%s]: %s", client_id, exc
                )

    async def _run_np_async(
        self, raw_text: str, parsed_category: str, ts: float, client_id: str | None = None
    ) -> None:
        """后台异步文本 NP：构建上下文 → LLM 归置 → 写库 → WS 推送。"""
        svc = self._deps.llm_service
        np_runner = self._deps.np_runner
        if svc is None or np_runner is None:
            logger.warning("NP Pipeline: llm_service or np_runner is None, cannot run")
            return

        await self._emit_np_status_preamble(svc)
        input_data = self._build_np_input(raw_text, parsed_category, ts)
        await self._finalize_np(
            np_runner(input_data, svc),
            ts=ts,
            client_id=client_id,
            raw_text_override=raw_text,
        )

    async def _run_np_voice_async(
        self, audio: bytes, ts: float, client_id: str | None = None
    ) -> None:
        """后台异步语音 NP（4.J）：场镜次上下文 + 音频 → 多模态 Gemma 归置 → 写库 → WS 推送。"""
        svc = self._deps.llm_service
        voice_runner = self._deps.voice_runner
        if svc is None or voice_runner is None:
            logger.warning("Voice NP Pipeline: llm_service or voice_runner is None, cannot run")
            return

        await self._emit_np_status_preamble(svc)
        # 语音无文字：raw_text='' 占位、parsed_category='note' 占位（voice runner 不读）。
        input_data = self._build_np_input("", "note", ts)
        # raw_text_override=None → 存模型转写正文（§8，语音无原始文字）。
        await self._finalize_np(
            voice_runner(input_data, audio, svc),
            ts=ts,
            client_id=client_id,
            raw_text_override=None,
        )

    def _np_done_callback(self, task: Any, *, label: str) -> None:
        """NP task done callback（文本/语音共用）：发 idle + 未知失败时 log warning。

        与 _l2_done_callback 对齐：
          - 成功 / 4.I 已兜底失败：_finalize_np 已推送 NOTE_PROCESSED/NOTE_FAILED，callback 只发 idle。
          - 未知异常（_finalize_np 上抛）：记 WARNING + 发 idle。
          - 取消：只发 idle。
        """
        self.publish(
            LLM_STATUS,
            LlmStatusPayload(state="idle", task_type="note_struct", take_id=None),
        )
        if task.cancelled():
            return
        exc = task.exception()
        if exc is None:
            return
        logger.warning("NP Pipeline failed for %s: %s", label, exc)


def create_orchestrator(
    dal: DAL,
    session: SessionState | None = None,
    *,
    llm_service: Any = None,
    l2_runner: Any = None,
    np_runner: Any = None,
    voice_runner: Any = None,
    diarization_backfill: Any = None,
) -> Orchestrator:
    """模块级工厂函数，供生产代码与测试注入依赖。

    老签名 Orchestrator(dal, session) 零改动，此函数提供更明确的依赖注入入口。
    llm_service 不为 None 时自动绑定默认 runner：
      - l2_runner 未显式传 → 绑定 run_l2_take
      - np_runner 未显式传 → 绑定 run_np_note
      - voice_runner 未显式传 → 绑定 run_np_voice（语音 NP，4.J）
    diarization_backfill 不为 None 时，take.end 后先跑回填链，L2 gate 到回填完成后。
    """
    if llm_service is not None:
        if l2_runner is None:
            from backend.pipelines.l2_take import run_l2_take
            l2_runner = run_l2_take
        if np_runner is None:
            from backend.pipelines.np_note import run_np_note
            np_runner = run_np_note
        if voice_runner is None:
            from backend.pipelines.np_note import run_np_voice
            voice_runner = run_np_voice
    return Orchestrator(
        dal, session,
        llm_service=llm_service,
        l2_runner=l2_runner,
        np_runner=np_runner,
        voice_runner=voice_runner,
        diarization_backfill=diarization_backfill,
    )
