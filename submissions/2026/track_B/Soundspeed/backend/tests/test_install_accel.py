"""测试 scripts/install_accel.py 的核心决策逻辑（0.A.1 §7）。

只测纯函数 plan_accel(device_info) -> list[dict]：给定 mock 的 detect 结果
dict，断言返回的「动作计划」语义正确。实际 subprocess 调用与 GPU offload
assert 在 main() 里，不在单测覆盖范围（见 spec §7「main 里实际执行部分不在
单测覆盖」）。

注意：device_info 的形态必须严格对齐 detect_device.collect() 的真实输出——
os.system 是 platform.system() 的值（"Darwin" / "Windows"，不是 sys.platform
的 "darwin" / "win32"），compute_cap 是字符串（"8.6"）。
"""
from __future__ import annotations

from scripts.install_accel import plan_accel


def _mac_arm64() -> dict:
    """境熙 mac：Darwin arm64，无 NVIDIA。"""
    return {
        "os": {"system": "Darwin", "machine": "arm64"},
        "nvidia_gpu": {"detected": False, "compute_cap": None},
    }


def _win_nvidia(compute_cap: str | None) -> dict:
    """经纬 Windows + NVIDIA，compute_cap 可调。"""
    return {
        "os": {"system": "Windows", "machine": "AMD64"},
        "nvidia_gpu": {"detected": True, "compute_cap": compute_cap},
    }


def _win_no_gpu() -> dict:
    """Windows 但无 NVIDIA GPU。"""
    return {
        "os": {"system": "Windows", "machine": "AMD64"},
        "nvidia_gpu": {"detected": False, "compute_cap": None},
    }


def _packages(plan: list[dict]) -> set[str]:
    return {a["package"] for a in plan if "package" in a}


def _action_for(plan: list[dict], package: str) -> dict | None:
    for a in plan:
        if a.get("package") == package:
            return a
    return None


# ---------- darwin + arm64 => no-op（仅 verify，不装包）----------


def test_mac_arm64_does_not_install_anything():
    plan = plan_accel(_mac_arm64())
    # mac 上 llama-cpp / pywhispercpp 的 PyPI wheel 已带 Metal，不需要重装。
    install_actions = [a for a in plan if a.get("action") == "install"]
    assert install_actions == []


def test_mac_arm64_has_verify_only():
    plan = plan_accel(_mac_arm64())
    # spec §7：mac 可选 assert llama_supports_gpu_offload() == True。
    verify_actions = [a for a in plan if a.get("action") == "verify"]
    assert verify_actions, "mac 分支应包含一个 verify 动作"
    assert any(a.get("check") == "llama_gpu_offload" for a in verify_actions)


# ---------- win32 + nvidia + compute_cap < 12.0 (Ampere 3060Ti) ----------


def test_win_ampere_llama_cpp_uses_cu124_wheel_index():
    plan = plan_accel(_win_nvidia("8.6"))
    llama = _action_for(plan, "llama-cpp-python")
    assert llama is not None, "Windows+NVIDIA 应规划 llama-cpp-python 动作"
    assert llama["action"] == "install"
    # cu124 wheel 直链（Ampere 原生支持）
    assert llama["kind"] == "wheel-index"
    cmd = " ".join(llama["cmd"])
    assert "https://abetlen.github.io/llama-cpp-python/whl/cu124" in cmd
    # 关键纪律：--reinstall --no-deps（否则 uv 重解析换回 CPU wheel）
    assert "--reinstall" in llama["cmd"]
    assert "--no-deps" in llama["cmd"]


def test_win_ampere_pywhispercpp_source_compile_no_binary():
    plan = plan_accel(_win_nvidia("8.6"))
    whisper = _action_for(plan, "pywhispercpp")
    assert whisper is not None, "Windows+NVIDIA 应规划 pywhispercpp 动作"
    assert whisper["action"] == "install"
    assert whisper["kind"] == "source-compile"
    # §5.5 关键坑：必须 --no-binary 才真编译，否则静默抓 CPU wheel
    assert "--no-binary" in whisper["cmd"]
    cmd = " ".join(whisper["cmd"])
    assert "pywhispercpp" in cmd
    # 编译要带 GGML_CUDA（在 env 或 cmd 里）
    blob = cmd + " " + " ".join(f"{k}={v}" for k, v in (whisper.get("env") or {}).items())
    assert "GGML_CUDA" in blob


def test_win_ampere_llama_has_gpu_verify():
    plan = plan_accel(_win_nvidia("8.6"))
    # 装后要 assert GPU offload，把静默退化变硬失败
    assert any(
        a.get("action") == "verify" and a.get("check") == "llama_gpu_offload"
        for a in plan
    )


# ---------- win32 + nvidia + compute_cap >= 12.0 (Blackwell, future) ----------


def test_win_blackwell_llama_cpp_source_compile_future_branch():
    plan = plan_accel(_win_nvidia("12.0"))
    llama = _action_for(plan, "llama-cpp-python")
    assert llama is not None
    # Blackwell：官方无 cu12x wheel → 源码编译 / 第三方（future 分支）
    assert llama["kind"] == "source-compile"


def test_compute_cap_compared_numerically_not_lexically():
    # 字符串比较陷阱："8.6" >= "12.0" 在字典序下为 True（'8' > '1'）。
    # 8.6 必须走 wheel-index（Ampere），不能误入 source-compile（Blackwell）。
    plan = plan_accel(_win_nvidia("8.6"))
    llama = _action_for(plan, "llama-cpp-python")
    assert llama["kind"] == "wheel-index"


# ---------- 无 GPU => 留 CPU（不装 GPU 变体）----------


def test_win_no_gpu_leaves_cpu():
    plan = plan_accel(_win_no_gpu())
    install_actions = [a for a in plan if a.get("action") == "install"]
    assert install_actions == [], "无 GPU 不应规划任何 GPU 变体安装"


def test_mac_no_gpu_branch_is_mac_not_cpu_fallthrough():
    # mac 无 NVIDIA 但有 Metal，应走 mac 分支（verify），不是「无 GPU 留 CPU」。
    plan = plan_accel(_mac_arm64())
    assert any(a.get("action") == "verify" for a in plan)


# ---------- compute_cap 缺失（老驱动）不崩 ----------


def test_win_nvidia_missing_compute_cap_does_not_crash():
    # compute_cap 为 None（老驱动不报该字段），plan_accel 不应抛异常。
    plan = plan_accel(_win_nvidia(None))
    assert isinstance(plan, list)
    # 缺 compute_cap 时默认按已知能跑的 Ampere wheel-index 兜底（保守、可跑）。
    llama = _action_for(plan, "llama-cpp-python")
    assert llama is not None
    assert llama["kind"] == "wheel-index"
