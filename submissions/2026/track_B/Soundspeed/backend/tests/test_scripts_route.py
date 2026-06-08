"""3.D scripts 路由测试（两段式 + 异步解析）：
  POST /scripts/upload             只提取 + 入库（不碰 LLM）
  GET  /scripts/uploads            列出上传记录
  POST /scripts/uploads/{id}/parse 启动后台解析，立即返回 status=parsing
  run_parse_job                    后台任务：逐场结构化 + 入库（直接单测）
  POST /scripts/import/confirm     重复场确认替换（直接构造 plan 测）

后台任务里的 split_for_parse / parse_scene_block 在 run_parse_job 单测中被 monkeypatch，
不跑真 Gemma；其余链路（extract_text、DAL 入库、plan_import/apply_import）全真。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.routes.scripts import router as scripts_router, run_parse_job
from backend.core.orchestrator import create_orchestrator
from backend.db.dal import DAL
from backend.pipelines.sp_script import ParsedLine, ParsedScene, Slugline

_TOKEN = "test-admin-token"
_HEADERS = {"Authorization": f"Bearer {_TOKEN}"}


class _FakeLLM:
    """最小假 llm_service：非 None（过门控）+ async aclose（过 lifespan shutdown）。"""

    async def aclose(self) -> None:
        pass


def _scene(code, lines, *, int_ext=None, tod=None, loc=None):
    return ParsedScene(
        scene_code=code,
        slugline=Slugline(int_ext=int_ext, time_of_day=tod, location=loc),
        lines=[ParsedLine(character=c, text=t) for c, t in lines],
    )


def _client(tmp_dal: DAL, monkeypatch, *, llm=True) -> TestClient:
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    app = create_app(
        create_orchestrator(tmp_dal), llm_service=_FakeLLM() if llm else None
    )
    app.include_router(scripts_router)
    return TestClient(app)


def _upload(c: TestClient, content=b"x", name="script.txt"):
    return c.post(
        "/api/v1/scripts/upload",
        files={"file": (name, content, "text/plain")},
        headers=_HEADERS,
    )


def _parse(c: TestClient, upload_id: int, target="multi_scene"):
    return c.post(
        f"/api/v1/scripts/uploads/{upload_id}/parse?target={target}",
        headers=_HEADERS,
    )


def _patch_parse(monkeypatch, blocks, per_block_scenes):
    """monkeypatch split_for_parse → 固定块；parse_scene_block → 按块顺序返回 scenes。"""
    monkeypatch.setattr(
        "backend.api.routes.scripts.split_for_parse", lambda raw, **k: blocks
    )
    it = iter(per_block_scenes)

    async def _fake_block(block, llm, **k):
        return next(it)

    monkeypatch.setattr("backend.api.routes.scripts.parse_scene_block", _fake_block)


# ── 无号场内容指纹（_block_fingerprint）──────────────────────────────────────


def test_block_fingerprint_stable_and_ws_insensitive():
    """同源块（含空白抖动）→ 同指纹；不同内容 → 不同指纹。无号场重传复用同场的基础。"""
    from backend.api.routes.scripts import _block_fingerprint

    a = _block_fingerprint("场1 内 咖啡馆 日\n罗湘：你好。")
    b = _block_fingerprint("场1 内 咖啡馆 日\n 罗湘：你好。 ")  # 换行/缩进抖动
    c = _block_fingerprint("场2 外 广场 夜\n阿明：再见。")
    assert a == b  # 去空白后内容相同 → 指纹相同（重传幂等）
    assert a != c  # 内容不同 → 指纹不同
    assert len(a) == 12 and all(ch in "0123456789abcdef" for ch in a)


# ── 阶段 1：上传（只入库，不碰 LLM）─────────────────────────────────────────


def test_upload_saves_only(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:
        r = _upload(c, content="内 咖啡馆 日\n罗湘：你好。".encode(), name="双日.txt")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "uploaded"
        assert body["filename"] == "双日.txt"
        assert body["char_count"] > 0
        uid = body["upload_id"]
        uploads = tmp_dal.list_script_uploads()
        assert [u["upload_id"] for u in uploads] == [uid]
        assert uploads[0]["status"] == "uploaded"


def test_upload_works_without_llm(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch, llm=False) as c:
        assert _upload(c, content="有内容".encode()).status_code == 200


def test_upload_empty_text_422(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:
        assert _upload(c, content=b"   \n  ").status_code == 422


def test_upload_unsupported_format_415(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:
        assert _upload(c, content=b"data", name="x.rtf").status_code == 415


def test_upload_requires_auth(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:
        r = c.post(
            "/api/v1/scripts/upload",
            files={"file": ("a.txt", b"x", "text/plain")},
        )
        assert r.status_code == 401


def test_list_uploads(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:
        _upload(c, content="aaa".encode(), name="a.txt")
        _upload(c, content="bbb".encode(), name="b.txt")
        r = c.get("/api/v1/scripts/uploads", headers=_HEADERS)
        assert r.status_code == 200
        names = [u["filename"] for u in r.json()]
        assert names == ["b.txt", "a.txt"]  # 最新在前


# ── 阶段 2：解析端点（启动后台任务，立即返回 parsing）────────────────────────


def test_parse_endpoint_starts_background(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:
        # 让后台任务的 parse_scene_block 无害（返回 []），只验证端点立即返回 parsing
        monkeypatch.setattr(
            "backend.api.routes.scripts.parse_scene_block",
            lambda *a, **k: _noop(),
        )
        uid = _upload(c, content="内 咖啡馆 日\n罗湘：你好。".encode()).json()["upload_id"]
        r = _parse(c, uid)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "parsing"


async def _noop():
    return []


def test_parse_unknown_upload_404(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:
        assert _parse(c, 999).status_code == 404


def test_parse_no_llm_503(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch, llm=False) as c:
        uid = _upload(c, content="x".encode()).json()["upload_id"]
        assert _parse(c, uid).status_code == 503


# ── 后台任务 run_parse_job（直接单测入库逻辑）──────────────────────────────────


@pytest.mark.asyncio
async def test_run_parse_job_imports(tmp_dal: DAL, monkeypatch):
    uid = tmp_dal.insert_script_upload("a.txt", "原文")
    _patch_parse(
        monkeypatch,
        ["b1", "b2"],
        [
            [_scene("1", [("罗湘", "你好"), (None, "罗湘坐下")], int_ext="内")],
            [_scene("2", [("阿明", "走吧")])],
        ],
    )
    await run_parse_job(tmp_dal, _FakeLLM(), uid, "原文", "multi_scene")

    info = tmp_dal.get_script_upload(uid)
    assert info["status"] == "parsed"
    assert "已导入 2 场" in info["detail"]
    assert {s["scene_code"] for s in tmp_dal.list_scenes()} >= {"1", "2"}


@pytest.mark.asyncio
async def test_run_parse_job_skips_conflict(tmp_dal: DAL, monkeypatch):
    sid, _ = tmp_dal.get_or_create_scene("7")
    script_id = tmp_dal.insert_script(sid, "旧台词")
    tmp_dal.insert_script_line(script_id, 1, "老角色", "旧台词")
    uid = tmp_dal.insert_script_upload("a.txt", "x")

    _patch_parse(monkeypatch, ["b1"], [[_scene("7", [("新角色", "新台词")])]])
    await run_parse_job(tmp_dal, _FakeLLM(), uid, "x", "multi_scene")

    info = tmp_dal.get_script_upload(uid)
    assert info["status"] == "parsed"
    assert "跳过" in info["detail"]
    # 重复场未被替换（仍是旧版本）
    assert tmp_dal.get_latest_script(sid)["version"] == 1


@pytest.mark.asyncio
async def test_run_parse_job_no_scenes_marks_error(tmp_dal: DAL, monkeypatch):
    uid = tmp_dal.insert_script_upload("a.txt", "x")
    _patch_parse(monkeypatch, ["b1"], [[]])  # 该块解析不出场
    await run_parse_job(tmp_dal, _FakeLLM(), uid, "x", "multi_scene")
    assert tmp_dal.get_script_upload(uid)["status"] == "error"


@pytest.mark.asyncio
async def test_run_parse_job_skips_failed_block(tmp_dal: DAL, monkeypatch):
    """某块解析抛错 → 跳过该块、其余照常入库。"""
    from backend.pipelines.sp_script import SPParseError

    uid = tmp_dal.insert_script_upload("a.txt", "x")
    monkeypatch.setattr(
        "backend.api.routes.scripts.split_for_parse", lambda raw, **k: ["b1", "b2"]
    )

    async def _fake_block(block, llm, **k):
        if block == "b1":
            raise SPParseError("坏块")
        return [_scene("2", [("阿明", "走吧")])]

    monkeypatch.setattr("backend.api.routes.scripts.parse_scene_block", _fake_block)
    await run_parse_job(tmp_dal, _FakeLLM(), uid, "x", "multi_scene")

    info = tmp_dal.get_script_upload(uid)
    assert info["status"] == "parsed"
    assert {s["scene_code"] for s in tmp_dal.list_scenes()} >= {"2"}


# ── import_single_scene（逐场增量入库）────────────────────────────────────────


def test_reset_stale_parsing_uploads(tmp_dal: DAL):
    """启动清理：残留 parsing → error；uploaded/parsed 不动。"""
    u_parsing = tmp_dal.insert_script_upload("a.txt", "x")
    tmp_dal.update_script_upload_status(u_parsing, "parsing", "解析中 5/10 场")
    u_done = tmp_dal.insert_script_upload("b.txt", "y")
    tmp_dal.update_script_upload_status(u_done, "parsed", "已导入 3 场")
    u_uploaded = tmp_dal.insert_script_upload("c.txt", "z")  # 保持 uploaded

    n = tmp_dal.reset_stale_parsing_uploads()
    assert n == 1
    assert tmp_dal.get_script_upload(u_parsing)["status"] == "error"
    assert tmp_dal.get_script_upload(u_done)["status"] == "parsed"
    assert tmp_dal.get_script_upload(u_uploaded)["status"] == "uploaded"


def test_import_single_scene_empty_skipped(tmp_dal: DAL):
    from backend.core.script_import import import_single_scene

    s = _scene(None, [(None, "   ")])  # 清洗后全空
    assert (
        import_single_scene(s, target="multi_scene", synthetic_code="import:b:0", dal=tmp_dal)
        is None
    )
    assert tmp_dal.list_scenes() == []


def test_import_single_scene_synthetic_unique(tmp_dal: DAL):
    from backend.core.script_import import import_single_scene

    r0 = import_single_scene(
        _scene(None, [("罗湘", "甲")]), target="multi_scene", synthetic_code="import:b:0", dal=tmp_dal
    )
    r1 = import_single_scene(
        _scene(None, [("阿明", "乙")]), target="multi_scene", synthetic_code="import:b:1", dal=tmp_dal
    )
    assert r0["scene_id"] != r1["scene_id"]  # 无号场各得唯一合成 code → 不同场
    assert {s["scene_code"] for s in tmp_dal.list_scenes()} >= {"import:b:0", "import:b:1"}


def test_import_single_scene_conflict_skipped(tmp_dal: DAL):
    from backend.core.script_import import import_single_scene

    sid, _ = tmp_dal.get_or_create_scene("5")
    sc = tmp_dal.insert_script(sid, "旧")
    tmp_dal.insert_script_line(sc, 1, "甲", "旧")
    # 命中已有脚本场 → 跳过、不替换
    assert (
        import_single_scene(
            _scene("5", [("乙", "新")]), target="multi_scene", synthetic_code="import:b:0", dal=tmp_dal
        )
        is None
    )
    assert tmp_dal.get_latest_script(sid)["version"] == 1


# ── 重复场确认端点（直接构造 plan 测）─────────────────────────────────────────


def test_confirm_replace(tmp_dal: DAL, monkeypatch):
    from backend.core.script_import import plan_import

    sid, _ = tmp_dal.get_or_create_scene("9")
    script_id = tmp_dal.insert_script(sid, "旧")
    tmp_dal.insert_script_line(script_id, 1, "甲", "旧")

    plan = plan_import(
        [_scene("9", [("乙", "新")])], target="multi_scene", batch_id="b", dal=tmp_dal
    )
    plan_dict = {"target": plan.target, "new_scenes": plan.new_scenes, "conflicts": plan.conflicts}

    with _client(tmp_dal, monkeypatch) as c:
        r = c.post(
            "/api/v1/scripts/import/confirm",
            json={"plan": plan_dict, "decisions": [{"scene_id": sid, "action": "replace"}]},
            headers=_HEADERS,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "imported"
        assert body["scenes"][0]["lines"][0]["character"] == "乙"
        assert tmp_dal.get_latest_script(sid)["version"] == 2


# ── 单场原生 FC：POST /scripts/parse-single（不入库）─────────────────────────


def _patch_parse_fc(monkeypatch, scene: ParsedScene) -> None:
    """monkeypatch parse_scene_block_fc → 固定返回 [scene]（不跑真 Gemma）。"""
    async def _fake_fc(block, llm, **k):
        return [scene]

    monkeypatch.setattr("backend.api.routes.scripts.parse_scene_block_fc", _fake_fc)


def test_parse_single_returns_structured(tmp_dal: DAL, monkeypatch):
    scene = _scene(
        "3", [("罗湘", "你好。"), (None, "罗湘走到窗边。")], int_ext="内", tod="日", loc="咖啡馆"
    )
    _patch_parse_fc(monkeypatch, scene)
    with _client(tmp_dal, monkeypatch) as c:
        r = c.post(
            "/api/v1/scripts/parse-single",
            json={"text": "场3 内 咖啡馆 日\n罗湘：你好。\n罗湘走到窗边。"},
            headers=_HEADERS,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["scene_code"] == "3"
        assert (body["int_ext"], body["time_of_day"], body["location"]) == ("内", "日", "咖啡馆")
        assert body["lines"][0] == {"character": "罗湘", "text": "你好。"}
        assert body["lines"][1] == {"character": None, "text": "罗湘走到窗边。"}


def test_parse_single_503_when_no_llm(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch, llm=False) as c:
        r = c.post(
            "/api/v1/scripts/parse-single", json={"text": "罗湘：你好。"}, headers=_HEADERS
        )
        assert r.status_code == 503


def test_parse_single_422_empty_text(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch) as c:  # llm 在，过 503 门控；文本空 → 422
        r = c.post("/api/v1/scripts/parse-single", json={"text": "   "}, headers=_HEADERS)
        assert r.status_code == 422


# ── 照片 → 单场：POST /scripts/parse-images（视觉 OCR → 复用 FC 解析，不入库）──────


def _patch_vision_available(monkeypatch, ocr_text: str) -> None:
    """假装多模态可用（_text_only=False + mmproj 命中）并把视觉 OCR 替换成固定文本。"""
    monkeypatch.setattr("backend.llm.service._text_only", lambda: False)
    monkeypatch.setattr(
        "backend.llm.service.resolve_mmproj_path", lambda download=False: "/x/mmproj.gguf"
    )

    async def _fake_ocr(llm, uris):
        return ocr_text

    monkeypatch.setattr("backend.api.routes.scripts._ocr_images_to_text", _fake_ocr)


def test_parse_images_returns_structured(tmp_dal: DAL, monkeypatch):
    scene = _scene("3", [("罗湘", "你好。")], int_ext="内", tod="日", loc="咖啡馆")

    # 照片路径走无 grammar 的 parse_scene_block（非 _fc）→ patch 它返回固定 scene。
    async def _fake_block(block, llm, **k):
        return [scene]

    monkeypatch.setattr("backend.api.routes.scripts.parse_scene_block", _fake_block)
    _patch_vision_available(monkeypatch, "场3 内 咖啡馆 日\n罗湘：你好。")
    with _client(tmp_dal, monkeypatch) as c:
        r = c.post(
            "/api/v1/scripts/parse-images",
            files=[("files", ("a.jpg", b"\xff\xd8\xff", "image/jpeg"))],
            headers=_HEADERS,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["scene_code"] == "3"
        assert body["lines"][0] == {"character": "罗湘", "text": "你好。"}
        assert body["raw_text"].startswith("场3")  # raw_text = OCR 文本


def test_parse_images_503_when_text_only(tmp_dal: DAL, monkeypatch):
    monkeypatch.setattr("backend.llm.service._text_only", lambda: True)  # 纯文本档无 mmproj
    with _client(tmp_dal, monkeypatch) as c:
        r = c.post(
            "/api/v1/scripts/parse-images",
            files=[("files", ("a.jpg", b"\xff\xd8\xff", "image/jpeg"))],
            headers=_HEADERS,
        )
        assert r.status_code == 503


def test_parse_images_503_when_no_llm(tmp_dal: DAL, monkeypatch):
    with _client(tmp_dal, monkeypatch, llm=False) as c:
        r = c.post(
            "/api/v1/scripts/parse-images",
            files=[("files", ("a.jpg", b"\xff\xd8\xff", "image/jpeg"))],
            headers=_HEADERS,
        )
        assert r.status_code == 503


def test_extract_target_scene_drops_adjacent_scenes():
    """多页 OCR 全文 → 只取目标场：丢首页上一场尾 + 末页下一场头。"""
    from backend.api.routes.scripts import _extract_target_scene_text

    text = "上一场的尾巴台词。\n场5 内 咖啡馆 日\n罗湘：你好。\n场6 外 街道 夜\n阿明：走吧。"
    out = _extract_target_scene_text(text, "5")  # "场5" / "5" 归一相同
    assert "罗湘：你好。" in out
    assert "上一场的尾巴" not in out  # 上一场尾（前言）被丢
    assert "阿明：走吧" not in out  # 下一场（场6）被丢


def test_strip_special_tokens_cuts_turn_runaway():
    """模型越界续写：遇到回合标记即截断其后全部内容（含 <|turn|> / <|turn>model 及续写）。"""
    from backend.api.routes.scripts import _strip_special_tokens

    text = "罗湘：你好。\n沈默：你来了。<|turn|>\n<|turn>model\n罗湘：你好。沈默：你来了。"
    out = _strip_special_tokens(text)
    assert out.rstrip().endswith("你来了。")
    assert "<|turn" not in out
    assert "model" not in out  # 越界续写被切掉
    # 无标记时原样返回
    assert _strip_special_tokens("罗湘：你好。") == "罗湘：你好。"


def test_dedup_repeated_lines_collapses_loops():
    """OCR 循环重复行被折叠；非连续的合法短句保留。"""
    from backend.api.routes.scripts import _dedup_repeated_lines

    # 短词连续循环（上笑。×N）→ 折成一条（不限长度，根治这类 degenerate loop）
    assert _dedup_repeated_lines("上笑。\n" * 30) == "上笑。"
    # 单行连续循环 → 折成一条
    assert _dedup_repeated_lines("罗湘：你来了。\n罗湘：你来了。\n罗湘：你来了。") == "罗湘：你来了。"
    # 近距块循环 A B A B → A B
    assert _dedup_repeated_lines("阿明：走吧。\n罗湘：等等。\n阿明：走吧。\n罗湘：等等。") == (
        "阿明：走吧。\n罗湘：等等。"
    )
    # 非连续短句（隔行重复）不误删
    assert _dedup_repeated_lines("好。\n嗯。\n好。") == "好。\n嗯。\n好。"


def test_extract_target_scene_fallback_keeps_all():
    """无 scene_code / 切不出多块 / 匹配不到 → 原样返回（兜底不丢内容）。"""
    from backend.api.routes.scripts import _extract_target_scene_text

    text = "场5 内 咖啡馆 日\n罗湘：你好。"
    assert _extract_target_scene_text(text, None) == text  # 没传场号
    assert _extract_target_scene_text(text, "99") == text  # 单块 / 匹配不到
