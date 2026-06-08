"""speakers 路由测试（切片 4）：CRUD + enroll（注入假 diarization_engine）。

create_app 不含 speakers 路由（由 entrypoint.build_app 挂载），测试里手动 include +
设 app.state.diarization_engine（None 或 fake），与生产接线等价。
"""
from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.routes.speakers import router as speakers_router
from backend.core.orchestrator import create_orchestrator
from backend.db.dal import DAL
from backend.diarization.enroll_recorder import CaptureActiveError, EnrollBusyError

_TOKEN = "test-admin-token"
_HEADERS = {"Authorization": f"Bearer {_TOKEN}"}


class _FakeEngine:
    """假 diarization engine：extract_embedding 返回固定向量。"""

    def __init__(self, dim: int = 4):
        self._dim = dim
        self.calls: list[int] = []

    def extract_embedding(self, pcm: np.ndarray):
        self.calls.append(len(pcm))
        return np.ones(self._dim, dtype=np.float32)


class _FakeRecorder:
    """假录音器：start/stop/abort 记账；stop 返回预置 pcm。"""

    def __init__(self, pcm: np.ndarray | None = None, capture_active: bool = False):
        self._pcm = pcm if pcm is not None else np.full(16000 * 3, 2000, dtype=np.int16)
        self._capture_active = capture_active
        self.running = False
        self.events: list[str] = []

    def start(self):
        if self._capture_active:
            raise CaptureActiveError("capture active")
        if self.running:
            raise EnrollBusyError("busy")
        self.running = True
        self.events.append("start")

    def stop(self):
        self.running = False
        self.events.append("stop")
        return self._pcm

    def abort(self):
        self.running = False
        self.events.append("abort")


def _client(tmp_dal: DAL, monkeypatch, engine=None, recorder=None) -> TestClient:
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    app = create_app(create_orchestrator(tmp_dal))
    app.include_router(speakers_router)
    app.state.diarization_engine = engine
    app.state.enroll_recorder = recorder
    return TestClient(app)


# ── CRUD ─────────────────────────────────────────────────────────────────────────


def test_create_then_get_and_list(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:
        r = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS)
        assert r.status_code == 201
        body = r.json()
        sid = body["speaker_id"]
        assert body["display_name"] == "张三"
        assert body["has_enrollment"] is False
        assert body["sample_count"] == 0

        r = c.get(f"/api/v1/speakers/{sid}", headers=_HEADERS)
        assert r.status_code == 200 and r.json()["display_name"] == "张三"

        r = c.get("/api/v1/speakers", headers=_HEADERS)
        assert [s["speaker_id"] for s in r.json()] == [sid]


def test_get_missing_404(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:
        assert c.get("/api/v1/speakers/999", headers=_HEADERS).status_code == 404


def test_patch_updates_display_name(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "说话人1"}, headers=_HEADERS).json()["speaker_id"]
        r = c.patch(f"/api/v1/speakers/{sid}", json={"display_name": "李四"}, headers=_HEADERS)
        assert r.status_code == 200 and r.json()["display_name"] == "李四"
        assert c.get(f"/api/v1/speakers/{sid}", headers=_HEADERS).json()["display_name"] == "李四"


def test_patch_missing_404(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:
        assert c.patch("/api/v1/speakers/999", json={"display_name": "x"}, headers=_HEADERS).status_code == 404


def test_delete_then_404(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        assert c.delete(f"/api/v1/speakers/{sid}", headers=_HEADERS).status_code == 204
        assert c.get(f"/api/v1/speakers/{sid}", headers=_HEADERS).status_code == 404


def test_requires_auth(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:
        assert c.get("/api/v1/speakers").status_code in (401, 403)


# ── enroll ───────────────────────────────────────────────────────────────────────


def _silent_pcm_bytes(seconds: float) -> bytes:
    return np.zeros(int(16000 * seconds), dtype=np.int16).tobytes()


def _audible_pcm_bytes(seconds: float, amp: int = 2000) -> bytes:
    # 恒定幅度方波，RMS=amp，远高于静音守卫阈值
    n = int(16000 * seconds)
    return np.full(n, amp, dtype=np.int16).tobytes()


def test_enroll_without_engine_503(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch, engine=None) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        r = c.post(
            f"/api/v1/speakers/{sid}/enroll",
            files={"file": ("a.pcm", _silent_pcm_bytes(3), "application/octet-stream")},  # 内容无关：engine=None 在 finalize 守卫之前就 503
            params={"sample_rate": 16000},
            headers=_HEADERS,
        )
        assert r.status_code == 503


def test_enroll_too_short_400(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch, engine=_FakeEngine()) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        r = c.post(
            f"/api/v1/speakers/{sid}/enroll",
            files={"file": ("a.pcm", _audible_pcm_bytes(1.0), "application/octet-stream")},  # 有声但 < 2s
            params={"sample_rate": 16000},
            headers=_HEADERS,
        )
        assert r.status_code == 400


def test_enroll_success_sets_embedding(tmp_dal: DAL, monkeypatch):
    engine = _FakeEngine()
    with _client(tmp_dal, monkeypatch, engine=engine) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        r = c.post(
            f"/api/v1/speakers/{sid}/enroll",
            files={"file": ("a.pcm", _audible_pcm_bytes(3), "application/octet-stream")},
            params={"sample_rate": 16000},
            headers=_HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["has_enrollment"] is True
        assert body["sample_count"] == 1
        assert engine.calls == [16000 * 3]


def test_enroll_silent_400(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch, engine=_FakeEngine()) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        r = c.post(
            f"/api/v1/speakers/{sid}/enroll",
            files={"file": ("a.pcm", _silent_pcm_bytes(3), "application/octet-stream")},  # 够长但静音
            params={"sample_rate": 16000},
            headers=_HEADERS,
        )
        assert r.status_code == 400


def test_enroll_empty_file_400(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch, engine=_FakeEngine()) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        r = c.post(
            f"/api/v1/speakers/{sid}/enroll",
            files={"file": ("a.pcm", b"", "application/octet-stream")},
            headers=_HEADERS,
        )
        assert r.status_code == 400


def test_enroll_missing_speaker_404(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch, engine=_FakeEngine()) as c:
        r = c.post(
            "/api/v1/speakers/999/enroll",
            files={"file": ("a.pcm", _audible_pcm_bytes(3), "application/octet-stream")},
            params={"sample_rate": 16000},
            headers=_HEADERS,
        )
        assert r.status_code == 404


# ── 现场麦录音端点 ────────────────────────────────────────────────────────────────


def test_enroll_start_then_stop_success(tmp_dal: DAL, monkeypatch):
    engine = _FakeEngine()
    rec = _FakeRecorder()
    with _client(tmp_dal, monkeypatch, engine=engine, recorder=rec) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        r = c.post(f"/api/v1/speakers/{sid}/enroll/start", headers=_HEADERS)
        assert r.status_code == 202
        assert rec.events == ["start"]
        r = c.post(f"/api/v1/speakers/{sid}/enroll/stop", headers=_HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["has_enrollment"] is True
        assert rec.events == ["start", "stop"]
        assert engine.calls == [16000 * 3]


def test_enroll_start_409_when_capture_active(tmp_dal: DAL, monkeypatch):
    rec = _FakeRecorder(capture_active=True)
    with _client(tmp_dal, monkeypatch, engine=_FakeEngine(), recorder=rec) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        r = c.post(f"/api/v1/speakers/{sid}/enroll/start", headers=_HEADERS)
        assert r.status_code == 409


def test_enroll_start_503_without_recorder(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch, engine=_FakeEngine(), recorder=None) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        r = c.post(f"/api/v1/speakers/{sid}/enroll/start", headers=_HEADERS)
        assert r.status_code == 503


def test_enroll_start_503_without_engine(tmp_dal: DAL, monkeypatch):
    rec = _FakeRecorder()
    with _client(tmp_dal, monkeypatch, engine=None, recorder=rec) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        r = c.post(f"/api/v1/speakers/{sid}/enroll/start", headers=_HEADERS)
        assert r.status_code == 503
        assert rec.events == []  # 无引擎不开录音（fail fast，不占设备）


def test_enroll_start_409_when_already_running(tmp_dal: DAL, monkeypatch):
    rec = _FakeRecorder()
    with _client(tmp_dal, monkeypatch, engine=_FakeEngine(), recorder=rec) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        assert c.post(f"/api/v1/speakers/{sid}/enroll/start", headers=_HEADERS).status_code == 202
        r = c.post(f"/api/v1/speakers/{sid}/enroll/start", headers=_HEADERS)  # 第二次：已在录
        assert r.status_code == 409


def test_enroll_stop_silent_400_releases_device(tmp_dal: DAL, monkeypatch):
    rec = _FakeRecorder(pcm=np.zeros(16000 * 3, dtype=np.int16))  # 静音
    with _client(tmp_dal, monkeypatch, engine=_FakeEngine(), recorder=rec) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        r = c.post(f"/api/v1/speakers/{sid}/enroll/stop", headers=_HEADERS)
        assert r.status_code == 400
        assert "stop" in rec.events  # 即使 400 也已 stop 释放设备


def test_enroll_start_missing_speaker_404(tmp_dal: DAL, monkeypatch):
    rec = _FakeRecorder()
    with _client(tmp_dal, monkeypatch, engine=_FakeEngine(), recorder=rec) as c:
        r = c.post("/api/v1/speakers/999/enroll/start", headers=_HEADERS)
        assert r.status_code == 404
        assert rec.events == []  # 不存在的 speaker 不开录音


def test_enroll_cancel_aborts(tmp_dal: DAL, monkeypatch):
    rec = _FakeRecorder()
    with _client(tmp_dal, monkeypatch, engine=_FakeEngine(), recorder=rec) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        c.post(f"/api/v1/speakers/{sid}/enroll/start", headers=_HEADERS)
        r = c.post(f"/api/v1/speakers/{sid}/enroll/cancel", headers=_HEADERS)
        assert r.status_code == 204
        assert rec.events == ["start", "abort"]


def test_enroll_cancel_without_recorder_is_204(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch, engine=_FakeEngine(), recorder=None) as c:
        sid = c.post("/api/v1/speakers", json={"display_name": "张三"}, headers=_HEADERS).json()["speaker_id"]
        r = c.post(f"/api/v1/speakers/{sid}/enroll/cancel", headers=_HEADERS)
        assert r.status_code == 204
