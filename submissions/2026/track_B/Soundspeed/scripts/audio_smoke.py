"""Audio Input Layer 手动验证封装。

交互式选择硬件输入或音频文件，逐块打印 AudioChunk 输出。
手动测试工具，不被 backend import。

运行（用 cactus venv 的 Python）：
    /opt/homebrew/Cellar/cactus/1.14_1/libexec/venv/bin/python scripts/audio_smoke.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sounddevice as sd  # noqa: E402

from backend.audio.device_source import DeviceError, DeviceSource  # noqa: E402
from backend.audio.file_source import FileSource  # noqa: E402
from backend.audio.source import AudioConfig, AudioSource  # noqa: E402


def _list_input_devices() -> list[int]:
    """打印所有输入设备，返回其索引列表。"""
    indices = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            indices.append(i)
            print(
                f"  [{i:2d}] {dev['name']}  "
                f"(声道 {dev['max_input_channels']}, "
                f"{int(dev['default_samplerate'])} Hz)"
            )
    return indices


def _choose_device() -> int:
    print("可用输入设备：")
    indices = _list_input_devices()
    if not indices:
        print("没有可用的输入设备。")
        sys.exit(1)
    while True:
        raw = input("输入设备索引数字: ").strip()
        try:
            idx = int(raw)
        except ValueError:
            print("请输入数字。")
            continue
        if idx in indices:
            return idx
        print(f"索引 {idx} 不是有效输入设备，从上面列表里选。")


def _choose_file() -> str:
    while True:
        path = Path(input("音频文件路径: ").strip()).expanduser()
        if path.is_file():
            return str(path)
        print(f"找不到文件: {path}")


def _print_chunks(src: AudioSource) -> None:
    """迭代源，逐块打印；结束时打印累计帧数。"""
    total = 0
    try:
        for chunk in src:
            peaks = [int(abs(c).max()) for c in chunk.channels]
            total += chunk.n_frames
            print(
                f"seq={chunk.seq:3d}  声道={len(chunk.channels)}  "
                f"n_frames={chunk.n_frames:4d}  start_frame={chunk.start_frame:8d}  "
                f"sr={chunk.sample_rate}  peak={peaks}"
            )
    finally:
        print(f"--- 共 {total} 帧，换算时长 {total / 16000:.3f}s ---")


def main() -> None:
    print("Audio Input Layer 手动验证")
    print("  1) 硬件输入")
    print("  2) 音频文件")
    choice = input("选择输入方式 [1/2]: ").strip()

    config = AudioConfig()
    if choice == "1":
        device = _choose_device()
        print(f"\n打开设备 [{device}]，Ctrl+C 停止采集。\n")
        with DeviceSource(device, config) as src:
            _print_chunks(src)
    elif choice == "2":
        path = _choose_file()
        print(f"\n处理文件 {path}\n")
        with FileSource(path, config) as src:
            _print_chunks(src)
    else:
        print("无效选择。")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已退出。")
    except (DeviceError, OSError) as exc:
        print(f"\n错误: {exc}")
        sys.exit(1)
