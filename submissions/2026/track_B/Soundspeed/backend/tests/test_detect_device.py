"""scripts/detect_device.py 探测项测试。

只测纯标准库探测逻辑，全程 monkeypatch，不依赖真实环境（不真跑
xcode-select，也不依赖当前机器是不是 mac）。
"""
import scripts.detect_device as detect_device


# --- detect_xcode_clt：mac 上 xcode-select -p 的探测（spec §8） ---


def test_xcode_clt_installed(monkeypatch):
    """Darwin + xcode-select -p 返回路径（退出码 0）=> installed True + path。"""
    monkeypatch.setattr(detect_device.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        detect_device,
        "_run",
        lambda cmd: "/Library/Developer/CommandLineTools\n",
    )

    result = detect_device.detect_xcode_clt()

    assert result["installed"] is True
    assert result["path"] == "/Library/Developer/CommandLineTools"
    assert result["error"] is None


def test_xcode_clt_not_installed(monkeypatch):
    """Darwin 但 xcode-select -p 失败（非零退出码 / 命令缺失，_run 返 None）
    => installed False + path None + 有 error。"""
    monkeypatch.setattr(detect_device.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(detect_device, "_run", lambda cmd: None)

    result = detect_device.detect_xcode_clt()

    assert result["installed"] is False
    assert result["path"] is None
    assert result["error"] is not None


def test_xcode_clt_nonzero_exit_via_subprocess(monkeypatch):
    """忠实测 spec「退出码 0 才算装好」：subprocess.run 返非零退出码时，
    _run 返 None，detect_xcode_clt 判定未安装。"""
    monkeypatch.setattr(detect_device.platform, "system", lambda: "Darwin")

    class _FakeProc:
        returncode = 2
        stdout = "xcode-select: error: ..."

    monkeypatch.setattr(
        detect_device.subprocess, "run", lambda *a, **k: _FakeProc()
    )

    result = detect_device.detect_xcode_clt()

    assert result["installed"] is False
    assert result["path"] is None


def test_xcode_clt_non_darwin(monkeypatch):
    """非 Darwin 平台 => installed False，error 标注不适用（含 'Darwin'）。"""
    monkeypatch.setattr(detect_device.platform, "system", lambda: "Windows")

    result = detect_device.detect_xcode_clt()

    assert result["installed"] is False
    assert result["path"] is None
    assert "Darwin" in result["error"]


# --- collect()：新探测项已接线 ---


def test_collect_includes_xcode_clt():
    """collect() 汇总里有 'xcode_clt' 键。"""
    data = detect_device.collect()
    assert "xcode_clt" in data
