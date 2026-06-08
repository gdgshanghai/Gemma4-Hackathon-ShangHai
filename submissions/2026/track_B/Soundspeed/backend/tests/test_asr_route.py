"""GET/POST /api/v1/asr 路由测试。最小 app + 假 session。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.asr import router

_TOKEN = "t"
_HDR = {"Authorization": f"Bearer {_TOKEN}"}


class _FakeSession:
    def __init__(self, language="zh", model_size="base"):
        self._lang = language
        self._model = model_size

    @property
    def language(self):
        return self._lang

    @property
    def model_size(self):
        return self._model

    def set_language(self, lang):
        self._lang = lang


def _client(live_asr) -> TestClient:
    app = FastAPI()
    app.state.admin_token = _TOKEN
    app.state.live_asr = live_asr
    app.include_router(router)
    return TestClient(app)


def test_get_asr_reports_language_and_model():
    r = _client(_FakeSession(language="zh", model_size="medium")).get("/api/v1/asr", headers=_HDR)
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["language"] == "zh"
    assert body["model"] == "medium"
    assert "zh" in body["languages"]


def test_get_asr_disabled_when_no_session():
    body = _client(None).get("/api/v1/asr", headers=_HDR).json()
    assert body["enabled"] is False
    assert body["language"] is None


def test_get_asr_requires_auth():
    assert _client(_FakeSession()).get("/api/v1/asr").status_code == 401


def test_set_language_updates_session():
    session = _FakeSession(language="zh")
    r = _client(session).post("/api/v1/asr/language", json={"language": "en"}, headers=_HDR)
    assert r.status_code == 200
    assert r.json()["language"] == "en"
    assert session.language == "en"


def test_set_language_empty_422():
    r = _client(_FakeSession()).post("/api/v1/asr/language", json={"language": "  "}, headers=_HDR)
    assert r.status_code == 422


def test_set_language_without_live_asr_409():
    r = _client(None).post("/api/v1/asr/language", json={"language": "en"}, headers=_HDR)
    assert r.status_code == 409
