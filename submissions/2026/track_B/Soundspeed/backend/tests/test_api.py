"""1.I FastAPI API 层 — 切片 A（REST 基座）测试。

TDD 红阶段：backend.api 尚不存在，5 个测试应全部 fail（feature-missing 红）。

覆盖（切片 A，仅 REST，不含 WS）：
  - GET /healthz → 200（无鉴权）
  - POST /api/v1/take/start 无 token → 401
  - POST /api/v1/take/start 带正确 token → 200 + orchestrator 收到 TakeStartPayload
  - POST /api/v1/take/end 带正确 token → 200 + orchestrator 收到 TakeEndPayload
  - POST /api/v1/take/end 在注入 deps 时创建 _l2_task（决策 1 核心，防回归）

测试用 FastAPI TestClient（httpx）。app 用 create_app(orchestrator) 工厂注入测试
orchestrator（带 tmp_dal）。ADMIN_TOKEN 用 monkeypatch.setenv 注入，create_app 在
构造时读环境（不在 import 时捕获，否则 setenv 不生效）。

注意：REST 测试一律 plain def，不加 @pytest.mark.asyncio。TestClient 在它自己的
portal 线程里同步驱动 event loop，POST 返回后即可直接断言 _l2_task，无需 await。
"""
from __future__ import annotations

import threading
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.api.app import create_app
from backend.core.events import (
    ASR_FINAL_CH1,
    TAKE_END,
    TAKE_SEGMENTS_UPDATED,
    TAKE_START,
    AsrFinalPayload,
    TakeEndPayload,
    TakeSegmentsUpdatedPayload,
    TakeStartPayload,
)
from backend.core.orchestrator import Orchestrator, create_orchestrator
from backend.core.session import SessionState
from backend.db.dal import DAL

_TOKEN = "test-admin-token"


def _make_client(orchestrator: Orchestrator, monkeypatch) -> TestClient:
    """构造 TestClient：先 setenv ADMIN_TOKEN，再 create_app（构造时读环境）。"""
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    app = create_app(orchestrator)
    return TestClient(app)


def test_healthz_returns_200(tmp_dal: DAL, monkeypatch) -> None:
    """GET /healthz → 200（无鉴权）。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.get("/healthz")
    assert resp.status_code == 200


def test_list_all_characters_endpoint(tmp_dal: DAL, monkeypatch) -> None:
    """GET /api/v1/scenes/characters → 整部戏跨场去重角色清单（注册弹窗下拉用）。"""
    s1 = tmp_dal.create_scene("Scene_1")
    scr1 = tmp_dal.insert_script(s1, "场一")
    tmp_dal.insert_script_line(scr1, 1, "夏雨", "你来了。")
    tmp_dal.insert_script_line(scr1, 2, None, "（坐下）")  # 舞台指示，排除
    s2 = tmp_dal.create_scene("Scene_2")
    scr2 = tmp_dal.insert_script(s2, "场二")
    tmp_dal.insert_script_line(scr2, 1, "顾朗", "走。")
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.get(
        "/api/v1/scenes/characters",
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200
    assert set(resp.json()["characters"]) == {"夏雨", "顾朗"}


def test_list_all_characters_endpoint_normalizes_variants(tmp_dal: DAL, monkeypatch) -> None:
    """端点归一括号注记后去重：夏雨 与 夏雨（V.O.）合并成一个夏雨。"""
    s1 = tmp_dal.create_scene("Scene_1")
    scr1 = tmp_dal.insert_script(s1, "场一")
    tmp_dal.insert_script_line(scr1, 1, "夏雨", "你来了。")
    tmp_dal.insert_script_line(scr1, 2, "夏雨（V.O.）", "那年冬天。")  # 历史数据变体
    tmp_dal.insert_script_line(scr1, 3, "顾朗", "嗯。")
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.get(
        "/api/v1/scenes/characters",
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200
    assert resp.json()["characters"] == ["夏雨", "顾朗"]  # 变体合并，sorted


def test_list_all_characters_endpoint_requires_auth(tmp_dal: DAL, monkeypatch) -> None:
    """GET /api/v1/scenes/characters 无 token → 401。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.get("/api/v1/scenes/characters")
    assert resp.status_code == 401


def test_update_scene_script_appends_new_version(tmp_dal: DAL, monkeypatch) -> None:
    """POST /scenes/{id}/script 追加新版本（version+1），读侧切到新内容。"""
    sid = tmp_dal.create_scene("S1")
    tmp_dal.insert_script(sid, "旧原文")  # v1
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        f"/api/v1/scenes/{sid}/script",
        headers={"Authorization": f"Bearer {_TOKEN}"},
        json={
            "raw_text": "新原文",
            "lines": [
                {"character": "夏雨", "text": "你来了。"},
                {"character": None, "text": "（夏雨坐下）"},
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 2 and body["skipped"] is False and body["line_count"] == 2
    latest = tmp_dal.get_latest_script(sid)
    assert latest["version"] == 2
    assert [r["character"] for r in tmp_dal.list_script_lines(latest["script_id"])] == ["夏雨", None]


def test_update_scene_script_idempotent_same_raw_text(tmp_dal: DAL, monkeypatch) -> None:
    """raw_text 与最新版相同 → skipped=True，不新建版本。"""
    sid = tmp_dal.create_scene("S1")
    scr = tmp_dal.insert_script(sid, "原文A")
    tmp_dal.insert_script_line(scr, 1, "夏雨", "你来了。")
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        f"/api/v1/scenes/{sid}/script",
        headers={"Authorization": f"Bearer {_TOKEN}"},
        json={"raw_text": "原文A", "lines": [{"character": "夏雨", "text": "你来了。"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["skipped"] is True
    assert tmp_dal.get_latest_script(sid)["version"] == 1  # 未刷版本


def test_update_scene_script_normalizes_character(tmp_dal: DAL, monkeypatch) -> None:
    """提交时 character 归一（夏雨（V.O.）→ 夏雨）。"""
    sid = tmp_dal.create_scene("S1")
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        f"/api/v1/scenes/{sid}/script",
        headers={"Authorization": f"Bearer {_TOKEN}"},
        json={"raw_text": "x", "lines": [{"character": "夏雨（V.O.）", "text": "旁白。"}]},
    )
    assert resp.status_code == 200
    latest = tmp_dal.get_latest_script(sid)
    assert tmp_dal.list_script_lines(latest["script_id"])[0]["character"] == "夏雨"


def test_update_scene_script_404_missing_scene(tmp_dal: DAL, monkeypatch) -> None:
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    resp = client.post(
        "/api/v1/scenes/99999/script",
        headers={"Authorization": f"Bearer {_TOKEN}"},
        json={"raw_text": "x", "lines": [{"character": "A", "text": "t"}]},
    )
    assert resp.status_code == 404


def test_update_scene_script_422_empty_lines(tmp_dal: DAL, monkeypatch) -> None:
    sid = tmp_dal.create_scene("S1")
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    resp = client.post(
        f"/api/v1/scenes/{sid}/script",
        headers={"Authorization": f"Bearer {_TOKEN}"},
        json={"raw_text": "x", "lines": []},
    )
    assert resp.status_code == 422


def test_diff_keeps_old_line_missing_from_new(tmp_dal: DAL, monkeypatch) -> None:
    """旧有新无的行 → status=kept 且仍进 merged（防 OCR 漏行把内容删没）。"""
    sid = tmp_dal.create_scene("S1")
    scr = tmp_dal.insert_script(sid, "v1")
    tmp_dal.insert_script_line(scr, 1, "夏雨", "你来了。")
    tmp_dal.insert_script_line(scr, 2, "顾朗", "嗯。")
    tmp_dal.insert_script_line(scr, 3, "夏雨", "走吧。")
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        f"/api/v1/scenes/{sid}/script/diff",
        headers={"Authorization": f"Bearer {_TOKEN}"},
        json={
            "lines": [
                {"character": "夏雨", "text": "你来了。"},
                {"character": "夏雨", "text": "走吧。"},  # 漏掉了「顾朗 嗯。」
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_old"] is True
    assert [r["status"] for r in body["rows"]] == ["equal", "kept", "equal"]
    # merged_raw_text 由 merged 重建（character：text 换行拼），与落库 lines 一致
    assert body["merged_raw_text"] == "夏雨：你来了。\n顾朗：嗯。\n夏雨：走吧。"
    assert [(l["character"], l["text"]) for l in body["merged"]] == [
        ("夏雨", "你来了。"),
        ("顾朗", "嗯。"),  # 被漏掉的旧行保留
        ("夏雨", "走吧。"),
    ]


def test_diff_marks_added_and_changed(tmp_dal: DAL, monkeypatch) -> None:
    """新增行→added、改动行→changed（取新文本）；新增/改动夹在相等锚点间，difflib 不折叠成同一块。"""
    sid = tmp_dal.create_scene("S1")
    scr = tmp_dal.insert_script(sid, "v1")
    tmp_dal.insert_script_line(scr, 1, "夏雨", "你来了。")
    tmp_dal.insert_script_line(scr, 2, "顾朗", "嗯。")
    tmp_dal.insert_script_line(scr, 3, "夏雨", "走吧。")
    tmp_dal.insert_script_line(scr, 4, "顾朗", "好。")
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        f"/api/v1/scenes/{sid}/script/diff",
        headers={"Authorization": f"Bearer {_TOKEN}"},
        json={
            "lines": [
                {"character": "夏雨", "text": "你来了。"},
                {"character": "林夏", "text": "我也在。"},  # added
                {"character": "顾朗", "text": "嗯。"},
                {"character": "夏雨", "text": "快走。"},  # changed vs 走吧。
                {"character": "顾朗", "text": "好。"},
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [r["status"] for r in body["rows"]] == ["equal", "added", "equal", "changed", "equal"]
    assert [(l["character"], l["text"]) for l in body["merged"]] == [
        ("夏雨", "你来了。"),
        ("林夏", "我也在。"),
        ("顾朗", "嗯。"),
        ("夏雨", "快走。"),  # 取新文本，旧「走吧。」被替换
        ("顾朗", "好。"),
    ]


def test_diff_no_old_all_added(tmp_dal: DAL, monkeypatch) -> None:
    """该场无旧版 → has_old=False，全部 added，merged 即新行。"""
    sid = tmp_dal.create_scene("S1")
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        f"/api/v1/scenes/{sid}/script/diff",
        headers={"Authorization": f"Bearer {_TOKEN}"},
        json={"lines": [{"character": "夏雨", "text": "你来了。"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_old"] is False
    assert [r["status"] for r in body["rows"]] == ["added"]
    assert body["merged"] == [{"character": "夏雨", "text": "你来了。"}]


def test_diff_404_missing_scene(tmp_dal: DAL, monkeypatch) -> None:
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    resp = client.post(
        "/api/v1/scenes/99999/script/diff",
        headers={"Authorization": f"Bearer {_TOKEN}"},
        json={"lines": [{"character": "A", "text": "t"}]},
    )
    assert resp.status_code == 404


def test_take_start_without_token_returns_401(tmp_dal: DAL, monkeypatch) -> None:
    """POST /api/v1/take/start 无 Authorization 头 → 401。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post("/api/v1/take/start", json={"scene_id": 1, "shot": "A"})
    assert resp.status_code == 401


def test_take_start_with_wrong_token_returns_401(tmp_dal: DAL, monkeypatch) -> None:
    """带错误但 ASCII 的 token → 401。守 compare_digest 比对逻辑本身。

    现有逻辑对 ASCII 错 token 已正确返 401，本测试修前就应绿——补漏测（之前完全
    没测比对逻辑，删了 compare_digest 也不会红），作为安全回归。
    """
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        "/api/v1/take/start",
        json={"scene_id": 1, "shot": "A"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


def test_take_start_with_non_ascii_token_returns_401(tmp_dal: DAL, monkeypatch) -> None:
    """带非 ASCII token（café 的 é，U+00E9，latin-1 内 → httpx 可编码进头）→ 401。

    header 值传 raw bytes b"Bearer caf\xe9"：httpx 对 str header 值按 ASCII 严格编码，
    "Bearer café" 会在客户端 UnicodeEncodeError 死掉（测到的是 transport 不是比对逻辑）。
    传 bytes 则 httpx 原样上线，starlette 服务端按 latin-1 解码 \xe9 → credentials
    "café"（非 ASCII str）——正是生产里的真实 bug 路径。
    修前红：secrets.compare_digest(str, str) 对含非 ASCII 的 str 在 auth.py 抛 TypeError，
    require_admin 未 catch → TestClient(raise_server_exceptions=True) 把 TypeError
    重抛进本测试（不是返 500）。
    修后绿：auth.py 改 bytes 比对，非 ASCII 安全比对失败 → 干净 401。
    """
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        "/api/v1/take/start",
        json={"scene_id": 1, "shot": "A"},
        headers={"Authorization": b"Bearer caf\xe9"},
    )
    assert resp.status_code == 401


def test_take_start_with_valid_token_publishes_event(tmp_dal: DAL, monkeypatch) -> None:
    """带正确 Bearer token，POST take/start → 200，orchestrator 收到 TakeStartPayload。

    spy 断言：scene_id 与 active scene 一致、shot=="A"、start_ts 是 float（服务端 time.time() 生成）。
    2.C：take/start 需要 scene_id == active scene，先建场并激活。
    """
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    # 2.C：先建场并激活，否则 take/start → 409
    scene_id = tmp_dal.create_scene("scene_publish_event")
    tmp_dal.set_active_scene(scene_id)

    received: list[object] = []
    orch.subscribe(TAKE_START, lambda p: received.append(p))

    resp = client.post(
        "/api/v1/take/start",
        json={"scene_id": scene_id, "shot": "A"},
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200

    assert len(received) == 1
    payload = received[0]
    assert isinstance(payload, TakeStartPayload)
    assert payload.scene_id == scene_id
    assert payload.shot == "A"
    assert isinstance(payload.start_ts, float)
    assert payload.take_number is None  # 未传 → None（后端自动取号）


def test_take_start_explicit_take_number_passthrough(tmp_dal: DAL, monkeypatch) -> None:
    """body 带 take_number → 透传进 TakeStartPayload；0/负数被 ge=1 挡成 422。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    scene_id = tmp_dal.create_scene("scene_explicit_num")
    tmp_dal.set_active_scene(scene_id)

    received: list[object] = []
    orch.subscribe(TAKE_START, lambda p: received.append(p))

    resp = client.post(
        "/api/v1/take/start",
        json={"scene_id": scene_id, "shot": "A", "take_number": 5},
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200
    assert isinstance(received[0], TakeStartPayload)
    assert received[0].take_number == 5

    # ge=1：take_number=0 → 422（FastAPI 请求体校验，不进 orchestrator）
    resp_zero = client.post(
        "/api/v1/take/start",
        json={"scene_id": scene_id, "shot": "A", "take_number": 0},
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp_zero.status_code == 422


def test_take_end_with_valid_token_publishes_event(tmp_dal: DAL, monkeypatch) -> None:
    """带 token POST take/end（body 空）→ 200，orchestrator 收到 TakeEndPayload。

    spy 断言：end_ts 是 float（服务端 time.time() 生成）。
    """
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    received: list[object] = []
    orch.subscribe(TAKE_END, lambda p: received.append(p))

    # body 空：take/end 端点不要求 body，否则 422
    resp = client.post(
        "/api/v1/take/end",
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200

    assert len(received) == 1
    payload = received[0]
    assert isinstance(payload, TakeEndPayload)
    assert isinstance(payload.end_ts, float)


def test_take_end_creates_l2_task_when_deps_injected(tmp_dal: DAL, monkeypatch) -> None:
    """决策 1 核心防回归：注入 deps 时 take/end 后 _l2_task 被创建。

    机制：take/end 的 fire-and-forget L2 靠 asyncio.get_running_loop()
    （orchestrator.py:214），且仅在注入 llm_service+l2_runner 时走到。
    端点必须 async def——FastAPI 在 TestClient 的 event loop 内直接 await async 端点，
    get_running_loop() 成功 → loop.create_task → _l2_task 被赋值。

    若端点被改回 def，FastAPI 会丢到线程池跑 → 无 running loop →
    get_running_loop() 抛 RuntimeError → 被 publish() 吞掉（orchestrator.py:79-82）→
    _l2_task 仍为 None。本测试就是守门它不被「简化」回 def。
    """
    scene_id = tmp_dal.create_scene("scene_api_l2")
    tmp_dal.set_active_scene(scene_id)  # 2.C：take/start 需要 active scene

    # stub llm_service（任意非 None）+ stub l2_runner（async 返回假对象）
    stub_svc = MagicMock()
    stub_runner = AsyncMock(return_value=MagicMock())

    session = SessionState()
    orch = create_orchestrator(
        tmp_dal, session, llm_service=stub_svc, l2_runner=stub_runner
    )
    client = _make_client(orch, monkeypatch)

    headers = {"Authorization": f"Bearer {_TOKEN}"}

    # 先起一个 take（take/end 需要 session.take_id 非 None 才会调度 L2）
    start_resp = client.post(
        "/api/v1/take/start",
        json={"scene_id": scene_id, "shot": None},
        headers=headers,
    )
    assert start_resp.status_code == 200
    assert session.take_id is not None

    # take/end → 在 async 端点的 running loop 下 fire-and-forget L2 被调度
    end_resp = client.post("/api/v1/take/end", headers=headers)
    assert end_resp.status_code == 200

    # 不 await：仅断言 task 被创建（决策 1 防回归核心断言）
    assert orch._l2_task is not None  # type: ignore[attr-defined]


# ── 切片 B：WS + 事件转发 ──────────────────────────────────────────────────────
#
# WS 测试必须用 `with TestClient(app) as client:`——只有 with 块才触发 lifespan，
# loop ref / orchestrator 订阅才生效。集合外的裸 TestClient 不跑 lifespan。
#
# ConnectionManager 一律通过 client.app.state.connection_manager 访问，
# 测试文件顶层不 import ws.py 符号——RED 阶段 ws.py 还不存在，顶层 import 会让整个
# 文件 collection 失败，连切片 A 的 5 个测试一起变红，分不清是 feature-missing 还是
# import 炸了。


def _recv_until(ws, topic: str, *, max_frames: int = 6) -> dict:
    """读 WS 帧直到 topic 匹配并返回该帧，跳过前面的 presence 噪声。

    connect 时 ConnectionManager 会先广播一帧 viewer.count（含自己），故所有「连上
    即收」的转发断言都要跳过它。注意：若目标 topic 因回归永不到达，最后一次
    receive_json 会阻塞挂死（本文件无 pytest-timeout，与既有转发测试同款风险）；
    max_frames 仅防持续涌入的噪声帧把循环跑飞，不把挂死变成干净 fail。
    """
    for _ in range(max_frames):
        msg = ws.receive_json()
        if msg["topic"] == topic:
            return msg
    raise AssertionError(f"未在 {max_frames} 帧内收到 topic={topic!r}")


def test_ws_without_token_rejected(tmp_dal: DAL, monkeypatch) -> None:
    """/ws 无 token → 握手被拒，close code 1008（不 accept）。

    断 code == 1008 而非仅断 WebSocketDisconnect：RED 阶段 /ws 路由还不存在，
    连不存在的 WS 路由本就抛 WebSocketDisconnect（关闭码非 1008），只断异常类型会假绿。
    断 1008 才真测到鉴权拒绝。
    """
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    app = create_app(create_orchestrator(tmp_dal))

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws"):
                pass
    assert exc_info.value.code == 1008


def test_ws_with_valid_token_connects(tmp_dal: DAL, monkeypatch) -> None:
    """/ws?token=<TOKEN> → 连上不被拒。"""
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    app = create_app(create_orchestrator(tmp_dal))

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws?token={_TOKEN}") as ws:
            # 连上即可——能进入 with 块说明握手成功（accept 了）。
            assert ws is not None


def test_ws_non_ascii_token_rejected(tmp_dal: DAL, monkeypatch) -> None:
    """/ws?token=<非 ASCII> → 干净 close 1008（WebSocketDisconnect code==1008）。

    修前红：ws_endpoint 里 secrets.compare_digest(token, expected) 对含非 ASCII 的
    str 抛 TypeError，在 close(1008) 之前抛 → 握手异常终止，surface 的不是
    WebSocketDisconnect(1008)，pytest.raises(WebSocketDisconnect) 拿不到 1008 → RED。
    修后绿：ws.py 改 bytes 比对，比对干净失败 → close(1008)。
    用 café（é，latin-1 内）保证 httpx 能编码进 query，RED 是服务端 TypeError 而非
    客户端编码错。镜像 test_ws_without_token_rejected。
    """
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    app = create_app(create_orchestrator(tmp_dal))

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws?token=caf%C3%A9"):
                pass
    assert exc_info.value.code == 1008


def test_ws_binary_frame_cleans_up_connection(tmp_dal: DAL, monkeypatch) -> None:
    """连上 ws 后发 binary frame → 连接最终从 cm._active 清理（不泄漏）。

    机制：保活循环 await receive_text() 收到 binary frame 时 starlette 抛 KeyError
    （message 只有 "bytes" 没 "text"）。
    修前红：循环只 except WebSocketDisconnect，KeyError 逃逸 → cm.disconnect 不跑 →
    _active 残留 1 个死连接（泄漏）。
    修后绿：finally: cm.disconnect(websocket) 保证任何退出路径都清理 → _active 空。
    KeyError 在两种状态下都会传播（finally 不吞它），唯一判别是 len(cm._active)：
    修前 1、修后 0。故整个 with 块包 try/except KeyError，让异常到不了断言。
    退出 with 的 join 保证服务端 task 跑完 finally 才走到断言（同 test_ws_disconnect_cleans_up）。
    """
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    app = create_app(create_orchestrator(tmp_dal))

    with TestClient(app) as client:
        cm = client.app.state.connection_manager
        try:
            with client.websocket_connect(f"/ws?token={_TOKEN}") as ws:
                ws.send_bytes(b"binary-frame")
        except KeyError:
            pass  # binary frame 致服务端 KeyError，两种状态都传播；判别只看 _active
        assert len(cm._active) == 0  # type: ignore[attr-defined]


def test_take_changed_forwarded_to_ws(tmp_dal: DAL, monkeypatch) -> None:
    """连上 ws 后 POST /take/start → ws 收到一条 take.changed（loop 线程内投递路径）。

    端到端真实链路：take/start → _on_take_start 写库 → publish(TAKE_CHANGED) →
    CM.broadcast（loop 线程内，走 create_task 路径）→ ws.send_json。

    必须先 create_scene：_on_take_start 在 publish 之前 start_take 写库，scene 不存在
    会让它在 publish 前抛异常并被 publish 吞掉，take.changed 永不发，_recv_until 死挂
    （挂死风险见 _recv_until docstring）。
    """
    scene_id = tmp_dal.create_scene("scene_ws_take")
    tmp_dal.set_active_scene(scene_id)  # 2.C：take/start 需要 active scene
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    app = create_app(create_orchestrator(tmp_dal))

    headers = {"Authorization": f"Bearer {_TOKEN}"}
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws?token={_TOKEN}") as ws:
            resp = client.post(
                "/api/v1/take/start",
                json={"scene_id": scene_id, "shot": "A"},
                headers=headers,
            )
            assert resp.status_code == 200

            msg = _recv_until(ws, "take.changed")
            assert msg["payload"]["scene_id"] == scene_id
            assert msg["payload"]["take_id"] is not None
            assert msg["payload"]["take_number"] == 1


def test_asr_final_forwarded_from_background_thread(tmp_dal: DAL, monkeypatch) -> None:
    """连上 ws 后，从后台线程 publish(ASR_FINAL_CH1, ...) → ws 收到 asr.final.ch1。

    跨线程路径（run_coroutine_threadsafe）：模拟未来 1.A ASR 线程触发同步 handler。
    take 未 active 时 _on_asr_final 直接 return（不写库），桥接转发仍应发生——
    转发是订阅 CM.broadcast，与内置 segment handler 互不影响。
    """
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)

    payload = AsrFinalPayload(
        text="hello from background",
        start_frame=0,
        end_frame=1000,
        speaker="A",
        take_id=None,
        is_partial=False,
    )

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws?token={_TOKEN}") as ws:
            t = threading.Thread(target=lambda: orch.publish(ASR_FINAL_CH1, payload))
            t.start()
            t.join()

            msg = _recv_until(ws, "asr.final.ch1")
            assert msg["payload"]["text"] == "hello from background"
            assert msg["payload"]["speaker"] == "A"


def test_take_segments_updated_forwarded_from_background_thread(
    tmp_dal: DAL, monkeypatch
) -> None:
    """从后台线程 publish(TAKE_SEGMENTS_UPDATED) → ws 收到 take.segments.updated。

    diarization 回填在 executor 线程内完成后 publish 此事件，前端据此 refetch。
    若 app.py 转发列表漏注册该 topic（回归 B1），ws 永不收到，本测试会因
    receive_json 死挂而暴露——与 take.changed / asr.final 同款转发链断言。
    """
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)

    payload = TakeSegmentsUpdatedPayload(take_id=42, scene_id=7)

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws?token={_TOKEN}") as ws:
            t = threading.Thread(
                target=lambda: orch.publish(TAKE_SEGMENTS_UPDATED, payload)
            )
            t.start()
            t.join()

            msg = _recv_until(ws, "take.segments.updated")
            assert msg["payload"]["take_id"] == 42
            assert msg["payload"]["scene_id"] == 7


def test_ws_disconnect_cleans_up(tmp_dal: DAL, monkeypatch) -> None:
    """连上再退出 with → cm._active 为空（连接清理）。"""
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    app = create_app(create_orchestrator(tmp_dal))

    with TestClient(app) as client:
        cm = client.app.state.connection_manager
        with client.websocket_connect(f"/ws?token={_TOKEN}"):
            pass
        # 退出 ws 上下文：TestClient join 服务端 task，
        # except WebSocketDisconnect 里 cm.disconnect 跑完才返回 → _active 应空。
        assert len(cm._active) == 0  # type: ignore[attr-defined]


def test_viewer_count_broadcast_on_connect(tmp_dal: DAL, monkeypatch) -> None:
    """连上 /ws → 立即收到 viewer.count，count == 活跃连接数（独连=含自己=1）。

    承重测试：单连接、无并发，确定性绿。它单独就能逼出 connect 路径上的
    _broadcast_count（口径=全部连接含自己）。RED 时 viewer.count topic 不存在，
    receive_json 永不收到该帧 → 挂死暴露（同款转发测试风险）。
    """
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    app = create_app(create_orchestrator(tmp_dal))

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws?token={_TOKEN}") as ws:
            msg = ws.receive_json()
            assert msg["topic"] == "viewer.count"
            assert msg["payload"]["count"] == 1


def test_viewer_count_updates_on_connect_and_disconnect(
    tmp_dal: DAL, monkeypatch
) -> None:
    """第二个客户端连上 → 两端都见 count==2；它断开后 → 第一端见 count==1。

    覆盖 disconnect 路径的广播。依赖 TestClient 单 portal 驱动两个并发 WS 会话
    （已知较脆）；故承重断言放在上面的单连接测试，本测试作为 disconnect 行为的
    端到端补充。_recv_until 跳过两端各自 connect 时的 viewer.count 首帧噪声。
    """
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    app = create_app(create_orchestrator(tmp_dal))

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws?token={_TOKEN}") as ws1:
            # ws1 独连：首帧 count==1
            assert ws1.receive_json()["payload"]["count"] == 1
            with client.websocket_connect(f"/ws?token={_TOKEN}") as ws2:
                # ws2 连上：connect 向全部活跃连接广播 count==2，两端各收到一帧。
                assert _recv_until(ws1, "viewer.count")["payload"]["count"] == 2
                assert _recv_until(ws2, "viewer.count")["payload"]["count"] == 2
            # ws2 退出 with → disconnect 后广播 count==1，仅 ws1 收到。
            assert _recv_until(ws1, "viewer.count")["payload"]["count"] == 1


# ── 切片 B：codex review BLOCKING 修复回归测试 ─────────────────────────────────
#
# 这些测试直接构造 ConnectionManager（ws.py 此时已存在，非 RED 阶段模块缺失），
# 不经 TestClient，单元级覆盖 WS loop lifecycle / Future 处理两个 BLOCKING。


def test_log_future_exception_ignores_cancelled() -> None:
    """BLOCKING 2：done-callback 对已 cancelled 的 Future 不自炸。

    concurrent.futures.Future.exception() 对 cancelled future 抛 CancelledError，
    若 callback 不先判 fut.cancelled() 就取 exception()，callback 自身崩。
    修前：_log_future_exception 直接 fut.exception() → CancelledError 冒泡。
    修后：callback 开头 if fut.cancelled(): return → 安全 no-op。
    """
    from concurrent.futures import Future

    from backend.api.ws import ConnectionManager

    fut: Future[object] = Future()
    fut.cancel()
    assert fut.cancelled()

    # 不抛即通过（修前会抛 CancelledError）。
    ConnectionManager._log_future_exception(fut)


def test_broadcast_noop_after_loop_cleared() -> None:
    """shutdown 清 loop（set_loop(None)）后 broadcast 安全 no-op，不抛。

    覆盖 lifespan shutdown 段 cm.set_loop(None) 后的安全性。命中 _loop is None 守卫，
    基线已绿（保留作回归，确保 None 守卫永远在 is_running() 之前短路）。
    """
    from backend.api.ws import ConnectionManager
    from backend.core.events import TAKE_CHANGED, TakeChangedPayload

    cm = ConnectionManager()
    cm.set_loop(None)

    payload = TakeChangedPayload(
        take_id=1,
        scene_id=1,
        take_number=1,
        status="tbd",
        script_diff=None,
    )
    # 不抛即通过（None 守卫 no-op）。
    cm.broadcast(TAKE_CHANGED, payload)


# ── 1.J-1.L 新增：GET 端点 / llm.status 转发 / dev ASR 注入 / llm_service lifecycle ──


def test_list_takes_empty_returns_200(tmp_dal: DAL, monkeypatch) -> None:
    """GET /api/v1/takes（带 token）→ 200，body {"takes":[]}。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.get("/api/v1/takes", headers={"Authorization": f"Bearer {_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json() == {"takes": []}


def test_list_takes_returns_all(tmp_dal: DAL, monkeypatch) -> None:
    """写两条 take → GET /api/v1/takes 返回 len==2。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    headers = {"Authorization": f"Bearer {_TOKEN}"}

    scene_id = tmp_dal.create_scene("scene_lt1")
    tmp_dal.set_active_scene(scene_id)  # 2.C：take/start 需要 active scene
    # 通过 REST 端点建 take（保证 session 状态正确）
    client.post("/api/v1/take/start", json={"scene_id": scene_id, "shot": "A"}, headers=headers)
    client.post("/api/v1/take/end", headers=headers)
    client.post("/api/v1/take/start", json={"scene_id": scene_id, "shot": "B"}, headers=headers)
    client.post("/api/v1/take/end", headers=headers)

    resp = client.get("/api/v1/takes", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["takes"]) == 2


def test_list_takes_scene_id_filter(tmp_dal: DAL, monkeypatch) -> None:
    """scene_1 + scene_2 各一条，?scene_id=scene_1 → 只返回 scene_1 的。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    headers = {"Authorization": f"Bearer {_TOKEN}"}

    scene1 = tmp_dal.create_scene("scene_f1a")
    scene2 = tmp_dal.create_scene("scene_f1b")
    # 2.C：take/start 需要 scene_id == active，交替激活
    tmp_dal.set_active_scene(scene1)
    client.post("/api/v1/take/start", json={"scene_id": scene1, "shot": None}, headers=headers)
    client.post("/api/v1/take/end", headers=headers)
    tmp_dal.set_active_scene(scene2)
    client.post("/api/v1/take/start", json={"scene_id": scene2, "shot": None}, headers=headers)
    client.post("/api/v1/take/end", headers=headers)

    resp = client.get(f"/api/v1/takes?scene_id={scene1}", headers=headers)
    assert resp.status_code == 200
    takes = resp.json()["takes"]
    assert len(takes) == 1
    assert takes[0]["scene_id"] == scene1


def test_list_takes_field_contract(tmp_dal: DAL, monkeypatch) -> None:
    """TakeDTO 含 11 个规定字段，有意省略 performer_issues / audio_quality。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    headers = {"Authorization": f"Bearer {_TOKEN}"}

    scene_id = tmp_dal.create_scene("scene_fc1")
    tmp_dal.set_active_scene(scene_id)  # 2.C：take/start 需要 active scene
    client.post("/api/v1/take/start", json={"scene_id": scene_id, "shot": "X"}, headers=headers)
    client.post("/api/v1/take/end", headers=headers)

    resp = client.get("/api/v1/takes", headers=headers)
    assert resp.status_code == 200
    take = resp.json()["takes"][0]

    required_fields = {
        "take_id", "scene_id", "take_number", "take_suffix", "shot",
        "start_ts", "end_ts", "status",
        "script_diff", "notes", "created_at", "updated_at",
    }
    assert required_fields.issubset(take.keys())
    # 有意省略字段不得出现
    assert "performer_issues" not in take
    assert "audio_quality" not in take


def test_list_takes_without_token_returns_401(tmp_dal: DAL, monkeypatch) -> None:
    """GET /api/v1/takes 无 Authorization 头 → 401。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.get("/api/v1/takes")
    assert resp.status_code == 401


def test_get_take_returns_detail_with_segments(tmp_dal: DAL, monkeypatch) -> None:
    """GET /api/v1/takes/{take_id} → 200，含 segments 列表。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    headers = {"Authorization": f"Bearer {_TOKEN}"}

    scene_id = tmp_dal.create_scene("scene_det1")
    tmp_dal.set_active_scene(scene_id)  # 2.C：take/start 需要 active scene
    client.post("/api/v1/take/start", json={"scene_id": scene_id, "shot": None}, headers=headers)
    # 直接用 DAL 插入 segment，避免需要 ASR pipeline
    take_id = tmp_dal.list_takes(scene_id)[0].take_id
    tmp_dal.insert_segment(take_id=take_id, ch=1, speaker="A", text="hello", start_frame=0, end_frame=1000)

    resp = client.get(f"/api/v1/takes/{take_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["take_id"] == take_id
    assert "segments" in body
    assert len(body["segments"]) == 1
    seg = body["segments"][0]
    assert seg["text"] == "hello"
    assert seg["ch"] == 1
    assert seg["speaker"] == "A"


def test_get_take_404_when_missing(tmp_dal: DAL, monkeypatch) -> None:
    """GET /api/v1/takes/999 → 404。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    headers = {"Authorization": f"Bearer {_TOKEN}"}

    resp = client.get("/api/v1/takes/999", headers=headers)
    assert resp.status_code == 404


def test_llm_status_forwarded_to_ws(tmp_dal: DAL, monkeypatch) -> None:
    """合成 publish llm.status → 已连 WS 收到 {"topic":"llm.status",...}。

    llm.status / LlmStatusPayload 导入放函数体内（RED 阶段这两个符号尚不存在，
    顶层 import 会炸掉 collection，令 35 条基线全红，分不清 feature-missing 还是 import 错）。
    """
    from backend.core.events import LLM_STATUS, LlmStatusPayload  # noqa: PLC0415

    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws?token={_TOKEN}") as ws:
            payload = LlmStatusPayload(state="loading", task_type="l2_take", take_id=1)
            t = threading.Thread(target=lambda: orch.publish(LLM_STATUS, payload))
            t.start()
            t.join()

            msg = _recv_until(ws, "llm.status")
            assert msg["payload"]["state"] == "loading"
            assert msg["payload"]["task_type"] == "l2_take"
            assert msg["payload"]["take_id"] == 1


def test_debug_asr_publishes_final(tmp_dal: DAL, monkeypatch) -> None:
    """SOUNDSPEED_DEV=1 挂载；POST /api/v1/debug/asr {is_partial:false} → orch 收到 ASR_FINAL_CH1。

    ASR_FINAL_CH1 / AsrFinalPayload 已在文件顶层 import（既有测试依赖），可直接用。
    """
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)
    client = TestClient(app)

    received: list[object] = []
    orch.subscribe(ASR_FINAL_CH1, lambda p: received.append(p))

    resp = client.post(
        "/api/v1/debug/asr",
        json={"ch": 1, "text": "hello debug", "speaker": "A", "is_partial": False},
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200
    assert len(received) == 1
    from backend.core.events import AsrFinalPayload  # noqa: PLC0415
    payload = received[0]
    assert isinstance(payload, AsrFinalPayload)
    assert payload.text == "hello debug"
    assert payload.speaker == "A"
    assert payload.is_partial is False


def test_debug_asr_publishes_partial(tmp_dal: DAL, monkeypatch) -> None:
    """SOUNDSPEED_DEV=1；is_partial:true → orch 收到 ASR_PARTIAL_CH1。"""
    from backend.core.events import ASR_PARTIAL_CH1  # noqa: PLC0415

    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)
    client = TestClient(app)

    received: list[object] = []
    orch.subscribe(ASR_PARTIAL_CH1, lambda p: received.append(p))

    resp = client.post(
        "/api/v1/debug/asr",
        json={"ch": 1, "text": "partial text", "speaker": None, "is_partial": True},
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200
    assert len(received) == 1
    from backend.core.events import AsrPartialPayload  # noqa: PLC0415
    payload = received[0]
    assert isinstance(payload, AsrPartialPayload)
    assert payload.text == "partial text"
    assert payload.is_partial is True


def test_debug_asr_final_persists_segment_when_take_active(tmp_dal: DAL, monkeypatch) -> None:
    """回归测试：active take 时 POST /debug/asr is_partial=false → 段写入 DB。

    smoke 发现的 bug：end_frame == start_frame 触发 CHECK(end_frame > start_frame)，
    sqlite3.IntegrityError 被 publish() 吞掉，段静默不存库（1.L take detail 为空）。
    修复后 end_frame = start_frame + 1000，此测试断言段确实写入。

    流程：先 POST take/start（session.take_active=True + take 行存在）→
    POST debug/asr ch=1 is_partial=false → dal.list_segments(take_id) 返回该段。
    """
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")
    scene_id = tmp_dal.create_scene("scene_debug_persist")
    tmp_dal.set_active_scene(scene_id)  # 2.C：take/start 需要 active scene
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_TOKEN}"}

    # 先起一个 take，使 session.take_active=True
    resp = client.post(
        "/api/v1/take/start",
        json={"scene_id": scene_id, "shot": None},
        headers=headers,
    )
    assert resp.status_code == 200
    take_id = tmp_dal.list_takes(scene_id)[0].take_id

    # 注入 final ASR（修复前会因 CHECK 约束失败静默丢弃）
    resp = client.post(
        "/api/v1/debug/asr",
        json={"ch": 1, "text": "injected segment", "speaker": "A", "is_partial": False},
        headers=headers,
    )
    assert resp.status_code == 200

    # 断言段已写入 DB（不是只推了 WS 就完）
    segments = tmp_dal.list_segments(take_id)
    assert len(segments) == 1, f"段应写库，实际 list_segments 返回 {len(segments)} 条"
    assert segments[0].text == "injected segment"
    assert segments[0].ch == 1
    assert segments[0].speaker == "A"
    # 顺带验证 end_frame > start_frame（约束合规）
    assert segments[0].end_frame > segments[0].start_frame


def test_debug_asr_absent_without_dev_flag(tmp_dal: DAL, monkeypatch) -> None:
    """SOUNDSPEED_DEV 未设 → POST /api/v1/debug/asr → 404（路由未挂载）。"""
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.delenv("SOUNDSPEED_DEV", raising=False)
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)
    client = TestClient(app)

    resp = client.post(
        "/api/v1/debug/asr",
        json={"ch": 1, "text": "x", "speaker": None, "is_partial": False},
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 404


# ── dev /debug/script 注入剧本 ───────────────────────────────────────────────


def test_debug_script_inserts_script_and_lines(tmp_dal: DAL, monkeypatch) -> None:
    """SOUNDSPEED_DEV=1：POST /debug/script → 200；script + lines 写入 DB 顺序正确。"""
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")
    scene_id = tmp_dal.create_scene("scene_script1")
    tmp_dal.set_active_scene(scene_id)
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_TOKEN}"}

    resp = client.post(
        "/api/v1/debug/script",
        json={
            "scene_id": scene_id,
            "lines": [
                {"character": "演员A", "text": "我不走。"},
                {"character": None, "text": "场景说明"},
                {"character": "演员B", "text": "你必须走。"},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["scene_id"] == scene_id
    assert body["line_count"] == 3
    script_id = body["script_id"]

    # script 行写入正确
    script = tmp_dal.get_latest_script(scene_id)
    assert script is not None
    assert script["script_id"] == script_id

    lines = tmp_dal.list_script_lines(script_id)
    assert len(lines) == 3
    assert lines[0]["line_no"] == 1
    assert lines[0]["text"] == "我不走。"
    assert lines[0]["character"] == "演员A"
    assert lines[1]["line_no"] == 2
    assert lines[1]["character"] is None
    assert lines[2]["line_no"] == 3
    assert lines[2]["text"] == "你必须走。"


def test_debug_script_uses_active_scene_when_no_scene_id(tmp_dal: DAL, monkeypatch) -> None:
    """scene_id 省略时回退 active scene。"""
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")
    scene_id = tmp_dal.create_scene("scene_script_active")
    tmp_dal.set_active_scene(scene_id)
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_TOKEN}"}

    resp = client.post(
        "/api/v1/debug/script",
        json={"lines": [{"character": "A", "text": "台词一"}]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["scene_id"] == scene_id


def test_debug_script_422_no_active_scene(tmp_dal: DAL, monkeypatch) -> None:
    """scene_id 未传 + 无 active scene → 422。"""
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_TOKEN}"}

    resp = client.post(
        "/api/v1/debug/script",
        json={"lines": [{"character": "A", "text": "台词"}]},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "no active scene" in resp.json()["detail"]


def test_debug_script_absent_without_dev_flag(tmp_dal: DAL, monkeypatch) -> None:
    """SOUNDSPEED_DEV 未设 → POST /debug/script → 404（路由未挂载）。"""
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.delenv("SOUNDSPEED_DEV", raising=False)
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)
    client = TestClient(app)

    resp = client.post(
        "/api/v1/debug/script",
        json={"lines": [{"character": "A", "text": "台词"}]},
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 404


def test_create_app_stores_llm_service(tmp_dal: DAL, monkeypatch) -> None:
    """create_app(orch, llm_service=stub) → app.state.llm_service is stub。"""
    from unittest.mock import MagicMock

    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    stub_llm = MagicMock()
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch, llm_service=stub_llm)
    assert app.state.llm_service is stub_llm


def test_lifespan_calls_aclose_on_shutdown(tmp_dal: DAL, monkeypatch) -> None:
    """TestClient with 块退出 → stub llm_service.aclose() 被 await 一次。"""
    from unittest.mock import AsyncMock, MagicMock

    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    stub_llm = MagicMock()
    stub_llm.aclose = AsyncMock()
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch, llm_service=stub_llm)

    with TestClient(app):
        pass  # 触发 lifespan startup + shutdown

    stub_llm.aclose.assert_awaited_once()


def test_entrypoint_build_app_healthz(tmp_path, monkeypatch) -> None:
    """build_app() → TestClient → GET /healthz == 200，llm_service 是 get_service() 单例。

    设 SOUNDSPEED_DB 指向 tmp_path，避免写 ./soundspeed.db。
    llm_service import 放函数体内，避免 RED 阶段符号不存在时炸 collection。
    """
    db_file = tmp_path / "entry_test.db"
    monkeypatch.setenv("SOUNDSPEED_DB", str(db_file))
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)

    from backend.api.entrypoint import build_app  # noqa: PLC0415
    from backend.llm.service import get_service  # noqa: PLC0415

    app = build_app()
    with TestClient(app) as client:
        resp = client.get("/healthz")
        assert resp.status_code == 200
    assert app.state.llm_service is get_service()


def test_default_db_path_is_repo_data_dir(monkeypatch) -> None:
    """不设 SOUNDSPEED_DB → 默认 DB 路径 = 仓库根下 data/soundspeed.db（绝对、持久）。"""
    from pathlib import Path  # noqa: PLC0415

    monkeypatch.delenv("SOUNDSPEED_DB", raising=False)
    from backend.api.entrypoint import _resolve_db_path  # noqa: PLC0415

    p = _resolve_db_path()
    repo_root = Path(__file__).resolve().parents[2]
    assert p == repo_root / "data" / "soundspeed.db"
    assert p.is_absolute()


def test_db_path_env_override_wins(monkeypatch, tmp_path) -> None:
    """显式 SOUNDSPEED_DB 优先于默认路径。"""
    custom = tmp_path / "custom.db"
    monkeypatch.setenv("SOUNDSPEED_DB", str(custom))
    from backend.api.entrypoint import _resolve_db_path  # noqa: PLC0415

    assert _resolve_db_path() == custom


def test_build_app_creates_db_when_missing(monkeypatch, tmp_path) -> None:
    """DB 路径不存在（连父目录都缺）→ build_app 自动创建新库。"""
    db_file = tmp_path / "fresh" / "soundspeed.db"  # 父目录 fresh/ 故意不存在
    monkeypatch.setenv("SOUNDSPEED_DB", str(db_file))
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    assert not db_file.exists()

    from backend.api.entrypoint import build_app  # noqa: PLC0415

    build_app()
    assert db_file.exists()


# ── DEV 固定 admin token ────────────────────────────────────────────────────
#
# resolve_admin_token 在函数体内 import（RED 阶段行为未改，顶层 import 会假绿），
# 实际上 resolve_admin_token 已在顶层 import 链里，可以直接用；
# 但 monkeypatch 必须在调用前设好 env（create_app 时读取）。


def test_dev_token_is_fixed_string(monkeypatch) -> None:
    """SOUNDSPEED_DEV=1 + ADMIN_TOKEN 未设 → resolve_admin_token() == "devtoken"。"""
    from backend.api.auth import resolve_admin_token  # noqa: PLC0415

    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")
    assert resolve_admin_token() == "devtoken"


def test_dev_token_env_wins(monkeypatch) -> None:
    """ADMIN_TOKEN 显式设置时 SOUNDSPEED_DEV 不覆盖，env 优先。"""
    from backend.api.auth import resolve_admin_token  # noqa: PLC0415

    monkeypatch.setenv("ADMIN_TOKEN", "explicit")
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")
    assert resolve_admin_token() == "explicit"


def test_non_dev_random_token(monkeypatch) -> None:
    """非 DEV + ADMIN_TOKEN 未设 → 返回非空随机 token（不等于 "devtoken"）。"""
    from backend.api.auth import resolve_admin_token  # noqa: PLC0415

    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("SOUNDSPEED_DEV", raising=False)
    token = resolve_admin_token()
    assert token  # 非空
    assert token != "devtoken"


def test_dev_token_auth_enforced(tmp_dal: DAL, monkeypatch) -> None:
    """DEV 模式下 token 固定为 "devtoken"，auth 仍生效：正确 token→200，错误 token→401。"""
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")
    scene_id = tmp_dal.create_scene("scene_dev_auth")
    tmp_dal.set_active_scene(scene_id)  # 2.C：take/start 需要 active scene
    orch = create_orchestrator(tmp_dal)
    # create_app 此时读 env：ADMIN_TOKEN 未设 + SOUNDSPEED_DEV=1 → admin_token="devtoken"
    app = create_app(orch)
    from fastapi.testclient import TestClient as _TC  # noqa: PLC0415
    client = _TC(app)

    # 正确 token → 200
    resp = client.post(
        "/api/v1/take/start",
        json={"scene_id": scene_id, "shot": None},
        headers={"Authorization": "Bearer devtoken"},
    )
    assert resp.status_code == 200

    # 错误 token → 401（auth 仍强制）
    resp = client.post(
        "/api/v1/take/start",
        json={"scene_id": scene_id, "shot": None},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401


# ── 1.J-1.L v0.3：GET /scenes + DEV 自动播种 ────────────────────────────────


def test_list_scenes_empty_returns_200(tmp_dal: DAL, monkeypatch) -> None:
    """GET /api/v1/scenes（带 token，空 DB）→ 200，body {"scenes":[]}。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.get("/api/v1/scenes", headers={"Authorization": f"Bearer {_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json() == {"scenes": []}


def test_list_scenes_returns_scenes_with_is_active(tmp_dal: DAL, monkeypatch) -> None:
    """GET /api/v1/scenes → 返回已建 scene，含 is_active 字段。"""
    sid = tmp_dal.create_scene("TestScene", description="desc")
    tmp_dal.set_active_scene(sid)

    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.get("/api/v1/scenes", headers={"Authorization": f"Bearer {_TOKEN}"})
    assert resp.status_code == 200
    scenes = resp.json()["scenes"]
    assert len(scenes) == 1
    scene = scenes[0]
    assert scene["scene_id"] == sid
    assert scene["scene_code"] == "TestScene"
    assert scene["is_active"] == 1


def test_list_scenes_without_token_returns_401(tmp_dal: DAL, monkeypatch) -> None:
    """GET /api/v1/scenes 无 Authorization 头 → 401。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.get("/api/v1/scenes")
    assert resp.status_code == 401


def test_dev_seed_creates_active_scene(tmp_path, monkeypatch) -> None:
    """build_app() + SOUNDSPEED_DEV=1 + 新鲜 DB → 恰好一个 active scene。

    断言走 orchestrator.dal.list_scenes()，直接查同一连接，不依赖 GET 端点。
    """
    from backend.api.entrypoint import build_app  # noqa: PLC0415

    db_file = tmp_path / "seed_test.db"
    monkeypatch.setenv("SOUNDSPEED_DB", str(db_file))
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")

    app = build_app()
    scenes = app.state.orchestrator.dal.list_scenes()
    assert len(scenes) == 1, f"播种后应有 1 个 scene，实际 {len(scenes)} 个"
    assert scenes[0]["scene_code"] == "1"
    assert scenes[0]["is_active"] == 1


def test_dev_seed_idempotent_on_restart(tmp_path, monkeypatch) -> None:
    """build_app() 二次调用（同一 DB）→ 仍只有 1 个 scene（不重复播种）。"""
    from backend.api.entrypoint import build_app  # noqa: PLC0415

    db_file = tmp_path / "seed_idem.db"
    monkeypatch.setenv("SOUNDSPEED_DB", str(db_file))
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")

    build_app()  # 第一次：播种
    app2 = build_app()  # 第二次：已有 scene，不再播种
    scenes = app2.state.orchestrator.dal.list_scenes()
    assert len(scenes) == 1, f"重启后仍应只有 1 个 scene，实际 {len(scenes)} 个"


def test_no_dev_seed_without_flag(tmp_path, monkeypatch) -> None:
    """build_app() 不带 SOUNDSPEED_DEV → DB 保持空（不播种）。"""
    from backend.api.entrypoint import build_app  # noqa: PLC0415

    db_file = tmp_path / "no_seed.db"
    monkeypatch.setenv("SOUNDSPEED_DB", str(db_file))
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.delenv("SOUNDSPEED_DEV", raising=False)

    app = build_app()
    scenes = app.state.orchestrator.dal.list_scenes()
    assert scenes == [], f"不带 SOUNDSPEED_DEV 时 scenes 应为空，实际 {scenes}"


def test_broadcast_noop_when_loop_not_running() -> None:
    """BLOCKING 1：loop 已建但未跑（stopped-but-not-closed）→ 跨线程 broadcast no-op。

    创建但从不 run 的 loop：is_closed() 为 False、is_running() 为 False。修前
    broadcast 只查 is_closed()，会走 else 分支 run_coroutine_threadsafe 把 coroutine
    调度到不跑的 loop → coroutine 泄漏。修后 is_running() 守卫直接 no-op。

    用 spy 替换 asyncio.run_coroutine_threadsafe 检测是否被调用：修前被调（RED），
    修后不被调（GREEN）。本测试在主线程跑，主线程无 running loop，
    asyncio.get_running_loop() 抛 RuntimeError → running=None → 命中跨线程 else 分支。
    """
    import asyncio as _asyncio

    from backend.api.ws import ConnectionManager
    from backend.core.events import TAKE_CHANGED, TakeChangedPayload

    loop = _asyncio.new_event_loop()  # 建但从不 run → not closed, not running
    try:
        assert not loop.is_closed()
        assert not loop.is_running()

        cm = ConnectionManager()
        cm.set_loop(loop)

        called = False

        def _spy(coro: object, target_loop: object):  # noqa: ANN202
            nonlocal called
            called = True
            coro.close()  # 防真泄漏（仅 spy 内）  # type: ignore[attr-defined]

        import backend.api.ws as ws_mod

        orig = ws_mod.asyncio.run_coroutine_threadsafe
        ws_mod.asyncio.run_coroutine_threadsafe = _spy  # type: ignore[assignment]
        try:
            payload = TakeChangedPayload(
                take_id=1,
                scene_id=1,
                take_number=1,
                status="tbd",
                script_diff=None,
            )
            cm.broadcast(TAKE_CHANGED, payload)
        finally:
            ws_mod.asyncio.run_coroutine_threadsafe = orig  # type: ignore[assignment]

        # 修前 called=True（调度到死 loop，泄漏）；修后 called=False（is_running 守卫 no-op）。
        assert called is False
    finally:
        loop.close()


# ── PATCH /takes/{take_id}/segments/{segment_id} ───────────────────────────

_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


def _seeded(tmp_dal: DAL) -> tuple[int, int, int]:
    """造 scene + take + ch1(有 speaker) + ch2(无 speaker)；返回 (take_id, ch1_seg, ch2_seg)。"""
    sid = tmp_dal.create_scene("scene_patch")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    ch1 = tmp_dal.insert_segment(tid, 1, "SPEAKER_00", "你好", 0, 16000)
    ch2 = tmp_dal.insert_segment(tid, 2, None, "杂音", 0, 16000)
    return tid, ch1, ch2


def test_patch_segment_speaker_valid(tmp_dal: DAL, monkeypatch) -> None:
    tid, ch1, _ = _seeded(tmp_dal)
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch(
        f"/api/v1/takes/{tid}/segments/{ch1}", json={"speaker": "SPEAKER_01"}, headers=_AUTH
    )
    assert resp.status_code == 200
    assert resp.json()["speaker"] == "SPEAKER_01"
    assert tmp_dal.get_segment(ch1).speaker == "SPEAKER_01"


def test_patch_segment_speaker_null(tmp_dal: DAL, monkeypatch) -> None:
    tid, ch1, _ = _seeded(tmp_dal)
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch(
        f"/api/v1/takes/{tid}/segments/{ch1}", json={"speaker": None}, headers=_AUTH
    )
    assert resp.status_code == 200
    assert resp.json()["speaker"] is None
    assert tmp_dal.get_segment(ch1).speaker is None


def test_patch_segment_speaker_blank_422(tmp_dal: DAL, monkeypatch) -> None:
    tid, ch1, _ = _seeded(tmp_dal)
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch(
        f"/api/v1/takes/{tid}/segments/{ch1}", json={"speaker": "   "}, headers=_AUTH
    )
    assert resp.status_code == 422


def test_patch_segment_missing_404(tmp_dal: DAL, monkeypatch) -> None:
    tid, _, _ = _seeded(tmp_dal)
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch(
        f"/api/v1/takes/{tid}/segments/99999", json={"speaker": "X"}, headers=_AUTH
    )
    assert resp.status_code == 404


def test_patch_segment_wrong_take_404(tmp_dal: DAL, monkeypatch) -> None:
    tid, ch1, _ = _seeded(tmp_dal)
    other, _ = tmp_dal.start_take(tmp_dal.create_scene("other"), "1", 2000.0)
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch(
        f"/api/v1/takes/{other}/segments/{ch1}", json={"speaker": "X"}, headers=_AUTH
    )
    assert resp.status_code == 404


def test_patch_segment_take_not_found_404(tmp_dal: DAL, monkeypatch) -> None:
    _, ch1, _ = _seeded(tmp_dal)
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch(
        f"/api/v1/takes/99999/segments/{ch1}", json={"speaker": "X"}, headers=_AUTH
    )
    assert resp.status_code == 404


def test_patch_segment_ch2_422(tmp_dal: DAL, monkeypatch) -> None:
    tid, _, ch2 = _seeded(tmp_dal)
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch(
        f"/api/v1/takes/{tid}/segments/{ch2}", json={"speaker": "X"}, headers=_AUTH
    )
    assert resp.status_code == 422


def test_patch_segment_no_token_401(tmp_dal: DAL, monkeypatch) -> None:
    tid, ch1, _ = _seeded(tmp_dal)
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch(f"/api/v1/takes/{tid}/segments/{ch1}", json={"speaker": "X"})
    assert resp.status_code == 401


def test_patch_segment_does_not_touch_script_diff(tmp_dal: DAL, monkeypatch) -> None:
    tid, ch1, _ = _seeded(tmp_dal)
    tmp_dal.update_take_l2_output(tid, {"script_diff_summary": "原始", "line_matches": [], "corrected_segments": []})
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    client.patch(f"/api/v1/takes/{tid}/segments/{ch1}", json={"speaker": "SPEAKER_09"}, headers=_AUTH)
    detail = client.get(f"/api/v1/takes/{tid}", headers=_AUTH).json()
    assert detail["script_diff"]["script_diff_summary"] == "原始"


# ── 2.C：POST /scenes 建场 ──────────────────────────────────────────────────


def test_post_scenes_creates_new_scene(tmp_dal: DAL, monkeypatch) -> None:
    """POST /api/v1/scenes 新 scene_code → 200，created=True。"""
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.post(
        "/api/v1/scenes",
        json={"scene_code": "SceneNew_1"},
        headers=_AUTH,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["scene_code"] == "SceneNew_1"
    assert body["created"] is True
    assert isinstance(body["scene_id"], int)
    assert "is_active" in body


def test_post_scenes_idempotent_returns_created_false(tmp_dal: DAL, monkeypatch) -> None:
    """POST /api/v1/scenes 已有 scene_code → 200，created=False，返回既有 scene_id。"""
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp1 = client.post("/api/v1/scenes", json={"scene_code": "SceneIdem"}, headers=_AUTH)
    resp2 = client.post("/api/v1/scenes", json={"scene_code": "SceneIdem"}, headers=_AUTH)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp2.json()["created"] is False
    assert resp2.json()["scene_id"] == resp1.json()["scene_id"]


def test_post_scenes_missing_scene_code_422(tmp_dal: DAL, monkeypatch) -> None:
    """POST /api/v1/scenes 缺少 scene_code → 422。"""
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.post("/api/v1/scenes", json={}, headers=_AUTH)
    assert resp.status_code == 422


def test_post_scenes_no_token_401(tmp_dal: DAL, monkeypatch) -> None:
    """POST /api/v1/scenes 无 token → 401。"""
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.post("/api/v1/scenes", json={"scene_code": "SceneNoAuth"})
    assert resp.status_code == 401


# ── 2.C：POST /scenes/{scene_id}/activate ──────────────────────────────────


def test_activate_scene_success(tmp_dal: DAL, monkeypatch) -> None:
    """POST /scenes/{scene_id}/activate → 200，返回 scene_id + scene_code。"""
    sid = tmp_dal.create_scene("SceneActivate_1")
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.post(f"/api/v1/scenes/{sid}/activate", headers=_AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["scene_id"] == sid
    assert body["scene_code"] == "SceneActivate_1"
    # 确认 DB 里 is_active 已更新
    active_id = tmp_dal.get_active_scene_id()
    assert active_id == sid


def test_activate_scene_not_found_404(tmp_dal: DAL, monkeypatch) -> None:
    """POST /scenes/99999/activate → 404。"""
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.post("/api/v1/scenes/99999/activate", headers=_AUTH)
    assert resp.status_code == 404


def test_activate_scene_during_recording_409(tmp_dal: DAL, monkeypatch) -> None:
    """录制中（session.take_active=True）激活场次 → 409 take_in_progress。"""
    sid = tmp_dal.create_scene("SceneActivateLocked")
    tmp_dal.set_active_scene(sid)

    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    headers = _AUTH

    # 先起一个 take，让 session.take_active=True
    client.post("/api/v1/take/start", json={"scene_id": sid, "shot": None}, headers=headers)
    assert orch.session.take_active is True

    sid2 = tmp_dal.create_scene("SceneActivateLocked_2")
    resp = client.post(f"/api/v1/scenes/{sid2}/activate", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "take_in_progress"


def test_activate_scene_publishes_scene_changed(tmp_dal: DAL, monkeypatch) -> None:
    """POST /activate → orchestrator publish SCENE_CHANGED。"""
    from backend.core.events import SCENE_CHANGED, SceneChangedPayload  # noqa: PLC0415

    sid = tmp_dal.create_scene("SceneActivateWS")
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    received: list[object] = []
    orch.subscribe(SCENE_CHANGED, lambda p: received.append(p))

    client.post(f"/api/v1/scenes/{sid}/activate", headers=_AUTH)

    assert len(received) == 1
    p = received[0]
    assert isinstance(p, SceneChangedPayload)
    assert p.scene_id == sid
    assert p.scene_code == "SceneActivateWS"
    assert p.is_active is True


# ── 2.C：take.start scene 校验 ─────────────────────────────────────────────


def test_take_start_scene_not_active_409(tmp_dal: DAL, monkeypatch) -> None:
    """take/start scene_id != active → 409 scene_not_active，payload 含 active_scene_id。"""
    sid1 = tmp_dal.create_scene("SceneActive")
    sid2 = tmp_dal.create_scene("SceneNotActive")
    tmp_dal.set_active_scene(sid1)

    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.post(
        "/api/v1/take/start",
        json={"scene_id": sid2, "shot": None},
        headers=_AUTH,
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["error"] == "scene_not_active"
    assert body["detail"]["active_scene_id"] == sid1


def test_take_start_no_active_scene_409(tmp_dal: DAL, monkeypatch) -> None:
    """无 active scene 时 take/start → 409 scene_not_active，active_scene_id=None。"""
    sid = tmp_dal.create_scene("SceneNoActive")
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.post(
        "/api/v1/take/start",
        json={"scene_id": sid, "shot": None},
        headers=_AUTH,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "scene_not_active"


# ── 2.C：PATCH /takes/{take_id} ────────────────────────────────────────────


def _make_take(tmp_dal: DAL, scene_code: str = "ScenePatch") -> tuple[int, int]:
    """建场+激活+开 take+结束 take，返回 (scene_id, take_id)。"""
    sid = tmp_dal.create_scene(scene_code)
    tmp_dal.set_active_scene(sid)
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    tmp_dal.end_take(tid, 1060.0, "tbd")
    return sid, tid


def test_patch_take_status(tmp_dal: DAL, monkeypatch) -> None:
    """PATCH /takes/{id} status=keep → 200，状态改变，有 take_events manual.mark。"""
    sid, tid = _make_take(tmp_dal, "ScenePatchStatus")
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch(f"/api/v1/takes/{tid}", json={"status": "keep"}, headers=_AUTH)
    assert resp.status_code == 200
    assert resp.json()["status"] == "keep"
    # DAL 里 status 已更新
    updated_take = tmp_dal.get_take(tid)
    assert updated_take is not None
    assert updated_take.status == "keep"
    # take_events 有 manual.mark 记录
    evts = tmp_dal.list_take_events(tid, event_type="manual.mark")
    assert len(evts) >= 1


def test_patch_take_invalid_status_422(tmp_dal: DAL, monkeypatch) -> None:
    """status 非法值 → 422（pydantic Literal 拦）。"""
    _, tid = _make_take(tmp_dal, "ScenePatchBadStatus")
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch(f"/api/v1/takes/{tid}", json={"status": "bad_value"}, headers=_AUTH)
    assert resp.status_code == 422


def test_patch_take_notes(tmp_dal: DAL, monkeypatch) -> None:
    """PATCH /takes/{id} notes → 200，notes 已更新。"""
    _, tid = _make_take(tmp_dal, "ScenePatchNotes")
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch(f"/api/v1/takes/{tid}", json={"notes": "NG 原因：灯光"}, headers=_AUTH)
    assert resp.status_code == 200
    assert resp.json()["notes"] == "NG 原因：灯光"


def test_patch_take_shot(tmp_dal: DAL, monkeypatch) -> None:
    """PATCH /takes/{id} shot → 200，shot 已更新。"""
    _, tid = _make_take(tmp_dal, "ScenePatchShot")
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch(f"/api/v1/takes/{tid}", json={"shot": "B"}, headers=_AUTH)
    assert resp.status_code == 200
    assert resp.json()["shot"] == "B"


def test_patch_take_number_suffix_when_conflict(tmp_dal: DAL, monkeypatch) -> None:
    """同场内改 take_number 撞已占用号 → 追加 '+' 后缀（不再交换），两条 take 各自保持编号。"""
    sid = tmp_dal.create_scene("ScenePatchSuffix")
    tmp_dal.set_active_scene(sid)
    # 两次 start_take 在同 shot="1" 组内，分别拿到 number=1, 2
    t1, _ = tmp_dal.start_take(sid, "1", 1000.0)   # shot="1", number=1
    tmp_dal.end_take(t1, 1010.0, "keep")
    t2, _ = tmp_dal.start_take(sid, "1", 1020.0)   # shot="1", number=2
    tmp_dal.end_take(t2, 1030.0, "ng")

    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    # 把 t1 的编号改为 2，已被 t2 占用 → t1 得到 suffix='+'，take_number=2
    resp = client.patch(f"/api/v1/takes/{t1}", json={"take_number": 2}, headers=_AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["take_number"] == 2
    assert body["take_suffix"] == "+"

    # t2 编号保持 2，suffix 仍 ''
    t2_updated = tmp_dal.get_take(t2)
    assert t2_updated is not None
    assert t2_updated.take_number == 2
    assert t2_updated.take_suffix == ""


def test_patch_take_scene_id_cross_scene_conflict_uses_suffix(tmp_dal: DAL, monkeypatch) -> None:
    """跨场移动，目标 (scene_id, shot, take_number, '') 已占用 → 追加后缀（不再 409）。"""
    sid1 = tmp_dal.create_scene("ScenePatchCross1")
    sid2 = tmp_dal.create_scene("ScenePatchCross2")
    tmp_dal.set_active_scene(sid1)

    t1, _ = tmp_dal.start_take(sid1, "1", 1000.0)   # shot="1", number=1
    tmp_dal.end_take(t1, 1010.0, "keep")
    t2, _ = tmp_dal.start_take(sid2, "1", 1020.0)   # shot="1", number=1（不同场）
    tmp_dal.end_take(t2, 1030.0, "keep")

    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    # 把 t1 移到 sid2 且指定 take_number=1（已被 t2 占用），应追加后缀而非 409
    resp = client.patch(f"/api/v1/takes/{t1}", json={"scene_id": sid2, "take_number": 1}, headers=_AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["scene_id"] == sid2
    assert body["take_number"] == 1
    assert body["take_suffix"] == "+"


def test_patch_take_scene_id_invalid_404(tmp_dal: DAL, monkeypatch) -> None:
    """改 scene_id 到不存在的场次 → 404。"""
    _, tid = _make_take(tmp_dal, "ScenePatchBadScene")
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch(f"/api/v1/takes/{tid}", json={"scene_id": 99999}, headers=_AUTH)
    assert resp.status_code == 404


def test_patch_take_recording_change_scene_409(tmp_dal: DAL, monkeypatch) -> None:
    """录制中（end_ts IS NULL）改 scene_id → 409 take_in_progress。"""
    sid = tmp_dal.create_scene("ScenePatchRecording")
    tmp_dal.set_active_scene(sid)

    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    headers = _AUTH

    # 开 take，不结束（end_ts IS NULL）
    client.post("/api/v1/take/start", json={"scene_id": sid, "shot": None}, headers=headers)
    tid = tmp_dal.list_takes(sid)[0].take_id

    sid2 = tmp_dal.create_scene("ScenePatchRecording2")
    resp = client.patch(f"/api/v1/takes/{tid}", json={"scene_id": sid2}, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "take_in_progress"


def test_patch_take_recording_change_notes_ok(tmp_dal: DAL, monkeypatch) -> None:
    """录制中改 notes 允许（200）。"""
    sid = tmp_dal.create_scene("ScenePatchRecordingNotes")
    tmp_dal.set_active_scene(sid)

    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    headers = _AUTH

    client.post("/api/v1/take/start", json={"scene_id": sid, "shot": None}, headers=headers)
    tid = tmp_dal.list_takes(sid)[0].take_id

    resp = client.patch(f"/api/v1/takes/{tid}", json={"notes": "现场备注"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["notes"] == "现场备注"


def test_patch_take_not_found_404(tmp_dal: DAL, monkeypatch) -> None:
    """PATCH /takes/99999 → 404。"""
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.patch("/api/v1/takes/99999", json={"notes": "x"}, headers=_AUTH)
    assert resp.status_code == 404


def test_patch_take_publishes_take_changed(tmp_dal: DAL, monkeypatch) -> None:
    """PATCH 成功后 orchestrator publish TAKE_CHANGED。"""
    from backend.core.events import TAKE_CHANGED, TakeChangedPayload  # noqa: PLC0415

    _, tid = _make_take(tmp_dal, "ScenePatchWS")
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    received: list[object] = []
    orch.subscribe(TAKE_CHANGED, lambda p: received.append(p))

    client.patch(f"/api/v1/takes/{tid}", json={"status": "ng"}, headers=_AUTH)

    assert len(received) == 1
    p = received[0]
    assert isinstance(p, TakeChangedPayload)
    assert p.take_id == tid
    assert p.status == "ng"


# ── 2.C：DELETE /takes/{take_id}（软删）──────────────────────────────────────


def test_delete_take_success_204_soft_delete(tmp_dal: DAL, monkeypatch) -> None:
    """DELETE /takes/{id} → 204；软删后 get_take 返 None（API 排除软删），但物理行保留。"""
    _, tid = _make_take(tmp_dal, "SceneDelete")
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.delete(f"/api/v1/takes/{tid}", headers=_AUTH)
    assert resp.status_code == 204
    # API get_take 排除软删行 → None
    assert tmp_dal.get_take(tid) is None
    # 物理行仍存在，deleted_at 已设置
    row = tmp_dal._conn.execute(
        "SELECT deleted_at FROM takes WHERE take_id = ?;", (tid,)
    ).fetchone()
    assert row is not None and row["deleted_at"] is not None


def test_delete_take_not_found_404(tmp_dal: DAL, monkeypatch) -> None:
    """DELETE /takes/99999 → 404（连软删行都没有）。"""
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.delete("/api/v1/takes/99999", headers=_AUTH)
    assert resp.status_code == 404


def test_delete_take_already_soft_deleted_404(tmp_dal: DAL, monkeypatch) -> None:
    """已软删的 take 再次 DELETE → 404（get_take 排除软删行，视为不存在）。"""
    _, tid = _make_take(tmp_dal, "SceneDeleteAgain")
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    # 第一次软删
    resp1 = client.delete(f"/api/v1/takes/{tid}", headers=_AUTH)
    assert resp1.status_code == 204
    # 第二次应该 404（已软删，get_take 返 None）
    resp2 = client.delete(f"/api/v1/takes/{tid}", headers=_AUTH)
    assert resp2.status_code == 404


def test_delete_take_recording_409(tmp_dal: DAL, monkeypatch) -> None:
    """录制中（end_ts IS NULL）删除 → 409 take_in_progress。"""
    sid = tmp_dal.create_scene("SceneDeleteRecording")
    tmp_dal.set_active_scene(sid)

    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    headers = _AUTH

    client.post("/api/v1/take/start", json={"scene_id": sid, "shot": None}, headers=headers)
    tid = tmp_dal.list_takes(sid)[0].take_id

    resp = client.delete(f"/api/v1/takes/{tid}", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "take_in_progress"


def test_delete_take_publishes_take_deleted(tmp_dal: DAL, monkeypatch) -> None:
    """DELETE 成功后 orchestrator publish TAKE_DELETED。"""
    from backend.core.events import TAKE_DELETED, TakeDeletedPayload  # noqa: PLC0415

    sid, tid = _make_take(tmp_dal, "SceneDeleteWS")
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    received: list[object] = []
    orch.subscribe(TAKE_DELETED, lambda p: received.append(p))

    client.delete(f"/api/v1/takes/{tid}", headers=_AUTH)

    assert len(received) == 1
    p = received[0]
    assert isinstance(p, TakeDeletedPayload)
    assert p.take_id == tid
    assert p.scene_id == sid


# ── 2.C：POST /takes/{take_id}/restore ─────────────────────────────────────


def test_restore_take_success(tmp_dal: DAL, monkeypatch) -> None:
    """POST /takes/{id}/restore → 200，恢复软删 take，返回更新后的 TakeDTO。"""
    _, tid = _make_take(tmp_dal, "SceneRestore")
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    # 先软删
    client.delete(f"/api/v1/takes/{tid}", headers=_AUTH)
    assert tmp_dal.get_take(tid) is None
    # 再 restore
    resp = client.post(f"/api/v1/takes/{tid}/restore", headers=_AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["take_id"] == tid
    assert body["deleted_at"] is None
    # DAL 也能读到了
    restored = tmp_dal.get_take(tid)
    assert restored is not None


def test_restore_take_not_found_404(tmp_dal: DAL, monkeypatch) -> None:
    """POST /takes/99999/restore → 404（连软删都没有）。"""
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    resp = client.post("/api/v1/takes/99999/restore", headers=_AUTH)
    assert resp.status_code == 404


def test_restore_take_not_deleted_404(tmp_dal: DAL, monkeypatch) -> None:
    """对未软删的 take POST restore → 404（不能 restore 未删除的 take；
    或者返回当前 take 即可，这里按「not deleted」语义返 404）。"""
    _, tid = _make_take(tmp_dal, "SceneRestoreNotDeleted")
    client = _make_client(create_orchestrator(tmp_dal), monkeypatch)
    # take 未软删，restore 应 404（没有被删的 take 可恢复）
    resp = client.post(f"/api/v1/takes/{tid}/restore", headers=_AUTH)
    assert resp.status_code == 404


# ── TakeDTO 含 take_suffix ──────────────────────────────────────────────────


def test_takedto_has_take_suffix_field(tmp_dal: DAL, monkeypatch) -> None:
    """TakeDTO 含 take_suffix 字段。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)
    headers = _AUTH

    scene_id = tmp_dal.create_scene("scene_dto_suffix")
    tmp_dal.set_active_scene(scene_id)
    client.post("/api/v1/take/start", json={"scene_id": scene_id, "shot": None}, headers=headers)
    client.post("/api/v1/take/end", headers=headers)

    resp = client.get("/api/v1/takes", headers=headers)
    assert resp.status_code == 200
    take = resp.json()["takes"][0]
    assert "take_suffix" in take


# ── POST /api/v1/debug/reset-db ──────────────────────────────────────────────


def test_debug_reset_db_clears_and_reseeds(tmp_dal: DAL, monkeypatch) -> None:
    """SOUNDSPEED_DEV=1 + 正确 token：造数据 → POST /debug/reset-db → 200；
    库被清空，恰好剩 1 个 active scene。"""
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")

    # 造点数据
    sid = tmp_dal.create_scene("scene_before_reset")
    tmp_dal.set_active_scene(sid)
    tmp_dal.start_take(sid, "", 100.0)

    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)
    client = TestClient(app)

    resp = client.post(
        "/api/v1/debug/reset-db",
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["reseeded"] is True

    # 验证恰好剩 1 个 active scene
    scenes = tmp_dal.list_scenes()
    assert len(scenes) == 1
    assert scenes[0]["is_active"] == 1


def test_debug_reset_db_absent_without_dev_flag(tmp_dal: DAL, monkeypatch) -> None:
    """SOUNDSPEED_DEV 未设 → POST /debug/reset-db → 404（路由未挂载）。"""
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.delenv("SOUNDSPEED_DEV", raising=False)
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)
    client = TestClient(app)

    resp = client.post(
        "/api/v1/debug/reset-db",
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 404


def test_debug_reset_db_no_token_returns_401(tmp_dal: DAL, monkeypatch) -> None:
    """SOUNDSPEED_DEV=1 + 无 token → 401。"""
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)
    client = TestClient(app)

    resp = client.post("/api/v1/debug/reset-db")
    assert resp.status_code == 401


def test_debug_reset_db_wrong_token_returns_401(tmp_dal: DAL, monkeypatch) -> None:
    """SOUNDSPEED_DEV=1 + 错误 token → 401。"""
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)
    client = TestClient(app)

    resp = client.post(
        "/api/v1/debug/reset-db",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


# ── POST /notes/voice 语音 note 端点（4.K）──────────────────────────────────────


def _auth() -> dict:
    return {"Authorization": f"Bearer {_TOKEN}"}


def test_notes_voice_without_token_returns_401(tmp_dal: DAL, monkeypatch) -> None:
    """无 Authorization → 401。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        "/api/v1/notes/voice",
        files={"file": ("note.wav", b"RIFFxxxxWAVE", "audio/wav")},
        data={"client_id": "cid-1"},
    )
    assert resp.status_code == 401


def test_notes_voice_happy_returns_202_and_calls_orchestrator(tmp_dal: DAL, monkeypatch) -> None:
    """合法 multipart（file + client_id + ts）→ 202 {status:processing, client_id}，
    且 orchestrator.run_np_voice_async 收到 audio 字节 + client_id + ts。"""
    orch = create_orchestrator(tmp_dal)
    captured: dict = {}
    orch.run_np_voice_async = lambda **kw: captured.update(kw)  # type: ignore[method-assign]
    client = _make_client(orch, monkeypatch)

    wav = b"RIFF\x00\x00\x00\x00WAVEfmt fake-pcm16-mono"
    resp = client.post(
        "/api/v1/notes/voice",
        files={"file": ("note.wav", wav, "audio/wav")},
        data={"client_id": "cid-voice-1", "ts": "123.5"},
        headers=_auth(),
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "processing"
    assert body["client_id"] == "cid-voice-1"
    assert captured["audio"] == wav
    assert captured["client_id"] == "cid-voice-1"
    assert captured["ts"] == 123.5


def test_notes_voice_empty_file_returns_400(tmp_dal: DAL, monkeypatch) -> None:
    """空音频 → 400（不进 NP）。"""
    orch = create_orchestrator(tmp_dal)
    called: list = []
    orch.run_np_voice_async = lambda **kw: called.append(kw)  # type: ignore[method-assign]
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        "/api/v1/notes/voice",
        files={"file": ("note.wav", b"", "audio/wav")},
        data={"client_id": "cid-2"},
        headers=_auth(),
    )
    assert resp.status_code == 400
    assert called == []


def test_notes_voice_oversized_returns_400(tmp_dal: DAL, monkeypatch) -> None:
    """音频超限 → 400（不进 NP）。"""
    orch = create_orchestrator(tmp_dal)
    called: list = []
    orch.run_np_voice_async = lambda **kw: called.append(kw)  # type: ignore[method-assign]
    client = _make_client(orch, monkeypatch)

    big = b"RIFF" + b"\x00" * (11 * 1024 * 1024)  # 11MB > 10MB 上限
    resp = client.post(
        "/api/v1/notes/voice",
        files={"file": ("big.wav", big, "audio/wav")},
        data={"client_id": "cid-3"},
        headers=_auth(),
    )
    assert resp.status_code == 400
    assert called == []


def test_notes_voice_missing_client_id_returns_422(tmp_dal: DAL, monkeypatch) -> None:
    """client_id 必填，缺失 → 422（FastAPI Form 校验）。"""
    orch = create_orchestrator(tmp_dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        "/api/v1/notes/voice",
        files={"file": ("note.wav", b"RIFFxxxxWAVE", "audio/wav")},
        headers=_auth(),
    )
    assert resp.status_code == 422


# ── DEVICE_WARNING / AUDIO_LEVEL WS 转发测试 ─────────────────────────────────


def test_device_warning_forwarded_to_ws(tmp_dal: DAL, monkeypatch) -> None:
    """publish device.warning → 已连 WS 收到 {"topic":"device.warning",...}。

    DEVICE_WARNING / DeviceWarningPayload 导入放函数体内（RED 阶段常量或转发注册
    尚未到位时，顶层 import 不炸，分得清「feature-missing」还是「import 错」）。
    """
    from backend.core.events import DEVICE_WARNING, DeviceWarningPayload  # noqa: PLC0415

    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws?token={_TOKEN}") as ws:
            payload = DeviceWarningPayload(
                message="设备已断开", device_name="MacBook Pro 麦克风"
            )
            t = threading.Thread(target=lambda: orch.publish(DEVICE_WARNING, payload))
            t.start()
            t.join()

            msg = _recv_until(ws, "device.warning")
            assert msg["payload"]["message"] == "设备已断开"
            assert msg["payload"]["device_name"] == "MacBook Pro 麦克风"


def test_audio_level_forwarded_to_ws(tmp_dal: DAL, monkeypatch) -> None:
    """publish audio.level → 已连 WS 收到 {"topic":"audio.level","payload":{"rms":...}}。

    AUDIO_LEVEL / AudioLevelPayload 导入放函数体内（RED 阶段两者尚不存在）。
    """
    from backend.core.events import AUDIO_LEVEL, AudioLevelPayload  # noqa: PLC0415

    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    orch = create_orchestrator(tmp_dal)
    app = create_app(orch)

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws?token={_TOKEN}") as ws:
            payload = AudioLevelPayload(rms=0.42)
            t = threading.Thread(target=lambda: orch.publish(AUDIO_LEVEL, payload))
            t.start()
            t.join()

            msg = _recv_until(ws, "audio.level")
            assert abs(msg["payload"]["rms"] - 0.42) < 1e-6
