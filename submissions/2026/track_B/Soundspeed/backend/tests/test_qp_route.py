"""POST /api/v1/query：跑 QP → 广播 qp.answer.{conn_id} + 同步返回答案。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.core.orchestrator import create_orchestrator
from backend.db.dal import DAL


class _FakeService:
    """跳过真实模型：run_qp_query 用不到它（route 经 monkeypatch 短路）。

    aclose 需实现：create_app lifespan shutdown 会 await llm_service.aclose()。
    """

    async def aclose(self) -> None:
        pass


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "devtoken")
    dal = DAL(tmp_path / "route.db")
    dal.create_scene("Scene_1")
    orch = create_orchestrator(dal)
    app = create_app(orch, llm_service=_FakeService())

    # 短路 run_qp_query，避免真模型；断言 route 把答案广播 + 返回
    async def _fake_run_qp_query(*, text, dal, service, timeout=30.0):
        return f"答复：{text}"

    monkeypatch.setattr("backend.api.routes.query.run_qp_query", _fake_run_qp_query)

    with TestClient(app) as c:
        c._dal = dal
        yield c
    dal.close()


def test_post_query_returns_answer(client) -> None:
    resp = client.post(
        "/api/v1/query",
        json={"text": "第一场拍了多少条", "conn_id": "abc"},
        headers={"Authorization": "Bearer devtoken"},
    )
    assert resp.status_code == 200
    assert resp.json()["answer"] == "答复：第一场拍了多少条"


def test_post_query_broadcasts_qp_answer(client, monkeypatch) -> None:
    captured = {}

    def _capture(topic, payload):
        captured["topic"] = topic
        captured["payload"] = payload

    monkeypatch.setattr(
        client.app.state.connection_manager, "broadcast", _capture
    )
    client.post(
        "/api/v1/query",
        json={"text": "hi", "conn_id": "abc"},
        headers={"Authorization": "Bearer devtoken"},
    )
    assert captured["topic"] == "qp.answer.abc"  # topic 带 conn_id，客户端按前缀过滤


def test_post_query_requires_auth(client) -> None:
    resp = client.post("/api/v1/query", json={"text": "x", "conn_id": "abc"})
    assert resp.status_code in (401, 403)


def test_post_query_exception_returns_fallback_not_500(client, monkeypatch) -> None:
    """run_qp_query 抛异常时 route try/except 兜底：200 + 友好文案 + 仍广播。"""
    async def _raise(*, text, dal, service, timeout=30.0):
        raise RuntimeError("模拟推理失败")

    monkeypatch.setattr("backend.api.routes.query.run_qp_query", _raise)

    captured = {}

    def _capture(topic, payload):
        captured["topic"] = topic
        captured["payload"] = payload

    monkeypatch.setattr(
        client.app.state.connection_manager, "broadcast", _capture
    )

    resp = client.post(
        "/api/v1/query",
        json={"text": "出错测试", "conn_id": "xyz"},
        headers={"Authorization": "Bearer devtoken"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # 兜底文案，不是 500
    assert "抱歉" in body["answer"] or "出错" in body["answer"]
    # 即使出错仍然广播（让前端不挂起）
    assert captured.get("topic") == "qp.answer.xyz"


def test_post_query_503_when_no_service(tmp_path, monkeypatch) -> None:
    """llm_service=None 时 route 在 try 块外抛 503（不被兜底吞）。"""
    monkeypatch.setenv("ADMIN_TOKEN", "devtoken")
    dal = DAL(tmp_path / "no_svc.db")
    orch = create_orchestrator(dal)
    app = create_app(orch, llm_service=None)  # 不注入 service

    with TestClient(app) as c:
        resp = c.post(
            "/api/v1/query",
            json={"text": "x", "conn_id": "abc"},
            headers={"Authorization": "Bearer devtoken"},
        )
    dal.close()
    assert resp.status_code == 503
