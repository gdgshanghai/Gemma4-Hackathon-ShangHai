import numpy as np
import pytest

from backend.audio.file_source import FileSource
from backend.audio.source import AudioConfig


def test_file_source_stereo_48k(stereo_48k_wav):
    with FileSource(stereo_48k_wav, AudioConfig()) as src:
        chunks = list(src)
    assert len(chunks) > 0
    for chunk in chunks:
        assert len(chunk.channels) == 2
        assert chunk.sample_rate == 16000
        assert all(c.dtype == np.int16 for c in chunk.channels)
    assert [c.seq for c in chunks] == list(range(len(chunks)))


def test_file_source_total_frames_match_duration(stereo_48k_wav):
    """1.0s 文件 -> 累计输出帧数接近 16000（尾部已排出，容差紧）。"""
    with FileSource(stereo_48k_wav, AudioConfig()) as src:
        total = sum(c.n_frames for c in src)
    assert abs(total - 16000) < 20


def test_file_source_mono(mono_16k_wav):
    with FileSource(mono_16k_wav, AudioConfig()) as src:
        chunks = list(src)
    assert all(len(c.channels) == 1 for c in chunks)


def test_file_source_truncates_four_channels(four_channel_wav):
    """4 声道文件 -> 只输出前 2 路。"""
    with FileSource(four_channel_wav, AudioConfig()) as src:
        chunks = list(src)
    assert all(len(c.channels) == 2 for c in chunks)


def test_file_source_odd_rate_resamples(odd_rate_wav):
    with FileSource(odd_rate_wav, AudioConfig()) as src:
        chunks = list(src)
    assert all(c.sample_rate == 16000 for c in chunks)


def test_file_source_missing_file_raises():
    with pytest.raises(OSError):
        with FileSource("/nonexistent/path_xyz.wav", AudioConfig()) as src:
            list(src)
