"""测试夹具：用 soundfile 合成临时 WAV。"""
from collections.abc import Iterator

import numpy as np
import pytest
import soundfile as sf

from backend.db.dal import DAL


def _sine(freq, rate, seconds):
    t = np.arange(int(rate * seconds), dtype=np.float32) / rate
    return 0.5 * np.sin(2 * np.pi * freq * t)


def _write(path, data, rate):
    sf.write(str(path), data.astype(np.float32), rate, subtype="FLOAT")
    return str(path)


@pytest.fixture
def stereo_48k_wav(tmp_path):
    """1.0s 立体声 48kHz：两路不同频率。"""
    left = _sine(440, 48000, 1.0)
    right = _sine(880, 48000, 1.0)
    data = np.stack([left, right], axis=1)
    return _write(tmp_path / "stereo_48k.wav", data, 48000)


@pytest.fixture
def mono_16k_wav(tmp_path):
    """1.0s 单声道 16kHz。"""
    return _write(tmp_path / "mono_16k.wav", _sine(440, 16000, 1.0), 16000)


@pytest.fixture
def odd_rate_wav(tmp_path):
    """1.0s 立体声 44.1kHz：非常规采样率。"""
    data = np.stack([_sine(440, 44100, 1.0), _sine(660, 44100, 1.0)], axis=1)
    return _write(tmp_path / "odd_44k.wav", data, 44100)


@pytest.fixture
def four_channel_wav(tmp_path):
    """1.0s 四声道 48kHz：超过 max_channels。"""
    chans = [_sine(f, 48000, 1.0) for f in (440, 550, 660, 770)]
    data = np.stack(chans, axis=1)
    return _write(tmp_path / "four_ch_48k.wav", data, 48000)


@pytest.fixture
def tmp_dal(tmp_path) -> Iterator[DAL]:
    """每个测试一个临时 sqlite DAL，自动 close。

    用 tmp_path（pytest 内置）而非 :memory:（DAL 双连接 migrations 不兼容）。
    """
    d = DAL(tmp_path / "test.db")
    try:
        yield d
    finally:
        d.close()
