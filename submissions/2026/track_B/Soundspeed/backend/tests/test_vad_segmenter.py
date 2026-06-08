"""ChannelVADSegmenter 端点状态机测试（VAD 层 v0.1 §9 测试矩阵）。

用确定性假探测器 _AmplitudeVad（按帧 RMS 判定），状态机零依赖可测；
真实 silero onnx 封装留 smoke / [手动测试]，不在此覆盖。
"""
from dataclasses import replace

import numpy as np

from backend.vad.models import SpeechSegment, VadConfig
from backend.vad.segmenter import ChannelVADSegmenter


# ── 确定性假探测器 ────────────────────────────────────────────────────────────


class _AmplitudeVad:
    """帧 RMS 超阈值即判语音。确定性、零下载，覆盖状态机全分支。"""

    def __init__(self, amp_threshold: float = 1000.0) -> None:
        self._amp = amp_threshold

    def speech_prob(self, frame: np.ndarray) -> float:
        rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))
        return 1.0 if rms > self._amp else 0.0

    def reset(self) -> None:
        pass


# ── 合成音频构造 ──────────────────────────────────────────────────────────────


def _silence(n: int) -> np.ndarray:
    return np.zeros(n, dtype=np.int16)


def _speech(n: int, amp: int = 8000) -> np.ndarray:
    """白噪：每个 512 帧 RMS 稳定超阈值（正弦过零点附近不稳，噪声更可靠）。"""
    rng = np.random.default_rng(0)
    return rng.integers(-amp, amp, size=n, endpoint=True).astype(np.int16)


def _cfg(**kw) -> VadConfig:
    base = VadConfig(
        frame_samples=512,
        threshold=0.5,
        min_silence_ms=300,    # 4800 样本 ≈ 9.4 帧
        min_speech_ms=250,     # 4000 样本
        pre_roll_ms=200,       # 3200 样本
        post_roll_ms=200,      # 3200 样本
        max_segment_ms=30000,
    )
    return replace(base, **kw)


def _run(audio: np.ndarray, cfg: VadConfig | None = None, start_frame: int = 0) -> list[SpeechSegment]:
    cfg = cfg or _cfg()
    sm = ChannelVADSegmenter(ch=0, detector=_AmplitudeVad(), config=cfg)
    out = sm.push(audio, start_frame)
    out += sm.flush()
    return out


# ── 测试矩阵 ──────────────────────────────────────────────────────────────────


def test_single_burst_one_segment():
    audio = np.concatenate([_silence(8000), _speech(16000), _silence(8000)])
    segs = _run(audio)
    assert len(segs) == 1
    seg = segs[0]
    assert seg.ch == 0
    assert seg.end_frame > seg.start_frame
    assert seg.audio.dtype == np.int16
    assert len(seg.audio) == seg.end_frame - seg.start_frame


def test_two_bursts_long_gap_two_segments():
    audio = np.concatenate(
        [_silence(4000), _speech(8000), _silence(8000), _speech(8000), _silence(8000)]
    )
    segs = _run(audio)
    assert len(segs) == 2


def test_two_bursts_short_gap_merged():
    # 间隔 2000 样本 < min_silence(4800) → 不收尾，合并成一段
    audio = np.concatenate(
        [_silence(4000), _speech(8000), _silence(2000), _speech(8000), _silence(8000)]
    )
    segs = _run(audio)
    assert len(segs) == 1


def test_all_silence_no_segment():
    segs = _run(_silence(32000))
    assert segs == []


def test_short_speech_dropped():
    # 语音 2000 样本 < min_speech(4000) → 丢弃
    audio = np.concatenate([_silence(4000), _speech(2000), _silence(8000)])
    segs = _run(audio)
    assert segs == []


def test_long_speech_force_split():
    cfg = _cfg(max_segment_ms=500)  # 8000 样本强切
    audio = np.concatenate([_silence(2000), _speech(40000), _silence(8000)])
    segs = _run(audio, cfg)
    assert len(segs) >= 3
    for seg in segs:
        assert seg.end_frame > seg.start_frame


def test_flush_emits_trailing_segment():
    # 末尾无静音收尾，segment 仍开着 → flush 吐出
    audio = np.concatenate([_silence(4000), _speech(8000)])
    cfg = _cfg()
    sm = ChannelVADSegmenter(ch=0, detector=_AmplitudeVad(), config=cfg)
    during = sm.push(audio, 0)
    after = sm.flush()
    assert during == []
    assert len(after) == 1


def test_pre_roll_extends_start():
    # 静音/语音都对齐 512 帧边界，便于核对 pre-roll 回补
    audio = np.concatenate([_silence(7680), _speech(8192), _silence(7680)])
    cfg = _cfg()
    segs = _run(audio, cfg)
    assert len(segs) == 1
    first_speech_abs = 7680
    pulled_back = first_speech_abs - segs[0].start_frame
    pre_roll_samples = cfg.pre_roll_ms * 16
    assert 0 < pulled_back <= pre_roll_samples + cfg.frame_samples


def test_frames_absolute_and_monotonic():
    audio = np.concatenate(
        [_silence(4000), _speech(8000), _silence(8000), _speech(8000), _silence(8000)]
    )
    segs = _run(audio, start_frame=100_000)
    assert len(segs) == 2
    assert segs[0].start_frame >= 100_000
    assert segs[0].end_frame > segs[0].start_frame
    assert segs[1].start_frame > segs[0].end_frame
    assert segs[1].end_frame > segs[1].start_frame


def test_chunk_not_frame_multiple():
    # 同一音频：整块 push vs 非 512 整数倍分块 push，结果一致（验证跨 push 帧边界）
    audio = np.concatenate(
        [_silence(4000), _speech(8000), _silence(8000), _speech(8000), _silence(8000)]
    )
    whole = _run(audio)

    cfg = _cfg()
    sm = ChannelVADSegmenter(ch=0, detector=_AmplitudeVad(), config=cfg)
    pieces: list[SpeechSegment] = []
    pos = 0
    for size in (300, 700, 1000, 512, 333, 5000, 2048, 9999, 100000):
        if pos >= len(audio):
            break
        block = audio[pos : pos + size]
        pieces += sm.push(block, pos)
        pos += len(block)
    pieces += sm.flush()

    assert len(pieces) == len(whole)
    for a, b in zip(pieces, whole):
        assert abs(a.start_frame - b.start_frame) <= cfg.frame_samples
        assert abs(a.end_frame - b.end_frame) <= cfg.frame_samples


def test_two_channels_independent():
    cfg = _cfg()
    sm0 = ChannelVADSegmenter(ch=0, detector=_AmplitudeVad(), config=cfg)
    sm1 = ChannelVADSegmenter(ch=1, detector=_AmplitudeVad(), config=cfg)
    ch0_audio = np.concatenate([_silence(4000), _speech(8000), _silence(8000)])
    ch1_audio = _silence(20000)

    segs0 = sm0.push(ch0_audio, 0) + sm0.flush()
    segs1 = sm1.push(ch1_audio, 0) + sm1.flush()

    assert len(segs0) == 1
    assert segs0[0].ch == 0
    assert segs1 == []
