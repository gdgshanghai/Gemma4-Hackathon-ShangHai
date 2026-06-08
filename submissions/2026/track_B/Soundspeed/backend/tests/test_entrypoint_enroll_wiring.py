"""take-start handler 顺序：必须先 abort enroll 再 start live ASR（Capture 优先，防设备抢占）。"""
from backend.api.entrypoint import _make_take_start_handler


class _FakeEnrollRecorder:
    def __init__(self, log): self._log = log
    def abort(self): self._log.append("abort")


class _FakeLiveAsr:
    def __init__(self, log): self._log = log
    def start(self): self._log.append("start")


def test_take_start_aborts_enroll_before_session_start():
    # Capture 优先：先 abort enroll（释放设备）再 start live ASR
    log: list[str] = []
    handler = _make_take_start_handler(_FakeLiveAsr(log), _FakeEnrollRecorder(log))
    handler(None)
    assert log == ["abort", "start"]


def test_take_start_handler_without_recorder():
    # 无 recorder 时只 start live ASR，不崩
    log: list[str] = []
    handler = _make_take_start_handler(_FakeLiveAsr(log), None)
    handler(None)
    assert log == ["start"]
