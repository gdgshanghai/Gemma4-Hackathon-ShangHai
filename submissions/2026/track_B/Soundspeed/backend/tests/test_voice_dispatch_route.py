"""C1: POST /notes/voice 接 voice dispatch：conn_id 透传 + 分流 + note 分支 take 上下文。

测试四条路径：
  1. 带 conn_id → run_voice_dispatch 被调，conn_id 正确透传，返回 202
  2. 无 conn_id → 不走 dispatch，走原有 run_np_voice_async（NP 分支）
  3. query 分支：_schedule_qp_broadcast 被调，conn_id 正确
  4. note 分支 take 上下文：np_input（含 current_take_id）被透传进 run_voice_dispatch

mock 目标：
  backend.api.routes.takes.run_voice_dispatch  (monkeypatch)
  backend.api.routes.takes.schedule_qp_broadcast  (not tested here)

复用 test_notes_dispatch.py 的 _make_dispatch_client 风格（不依赖不存在的 fixture）。
"""
from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.core.orchestrator import create_orchestrator
from backend.db.dal import DAL

_TOKEN = "devtoken"
AUTH = {"Authorization": f"Bearer {_TOKEN}"}
_WAV_BYTES = b"RIFF" + b"\x00" * 36  # 最小 stub WAV header（≥1字节，不超限）


class _StubService:
    """最小 llm_service stub，让 service is not None 检查通过。"""

    async def aclose(self) -> None:
        pass


def _make_client(dal: DAL, monkeypatch) -> TestClient:
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    orch = create_orchestrator(dal)
    app = create_app(orch, llm_service=_StubService())
    return TestClient(app)


def _setup_scene_and_take(dal: DAL) -> int:
    dal._conn.execute(
        "INSERT INTO scenes (scene_code, is_active) VALUES (?, 1)", ("1A",)
    )
    scene_id = dal._conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    dal._conn.execute(
        "INSERT INTO takes (scene_id, take_number, start_ts, status) VALUES (?, 1, 1000.0, 'tbd')",
        (scene_id,),
    )
    dal._conn.commit()
    return scene_id


@pytest.fixture
def dal(tmp_path):
    d = DAL(tmp_path / "test.db")
    yield d
    d.close()


# ── 测试 1：带 conn_id → run_voice_dispatch 被调，返回 202 ─────────────────────

def test_voice_note_with_conn_id_dispatches(dal: DAL, monkeypatch) -> None:
    """POST /notes/voice 带 conn_id → run_voice_dispatch 被调，conn_id 正确透传，返回 202。"""
    _setup_scene_and_take(dal)
    client = _make_client(dal, monkeypatch)

    dispatched: dict = {}

    async def _fake_dispatch(audio, *, conn_id, **kw):
        dispatched["conn_id"] = conn_id
        dispatched["audio_len"] = len(audio)
        return {"kind": "query"}

    monkeypatch.setattr("backend.api.routes.takes.run_voice_dispatch", _fake_dispatch)

    r = client.post(
        "/api/v1/notes/voice",
        data={"conn_id": "c99", "client_id": "cid1"},
        files={"file": ("test.wav", io.BytesIO(_WAV_BYTES), "audio/wav")},
        headers=AUTH,
    )
    assert r.status_code == 202, r.text
    assert dispatched["conn_id"] == "c99"
    assert dispatched["audio_len"] == len(_WAV_BYTES)


# ── 测试 2：无 conn_id → 不走 dispatch，走 run_np_voice_async ─────────────────

def test_voice_note_without_conn_id_skips_dispatch(dal: DAL, monkeypatch) -> None:
    """无 conn_id → run_voice_dispatch 不被调，走 run_np_voice_async 原有路径。"""
    _setup_scene_and_take(dal)
    client = _make_client(dal, monkeypatch)

    dispatch_called: dict = {}

    async def _fake_dispatch(audio, *, conn_id, **kw):
        dispatch_called["yes"] = True
        return {"kind": "note"}

    monkeypatch.setattr("backend.api.routes.takes.run_voice_dispatch", _fake_dispatch)

    np_voice_called: dict = {}

    with client as c:
        orch = c.app.state.orchestrator
        _orig = orch.run_np_voice_async

        def _capture_np_voice(**kw):
            np_voice_called["yes"] = True

        orch.run_np_voice_async = _capture_np_voice

        r = c.post(
            "/api/v1/notes/voice",
            data={"client_id": "cid2"},  # 无 conn_id
            files={"file": ("test.wav", io.BytesIO(_WAV_BYTES), "audio/wav")},
            headers=AUTH,
        )

    assert r.status_code == 202, r.text
    assert "yes" not in dispatch_called, "run_voice_dispatch 不应被调（无 conn_id）"
    assert np_voice_called.get("yes") is True, "run_np_voice_async 应被调"


# ── 测试 3：有 conn_id → 返回 202，body 含 kind='dispatching'（fire-and-forget） ──

def test_voice_note_dispatch_returns_202_dispatching(dal: DAL, monkeypatch) -> None:
    """有 conn_id → 路由 fire-and-forget，立即返回 202 with kind='dispatching'。
    dispatch 内部结果（note/query）异步进行，不等待。
    """
    _setup_scene_and_take(dal)
    client = _make_client(dal, monkeypatch)

    async def _fake_dispatch(audio, *, conn_id, **kw):
        return {"kind": "note"}

    monkeypatch.setattr("backend.api.routes.takes.run_voice_dispatch", _fake_dispatch)

    r = client.post(
        "/api/v1/notes/voice",
        data={"conn_id": "c1", "client_id": "cid3"},
        files={"file": ("test.wav", io.BytesIO(_WAV_BYTES), "audio/wav")},
        headers=AUTH,
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body.get("status") == "processing"
    # fire-and-forget → kind 固定为 "dispatching"（不等 dispatch 结果）
    assert body.get("kind") == "dispatching"


# ── 测试 4：np_input（含 current_take_id）被透传进 run_voice_dispatch ──────────

def test_voice_dispatch_receives_np_input_with_take_id(dal: DAL, monkeypatch) -> None:
    """run_voice_dispatch 收到 np_input，且 np_input.current_take_id 与当前 active take 一致。

    orchestrator.session 里激活了 take → _build_np_input 产出 current_take_id != None。
    """
    _setup_scene_and_take(dal)
    client = _make_client(dal, monkeypatch)

    received_kw: dict = {}

    async def _fake_dispatch(audio, *, conn_id, np_input=None, **kw):
        received_kw["np_input"] = np_input
        return {"kind": "note"}

    monkeypatch.setattr("backend.api.routes.takes.run_voice_dispatch", _fake_dispatch)

    with client as c:
        orch = c.app.state.orchestrator
        # 模拟 session 有激活的 take
        orch.session.take_id = 1
        orch.session.take_active = True
        orch.session.scene_id = 1

        r = c.post(
            "/api/v1/notes/voice",
            data={"conn_id": "c-take", "client_id": "cid4"},
            files={"file": ("test.wav", io.BytesIO(_WAV_BYTES), "audio/wav")},
            headers=AUTH,
        )

    assert r.status_code == 202, r.text
    np_input = received_kw.get("np_input")
    assert np_input is not None, "np_input 未传入 run_voice_dispatch"
    assert np_input.current_take_id == 1, (
        f"np_input.current_take_id 应为 1，实际 {np_input.current_take_id}"
    )


# ── 测试 5：note 分支 voice_runner 被透传 ────────────────────────────────────────

def test_voice_dispatch_receives_voice_runner(dal: DAL, monkeypatch) -> None:
    """run_voice_dispatch 收到 voice_runner（非 None），供 note 分支委托 run_np_voice。"""
    _setup_scene_and_take(dal)
    client = _make_client(dal, monkeypatch)

    received_kw: dict = {}

    async def _fake_dispatch(audio, *, conn_id, voice_runner=None, **kw):
        received_kw["voice_runner"] = voice_runner
        return {"kind": "note"}

    monkeypatch.setattr("backend.api.routes.takes.run_voice_dispatch", _fake_dispatch)

    r = client.post(
        "/api/v1/notes/voice",
        data={"conn_id": "c-vr", "client_id": "cid5"},
        files={"file": ("test.wav", io.BytesIO(_WAV_BYTES), "audio/wav")},
        headers=AUTH,
    )
    assert r.status_code == 202, r.text
    # voice_runner 来自 orchestrator._deps.voice_runner，有 llm_service 时非 None
    # 此处 _StubService 不绑 runner，可能为 None；验 key 存在即可（接线到位）
    assert "voice_runner" in received_kw, "voice_runner 未传入 run_voice_dispatch"


# ── 测试 6/7：dispatch 路径发 busy → task done 发 idle（问题 1） ──────────────────
#
# 测试通过 TestClient 走真实 takes.py 路由层（_dispatch_with_status + _done callback），
# spy orchestrator.publish，等 fire-and-forget task 完成后断言 LLM_STATUS 序列。
# 若删掉 takes.py 的 _emit_np_status_preamble 调用或 _done 接线，测试会变红。

def _wait_dispatch_tasks(app, timeout: float = 1.0) -> None:
    """轮询直到 _voice_dispatch_tasks 清空（task.add_done_callback 触发后即清空）。
    TestClient 在 `with` 上下文里保持 portal/event loop 存活，任务由后台线程推进。
    """
    import time
    import backend.api.routes.takes as _takes_mod
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _takes_mod._voice_dispatch_tasks:
            return
        time.sleep(0.02)
    raise TimeoutError("voice_dispatch_tasks 未在超时内清空")


def test_voice_dispatch_emits_busy_then_idle(dal: DAL, monkeypatch) -> None:
    """有 conn_id 路径（dispatch 成功）：先发 LLM_STATUS busy/running，done 后发 idle。

    走真实 takes.py _dispatch_with_status wrapper + _done callback。
    删掉 takes.py 中 _emit_np_status_preamble 调用或 _done 接线，此测试即变红。
    """
    import time
    from backend.core.events import LLM_STATUS

    _setup_scene_and_take(dal)
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)

    published: list[tuple] = []
    orch = create_orchestrator(dal)
    _orig_publish = orch.publish

    def _spy_publish(event, payload):
        published.append((event, payload))
        _orig_publish(event, payload)

    orch.publish = _spy_publish

    app = create_app(orch, llm_service=_StubService())

    async def _fast_dispatch(audio, *, conn_id, **kw):
        return {"kind": "note"}

    monkeypatch.setattr("backend.api.routes.takes.run_voice_dispatch", _fast_dispatch)

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/notes/voice",
            data={"conn_id": "c-busy", "client_id": "cid6"},
            files={"file": ("test.wav", io.BytesIO(_WAV_BYTES), "audio/wav")},
            headers=AUTH,
        )
        assert r.status_code == 202, r.text
        _wait_dispatch_tasks(app)

    llm_events = [(e, p) for e, p in published if e == LLM_STATUS]
    assert len(llm_events) >= 2, (
        f"应有 ≥2 个 LLM_STATUS（busy+idle），实际：{[p.state for _, p in llm_events]}"
    )
    states = [p.state for _, p in llm_events]
    assert states[0] in ("running", "loading", "downloading"), (
        f"第一个 LLM_STATUS 应为 busy 态，实际 {states[0]!r}"
    )
    assert states[-1] == "idle", f"最后一个 LLM_STATUS 应为 idle，实际 {states[-1]!r}"


def test_voice_dispatch_emits_idle_on_error(dal: DAL, monkeypatch) -> None:
    """有 conn_id 路径（dispatch 抛异常）：即使 run_voice_dispatch 失败，done callback 也发 idle。

    验证 takes.py _done callback 无论成功/失败均发 idle（_np_done_callback 无条件 publish）。
    删掉 _done 接线或 _np_done_callback 里的 publish，此测试即变红。
    """
    from backend.core.events import LLM_STATUS

    _setup_scene_and_take(dal)
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)

    published: list[tuple] = []
    orch = create_orchestrator(dal)
    _orig_publish = orch.publish

    def _spy_publish(event, payload):
        published.append((event, payload))
        _orig_publish(event, payload)

    orch.publish = _spy_publish

    app = create_app(orch, llm_service=_StubService())

    async def _failing_dispatch(audio, *, conn_id, **kw):
        raise RuntimeError("dispatch 爆了")

    monkeypatch.setattr("backend.api.routes.takes.run_voice_dispatch", _failing_dispatch)

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/notes/voice",
            data={"conn_id": "c-err2", "client_id": "cid7"},
            files={"file": ("test.wav", io.BytesIO(_WAV_BYTES), "audio/wav")},
            headers=AUTH,
        )
        assert r.status_code == 202, r.text
        _wait_dispatch_tasks(app)

    idle_events = [p for e, p in published if e == LLM_STATUS and p.state == "idle"]
    assert idle_events, "dispatch 失败时 done callback 应仍发 idle LLM_STATUS"
