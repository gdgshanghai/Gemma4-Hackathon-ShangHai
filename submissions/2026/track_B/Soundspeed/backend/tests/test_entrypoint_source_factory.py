"""entrypoint 启动解析 + _source_factory 行为测试。

只测「设备解析接线」，不测 ASR 模型加载（那是 test_whisper_runner.py 的职责）。
直接调 resolve_device_name / resolve_device_index 纯函数，验证 entrypoint 使用的接线语义。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from backend.audio.devices import InputDevice
from backend.db.dal import DAL

_DEVICES = [
    InputDevice(index=1, name="MacBook Pro Microphone", max_input_channels=1, is_default=True),
    InputDevice(index=3, name="USB Audio Device", max_input_channels=2, is_default=False),
]
_DEFAULT_INDEX = 1


def _make_orchestrator(dal: DAL):
    orch = MagicMock()
    orch.dal = dal
    orch.publish = MagicMock()
    orch.subscribe = MagicMock()
    return orch


# ── 启动时 default_device 解析 ────────────────────────────────────────────────


def test_startup_no_persisted_no_env_uses_system_default(tmp_path: Path):
    """无持久化、无 env → default_device 设为系统默认设备名。"""
    dal = DAL(tmp_path / "test.db")

    from backend.audio.device_resolve import resolve_device_name

    name, source = resolve_device_name(
        persisted_name=dal.get_setting("audio_input_device"),  # None
        env_value=None,
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )

    assert name == "MacBook Pro Microphone"
    assert source == "system_default"
    dal.close()


def test_startup_persisted_name_wins_over_env(tmp_path: Path):
    """持久化名字在场 → 即使 env 指向另一台设备，持久化赢。"""
    dal = DAL(tmp_path / "test.db")
    dal.set_setting("audio_input_device", "USB Audio Device")

    from backend.audio.device_resolve import resolve_device_name

    name, source = resolve_device_name(
        persisted_name=dal.get_setting("audio_input_device"),
        env_value="1",  # MacBook Pro Microphone（index 1）
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert name == "USB Audio Device"
    assert source == "persisted"
    dal.close()


def test_startup_persisted_not_present_env_used(tmp_path: Path):
    """持久化设备不在场 → 退 env。"""
    dal = DAL(tmp_path / "test.db")
    dal.set_setting("audio_input_device", "Dead Device")

    from backend.audio.device_resolve import resolve_device_name

    name, source = resolve_device_name(
        persisted_name=dal.get_setting("audio_input_device"),
        env_value="3",  # USB Audio Device（index 3）
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert name == "USB Audio Device"
    assert source == "env"
    dal.close()


# ── _source_factory：name→index 解析 ─────────────────────────────────────────


def test_source_factory_resolves_name_to_index():
    """_source_factory 收到名字 → 查 index → 按 index 开流（DeviceSource 收到 index）。"""
    from backend.audio.device_resolve import resolve_device_index

    idx, available = resolve_device_index(
        name="USB Audio Device",
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert idx == 3
    assert available is True


def test_source_factory_fallback_when_device_missing():
    """_source_factory 设备已拔走 → fallback 到 default_index，available=False。"""
    from backend.audio.device_resolve import resolve_device_index

    idx, available = resolve_device_index(
        name="Dead Device",
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert idx == _DEFAULT_INDEX
    assert available is False
