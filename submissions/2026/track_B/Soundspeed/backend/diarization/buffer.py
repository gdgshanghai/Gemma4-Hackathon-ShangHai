"""TakeAudioBuffer：take 期间累积 ch1 PCM 的内存缓冲。

约 8MB / 4分钟（int16 16kHz 单声道）。不落盘。
线程安全：StreamDriver 后台线程 append，take.end 时 Orchestrator 读取。

**连续时间轴（spec realtime-diarization §4 / B2 修复）**：累积的是**连续 ch1**
（逐 chunk 全量，含静音），不是 VAD 切出的语音段。这样 diarization 在拼接音频
上产出的 turn 时间轴 == take 绝对时间轴，可直接与 ASR segment 的绝对帧对齐。
首次 append 记录 base_frame（首块绝对 16k 帧），供对齐时换算秒/毫秒基准。
"""
from __future__ import annotations

import threading

import numpy as np

SAMPLE_RATE = 16000


class TakeAudioBuffer:
    """线程安全的 int16 16kHz 单声道连续 PCM 内存缓冲。

    take.start → 清空；take 录制期间 StreamDriver 逐 chunk 调 append()；
    take.end → Orchestrator 调 get_audio() 取整段 + 读 base_frame；之后 clear() 释放。
    """

    def __init__(self) -> None:
        self._chunks: list[np.ndarray] = []
        self._base_frame: int | None = None
        self._lock = threading.Lock()

    def append(self, pcm: np.ndarray, start_frame: int | None = None) -> None:
        """追加一块连续 ch1 int16 PCM。线程安全，可从任意线程调用。

        start_frame 为该块首样本的绝对 16k 帧位置；首次 append 时据此记录 base_frame
        （后续块只拼接、不更新 base）。不传时 base_frame 退化为 0。
        """
        with self._lock:
            if self._base_frame is None:
                self._base_frame = start_frame if start_frame is not None else 0
            self._chunks.append(pcm.copy() if not pcm.flags["OWNDATA"] else pcm)

    def get_audio(self) -> np.ndarray:
        """返回拼接后的完整 int16 PCM 数组。未录制时返回空数组。"""
        with self._lock:
            if not self._chunks:
                return np.array([], dtype=np.int16)
            return np.concatenate(self._chunks)

    def clear(self) -> None:
        """释放所有内存 + 复位 base_frame（take 结束、diarization 完成后调用）。"""
        with self._lock:
            self._chunks.clear()
            self._base_frame = None

    @property
    def base_frame(self) -> int:
        """缓冲首样本的绝对 16k 帧位置（未 append 过时为 0）。"""
        with self._lock:
            return self._base_frame if self._base_frame is not None else 0

    @property
    def sample_count(self) -> int:
        """已缓存的样本总数。"""
        with self._lock:
            return sum(len(c) for c in self._chunks)

    @property
    def duration_s(self) -> float:
        """已缓存时长（秒），假设 16000 Hz。"""
        return self.sample_count / SAMPLE_RATE
