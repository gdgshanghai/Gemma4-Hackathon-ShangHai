"""Voice Activity Layer 数据结构（spec v0.1 §2 §6）。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SpeechSegment:
    """VAD 层 → ASRService 的输入（asr-service §8 的 segment 参数）。

    单位为 16kHz 绝对帧（与 AudioChunk.start_frame 同基），不是毫秒。
    publisher（1.C）在转 contract C1 时再做帧 → 毫秒换算。
    """

    ch: int                # 声道号，AudioChunk.channels 的索引（0-based）
    audio: np.ndarray      # 16kHz 单声道 int16，含 pre/post-roll
    start_frame: int       # 16kHz 绝对帧（含 pre-roll 起点）
    end_frame: int         # 16kHz 绝对帧（含 post-roll 终点）；end_frame > start_frame


@dataclass(frozen=True)
class VadConfig:
    """端点切段参数。ms → 帧换算用 16kHz（frames = ms * 16）。"""

    frame_samples: int = 512        # silero v5 @ 16k 硬要求，不要改
    threshold: float = 0.5          # speech_prob 阈值
    min_silence_ms: int = 300       # 静音多久算 turn 收尾（实时手感主旋钮；原 600ms，减少感知延迟）
    min_speech_ms: int = 250        # 短于此的语音段丢弃（同时也是抗幻觉最短门限）
    pre_roll_ms: int = 150          # 段首回补，防吃掉起音
    post_roll_ms: int = 150         # 段尾延伸，防切掉收音
    max_segment_ms: int = 30000     # 超长强切
