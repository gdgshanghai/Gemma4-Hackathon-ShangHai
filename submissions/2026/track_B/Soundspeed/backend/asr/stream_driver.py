"""StreamDriver：把音频源驱动成实时 ASR 事件。

AudioSource（DeviceSource 实时 / FileSource 批）→ 每声道 ChannelVADSegmenter 端点切段
→ 每个 SpeechSegment 经 WhisperRunner 转文字 → 组 AsrFinalPayload → publish 到 orchestrator
→（既有 WS 转发）前端实时上屏。

Phase 1：段级 final（turn 收尾出一条），speaker 一律 None（ch1 的 speaker 由 take.end
后批量 diarization 回填，见 2026-06-02-realtime-diarization-voicenote-design）。
run() 是阻塞循环，意在后台线程里跑（接入见 take 生命周期）。
"""
from __future__ import annotations

import logging
import math
import threading
from collections.abc import Callable, Iterable
from typing import Any

import numpy as np
import opencc

from backend.asr.whisper_runner import WhisperRunner
from backend.core.events import (
    AUDIO_LEVEL,
    ASR_FINAL_CH1,
    ASR_FINAL_CH2,
    AsrFinalPayload,
    AudioLevelPayload,
)
from backend.vad.detector import VadDetector
from backend.vad.models import SpeechSegment, VadConfig
from backend.vad.segmenter import ChannelVADSegmenter

logger = logging.getLogger(__name__)

_FRAMES_PER_MS = 16  # 16kHz → 每毫秒 16 帧


class StreamDriver:
    """把 AudioSource 驱动成 asr.final.chN 事件流。"""

    def __init__(
        self,
        runner: WhisperRunner,
        publish: Callable[[str, object], None],
        vad_config: VadConfig,
        detector_factory: Callable[[], VadDetector],
        audio_sink: Callable[[Any, int], None] | None = None,
        process_channels: tuple[int, ...] | None = None,
    ) -> None:
        self._runner = runner
        self._publish = publish
        self._vad_config = vad_config
        self._detector_factory = detector_factory
        # ch1 连续音频写入（用于 TakeAudioBuffer → diarization）。
        # 签名 (pcm, start_frame)：喂逐 chunk 的全量 ch1（含静音），保证 buffer
        # 时间轴 == take 绝对时间轴，diarization turn 才能与 ASR 绝对帧对齐（B2）。
        self._audio_sink = audio_sink
        # 只处理这些声道索引（None = 全部）。生产暂设 (0,) 只跑 ch1：避免设备双声道
        # 同源导致每句重复转录；ch2（场记 voice note）路径待基础链路跑通后再开。
        self._process_channels = process_channels
        self._stop = threading.Event()

    def stop(self) -> None:
        """请求停止 run() 循环（线程安全）。DeviceSource 下一块读完后退出（≤chunk_ms 延迟）。"""
        self._stop.set()

    def run(self, source: Iterable) -> None:
        """阻塞驱动：消费 source 的 AudioChunk 直到耗尽（FileSource）或被 stop() 停掉（DeviceSource）。"""
        self._stop.clear()
        segmenters: list[ChannelVADSegmenter] = []
        with source as src:  # type: ignore[attr-defined]
            for chunk in src:
                if self._stop.is_set():
                    break
                if not segmenters:
                    segmenters = [
                        ChannelVADSegmenter(ch=i, detector=self._detector_factory(), config=self._vad_config)
                        for i in range(len(chunk.channels))
                    ]
                # ch1（index 0）全量连续音频送入 buffer（含静音），供 take.end 后 diarization。
                # 在 VAD 之前、逐 chunk 写入：buffer 时间轴 = take 绝对时间轴。
                if chunk.channels:
                    ch1 = chunk.channels[0]
                    if self._audio_sink is not None:
                        self._audio_sink(ch1, chunk.start_frame)
                    # 旁路：对 ch1 算 RMS 并推 audio.level（每 chunk 一条，约 5 Hz）。
                    # publish 内部吞异常，失败不影响采集主循环。
                    try:
                        samples = ch1.astype(np.float64)
                        mean_sq = float(np.mean(samples * samples))
                        rms = math.sqrt(mean_sq) / 32768.0
                        rms = min(rms, 1.0)
                        self._publish(AUDIO_LEVEL, AudioLevelPayload(rms=rms))
                    except Exception:  # noqa: BLE001
                        logger.debug("audio.level RMS 计算失败，跳过", exc_info=True)
                for i, ch_audio in enumerate(chunk.channels):
                    if self._process_channels is not None and i not in self._process_channels:
                        continue
                    for seg in segmenters[i].push(ch_audio, chunk.start_frame):
                        self._emit(seg)
        for sm in segmenters:
            for seg in sm.flush():
                self._emit(seg)

    def _emit(self, seg: SpeechSegment) -> None:
        # 注意：ch1 音频在 run() 的 chunk 循环里逐块全量写 buffer（含静音），不在此处
        # 按语音段写——否则 buffer 是去静音的压缩时间轴，diarization 无法与 ASR 绝对帧对齐。
        text = self._runner.transcribe_pcm(seg.audio)
        text = _normalize_to_simplified(text)  # 繁→简，幻觉过滤前（繁体幻觉转简后能被简体表拦截）
        if not text.strip():
            return  # 空转录（静音误触/噪声）不推
        if _is_hallucination(text):
            logger.debug("丢弃疑似幻觉转录: %r", text)
            return
        topic = ASR_FINAL_CH1 if seg.ch == 0 else ASR_FINAL_CH2
        payload = AsrFinalPayload(
            text=text,
            start_frame=round(seg.start_frame / _FRAMES_PER_MS),  # 16k 帧 → 毫秒（contract C1）
            end_frame=round(seg.end_frame / _FRAMES_PER_MS),
            speaker=None,            # Phase 1 不出 speaker；take.end 后回填
            take_id=None,            # orchestrator 由 session.take_id 回退
            is_partial=False,
        )
        self._publish(topic, payload)


# Whisper 在噪声/静音段上的典型幻觉输出（大小写不敏感，含即过滤）
_HALLUCINATION_PATTERNS = [
    "谢谢",
    "谢谢观看",
    "请订阅",
    "字幕",
    "thank you",
    "thanks for watching",
    "subscribe",
    "please subscribe",
    "[music]",
    "[applause]",
    "[noise]",
    "[blank_audio]",
    "♪",
]


def _is_hallucination(text: str) -> bool:
    """检测 Whisper 常见幻觉输出。匹配到任一模式即丢弃。"""
    t = text.strip().lower()
    # 极短文本（≤2字符）通常是幻觉
    if len(t) <= 2:
        return True
    return any(pat in t for pat in _HALLUCINATION_PATTERNS)


# 模块级 opencc 单例，避免每次 _emit 重复初始化
_CC = opencc.OpenCC("t2s")


def _normalize_to_simplified(text: str) -> str:
    """繁体转简体（opencc t2s）。已是简体或英文时完全幂等。"""
    return _CC.convert(text)
