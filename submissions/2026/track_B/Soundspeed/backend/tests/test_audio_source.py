import numpy as np
import pytest

from backend.audio.constants import OUTPUT_SAMPLE_RATE
from backend.audio.source import AudioChunk, AudioConfig, AudioSource


def test_output_sample_rate_is_16k():
    assert OUTPUT_SAMPLE_RATE == 16000


def test_audio_config_defaults():
    cfg = AudioConfig()
    assert cfg.chunk_ms == 200
    assert cfg.max_channels == 2


def test_audio_chunk_holds_independent_channel_arrays():
    ch0 = np.zeros(3200, dtype=np.int16)
    ch1 = np.ones(3200, dtype=np.int16)
    chunk = AudioChunk(seq=0, channels=[ch0, ch1], n_frames=3200, start_frame=0)
    assert chunk.sample_rate == 16000
    assert len(chunk.channels) == 2
    assert chunk.channels[0] is ch0 and chunk.channels[1] is ch1


def test_audio_chunk_is_frozen():
    import dataclasses

    chunk = AudioChunk(seq=0, channels=[], n_frames=0, start_frame=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        chunk.seq = 1


class _FakeSource(AudioSource):
    """测试桩：用合成 float32 数据驱动基类，不碰真实设备 / 文件。"""

    def __init__(self, config, rate, channels, n_blocks, block_frames):
        super().__init__(config)
        self._rate = rate
        self._channels = channels
        self._remaining = n_blocks
        self._block_frames = block_frames
        self.closed = False

    def _open(self):
        return self._rate, self._channels

    def _read_raw_block(self):
        if self._remaining <= 0:
            return None
        self._remaining -= 1
        return np.full(
            (self._block_frames, self._channels), 0.25, dtype=np.float32
        )

    def _close(self):
        self.closed = True


def test_source_yields_chunks_with_truncated_channels():
    """输入 8 声道，max_channels=2 -> 每个 chunk 只有 2 路。"""
    src = _FakeSource(AudioConfig(), rate=48000, channels=8,
                      n_blocks=5, block_frames=9600)
    with src as s:
        chunks = list(s)
    assert len(chunks) >= 5  # 5 个数据 chunk，可能再加一个尾部排出 chunk
    for chunk in chunks:
        assert len(chunk.channels) == 2


def test_source_mono_input_yields_one_channel():
    src = _FakeSource(AudioConfig(), rate=16000, channels=1,
                      n_blocks=3, block_frames=3200)
    with src as s:
        chunks = list(s)
    assert all(len(c.channels) == 1 for c in chunks)


def test_source_seq_and_start_frame_accumulate():
    src = _FakeSource(AudioConfig(), rate=16000, channels=2,
                      n_blocks=4, block_frames=3200)
    with src as s:
        chunks = list(s)
    assert [c.seq for c in chunks] == list(range(len(chunks)))
    expected = 0
    for chunk in chunks:
        assert chunk.start_frame == expected
        expected += chunk.n_frames


def test_source_channels_are_independent_arrays():
    src = _FakeSource(AudioConfig(), rate=48000, channels=2,
                      n_blocks=1, block_frames=9600)
    with src as s:
        chunk = next(iter(s))
    assert chunk.channels[0] is not chunk.channels[1]


def test_source_closes_on_context_exit():
    src = _FakeSource(AudioConfig(), rate=16000, channels=2,
                      n_blocks=1, block_frames=3200)
    with src as s:
        list(s)
    assert src.closed is True


def test_public_api_reexported():
    import backend.audio as audio

    expected = {"AudioConfig", "AudioChunk", "AudioSource", "ChannelProcessor",
                "FileSource", "DeviceSource", "DeviceError", "OUTPUT_SAMPLE_RATE"}
    for name in expected:
        assert hasattr(audio, name), name
    assert set(audio.__all__) == expected


def test_source_closes_when_processor_init_fails(monkeypatch):
    """_open 成功后 ChannelProcessor 构造失败 -> _close 仍被调用，不泄漏句柄。"""
    def _boom(*args, **kwargs):
        raise RuntimeError("resampler init failed")

    monkeypatch.setattr("backend.audio.source.ChannelProcessor", _boom)
    src = _FakeSource(AudioConfig(), rate=48000, channels=2,
                      n_blocks=1, block_frames=9600)
    with pytest.raises(RuntimeError):
        src.__enter__()
    assert src.closed is True
