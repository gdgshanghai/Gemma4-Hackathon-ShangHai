"""设备解析纯函数测试（TDD 红阶段）。

测试两个纯函数：
- resolve_device_name(persisted_name, env_value, devices, default_index)
  启动时全优先级解析，返回 (name, source) 二元组。
  source: 'persisted' | 'env' | 'system_default' | 'first_available' | None（无设备）
- resolve_device_index(name, devices, default_index)
  name→index+available，供 _source_factory 与 GET /devices 使用。
  返回 (index, available) 二元组。
"""
from __future__ import annotations

from backend.audio.devices import InputDevice
from backend.audio.device_resolve import resolve_device_name, resolve_device_index

_DEVICES = [
    InputDevice(index=1, name="MacBook Pro Microphone", max_input_channels=1, is_default=True),
    InputDevice(index=3, name="USB Audio Device", max_input_channels=2, is_default=False),
    InputDevice(index=5, name="iPhone Microphone", max_input_channels=1, is_default=False),
]
_DEFAULT_INDEX = 1  # 与 _DEVICES[0] 对应


# ── resolve_device_name：启动优先级 ──────────────────────────────────────────


def test_resolve_persisted_wins_over_env() -> None:
    """持久化设备在场 → 选持久化，source='persisted'，不管 env 写了什么。"""
    name, source = resolve_device_name(
        persisted_name="USB Audio Device",
        env_value="5",  # 指向 iPhone（序号），但持久化优先
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert name == "USB Audio Device"
    assert source == "persisted"


def test_resolve_persisted_not_present_falls_to_env_by_index() -> None:
    """持久化设备不在场 → 退 env（序号格式），source='env'。"""
    name, source = resolve_device_name(
        persisted_name="Dead Device",
        env_value="3",  # USB Audio Device 的 index
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert name == "USB Audio Device"
    assert source == "env"


def test_resolve_persisted_not_present_falls_to_env_by_name() -> None:
    """持久化设备不在场 → 退 env（名字格式），source='env'。"""
    name, source = resolve_device_name(
        persisted_name="Dead Device",
        env_value="USB Audio Device",
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert name == "USB Audio Device"
    assert source == "env"


def test_resolve_no_persisted_env_wins() -> None:
    """无持久化 → env（名字），source='env'。"""
    name, source = resolve_device_name(
        persisted_name=None,
        env_value="iPhone Microphone",
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert name == "iPhone Microphone"
    assert source == "env"


def test_resolve_no_persisted_no_env_system_default() -> None:
    """无持久化、无 env → 系统默认，source='system_default'。"""
    name, source = resolve_device_name(
        persisted_name=None,
        env_value=None,
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert name == "MacBook Pro Microphone"
    assert source == "system_default"


def test_resolve_no_default_falls_first_available() -> None:
    """系统默认 index 找不到对应设备 → 第一个可用，source='first_available'。"""
    name, source = resolve_device_name(
        persisted_name=None,
        env_value=None,
        devices=_DEVICES,
        default_index=99,  # 不存在
    )
    assert name == _DEVICES[0].name
    assert source == "first_available"


def test_resolve_no_devices_returns_none() -> None:
    """零设备 → (None, None)。"""
    name, source = resolve_device_name(
        persisted_name=None,
        env_value=None,
        devices=[],
        default_index=None,
    )
    assert name is None
    assert source is None


def test_resolve_env_invalid_index_skips_to_system_default() -> None:
    """env 是序号但在 devices 里不存在 → 跳过 env，退系统默认。"""
    name, source = resolve_device_name(
        persisted_name=None,
        env_value="99",  # 不存在的 index
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert name == "MacBook Pro Microphone"
    assert source == "system_default"


def test_resolve_env_invalid_name_skips_to_system_default() -> None:
    """env 是不存在的名字 → 跳过 env，退系统默认。"""
    name, source = resolve_device_name(
        persisted_name=None,
        env_value="Ghost Device",
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert name == "MacBook Pro Microphone"
    assert source == "system_default"


def test_resolve_env_negative_index_skips() -> None:
    """SOUNDSPEED_AUDIO_DEVICE="-1" → 解析成 int(-1)，在 devices 里不存在，跳过 env，退系统默认。

    sounddevice 用 -1 表示「未设」，不是有效设备 index。
    """
    name, source = resolve_device_name(
        persisted_name=None,
        env_value="-1",
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert name == "MacBook Pro Microphone"
    assert source == "system_default"


# ── resolve_device_index：name→index 回查 ────────────────────────────────────


def test_resolve_index_found() -> None:
    """已知名字 → (index, True)。"""
    index, available = resolve_device_index(
        name="USB Audio Device",
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert index == 3
    assert available is True


def test_resolve_index_not_found_falls_to_default() -> None:
    """设备已拔走 → 退系统默认 index，available=False。"""
    index, available = resolve_device_index(
        name="Dead Device",
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert index == _DEFAULT_INDEX
    assert available is False


def test_resolve_index_none_name_returns_default() -> None:
    """name=None（零设备退化场景）→ 退系统默认 index，available=False。"""
    index, available = resolve_device_index(
        name=None,
        devices=_DEVICES,
        default_index=_DEFAULT_INDEX,
    )
    assert index == _DEFAULT_INDEX
    assert available is False


def test_resolve_index_no_devices_no_default() -> None:
    """零设备 + 无默认 → (None, False)。"""
    index, available = resolve_device_index(
        name="Any",
        devices=[],
        default_index=None,
    )
    assert index is None
    assert available is False


def test_resolve_index_roundtrip() -> None:
    """POST select index=N → resolve_index(name) 往返闭合：index 还是 N。"""
    # 模拟 POST select: index=3 → name="USB Audio Device"
    selected_index = 3
    matched = next(d for d in _DEVICES if d.index == selected_index)
    name = matched.name

    # GET: name → index 往返
    idx, available = resolve_device_index(name, _DEVICES, _DEFAULT_INDEX)
    assert idx == selected_index
    assert available is True
