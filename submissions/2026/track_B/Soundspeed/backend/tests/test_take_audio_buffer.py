"""TakeAudioBuffer 单测：连续累积 + base_frame 记账（切片 1 / B2 修复）。"""
from __future__ import annotations

import numpy as np

from backend.diarization.buffer import TakeAudioBuffer


def _pcm(n: int, val: int = 1) -> np.ndarray:
    return np.full(n, val, dtype=np.int16)


def test_append_accumulates_in_order():
    buf = TakeAudioBuffer()
    buf.append(_pcm(3, 1), start_frame=0)
    buf.append(_pcm(2, 2), start_frame=3)
    out = buf.get_audio()
    assert out.dtype == np.int16
    assert out.tolist() == [1, 1, 1, 2, 2]
    assert buf.sample_count == 5


def test_empty_buffer_returns_empty_array():
    buf = TakeAudioBuffer()
    out = buf.get_audio()
    assert out.dtype == np.int16
    assert out.size == 0
    assert buf.sample_count == 0
    assert buf.base_frame == 0


def test_base_frame_set_by_first_append_only():
    buf = TakeAudioBuffer()
    buf.append(_pcm(4), start_frame=32000)
    buf.append(_pcm(4), start_frame=99999)  # 后续块不改 base
    assert buf.base_frame == 32000


def test_base_frame_defaults_zero_when_not_given():
    buf = TakeAudioBuffer()
    buf.append(_pcm(4))
    assert buf.base_frame == 0


def test_clear_releases_and_resets_base():
    buf = TakeAudioBuffer()
    buf.append(_pcm(4), start_frame=16000)
    buf.clear()
    assert buf.sample_count == 0
    assert buf.get_audio().size == 0
    assert buf.base_frame == 0
    # 清空后可作为新 take 重新起 base
    buf.append(_pcm(2), start_frame=48000)
    assert buf.base_frame == 48000


def test_append_copies_non_owning_view():
    """传入切片视图时存独立副本，源数组被改不应污染缓冲。"""
    buf = TakeAudioBuffer()
    src = _pcm(6, 7)
    buf.append(src[1:4], start_frame=0)  # 视图，OWNDATA=False
    src[:] = 0
    assert buf.get_audio().tolist() == [7, 7, 7]


def test_duration_s_assumes_16k():
    buf = TakeAudioBuffer()
    buf.append(_pcm(16000), start_frame=0)
    assert buf.duration_s == 1.0
