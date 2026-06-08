"""ChannelVADSegmenter：每声道端点切段状态机（spec v0.1 §3 §5）。

纯逻辑、零重依赖（numpy + VadDetector 协议）。逐 chunk 喂入、收尾时吐 segment，
批（FileSource）/ 实时（DeviceSource）同一份代码。
"""
from __future__ import annotations

import logging
import math
from collections import deque

import numpy as np

from backend.vad.detector import VadDetector
from backend.vad.models import SpeechSegment, VadConfig

logger = logging.getLogger(__name__)

_SILENCE = 0
_SPEECH = 1


class ChannelVADSegmenter:
    """单声道有状态切段器。每声道一个实例。"""

    def __init__(self, ch: int, detector: VadDetector, config: VadConfig) -> None:
        self._ch = ch
        self._detector = detector
        self._cfg = config

        fs = config.frame_samples
        self._fs = fs
        # ms → 帧数（向上取整，至少 1 帧的语义边界）
        self._min_silence_frames = max(1, math.ceil(config.min_silence_ms * 16 / fs))
        self._pre_roll_frames = math.ceil(config.pre_roll_ms * 16 / fs)
        self._post_roll_samples = config.post_roll_ms * 16
        self._min_speech_samples = config.min_speech_ms * 16
        self._max_segment_samples = config.max_segment_ms * 16

        # 流位置记账
        self._initialized = False
        self._abs_next = 0                       # 下一个 leftover 首样本的绝对帧
        self._leftover = np.empty(0, dtype=np.int16)

        # 状态机
        self._state = _SILENCE
        self._preroll: deque[np.ndarray] = deque(maxlen=max(1, self._pre_roll_frames))
        self._seg_frames: list[np.ndarray] = []
        self._seg_start_abs = 0
        self._first_speech_abs = 0
        self._last_speech_end = 0
        self._trailing_silence = 0

    # ---- 公开接口 ----

    def push(self, audio: np.ndarray, start_frame: int) -> list[SpeechSegment]:
        """喂一块 16kHz int16 单声道，返回本次已收尾的 segment。"""
        audio = np.ascontiguousarray(audio, dtype=np.int16).reshape(-1)

        if not self._initialized:
            self._abs_next = start_frame
            self._initialized = True
        else:
            expected = self._abs_next + len(self._leftover)
            if start_frame != expected:
                logger.warning(
                    "VAD ch%d: 非连续 push start_frame=%d，期望 %d，按内部游标为准",
                    self._ch, start_frame, expected,
                )

        buf = (
            np.concatenate([self._leftover, audio])
            if len(self._leftover)
            else audio
        )
        fs = self._fs
        n_full = len(buf) // fs

        emitted: list[SpeechSegment] = []
        for k in range(n_full):
            frame = buf[k * fs : (k + 1) * fs]
            abs_start = self._abs_next + k * fs
            seg = self._process_frame(frame, abs_start)
            if seg is not None:
                emitted.append(seg)

        consumed = n_full * fs
        self._leftover = buf[consumed:].copy()
        self._abs_next += consumed
        return emitted

    def flush(self) -> list[SpeechSegment]:
        """流结束：排出仍在进行中的 speech buffer（时长达标则成段）。"""
        if self._state != _SPEECH:
            return []
        seg = self._close_segment(trim_post_roll=True)
        self._state = _SILENCE
        self._reset_segment()
        return [seg] if seg is not None else []

    # ---- 内部 ----

    def _process_frame(self, frame: np.ndarray, abs_start: int) -> SpeechSegment | None:
        is_speech = self._detector.speech_prob(frame) >= self._cfg.threshold

        if self._state == _SILENCE:
            self._preroll.append(frame)
            if is_speech:
                self._enter_speech(abs_start)
            return None

        # _SPEECH
        self._seg_frames.append(frame)
        if is_speech:
            self._last_speech_end = abs_start + self._fs
            self._trailing_silence = 0
        else:
            self._trailing_silence += 1
            if self._trailing_silence >= self._min_silence_frames:
                seg = self._close_segment(trim_post_roll=True)
                self._state = _SILENCE
                self._reset_segment()
                return seg

        # 超长强切（不修 post-roll，仍在语音中）
        seg_len = (abs_start + self._fs) - self._seg_start_abs
        if seg_len >= self._max_segment_samples:
            seg = self._close_segment(trim_post_roll=False)
            # 立即续开新段，仍处 SPEECH，无 pre-roll
            self._seg_frames = []
            self._seg_start_abs = abs_start + self._fs
            self._first_speech_abs = abs_start + self._fs
            self._last_speech_end = abs_start + self._fs
            self._trailing_silence = 0
            return seg

        return None

    def _enter_speech(self, abs_start: int) -> None:
        preroll = list(self._preroll)  # 含当前帧（刚 append）
        self._seg_frames = preroll.copy()
        self._seg_start_abs = abs_start - (len(preroll) - 1) * self._fs
        self._first_speech_abs = abs_start
        self._last_speech_end = abs_start + self._fs
        self._trailing_silence = 0
        self._state = _SPEECH
        self._preroll.clear()

    def _close_segment(self, *, trim_post_roll: bool) -> SpeechSegment | None:
        """组装当前 segment。trim_post_roll 时把尾静音裁到 post_roll。"""
        if not self._seg_frames:
            return None
        full = np.concatenate(self._seg_frames)
        buf_end = self._seg_start_abs + len(full)

        if trim_post_roll:
            # 时长按语音跨度判定（不含 pre/post-roll）
            speech_span = self._last_speech_end - self._first_speech_abs
            if speech_span < self._min_speech_samples:
                return None
            desired_end = min(self._last_speech_end + self._post_roll_samples, buf_end)
        else:
            desired_end = buf_end

        keep = desired_end - self._seg_start_abs
        audio = np.ascontiguousarray(full[:keep])
        return SpeechSegment(
            ch=self._ch,
            audio=audio,
            start_frame=self._seg_start_abs,
            end_frame=self._seg_start_abs + keep,
        )

    def _reset_segment(self) -> None:
        self._seg_frames = []
        self._preroll.clear()
        self._trailing_silence = 0
