"""A5 分流调度器测试：POST /notes 按 classify_memo 结果分流到 QP 或 NP。

四个分支：
  1. conn_id + classify=query → schedule_qp_broadcast 被调、不进 run_np_async、返回 202 kind=query
  2. conn_id + classify=note  → 不调 schedule_qp_broadcast、进 run_np_async
  3. 无 conn_id               → 不调 classify_memo、进 run_np_async
  4. @keep 开头（显式类别）   → 不调 classify_memo、进 run_np_async

monkeypatch 目标：
  backend.api.routes.takes.classify_memo
  backend.api.routes.takes.schedule_qp_broadcast

复用 test_api_notes.py 的 DAL + create_orchestrator + create_app 风格。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.core.orchestrator import create_orchestrator
from backend.db.dal import DAL

_TOKEN = "devtoken"
AUTH = {"Authorization": f"Bearer {_TOKEN}"}


# ── 辅助 fixture ─────────────────────────────────────────────────────────────


class _StubService:
    """最小 llm_service stub：让 service is not None 检查通过。

    实现 aclose()（create_app lifespan shutdown 会调用）。
    """

    async def aclose(self) -> None:
        pass


def _make_dispatch_client(
    dal: DAL,
    monkeypatch,
    *,
    with_service: bool = True,
) -> TestClient:
    """构造含 llm_service 的 app client，用于测分流逻辑。"""
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    orch = create_orchestrator(dal)
    service = _StubService() if with_service else None
    app = create_app(orch, llm_service=service)
    return TestClient(app)


@pytest.fixture
def dal(tmp_path):
    d = DAL(tmp_path / "test.db")
    yield d
    d.close()


def _setup_scene_and_take(dal: DAL, scene_code: str = "3A") -> int:
    dal._conn.execute(
        "INSERT INTO scenes (scene_code, is_active) VALUES (?, 1)",
        (scene_code,),
    )
    scene_id = dal._conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    dal._conn.execute(
        "INSERT INTO takes (scene_id, take_number, start_ts, status) VALUES (?, 1, 1000.0, 'tbd')",
        (scene_id,),
    )
    dal._conn.commit()
    return dal._conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── 测试：分支 1 —— conn_id + classify=query ─────────────────────────────────


def test_dispatch_query_branch_schedules_qp_not_np(dal: DAL, monkeypatch) -> None:
    """conn_id 存在且 classify=query → schedule_qp_broadcast 被调（text/conn_id 正确），
    不进 run_np_async，返回 202 且 kind='query'。
    """
    _setup_scene_and_take(dal)
    client = _make_dispatch_client(dal, monkeypatch)

    # 捕获 classify 返回 query
    async def _fake_classify(text, service, **kw):
        return "query"

    monkeypatch.setattr("backend.api.routes.takes.classify_memo", _fake_classify)

    # 捕获 schedule_qp_broadcast 调用
    schedule_calls: list[tuple] = []

    def _fake_schedule(text, conn_id, **kwargs):
        schedule_calls.append((text, conn_id))

    monkeypatch.setattr("backend.api.routes.takes.schedule_qp_broadcast", _fake_schedule)

    # 捕获 run_np_async（通过 orch 实例——app.state.orchestrator）
    np_calls: list[dict] = []
    with client as c:
        orch = c.app.state.orchestrator
        _orig_np = orch.run_np_async

        def _capture_np(**kw):
            np_calls.append(kw)

        orch.run_np_async = _capture_np

        resp = c.post(
            "/api/v1/notes",
            json={"text": "第一场拍了多少条", "conn_id": "conn-abc"},
            headers=AUTH,
        )

    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["status"] == "processing"
    assert data["kind"] == "query"

    assert len(schedule_calls) == 1, f"schedule_qp_broadcast 应被调一次，实际 {schedule_calls}"
    called_text, called_conn_id = schedule_calls[0]
    assert called_conn_id == "conn-abc"
    # parse_note 不修改纯文本（无 @category）时 raw_text == text
    assert called_text == "第一场拍了多少条"

    assert np_calls == [], f"run_np_async 不应被调，实际 {np_calls}"


def test_dispatch_query_branch_passes_client_id_to_qp(dal: DAL, monkeypatch) -> None:
    """conn_id + client_id + classify=query → schedule_qp_broadcast 收到 client_id。

    队列模型据此把 qp.answer 落到对应那条 qaItem（client_id 是前端乐观去重键）。
    """
    _setup_scene_and_take(dal)
    client = _make_dispatch_client(dal, monkeypatch)

    async def _fake_classify(text, service, **kw):
        return "query"

    monkeypatch.setattr("backend.api.routes.takes.classify_memo", _fake_classify)

    schedule_kwargs: list[dict] = []

    def _fake_schedule(text, conn_id, **kwargs):
        schedule_kwargs.append(kwargs)

    monkeypatch.setattr("backend.api.routes.takes.schedule_qp_broadcast", _fake_schedule)

    with client as c:
        resp = c.post(
            "/api/v1/notes",
            json={
                "text": "第一场拍了多少条",
                "conn_id": "conn-abc",
                "client_id": "cid-xyz",
            },
            headers=AUTH,
        )

    assert resp.status_code == 202, resp.text
    assert len(schedule_kwargs) == 1, f"schedule_qp_broadcast 应被调一次，实际 {schedule_kwargs}"
    assert schedule_kwargs[0].get("client_id") == "cid-xyz", (
        f"client_id 应透传进 schedule_qp_broadcast，实际 {schedule_kwargs[0]}"
    )


# ── 测试：分支 2 —— conn_id + classify=note ──────────────────────────────────


def test_dispatch_note_branch_goes_to_np(dal: DAL, monkeypatch) -> None:
    """classify=note → 不调 schedule_qp_broadcast，进 run_np_async。"""
    _setup_scene_and_take(dal)
    client = _make_dispatch_client(dal, monkeypatch)

    async def _fake_classify(text, service, **kw):
        return "note"

    monkeypatch.setattr("backend.api.routes.takes.classify_memo", _fake_classify)

    schedule_calls: list = []

    def _fake_schedule(text, conn_id, **kwargs):
        schedule_calls.append((text, conn_id))

    monkeypatch.setattr("backend.api.routes.takes.schedule_qp_broadcast", _fake_schedule)

    np_calls: list[dict] = []
    with client as c:
        orch = c.app.state.orchestrator

        def _capture_np(**kw):
            np_calls.append(kw)

        orch.run_np_async = _capture_np

        resp = c.post(
            "/api/v1/notes",
            json={"text": "这条声音有点小", "conn_id": "conn-abc"},
            headers=AUTH,
        )

    assert resp.status_code == 202, resp.text
    assert schedule_calls == [], f"schedule_qp_broadcast 不应被调，实际 {schedule_calls}"
    assert len(np_calls) == 1, f"run_np_async 应被调一次，实际 {np_calls}"


# ── 测试：分支 3 —— 无 conn_id ───────────────────────────────────────────────


def test_dispatch_no_conn_id_skips_classify_goes_to_np(dal: DAL, monkeypatch) -> None:
    """无 conn_id → 不调 classify_memo，进 run_np_async。"""
    _setup_scene_and_take(dal)
    client = _make_dispatch_client(dal, monkeypatch)

    classify_calls: list = []

    async def _fake_classify(text, service, **kw):
        classify_calls.append(text)
        return "query"  # 就算被调了 classify 返回 query，也要进 np

    monkeypatch.setattr("backend.api.routes.takes.classify_memo", _fake_classify)

    np_calls: list[dict] = []
    with client as c:
        orch = c.app.state.orchestrator

        def _capture_np(**kw):
            np_calls.append(kw)

        orch.run_np_async = _capture_np

        resp = c.post(
            "/api/v1/notes",
            json={"text": "飞机声"},  # 无 conn_id
            headers=AUTH,
        )

    assert resp.status_code == 202, resp.text
    assert classify_calls == [], f"classify_memo 不应被调，实际 {classify_calls}"
    assert len(np_calls) == 1, f"run_np_async 应被调一次，实际 {np_calls}"


# ── 测试：分支 4 —— @keep 开头（显式类别）────────────────────────────────────


def test_dispatch_explicit_category_skips_classify_goes_to_np(dal: DAL, monkeypatch) -> None:
    """@keep 开头 → 不调 classify_memo，进 run_np_async。"""
    _setup_scene_and_take(dal)
    client = _make_dispatch_client(dal, monkeypatch)

    classify_calls: list = []

    async def _fake_classify(text, service, **kw):
        classify_calls.append(text)
        return "query"

    monkeypatch.setattr("backend.api.routes.takes.classify_memo", _fake_classify)

    np_calls: list[dict] = []
    with client as c:
        orch = c.app.state.orchestrator

        def _capture_np(**kw):
            np_calls.append(kw)

        orch.run_np_async = _capture_np

        resp = c.post(
            "/api/v1/notes",
            json={"text": "@keep 这条留着", "conn_id": "conn-xyz"},
            headers=AUTH,
        )

    assert resp.status_code == 202, resp.text
    assert classify_calls == [], f"classify_memo 不应被调（显式类别），实际 {classify_calls}"
    assert len(np_calls) == 1, f"run_np_async 应被调一次，实际 {np_calls}"
