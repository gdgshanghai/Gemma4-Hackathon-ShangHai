import pytest

from backend.audio.device_source import DeviceError, DeviceSource, open_device_with_fallback
from backend.audio.source import AudioConfig


def test_device_source_unknown_device_raises_with_device_list():
    """不存在的设备名 -> DeviceError，错误信息含可用设备清单。"""
    src = DeviceSource("不存在的设备_xyz_12345", AudioConfig())
    with pytest.raises(DeviceError) as exc:
        with src:
            pass
    assert "可用输入设备" in str(exc.value)


# ── open_device_with_fallback 纯逻辑测试（注入假 probe）────────────────────
#
# open_device_with_fallback 返回首个可成功打开的 index/name（int | str）。
# 调用方用返回值重新构造 DeviceSource，避免双重 _open。
# 测试注入假 probe（只在 fail_indices 里的设备抛 DeviceError），不依赖真 PortAudio。


def _make_probe(fail_indices: set[int | str]):
    """构造假 probe：fail_indices 里的设备抛 DeviceError，其余静默通过。"""
    call_log: list[int | str] = []

    def probe(device: int | str, config: AudioConfig) -> None:
        call_log.append(device)
        if device in fail_indices:
            raise DeviceError(f"fake: 无法打开 {device!r}")

    return probe, call_log


def test_open_fallback_first_candidate_succeeds():
    """第一个候选成功 → 返回该 index，不尝试后续。"""
    probe, log = _make_probe(fail_indices=set())
    result = open_device_with_fallback([2, 1, 0], AudioConfig(), _probe=probe)
    assert result == 2
    assert log == [2]


def test_open_fallback_skips_failing_candidates():
    """前 N 个候选失败 → 依次尝试，第 N+1 个成功时返回。"""
    probe, log = _make_probe(fail_indices={2, 1})
    result = open_device_with_fallback([2, 1, 0], AudioConfig(), _probe=probe)
    assert result == 0
    assert log == [2, 1, 0]


def test_open_fallback_all_fail_raises():
    """全部候选失败 → 抛 DeviceError。"""
    probe, log = _make_probe(fail_indices={2, 1, 0})
    with pytest.raises(DeviceError):
        open_device_with_fallback([2, 1, 0], AudioConfig(), _probe=probe)
    assert log == [2, 1, 0]


def test_open_fallback_dedup_candidates():
    """候选列表有重复 index → 不重复尝试（去重后顺序不变）。"""
    probe, log = _make_probe(fail_indices={2})
    result = open_device_with_fallback([2, 2, 1], AudioConfig(), _probe=probe)
    assert result == 1
    assert log == [2, 1]  # index=2 只试一次


def test_open_fallback_none_in_candidates_skipped():
    """候选列表含 None → None 被跳过（zero-device 退化不应尝试）。"""
    probe, log = _make_probe(fail_indices=set())
    result = open_device_with_fallback([None, 1], AudioConfig(), _probe=probe)  # type: ignore[list-item]
    assert result == 1
    assert None not in log
