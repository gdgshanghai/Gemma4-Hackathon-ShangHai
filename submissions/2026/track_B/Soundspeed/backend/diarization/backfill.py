"""DiarizationBackfill：take.end 后的异步批量说话人回填。

数据流：
  TakeAudioBuffer.get_audio()
    → DiarizationEngine.diarize()  → [SpeakerTurn]
    → SpeakerRegistry.resolve()    → {local_label: global_name}
    → align()                      → {segment_id: global_name}
    → DAL.bulk_update_segment_speaker()
    → publish(TAKE_SEGMENTS_UPDATED)
    → trigger L2

L2 gate：L2 由本链第 6 步（回填完成后）触发，不再由 take.end 直接触发。
"""
from __future__ import annotations

import asyncio
import functools
import logging
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from backend.diarization.buffer import TakeAudioBuffer
    from backend.diarization.engine import DiarizationEngine
    from backend.diarization.registry import SpeakerRegistry
    from backend.db.dal import DAL

logger = logging.getLogger(__name__)


def align_segments(
    segments: list[Any],  # list[TranscriptSegment]
    turns: list[Any],     # list[SpeakerTurn]
    speaker_map: dict[str, str],
    audio_start_s: float = 0.0,
) -> dict[int, str]:
    """将 ASR segments 与 diarization turns 按最大时间重叠对齐。

    返回 {segment_id: global_speaker_name}（只含有 speaker 分配的 segment）。
    ASR segment 的 start_frame / end_frame 单位为毫秒、且是 take **绝对**时间轴；
    SpeakerTurn 单位为秒、相对 diarization 缓冲起点。两者经 audio_start_s 对齐到
    同一绝对秒轴：turn 绝对秒 = audio_start_s + turn.start_s（audio_start_s =
    TakeAudioBuffer.base_frame / 16000，即缓冲首样本的绝对位置）。
    """
    result: dict[int, str] = {}

    for seg in segments:
        seg_start_s = seg.start_frame / 1000.0
        seg_end_s = seg.end_frame / 1000.0
        seg_duration = seg_end_s - seg_start_s
        if seg_duration <= 0:
            continue

        best_overlap = 0.0
        best_label: str | None = None

        for turn in turns:
            turn_start_s = audio_start_s + turn.start_s
            turn_end_s = audio_start_s + turn.end_s
            overlap_start = max(seg_start_s, turn_start_s)
            overlap_end = min(seg_end_s, turn_end_s)
            overlap = max(0.0, overlap_end - overlap_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_label = turn.label

        if best_label is not None and best_overlap > 0:
            global_name = speaker_map.get(best_label)
            if global_name is not None:
                result[seg.segment_id] = global_name

    return result


def build_structured_transcript(segments: list[Any]) -> dict:
    """把 ch1 transcript segments 整合成结构化合并文档（ASR + speaker）。

    segments 假定为同一 take 的 ch1 段（list_segments 已按 start_frame 升序）。
    start_ms / end_ms 单位为毫秒（与 transcript_segments.start_frame/end_frame 一致）。
    本轮只含 ch1；ch2 note 区与 L2 接入留后续 ticket。
    """
    return {
        "version": 1,
        "ch1": [
            {
                "speaker": s.speaker,
                "text": s.text,
                "start_ms": s.start_frame,
                "end_ms": s.end_frame,
            }
            for s in segments
        ],
    }


class DiarizationBackfill:
    """异步批量回填协调者。由 Orchestrator take.end 路径调用。

    engine / registry 可为 None（跳过 diarization，直接触发 L2）。
    """

    def __init__(
        self,
        dal: "DAL",
        buffer: "TakeAudioBuffer",
        engine: "DiarizationEngine | None",
        registry: "SpeakerRegistry | None",
        publish: Any,
        l2_trigger: Any,  # callable(take_id, scene_id, take_number) -> Awaitable
    ) -> None:
        self._dal = dal
        self._buffer = buffer
        self._engine = engine
        self._registry = registry
        self._publish = publish
        self._l2_trigger = l2_trigger

    def _emit_processing(self, take_id: int, scene_id: int, phase: str, detail: str | None = None) -> None:
        from backend.core.events import TAKE_PROCESSING, TakeProcessingPayload

        self._publish(
            TAKE_PROCESSING,
            TakeProcessingPayload(take_id=take_id, scene_id=scene_id, phase=phase, detail=detail),
        )

    async def run(self, take_id: int, scene_id: int, take_number: int) -> None:
        """执行完整的回填异步链。"""
        try:
            await self._do_backfill(take_id, scene_id, take_number)
        except Exception as exc:
            logger.exception("diarization 回填异常（take_id=%d），继续触发 L2", take_id)
            # 前端 Live 框状态条提示分离失败（如显存 OOM）；L2 仍会继续
            self._emit_processing(take_id, scene_id, "error", f"说话人分离失败：{exc}")
        finally:
            # 无论回填成功与否，都触发 L2（保证 L2 不被 diarization 失败阻断）
            if self._l2_trigger is not None:
                await self._l2_trigger(take_id, scene_id, take_number)

    async def _do_backfill(self, take_id: int, scene_id: int, take_number: int) -> None:
        from backend.core.events import TAKE_SEGMENTS_UPDATED, TakeSegmentsUpdatedPayload

        # 取整段 ch1 PCM + 缓冲起点（对齐基准），再清空释放内存（不落盘保证）
        pcm = self._buffer.get_audio()
        audio_start_s = self._buffer.base_frame / 16000.0
        self._buffer.clear()

        if self._engine is None or self._registry is None:
            logger.info("diarization 未配置（engine/registry=None），跳过回填 take_id=%d", take_id)
            return

        duration_s = len(pcm) / 16000.0
        if duration_s < 1.0:
            logger.info("ch1 音频太短（%.1fs），跳过 diarization take_id=%d", duration_s, take_id)
            return

        logger.info("开始 diarization（take_id=%d, 时长=%.1fs）", take_id, duration_s)
        # 前端 Live 框状态条：正在分离说话人（pyannote 跑批，较慢）
        self._emit_processing(take_id, scene_id, "diarizing")

        # 本 take 选定的参演演员：既作为 pyannote 人数先验（防单麦/相似音色塌成一人），
        # 也用于后续声纹匹配。num_speakers=None（没选演员）时 pyannote 自动判定。
        candidates = self._dal.list_take_speakers(take_id)
        num_hint = len(candidates) if candidates else None

        # 在 executor 里跑（阻塞的 CPU/GPU 操作）
        loop = asyncio.get_running_loop()
        turns = await loop.run_in_executor(
            None, functools.partial(self._engine.diarize, pcm, num_speakers=num_hint)
        )

        if not turns:
            logger.info("diarization 返回空 turns（take_id=%d）", take_id)
            return

        # 提取 local_label → embedding 映射
        local_embeddings: dict[str, list] = {}
        for t in turns:
            if t.label not in local_embeddings:
                local_embeddings[t.label] = []
            if t.embedding is not None:
                local_embeddings[t.label].append(t.embedding)

        avg_embeddings: dict[str, np.ndarray | None] = {}
        for label, embs in local_embeddings.items():
            avg_embeddings[label] = np.mean(embs, axis=0) if embs else None

        # 声纹匹配：只在本 take 挂的已注册演员里匹配（candidates 上面已取）；未命中 → 匿名说话人N
        speaker_map = await loop.run_in_executor(
            None, self._registry.resolve, avg_embeddings, candidates
        )
        logger.info(
            "take_id=%d 挂 %d 个注册演员，speaker_map=%s", take_id, len(candidates), speaker_map
        )

        # 取 ch1 segments
        segments = self._dal.list_segments(take_id, ch=1)

        # 时间对齐（turn 相对秒 + audio_start_s → 绝对秒，与 ASR 绝对 ms 对齐）
        seg_speaker_map = align_segments(segments, turns, speaker_map, audio_start_s=audio_start_s)

        # 批量写入 speaker（对齐为空也继续——仍要产出结构化转录）
        if seg_speaker_map:
            self._dal.bulk_update_segment_speaker(seg_speaker_map)
            logger.info("回填完成：%d 个 segment 更新说话人（take_id=%d）", len(seg_speaker_map), take_id)
        else:
            logger.info("对齐后无 segment 分配到说话人（take_id=%d）", take_id)

        # 重读 ch1 segments（带回填后的 speaker）→ 组装结构化合并 JSON 写入 take（v4）
        final_segments = self._dal.list_segments(take_id, ch=1)
        structured = build_structured_transcript(final_segments)
        self._dal.update_take_structured_transcript(take_id, structured)
        logger.info("结构化转录已写入 take_id=%d（%d 段 ch1）", take_id, len(final_segments))

        # 通知前端刷新 segments（说话人标签 + 结构化转录）
        self._publish(
            TAKE_SEGMENTS_UPDATED,
            TakeSegmentsUpdatedPayload(take_id=take_id, scene_id=scene_id),
        )
