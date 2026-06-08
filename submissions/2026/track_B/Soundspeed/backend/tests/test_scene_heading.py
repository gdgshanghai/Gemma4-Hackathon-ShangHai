"""scene heading TDD 测试：迁移 v2 + DAL + 读剧本端点 + debug/script heading + DEV 播种。

测试顺序：
  1. 迁移：v2 后 user_version==2、scenes 有三列；v1→v2 升级幂等。
  2. DAL：update_scene_heading 部分更新；list_scenes 含三列。
  3. 端点：GET /scenes/{id}/script 有/无剧本；行按 line_no 升序；character null 序列化正确。
  4. /debug/script 带 heading → scene 三列被更新。
  5. DEV 播种默认 heading。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.core.orchestrator import create_orchestrator
from backend.db.dal import DAL
from backend.db.migrations.runner import MIGRATION_FILES, apply_migrations

_TOKEN = "test-admin-token"


# ── 辅助 ─────────────────────────────────────────────────────────────────────


def _raw_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _make_client(orchestrator, monkeypatch) -> TestClient:
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")
    app = create_app(orchestrator)
    return TestClient(app)


# ── 1. 迁移 v2 ────────────────────────────────────────────────────────────────


def test_v2_migration_user_version_is_current(tmp_path: Path) -> None:
    """apply_migrations 后 PRAGMA user_version 等于当前最新版本（v4 后为 4）。"""
    db_path = tmp_path / "test.db"
    apply_migrations(db_path)
    conn = _raw_conn(db_path)
    version = conn.execute("PRAGMA user_version;").fetchone()[0]
    conn.close()
    assert version == max(MIGRATION_FILES)


def test_v2_migration_scenes_has_three_new_columns(tmp_path: Path) -> None:
    """迁移后 scenes 表含 int_ext、time_of_day、location 三列。"""
    db_path = tmp_path / "test.db"
    apply_migrations(db_path)
    conn = _raw_conn(db_path)
    cols_rows = conn.execute("PRAGMA table_info(scenes);").fetchall()
    conn.close()
    col_names = {r["name"] for r in cols_rows}
    assert "int_ext" in col_names
    assert "time_of_day" in col_names
    assert "location" in col_names


def test_v2_migration_idempotent(tmp_path: Path) -> None:
    """apply_migrations 重复调用不报错（幂等）。"""
    db_path = tmp_path / "test.db"
    apply_migrations(db_path)
    # 第二次：version==4（最新），runner 跳过全部，不报错
    apply_migrations(db_path)
    conn = _raw_conn(db_path)
    version = conn.execute("PRAGMA user_version;").fetchone()[0]
    conn.close()
    assert version == max(MIGRATION_FILES)


def test_v2_migration_preserves_existing_scenes_rows(tmp_path: Path) -> None:
    """v1→v2 升级后旧行仍存在，三列为 NULL（向后兼容）。"""
    db_path = tmp_path / "test.db"
    # 先只跑 v1（模拟旧 DB）：直接调用 apply_migrations，但手动把 user_version 改回 1
    # 比较简单的方式：先建 DAL（apply v1+v2），插一行后核查；
    # 这里用 runner 的 MIGRATION_FILES patch 来模拟 v1-only 先跑，再跑 v2
    # 更直接：手动建 v1 结构 + 写行，再 apply_migrations 升级
    conn = sqlite3.connect(db_path)
    v1_sql = (Path(__file__).parent.parent / "db/migrations/v1_init.sql").read_text(encoding="utf-8")
    conn.executescript(v1_sql)
    conn.execute(
        "INSERT INTO scenes (scene_code) VALUES ('OldScene');"
    )
    conn.commit()
    # 此时 user_version==1（v1_init.sql 末尾 PRAGMA user_version=1）
    conn.close()

    # 现在 apply_migrations，期望升到 v4（当前最新）
    apply_migrations(db_path)

    conn = _raw_conn(db_path)
    version = conn.execute("PRAGMA user_version;").fetchone()[0]
    assert version == max(MIGRATION_FILES)
    row = conn.execute("SELECT int_ext, time_of_day, location FROM scenes WHERE scene_code='OldScene';").fetchone()
    assert row is not None
    assert row["int_ext"] is None
    assert row["time_of_day"] is None
    assert row["location"] is None
    conn.close()


# ── 2. DAL ────────────────────────────────────────────────────────────────────


def test_update_scene_heading_partial_one_field(tmp_path: Path) -> None:
    """update_scene_heading 只传 int_ext，其他两列不变（部分更新）。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("S1")
    # 先设初始值
    dal.update_scene_heading(sid, int_ext="室内", time_of_day="日", location="咖啡馆")
    # 只更新 location
    dal.update_scene_heading(sid, location="街道")
    scenes = dal.list_scenes()
    s = next(sc for sc in scenes if sc["scene_id"] == sid)
    assert s["int_ext"] == "室内"        # 不变
    assert s["time_of_day"] == "日"      # 不变
    assert s["location"] == "街道"       # 被更新


def test_update_scene_heading_all_none_no_op(tmp_path: Path) -> None:
    """update_scene_heading 全部 None → 不改任何字段（COALESCE 保留原值）。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("S2")
    dal.update_scene_heading(sid, int_ext="室外", time_of_day="夜", location="广场")
    dal.update_scene_heading(sid)  # 全 None，不传任何字段
    scenes = dal.list_scenes()
    s = next(sc for sc in scenes if sc["scene_id"] == sid)
    assert s["int_ext"] == "室外"
    assert s["time_of_day"] == "夜"
    assert s["location"] == "广场"


def test_list_scenes_includes_heading_columns(tmp_path: Path) -> None:
    """list_scenes 返回的 dict 含 int_ext、time_of_day、location 三列。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("S3")
    dal.update_scene_heading(sid, int_ext="室外", time_of_day="日", location="街道")
    scenes = dal.list_scenes()
    s = next(sc for sc in scenes if sc["scene_id"] == sid)
    assert "int_ext" in s
    assert "time_of_day" in s
    assert "location" in s
    assert s["int_ext"] == "室外"
    assert s["time_of_day"] == "日"
    assert s["location"] == "街道"


def test_update_scene_heading_initial_nulls(tmp_path: Path) -> None:
    """新建 scene 三列初始为 NULL；update 后可读到正确值。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("S4")
    scenes = dal.list_scenes()
    s = next(sc for sc in scenes if sc["scene_id"] == sid)
    assert s["int_ext"] is None
    assert s["time_of_day"] is None
    assert s["location"] is None

    dal.update_scene_heading(sid, int_ext="室外")
    scenes = dal.list_scenes()
    s = next(sc for sc in scenes if sc["scene_id"] == sid)
    assert s["int_ext"] == "室外"
    assert s["time_of_day"] is None  # 未设，仍 NULL
    assert s["location"] is None     # 未设，仍 NULL


# ── 3. GET /scenes/{scene_id}/script 端点 ────────────────────────────────────


def test_get_scene_script_with_lines(tmp_path: Path, monkeypatch) -> None:
    """有剧本时返回 script + lines，按 line_no 升序（插入顺序故意乱）。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("ScriptScene")
    script_id = dal.insert_script(sid, "raw text")
    # 故意以 line_no 倒序插入
    dal.insert_script_line(script_id, 3, "演员B", "第三行台词")
    dal.insert_script_line(script_id, 1, "演员A", "第一行台词")
    dal.insert_script_line(script_id, 2, None, "舞台指示（无角色）")

    orch = create_orchestrator(dal)
    client = _make_client(orch, monkeypatch)

    resp = client.get(
        f"/api/v1/scenes/{sid}/script",
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "script" in body
    script = body["script"]
    assert script["script_id"] == script_id
    assert isinstance(script["version"], int)
    lines = script["lines"]
    assert len(lines) == 3
    # line_no 升序
    assert lines[0]["line_no"] == 1
    assert lines[1]["line_no"] == 2
    assert lines[2]["line_no"] == 3
    # character 非 null
    assert lines[0]["character"] == "演员A"
    assert lines[0]["text"] == "第一行台词"
    # character null
    assert lines[1]["character"] is None
    assert lines[1]["text"] == "舞台指示（无角色）"


def test_get_scene_script_no_script_returns_null(tmp_path: Path, monkeypatch) -> None:
    """无剧本时返回 {"script": null}，状态 200。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("NoScript")

    orch = create_orchestrator(dal)
    client = _make_client(orch, monkeypatch)

    resp = client.get(
        f"/api/v1/scenes/{sid}/script",
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"script": None}


def test_get_scene_script_nonexistent_scene_returns_null(tmp_path: Path, monkeypatch) -> None:
    """scene 不存在时返回 {"script": null}，状态 200（不 404）。"""
    dal = DAL(tmp_path / "test.db")

    orch = create_orchestrator(dal)
    client = _make_client(orch, monkeypatch)

    resp = client.get(
        "/api/v1/scenes/9999/script",
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"script": None}


def test_get_scene_script_requires_auth(tmp_path: Path, monkeypatch) -> None:
    """无 Authorization 头 → 401。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("AuthScene")

    orch = create_orchestrator(dal)
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")
    app = create_app(orch)
    client = TestClient(app)

    resp = client.get(f"/api/v1/scenes/{sid}/script")
    assert resp.status_code == 401


def test_get_scene_script_returns_latest_version(tmp_path: Path, monkeypatch) -> None:
    """同场次多版本剧本，端点返回最新版本。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("MultiVersion")
    scr1 = dal.insert_script(sid, "第一版")
    dal.insert_script_line(scr1, 1, "A", "旧台词")
    scr2 = dal.insert_script(sid, "第二版")
    dal.insert_script_line(scr2, 1, "B", "新台词")

    orch = create_orchestrator(dal)
    client = _make_client(orch, monkeypatch)

    resp = client.get(
        f"/api/v1/scenes/{sid}/script",
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200
    script = resp.json()["script"]
    assert script["script_id"] == scr2
    assert script["lines"][0]["character"] == "B"
    assert script["lines"][0]["text"] == "新台词"


# ── 4. /debug/script 带 heading ───────────────────────────────────────────────


def test_debug_script_with_heading_updates_scene(tmp_path: Path, monkeypatch) -> None:
    """/debug/script 带 int_ext/time_of_day/location → scene 三列被写入。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("HeadingScene")
    dal.set_active_scene(sid)

    orch = create_orchestrator(dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        "/api/v1/debug/script",
        json={
            "scene_id": sid,
            "int_ext": "室外",
            "time_of_day": "日",
            "location": "街道",
            "lines": [{"character": "演员A", "text": "台词一"}],
        },
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200

    scenes = dal.list_scenes()
    s = next(sc for sc in scenes if sc["scene_id"] == sid)
    assert s["int_ext"] == "室外"
    assert s["time_of_day"] == "日"
    assert s["location"] == "街道"


def test_debug_script_without_heading_does_not_clear_existing(tmp_path: Path, monkeypatch) -> None:
    """/debug/script 不带 heading 字段 → 已有的 scene heading 不被清空。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("PreHeading")
    dal.set_active_scene(sid)
    dal.update_scene_heading(sid, int_ext="室内", time_of_day="夜", location="咖啡馆")

    orch = create_orchestrator(dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        "/api/v1/debug/script",
        json={
            "scene_id": sid,
            "lines": [{"character": "A", "text": "台词"}],
        },
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200

    scenes = dal.list_scenes()
    s = next(sc for sc in scenes if sc["scene_id"] == sid)
    assert s["int_ext"] == "室内"    # 未改变
    assert s["time_of_day"] == "夜"  # 未改变
    assert s["location"] == "咖啡馆" # 未改变


def test_debug_script_partial_heading_updates_only_provided(tmp_path: Path, monkeypatch) -> None:
    """/debug/script 只带 int_ext → 只更新 int_ext，其他不变。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("PartialHead")
    dal.set_active_scene(sid)
    dal.update_scene_heading(sid, int_ext="室内", time_of_day="日", location="办公室")

    orch = create_orchestrator(dal)
    client = _make_client(orch, monkeypatch)

    resp = client.post(
        "/api/v1/debug/script",
        json={
            "scene_id": sid,
            "int_ext": "室外",
            "lines": [{"character": "A", "text": "台词"}],
        },
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )
    assert resp.status_code == 200

    scenes = dal.list_scenes()
    s = next(sc for sc in scenes if sc["scene_id"] == sid)
    assert s["int_ext"] == "室外"    # 被更新
    assert s["time_of_day"] == "日"  # 不变
    assert s["location"] == "办公室" # 不变


# ── 5. DEV 播种默认 heading ──────────────────────────────────────────────────


def test_dev_seed_includes_default_heading(tmp_path, monkeypatch) -> None:
    """build_app() + SOUNDSPEED_DEV=1 + 新鲜 DB → Scene_1 三列被播种为室外/日/街道。"""
    from backend.api.entrypoint import build_app  # noqa: PLC0415

    db_file = tmp_path / "seed_heading.db"
    monkeypatch.setenv("SOUNDSPEED_DB", str(db_file))
    monkeypatch.setenv("ADMIN_TOKEN", _TOKEN)
    monkeypatch.setenv("SOUNDSPEED_DEV", "1")

    app = build_app()
    dal = app.state.orchestrator.dal
    scenes = dal.list_scenes()
    assert len(scenes) == 1
    s = scenes[0]
    assert s["int_ext"] == "室外"
    assert s["time_of_day"] == "日"
    assert s["location"] == "街道"


# ── 6. 空串/纯空白不清值（P3 bug 回归）────────────────────────────────────────


def test_update_scene_heading_empty_string_does_not_clear_value(tmp_path: Path) -> None:
    """空串参数不清除已有值，语义等同 None（不更新该字段）。

    场景：现有 int_ext=室外, time_of_day=日, location=街道。
    调用 update_scene_heading(sid, int_ext="", time_of_day="夜", location="")。
    期望：int_ext 仍=室外，time_of_day=夜，location 仍=街道。
    """
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("EmptyStrScene")
    dal.update_scene_heading(sid, int_ext="室外", time_of_day="日", location="街道")

    # 空串表示「不想改这个字段」，非空串 time_of_day="夜" 才是真正的更新
    dal.update_scene_heading(sid, int_ext="", time_of_day="夜", location="")

    scenes = dal.list_scenes()
    s = next(sc for sc in scenes if sc["scene_id"] == sid)
    assert s["int_ext"] == "室外"    # 空串不清值，保留原值
    assert s["time_of_day"] == "夜"  # 非空，正常更新
    assert s["location"] == "街道"   # 空串不清值，保留原值


def test_update_scene_heading_whitespace_string_does_not_clear_value(tmp_path: Path) -> None:
    """纯空白字符串（只有空格）也视同 None，不更新该字段。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("WhitespaceScene")
    dal.update_scene_heading(sid, int_ext="室内", time_of_day="日", location="办公室")

    dal.update_scene_heading(sid, int_ext="   ", time_of_day="   ", location="   ")

    scenes = dal.list_scenes()
    s = next(sc for sc in scenes if sc["scene_id"] == sid)
    assert s["int_ext"] == "室内"    # 纯空白不清值
    assert s["time_of_day"] == "日"  # 纯空白不清值
    assert s["location"] == "办公室" # 纯空白不清值


def test_update_scene_heading_none_still_no_op(tmp_path: Path) -> None:
    """确保现有「None 不更新」行为不受影响（回归保护）。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("NoneNoOpScene")
    dal.update_scene_heading(sid, int_ext="室外", time_of_day="夜", location="广场")

    dal.update_scene_heading(sid, int_ext=None, time_of_day=None, location=None)

    scenes = dal.list_scenes()
    s = next(sc for sc in scenes if sc["scene_id"] == sid)
    assert s["int_ext"] == "室外"
    assert s["time_of_day"] == "夜"
    assert s["location"] == "广场"
