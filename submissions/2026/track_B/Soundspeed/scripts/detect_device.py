#!/usr/bin/env python3
"""新设备硬件探测脚本（Notion 0.A.0 跨平台安装 onboarding）。

用途：在一台全新的 Windows / macOS / Linux 机器上，给出一份机器环境快照
（OS、Python、NVIDIA GPU、CUDA、Apple Metal、llama-cpp-python、模型权重），
供安装决策（装哪个 wheel、要不要自编译、要不要降参）使用，也可作为 0.C.1
spike 的验证证据附 PR。

硬约束：
- 只用 Python 标准库（platform / sys / os / subprocess / shutil / json /
  datetime / argparse / importlib.metadata / re / pathlib），不 import 任何
  第三方包。原因：这个脚本要在「还没装依赖的全新 venv」里就能跑，第三方包
  那时还不存在。
- 全程容错：每个探测项各自 try/except，任何一项失败都不让脚本崩，失败就在
  该字段记 {"ok": false, "error": "<原因>"} 或 null。

结果默认写到仓库根的 device-detected.json（--output 可改），同时往 stdout
打一份中文人读摘要。device-detected.json 每台机不同，已被 .gitignore 忽略。

跑法（装依赖前后都能跑）：
    python scripts/detect_device.py
    python scripts/detect_device.py --output /tmp/dev.json
"""

from __future__ import annotations

import argparse
import datetime
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1

# 仓库根：本文件在 <repo>/scripts/detect_device.py，向上两级即仓库根。
# 用 __file__ 而非 cwd，保证脚本无论从哪个目录调用，默认输出路径和模型默认
# 路径都锚定在仓库根。
REPO_ROOT = Path(__file__).resolve().parent.parent

# 与 backend/llm/client.py 的 _DEFAULT_MODEL_PATH 对应（相对仓库根）。
_DEFAULT_MODEL_REL = "models/gemma-4-E4B-it-Q4_K_M.gguf"

# subprocess 超时（秒），避免某个工具卡死拖垮整个脚本。
_SUBPROCESS_TIMEOUT = 15


def _run(cmd: list[str]) -> str | None:
    """跑一个外部命令，返回 stdout 文本；任何失败返回 None（不抛）。

    捕获 FileNotFoundError / TimeoutExpired / OSError 等所有情况，
    非零退出码也视为失败返回 None。
    """
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError, ValueError):
        return None
    if proc.returncode != 0:
        # 有些工具（如无参 nvidia-smi）正常时 returncode=0；非零一律当失败。
        return None
    return proc.stdout


def detect_os() -> dict:
    """OS 信息（platform 模块）。"""
    try:
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def detect_python() -> dict:
    """Python 解释器信息。in_venv = sys.prefix != sys.base_prefix。"""
    try:
        return {
            "version": platform.python_version(),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
            "in_venv": sys.prefix != sys.base_prefix,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def detect_nvidia() -> dict:
    """NVIDIA GPU 信息，靠 nvidia-smi。

    - nvidia-smi 不存在（shutil.which 为 None）→ detected=false。
    - 查询版：nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap
      --format=csv,noheader,nounits 解析 name / memory_total_mb / driver_version /
      compute_cap。compute_cap 即 GPU 的 compute capability（形如 "8.6"），对应
      sm 架构（sm86），选 dougeeai 等按架构分的 wheel 时要用。老驱动可能不支持
      该字段，解析按列数防越界，缺则保持 None。
    - CUDA driver 版本：另跑无参 nvidia-smi，正则提 "CUDA Version: X.Y"。
    """
    result = {
        "detected": False,
        "name": None,
        "memory_total_mb": None,
        "driver_version": None,
        "compute_cap": None,
        "cuda_version_driver": None,
        "error": None,
    }
    try:
        if shutil.which("nvidia-smi") is None:
            result["error"] = "nvidia-smi 未找到（无 NVIDIA 驱动或不在 PATH）"
            return result

        query = _run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version,compute_cap",
                "--format=csv,noheader,nounits",
            ]
        )
        if query:
            # 多卡时取第一行
            first = query.strip().splitlines()[0]
            parts = [p.strip() for p in first.split(",")]
            if len(parts) >= 3:
                result["detected"] = True
                result["name"] = parts[0] or None
                try:
                    result["memory_total_mb"] = int(float(parts[1]))
                except (ValueError, TypeError):
                    result["memory_total_mb"] = None
                result["driver_version"] = parts[2] or None
                # 第 4 列 compute_cap，老驱动不支持该字段时不会有这一列，按列数防越界
                if len(parts) >= 4:
                    result["compute_cap"] = parts[3] or None

        # CUDA driver 版本来自无参 nvidia-smi 头部
        plain = _run(["nvidia-smi"])
        if plain:
            m = re.search(r"CUDA Version:\s*([\d.]+)", plain)
            if m:
                result["cuda_version_driver"] = m.group(1)

        if not result["detected"] and result["error"] is None:
            result["error"] = "nvidia-smi 存在但查询失败或无 GPU"
        return result
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def detect_cuda_toolkit() -> dict:
    """CUDA Toolkit（编译期），靠 nvcc --version 解析 "release X.Y"。"""
    result = {"nvcc_found": False, "version": None, "error": None}
    try:
        if shutil.which("nvcc") is None:
            result["error"] = "nvcc 未找到（未装 CUDA Toolkit 或不在 PATH）"
            return result
        out = _run(["nvcc", "--version"])
        if out:
            result["nvcc_found"] = True
            m = re.search(r"release\s+([\d.]+)", out)
            if m:
                result["version"] = m.group(1)
        else:
            result["error"] = "nvcc 存在但 --version 执行失败"
        return result
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def detect_apple_metal() -> dict:
    """Apple Metal（仅 Darwin 有意义）。

    Darwin 且 machine 含 arm64 视为 Metal 可用；chip 从
    sysctl -n machdep.cpu.brand_string 拿（容错）。
    """
    result = {"detected": False, "chip": None, "error": None}
    try:
        if platform.system() != "Darwin":
            result["error"] = "非 Darwin 平台，Apple Metal 不适用"
            return result
        if "arm64" in platform.machine().lower():
            result["detected"] = True
        chip = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        if chip:
            result["chip"] = chip.strip() or None
        if not result["detected"]:
            result["error"] = "Darwin 但非 arm64（Intel Mac 无 Apple GPU Metal 卸载）"
        return result
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def detect_xcode_clt() -> dict:
    """Xcode Command Line Tools（仅 Darwin 有意义，spec §8 编译前提门控）。

    llama-cpp-python / pywhispercpp 的 mac 源码编译（Metal）需要 Xcode CLT。
    `xcode-select -p` 返回安装路径且退出码 0 即视为已装；非零退出码或命令
    不存在（_run 返 None）视为未装。非 Darwin 平台标注不适用。
    """
    result = {"installed": False, "path": None, "error": None}
    try:
        if platform.system() != "Darwin":
            result["error"] = "非 Darwin 平台，Xcode CLT 不适用"
            return result
        out = _run(["xcode-select", "-p"])
        if out and out.strip():
            result["installed"] = True
            result["path"] = out.strip()
        else:
            result["error"] = "xcode-select -p 失败（未装 Xcode CLT 或不在 PATH）"
        return result
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def detect_llama_cpp() -> dict:
    """llama-cpp-python 安装与 GPU 卸载支持情况。

    - importlib.metadata.version("llama-cpp-python") 拿版本
      （PackageNotFoundError → installed=false）。
    - try import llama_cpp 设 import_ok。
    - try from llama_cpp import llama_supports_gpu_offload; llama_supports_gpu_offload()
      设 gpu_offload_supported（函数不存在/异常 → null）。
    """
    result = {
        "installed": False,
        "version": None,
        "import_ok": False,
        "gpu_offload_supported": None,
        "error": None,
    }
    try:
        try:
            result["version"] = importlib.metadata.version("llama-cpp-python")
            result["installed"] = True
        except importlib.metadata.PackageNotFoundError:
            result["error"] = "llama-cpp-python 未安装（PackageNotFoundError）"
            return result

        try:
            import llama_cpp  # type: ignore[import]  # noqa: F401,PLC0415

            result["import_ok"] = True
            try:
                from llama_cpp import (  # type: ignore[import]  # noqa: PLC0415
                    llama_supports_gpu_offload,
                )

                result["gpu_offload_supported"] = bool(llama_supports_gpu_offload())
            except Exception:  # noqa: BLE001
                # 函数不存在或调用异常 → 保持 null
                result["gpu_offload_supported"] = None
        except Exception as exc:  # noqa: BLE001
            # 已装但 import 失败（典型：Windows DLL load failed 找不到 CUDA 运行时）
            result["import_ok"] = False
            result["error"] = f"import 失败: {type(exc).__name__}: {exc}"
        return result
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def _path_info(path: str | None) -> tuple[bool, int | None]:
    """返回 (exists, size_bytes)，容错。"""
    if not path:
        return False, None
    try:
        if os.path.exists(path):
            try:
                return True, os.path.getsize(path)
            except OSError:
                return True, None
        return False, None
    except Exception:  # noqa: BLE001
        return False, None


def detect_model() -> dict:
    """模型权重探测（纯 os.environ + os.path，绝不碰 huggingface_hub）。

    刻意保持「笨」：service.py 的 resolve_model_path 会 import huggingface_hub
    探 HF cache，那会违反「只用标准库」且在全新 venv 里崩。这里只看 env 路径
    和仓库默认路径是否存在。
    """
    result = {
        "gemma_model_path_env": None,
        "env_path_exists": False,
        "default_path": None,
        "default_path_exists": False,
        "size_bytes": None,
    }
    try:
        env_path = os.environ.get("GEMMA_MODEL_PATH")
        result["gemma_model_path_env"] = env_path
        env_exists, env_size = _path_info(env_path)
        result["env_path_exists"] = env_exists

        default_path = str(REPO_ROOT / _DEFAULT_MODEL_REL)
        result["default_path"] = default_path
        def_exists, def_size = _path_info(default_path)
        result["default_path_exists"] = def_exists

        # size_bytes 优先取实际存在的那一个（env 优先，回退默认）
        if env_exists and env_size is not None:
            result["size_bytes"] = env_size
        elif def_exists and def_size is not None:
            result["size_bytes"] = def_size
        return result
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def collect() -> dict:
    """汇总所有探测项为一个 dict（每项独立容错，整体不崩）。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.datetime.now().isoformat(),
        "os": detect_os(),
        "python": detect_python(),
        "nvidia_gpu": detect_nvidia(),
        "cuda_toolkit": detect_cuda_toolkit(),
        "apple_metal": detect_apple_metal(),
        "xcode_clt": detect_xcode_clt(),
        "llama_cpp_python": detect_llama_cpp(),
        "model": detect_model(),
    }


def _fmt_size(n: int | None) -> str:
    if not n:
        return "—"
    return f"{n / (1024 ** 3):.2f} GB"


def print_summary(data: dict, out_path: Path) -> None:
    """往 stdout 打中文人读摘要。"""
    osd = data.get("os", {})
    py = data.get("python", {})
    gpu = data.get("nvidia_gpu", {})
    cuda = data.get("cuda_toolkit", {})
    metal = data.get("apple_metal", {})
    clt = data.get("xcode_clt", {})
    llama = data.get("llama_cpp_python", {})
    model = data.get("model", {})

    lines = []
    lines.append("=" * 56)
    lines.append("Soundspeed 设备探测（0.A.0）")
    lines.append("=" * 56)
    lines.append(f"时间      ：{data.get('timestamp')}")
    lines.append(
        f"系统      ：{osd.get('system')} {osd.get('release')}（{osd.get('machine')}）"
    )
    lines.append(
        f"Python    ：{py.get('version')} {py.get('implementation')}"
        f"，venv={'是' if py.get('in_venv') else '否'}"
    )

    if gpu.get("detected"):
        lines.append(
            f"NVIDIA GPU：{gpu.get('name')}，显存 {gpu.get('memory_total_mb')} MB"
            f"，驱动 {gpu.get('driver_version')}"
            f"，compute_cap {gpu.get('compute_cap')}"
            f"，CUDA(driver) {gpu.get('cuda_version_driver')}"
        )
    else:
        lines.append(f"NVIDIA GPU：未检测到（{gpu.get('error')}）")

    if cuda.get("nvcc_found"):
        lines.append(f"CUDA 工具链：nvcc {cuda.get('version')}")
    else:
        lines.append(f"CUDA 工具链：未找到 nvcc（{cuda.get('error')}）")

    if metal.get("detected"):
        lines.append(f"Apple Metal：可用（{metal.get('chip')}）")
    else:
        lines.append(f"Apple Metal：不可用（{metal.get('error')}）")

    if clt.get("installed"):
        lines.append(f"Xcode CLT ：已装（{clt.get('path')}）")
    elif osd.get("system") != "Darwin":
        lines.append(f"Xcode CLT ：不适用（{clt.get('error')}）")
    else:
        lines.append(f"Xcode CLT ：未装（{clt.get('error')}）")

    if llama.get("installed"):
        offload = llama.get("gpu_offload_supported")
        offload_str = "未知" if offload is None else ("支持" if offload else "不支持")
        lines.append(
            f"llama-cpp ：已装 {llama.get('version')}"
            f"，import={'成功' if llama.get('import_ok') else '失败'}"
            f"，GPU 卸载={offload_str}"
        )
        if not llama.get("import_ok") and llama.get("error"):
            lines.append(f"            └ {llama.get('error')}")
    else:
        lines.append(f"llama-cpp ：未安装（{llama.get('error')}）")

    lines.append("模型权重  ：")
    lines.append(
        f"  env GEMMA_MODEL_PATH={model.get('gemma_model_path_env')}"
        f"（存在={'是' if model.get('env_path_exists') else '否'}）"
    )
    lines.append(
        f"  默认 {model.get('default_path')}"
        f"（存在={'是' if model.get('default_path_exists') else '否'}）"
    )
    lines.append(f"  大小 {_fmt_size(model.get('size_bytes'))}")

    lines.append("-" * 56)
    lines.append(f"结果已写入：{out_path}")
    lines.append("=" * 56)

    print("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Soundspeed 新设备硬件探测（0.A.0），只用标准库，装依赖前后都能跑。"
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(REPO_ROOT / "device-detected.json"),
        help="结果 JSON 输出路径（默认仓库根 device-detected.json）。",
    )
    args = parser.parse_args(argv)

    data = collect()

    out_path = Path(args.output)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        # 写文件失败也不崩，至少把 JSON 打到 stdout
        print(f"[警告] 写入 {out_path} 失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 1

    print_summary(data, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
