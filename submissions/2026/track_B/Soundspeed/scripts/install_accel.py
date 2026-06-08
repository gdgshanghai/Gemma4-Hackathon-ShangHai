#!/usr/bin/env python3
"""按硬件兜底装编译型 GPU 加速包（0.A.1 §7）。

`uv sync` 之后跑 `python scripts/install_accel.py`，读 detect_device 结果，
按平台/硬件装声明式表达不了的 GPU 变体（llama-cpp-python / pywhispercpp 的
CUDA/Metal 后端）。职责单一：只处理纯声明装不对的那两个包。

设计（spec §7）：
- 决策抽成纯函数 plan_accel(device_info) -> list[dict]（可单测，不真装包）。
- 实际 subprocess 调用、装后 assert GPU offload 在 main() 里（不在单测覆盖）。

平台分支（注意对齐 detect_device.collect() 的真实输出）：
- macOS arm64（os.system == "Darwin" and machine 含 arm64）：基本 no-op，
  llama-cpp / pywhispercpp 的 PyPI wheel 已带 Metal。仅 verify GPU offload。
- Windows + NVIDIA 检测到：按 compute_cap 分支
  - < 12.0（含 3060Ti 的 8.6，Ampere）：llama-cpp 走官方 cu124 wheel 直链；
    pywhispercpp 源码编译（--no-binary + GGML_CUDA）。
  - >= 12.0（Blackwell，future）：llama-cpp 源码编译 / 第三方。
- 无 GPU：留 CPU，不装 GPU 变体。

关键纪律（spec §7）：重装一律 --reinstall --no-deps（否则 uv 重解析把刚装的
换回 PyPI 默认 wheel）；用确切 wheel 直链（绕开 first-index 静默装 CPU sdist
的坑）；装完 assert GPU offload，把静默退化变硬失败。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_DEVICE_JSON = REPO_ROOT / "device-detected.json"

# llama-cpp-python 官方 cu124 wheel index（Ampere sm_86 原生支持，spec §5.4）。
_LLAMA_CU124_INDEX = "https://abetlen.github.io/llama-cpp-python/whl/cu124"

# Blackwell（sm_120）分界：compute_cap >= 此值走源码编译/第三方（future）。
_BLACKWELL_CAP = 12.0

# verify 检查标识：装后 assert llama_supports_gpu_offload() == True。
_VERIFY_LLAMA_GPU = "llama_gpu_offload"


def _is_mac_arm64(device_info: dict) -> bool:
    """对齐 detect_apple_metal：Darwin 且 machine 含 arm64。"""
    osd = device_info.get("os") or {}
    system = (osd.get("system") or "").strip()
    machine = (osd.get("machine") or "").lower()
    return system == "Darwin" and "arm64" in machine


def _is_windows(device_info: dict) -> bool:
    osd = device_info.get("os") or {}
    return (osd.get("system") or "").strip() == "Windows"


def _parse_compute_cap(nvidia: dict) -> float | None:
    """compute_cap 是字符串（"8.6"）；按数值解析，缺/坏返回 None。

    必须 float() 后再比 12.0：字符串比较有陷阱（"8.6" >= "12.0" 字典序为 True）。
    """
    raw = nvidia.get("compute_cap")
    if raw is None:
        return None
    try:
        return float(str(raw).strip())
    except (ValueError, TypeError):
        return None


def _verify_llama_action() -> dict:
    return {"action": "verify", "check": _VERIFY_LLAMA_GPU}


def _llama_cu124_wheel_action() -> dict:
    """llama-cpp-python 官方 cu124 wheel 直链（--reinstall --no-deps）。"""
    return {
        "action": "install",
        "package": "llama-cpp-python",
        "kind": "wheel-index",
        "cmd": [
            "uv",
            "pip",
            "install",
            "--reinstall",
            "--no-deps",
            "llama-cpp-python",
            "--index-url",
            _LLAMA_CU124_INDEX,
        ],
    }


def _llama_source_compile_action() -> dict:
    """llama-cpp-python 源码编译 CUDA（Blackwell/future 分支）。

    刻意不带 --no-build-isolation（与下面 pywhispercpp 不同）：llama-cpp-python
    用 scikit-build-core 构建，CMAKE_ARGS 在隔离构建子进程里照样读到，无需关隔离。
    与 docs/2026-06-02-windows-llama-cpp-runbook.md §3 自编译命令一致（那条
    `pip install llama-cpp-python --no-binary llama-cpp-python` 也不带）。加上反而
    要求 scikit-build-core/cmake/ninja 预装在当前环境，更脆。
    """
    return {
        "action": "install",
        "package": "llama-cpp-python",
        "kind": "source-compile",
        "env": {"CMAKE_ARGS": "-DGGML_CUDA=on", "FORCE_CMAKE": "1"},
        "cmd": [
            "uv",
            "pip",
            "install",
            "--reinstall",
            "--no-deps",
            "--no-binary",
            "llama-cpp-python",
            "llama-cpp-python>=0.3,<0.4",
        ],
    }


def _pywhispercpp_source_compile_action() -> dict:
    """pywhispercpp 源码编译 CUDA。

    §5.5 关键坑：GGML_CUDA=1 装会静默抓 CPU wheel 忽略 flag，必须 --no-binary
    才真编译。§7 字面命令带 --no-build-isolation --no-cache-dir 但漏了
    --no-binary；这里以 §5.5 + 任务步骤 2 为准补上 --no-binary（见返回里的
    deviation 说明）。

    保留 --no-build-isolation（与 llama 分支刻意不同）：沿用 spec §7 字面命令。
    pywhispercpp 1.5.0 的 Windows CUDA 源码编译路径尚未实测，不擅自删此 flag。
    两个包命令不对称是有意保留的，不是疏漏。
    """
    return {
        "action": "install",
        "package": "pywhispercpp",
        "kind": "source-compile",
        "env": {
            "CMAKE_ARGS": "-DGGML_CUDA=on",
            "GGML_CUDA": "1",
            "FORCE_CMAKE": "1",
        },
        "cmd": [
            "uv",
            "pip",
            "install",
            "--reinstall",
            "--no-deps",
            "--no-build-isolation",
            "--no-cache-dir",
            "--no-binary",
            "pywhispercpp",
            "pywhispercpp==1.5.0",
        ],
    }


def plan_accel(device_info: dict) -> list[dict]:
    """纯决策：读 detect 结果 dict，返回要执行的动作计划（不真装包）。

    动作项形态：
    - install：{"action":"install", "package":..., "kind":"wheel-index"|"source-compile",
       "cmd":[...], "env":{...}?}
    - verify ：{"action":"verify", "check":"llama_gpu_offload"}
    """
    plan: list[dict] = []

    # macOS arm64：no-op，PyPI wheel 已带 Metal；仅 verify。
    if _is_mac_arm64(device_info):
        plan.append(_verify_llama_action())
        return plan

    # Windows + NVIDIA 检测到：按 compute_cap 分流。
    if _is_windows(device_info):
        nvidia = device_info.get("nvidia_gpu") or {}
        if nvidia.get("detected"):
            cap = _parse_compute_cap(nvidia)
            # 缺 compute_cap（老驱动）保守按 Ampere wheel-index 兜底（已知能跑）。
            if cap is not None and cap >= _BLACKWELL_CAP:
                plan.append(_llama_source_compile_action())  # Blackwell/future
            else:
                plan.append(_llama_cu124_wheel_action())  # Ampere cu124 wheel
            plan.append(_pywhispercpp_source_compile_action())
            plan.append(_verify_llama_action())
            return plan
        # Windows 无 GPU：留 CPU，不装 GPU 变体。
        return plan

    # 其它平台（非目标，spec 非目标含 Intel Mac / Linux）：留 CPU。
    return plan


# --------- 以下为 main() 实际执行部分，不在单测覆盖（spec §7）---------


def _load_device_info(path: Path) -> dict:
    """读 device-detected.json；无则调 detect_device.collect()。"""
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(
                f"[警告] 解析 {path} 失败（{type(exc).__name__}: {exc}），"
                f"改跑 detect_device.collect()",
                file=sys.stderr,
            )
    # 复用 0.A.0 探测脚本（同目录），不重复实现硬件探测。
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import detect_device  # noqa: PLC0415

    return detect_device.collect()


def _run_action(action: dict, *, dry_run: bool) -> None:
    """执行单个 install 动作（subprocess 调 uv pip install）。"""
    cmd = action["cmd"]
    env_extra = action.get("env") or {}
    pretty = " ".join(cmd)
    if env_extra:
        pretty = " ".join(f"{k}={v}" for k, v in env_extra.items()) + " " + pretty
    print(f"[install_accel] {action['package']}（{action['kind']}）：{pretty}")
    if dry_run:
        print("[install_accel]   (dry-run，跳过执行)")
        return

    import os  # noqa: PLC0415

    env = os.environ.copy()
    env.update(env_extra)
    proc = subprocess.run(cmd, env=env, check=False)
    if proc.returncode != 0:
        # 失败硬报错，不静默回落 CPU（spec §7）。
        raise SystemExit(
            f"[install_accel] {action['package']} 安装失败（exit {proc.returncode}）"
        )


def _verify(check: str, *, dry_run: bool) -> None:
    """装后 assert GPU offload，把静默退化变硬失败（spec §7）。"""
    if check != _VERIFY_LLAMA_GPU:
        print(f"[install_accel] 未知 verify 检查：{check}，跳过")
        return
    if dry_run:
        print("[install_accel] verify llama_supports_gpu_offload (dry-run，跳过)")
        return
    # 懒导入：模块本身不依赖 llama_cpp（单测可在未装时导入本模块）。
    from llama_cpp import llama_supports_gpu_offload  # noqa: PLC0415

    ok = bool(llama_supports_gpu_offload())
    print(f"[install_accel] verify llama_supports_gpu_offload() == {ok}")
    assert ok is True, (
        "llama_supports_gpu_offload() 返回 False——装的是 CPU 版，"
        "GPU 加速未生效（spec §7：静默退化应为硬失败）"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="按硬件兜底装编译型 GPU 加速包（0.A.1 §7）。"
    )
    parser.add_argument(
        "--device-json",
        default=str(_DEVICE_JSON),
        help="device-detected.json 路径（无则现跑 detect_device.collect()）。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印计划，不真装、不 verify。",
    )
    args = parser.parse_args(argv)

    device_info = _load_device_info(Path(args.device_json))
    plan = plan_accel(device_info)

    if not plan:
        print("[install_accel] 当前硬件无需额外装 GPU 变体（CPU / 非目标平台）。")
        return 0

    for action in plan:
        kind = action.get("action")
        if kind == "install":
            _run_action(action, dry_run=args.dry_run)
        elif kind == "verify":
            _verify(action["check"], dry_run=args.dry_run)

    print("[install_accel] 完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
