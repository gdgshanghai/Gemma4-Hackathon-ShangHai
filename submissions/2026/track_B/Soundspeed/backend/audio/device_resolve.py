"""设备选择解析纯函数（无副作用，便于单测）。

两个纯函数：
- resolve_device_name：启动时全优先级解析，返回 (name, source)
- resolve_device_index：name→index 回查，供 _source_factory 和 GET /devices 使用
"""
from __future__ import annotations

import logging

from backend.audio.devices import InputDevice

logger = logging.getLogger(__name__)

# resolve_device_name 返回的 source 常量
SOURCE_PERSISTED = "persisted"
SOURCE_ENV = "env"
SOURCE_SYSTEM_DEFAULT = "system_default"
SOURCE_FIRST_AVAILABLE = "first_available"


def resolve_device_name(
    persisted_name: str | None,
    env_value: str | None,
    devices: list[InputDevice],
    default_index: int | None,
) -> tuple[str | None, str | None]:
    """启动时全优先级设备解析。

    优先级（高→低）：
      1. 持久化名字（persisted_name）且当前在场
      2. SOUNDSPEED_AUDIO_DEVICE env（名字或序号）且当前在场/存在
      3. 系统默认输入（default_index 对应的设备）
      4. 第一个可用设备
      5. 零设备 → (None, None)

    参数：
      persisted_name: 上次保存的设备名（来自 get_setting("audio_input_device")）；None 表示无持久化。
      env_value: SOUNDSPEED_AUDIO_DEVICE 环境变量值；None 表示未设。
        数字字符串 → 按 index 查；否则按 name 查。
      devices: 当前 list_input_devices() 结果（已去重）。
      default_index: 系统默认输入设备 index（来自 sd.default.device[0]）；None 表示未设。

    返回：
      (name, source)：name 为选中设备名；source 为命中来源常量；零设备时均 None。
    """
    # 建两个快速查找表
    by_name: dict[str, InputDevice] = {d.name: d for d in devices}
    by_index: dict[int, InputDevice] = {d.index: d for d in devices}

    # 1. 持久化
    if persisted_name is not None:
        if persisted_name in by_name:
            logger.info("设备选择：命中持久化设备 %r", persisted_name)
            return persisted_name, SOURCE_PERSISTED
        logger.info("设备选择：持久化设备 %r 当前不在场，向下 fallback", persisted_name)

    # 2. env
    if env_value is not None:
        env_device = _resolve_env(env_value, by_name, by_index)
        if env_device is not None:
            logger.info("设备选择：命中 env 设备 %r（env=%r）", env_device.name, env_value)
            return env_device.name, SOURCE_ENV
        logger.info("设备选择：env=%r 无法匹配到设备，向下 fallback", env_value)

    # 3. 系统默认
    if default_index is not None and default_index in by_index:
        name = by_index[default_index].name
        logger.info("设备选择：使用系统默认设备 %r（index=%d）", name, default_index)
        return name, SOURCE_SYSTEM_DEFAULT

    # 4. 第一个可用
    if devices:
        name = devices[0].name
        logger.info("设备选择：退至第一个可用设备 %r", name)
        return name, SOURCE_FIRST_AVAILABLE

    # 5. 零设备
    logger.warning("设备选择：无可用输入设备")
    return None, None


def _resolve_env(
    env_value: str,
    by_name: dict[str, InputDevice],
    by_index: dict[int, InputDevice],
) -> InputDevice | None:
    """将 env 字符串解析为 InputDevice。数字 → 按 index 查；否则按 name 查。"""
    stripped = env_value.lstrip("-")
    if stripped.isdigit():
        idx = int(env_value)
        return by_index.get(idx)
    return by_name.get(env_value)


def resolve_device_index(
    name: str | None,
    devices: list[InputDevice],
    default_index: int | None,
) -> tuple[int | None, bool]:
    """将设备名解析为当前 index（供 _source_factory 和 GET /devices）。

    参数：
      name: session._device 存储的设备名；None 表示零设备退化。
      devices: 当前 list_input_devices() 结果（已去重）。
      default_index: 系统默认输入设备 index；None 表示未设。

    返回：
      (index, available)：
        available=True  → 设备在场，index 为其当前序号。
        available=False → 设备不在场（或 name=None），已 fallback 到 default_index。
        (None, False)   → 零设备且无默认。
    """
    if name is not None:
        by_name: dict[str, InputDevice] = {d.name: d for d in devices}
        if name in by_name:
            return by_name[name].index, True
        # 设备不在场 → fallback 到系统默认（调用方负责 log/告警，此处静默）

    # name=None 或设备不在场
    if default_index is not None:
        return default_index, False

    return None, False
