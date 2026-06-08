"""align_segments 单测：ASR 绝对 ms 轴 与 diarization 相对秒轴 对齐（切片 1 / B2）。

重点守护 B2 修复：diarization turn 是相对缓冲起点的秒数，ASR segment 是 take 绝对 ms。
必须经 audio_start_s（= buffer.base_frame / 16000）把 turn 抬到绝对秒轴才能正确重叠。
"""
from __future__ import annotations

from types import SimpleNamespace

from backend.diarization.backfill import align_segments


def _seg(segment_id: int, start_ms: int, end_ms: int):
    return SimpleNamespace(segment_id=segment_id, start_frame=start_ms, end_frame=end_ms)


def _turn(start_s: float, end_s: float, label: str):
    return SimpleNamespace(start_s=start_s, end_s=end_s, label=label)


def test_basic_overlap_assigns_speaker():
    segs = [_seg(1, 0, 5000)]              # 0–5s 绝对
    turns = [_turn(0.0, 5.0, "SPEAKER_00")]
    out = align_segments(segs, turns, {"SPEAKER_00": "说话人1"})
    assert out == {1: "说话人1"}


def test_audio_start_offset_required_for_match():
    """take 在第 10s 才开始缓冲：turn 相对 0–5s = 绝对 10–15s，需 audio_start_s=10 才命中。"""
    segs = [_seg(1, 10_000, 15_000)]      # 绝对 10–15s
    turns = [_turn(0.0, 5.0, "SPEAKER_00")]  # 相对缓冲起点
    smap = {"SPEAKER_00": "说话人1"}

    # 不加偏移（旧 B2 bug）→ turn 落在绝对 0–5s，与 segment 无重叠 → 不分配
    assert align_segments(segs, turns, smap, audio_start_s=0.0) == {}
    # 加偏移 → turn 抬到绝对 10–15s，完全重叠 → 分配
    assert align_segments(segs, turns, smap, audio_start_s=10.0) == {1: "说话人1"}


def test_picks_max_overlap_turn():
    seg = [_seg(1, 0, 10_000)]            # 0–10s
    turns = [
        _turn(0.0, 3.0, "SPEAKER_00"),   # 重叠 3s
        _turn(3.0, 10.0, "SPEAKER_01"),  # 重叠 7s ← 最大
    ]
    out = align_segments(seg, turns, {"SPEAKER_00": "甲", "SPEAKER_01": "乙"})
    assert out == {1: "乙"}


def test_no_overlap_left_unassigned():
    seg = [_seg(1, 0, 1000)]             # 0–1s
    turns = [_turn(5.0, 8.0, "SPEAKER_00")]
    out = align_segments(seg, turns, {"SPEAKER_00": "说话人1"})
    assert out == {}


def test_label_not_in_speaker_map_skipped():
    seg = [_seg(1, 0, 5000)]
    turns = [_turn(0.0, 5.0, "SPEAKER_09")]
    out = align_segments(seg, turns, {"SPEAKER_00": "说话人1"})  # 09 未映射
    assert out == {}


def test_zero_duration_segment_skipped():
    seg = [_seg(1, 5000, 5000)]
    turns = [_turn(0.0, 10.0, "SPEAKER_00")]
    out = align_segments(seg, turns, {"SPEAKER_00": "说话人1"})
    assert out == {}
