"""EnergyVad 探测器测试（零依赖 fallback）。SileroVad 需 torch，留 [手动测试]。"""
import numpy as np

from backend.vad.detector import EnergyVad, VadDetector


def test_energy_vad_speech_above_threshold():
    vad = EnergyVad(rms_threshold=500.0)
    loud = (np.ones(512) * 8000).astype(np.int16)
    assert vad.speech_prob(loud) == 1.0


def test_energy_vad_silence_below_threshold():
    vad = EnergyVad(rms_threshold=500.0)
    assert vad.speech_prob(np.zeros(512, dtype=np.int16)) == 0.0


def test_energy_vad_satisfies_protocol():
    vad = EnergyVad()
    assert isinstance(vad, VadDetector)  # 运行时可检查协议
    vad.reset()  # 不崩
