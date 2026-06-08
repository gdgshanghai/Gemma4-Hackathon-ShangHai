"""DAL 与迁移的测试用例（按 0.E sqlite-schema spec v0.2 §7 测试入口清单）。

所有测试用 tmp_path fixture 给每个测试干净 db 文件，互不干扰。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.db.dal import DAL
from backend.db.migrations.runner import MIGRATION_FILES, apply_migrations


# ── 辅助：打开裸 sqlite3 连接读取元数据 ──────────────────────────────────────


def _raw_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ── 迁移与初始化 ──────────────────────────────────────────────────────────────


def test_apply_migrations_creates_all_tables(tmp_path: Path) -> None:
    """迁移后 9 张物理表和 FTS5 虚拟表全部存在。"""
    db_path = tmp_path / "test.db"
    apply_migrations(db_path)
    conn = _raw_conn(db_path)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow') ORDER BY name;"
    ).fetchall()
    names = {r["name"] for r in rows}
    expected = {
        "scenes",
        "takes",
        "take_events",
        "scripts",
        "script_lines",
        "take_line_matches",
        "transcript_segments",
        "audit_log",
        "active_observers",
        "script_lines_fts",
    }
    assert expected.issubset(names), f"缺少表：{expected - names}"
    conn.close()


def test_apply_migrations_idempotent(tmp_path: Path) -> None:
    """多次调用 apply_migrations 不报错、不重复建表。"""
    db_path = tmp_path / "test.db"
    apply_migrations(db_path)
    apply_migrations(db_path)  # 第二次调用，期望幂等
    conn = _raw_conn(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='scenes';"
    ).fetchone()[0]
    assert count == 1
    conn.close()


def test_apply_migrations_user_version(tmp_path: Path) -> None:
    """迁移后 PRAGMA user_version 等于当前最高已注册版本。"""
    db_path = tmp_path / "test.db"
    apply_migrations(db_path)
    conn = _raw_conn(db_path)
    version = conn.execute("PRAGMA user_version;").fetchone()[0]
    assert version == max(MIGRATION_FILES)
    conn.close()


def test_apply_migrations_does_not_purge_observers(tmp_path: Path) -> None:
    """apply_migrations 多次调用不清空 active_observers，已存在的行保留。"""
    db_path = tmp_path / "test.db"
    apply_migrations(db_path)
    # 直接插入一条观察者记录
    conn = _raw_conn(db_path)
    conn.execute(
        "INSERT INTO active_observers (connection_id, name) VALUES ('conn-1', 'director');"
    )
    conn.commit()
    conn.close()
    # 再次调用 apply_migrations，期望不清空
    apply_migrations(db_path)
    conn = _raw_conn(db_path)
    count = conn.execute("SELECT COUNT(*) FROM active_observers;").fetchone()[0]
    assert count == 1  # 行仍然存在
    conn.close()


def test_v3_migration_adds_columns_and_unique(tmp_path: Path) -> None:
    """v3 迁移后 takes 表含 take_suffix / deleted_at，UNIQUE 变三元。"""
    db_path = tmp_path / "test.db"
    apply_migrations(db_path)
    conn = _raw_conn(db_path)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(takes);").fetchall()}
    assert "take_suffix" in cols, "takes 表缺 take_suffix 列"
    assert "deleted_at" in cols, "takes 表缺 deleted_at 列"
    conn.close()


def test_v3_migration_preserves_data(tmp_path: Path) -> None:
    """先用 v2 状态插入数据，跑到 v3 后数据保留，take_suffix=''，deleted_at=NULL。"""
    import sqlite3 as _sql

    db_path = tmp_path / "v2_to_v3.db"
    # 手动只运行 v1 + v2
    from backend.db.migrations.runner import MIGRATIONS_DIR
    v1_sql = (MIGRATIONS_DIR / "v1_init.sql").read_text(encoding="utf-8")
    v2_sql = (MIGRATIONS_DIR / "v2_scene_heading.sql").read_text(encoding="utf-8")

    conn = _sql.connect(db_path)
    conn.row_factory = _sql.Row
    conn.executescript(v1_sql)
    conn.executescript(v2_sql)

    # 插入一条 scene + take
    sid = conn.execute("INSERT INTO scenes (scene_code) VALUES ('S1');").lastrowid
    conn.execute(
        "INSERT INTO takes (scene_id, take_number, start_ts, status) VALUES (?, 1, 1000.0, 'tbd');",
        (sid,),
    )
    conn.commit()
    conn.close()

    # 跑完整迁移链到 v3
    apply_migrations(db_path)

    conn = _sql.connect(db_path)
    conn.row_factory = _sql.Row
    row = conn.execute("SELECT * FROM takes WHERE take_number = 1;").fetchone()
    assert row is not None
    assert row["scene_id"] == sid
    assert row["take_suffix"] == ""
    assert row["deleted_at"] is None
    conn.close()


def test_v3_migration_three_way_unique(tmp_path: Path) -> None:
    """v3 后 (scene_id, take_number, take_suffix) 三元 UNIQUE：同 scene 同 number 不同 suffix 可共存。"""
    import sqlite3 as _sql

    db_path = tmp_path / "v3_unique.db"
    apply_migrations(db_path)

    conn = _sql.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    sid = conn.execute("INSERT INTO scenes (scene_code) VALUES ('S1');").lastrowid
    conn.execute(
        "INSERT INTO takes (scene_id, take_number, take_suffix, start_ts) VALUES (?, 1, '', 1000.0);",
        (sid,),
    )
    # 同 number 不同 suffix，应可插入
    conn.execute(
        "INSERT INTO takes (scene_id, take_number, take_suffix, start_ts) VALUES (?, 1, '+', 1001.0);",
        (sid,),
    )
    conn.commit()
    count = conn.execute(
        "SELECT COUNT(*) FROM takes WHERE scene_id = ? AND take_number = 1;", (sid,)
    ).fetchone()[0]
    assert count == 2
    # 同 number 同 suffix 应触发 UNIQUE 冲突
    with pytest.raises(_sql.IntegrityError):
        conn.execute(
            "INSERT INTO takes (scene_id, take_number, take_suffix, start_ts) VALUES (?, 1, '', 1002.0);",
            (sid,),
        )
    conn.close()


def test_v3_migration_fk_check_passes(tmp_path: Path) -> None:
    """v3 迁移后 PRAGMA foreign_key_check 通过（子表 FK 关系完好）。"""
    import sqlite3 as _sql

    db_path = tmp_path / "v3_fk.db"
    # 先用 v2 插入数据（带子表记录），再迁移到 v3
    from backend.db.migrations.runner import MIGRATIONS_DIR
    v1_sql = (MIGRATIONS_DIR / "v1_init.sql").read_text(encoding="utf-8")
    v2_sql = (MIGRATIONS_DIR / "v2_scene_heading.sql").read_text(encoding="utf-8")

    conn = _sql.connect(db_path)
    conn.row_factory = _sql.Row
    conn.executescript(v1_sql)
    conn.executescript(v2_sql)

    sid = conn.execute("INSERT INTO scenes (scene_code) VALUES ('S1');").lastrowid
    tid = conn.execute(
        "INSERT INTO takes (scene_id, take_number, start_ts) VALUES (?, 1, 1000.0);", (sid,)
    ).lastrowid
    conn.execute(
        "INSERT INTO take_events (take_id, event_type, ts, payload) VALUES (?, 'manual.mark', 1010.0, '{}');",
        (tid,),
    )
    conn.commit()
    conn.close()

    apply_migrations(db_path)

    conn = _sql.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
    assert violations == [], f"迁移后 FK 约束违规：{violations}"
    conn.close()


# ── PRAGMA 验证 ───────────────────────────────────────────────────────────────


def test_dal_enables_wal_mode(tmp_path: Path) -> None:
    """DAL 初始化后 journal_mode 为 wal。"""
    db_path = tmp_path / "test.db"
    _dal = DAL(db_path)
    conn = _raw_conn(db_path)
    mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    conn.close()
    assert mode == "wal"


def test_dal_enables_foreign_keys(tmp_path: Path) -> None:
    """DAL 初始化后 foreign_keys 已启用。"""
    db_path = tmp_path / "test.db"
    _dal = DAL(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    # 验证外键约束生效：向 takes 插入不存在的 scene_id
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO takes (scene_id, take_number, start_ts) VALUES (9999, 1, 1.0);"
        )
    conn.close()


# ── scenes ───────────────────────────────────────────────────────────────────


def test_create_scene_returns_id(tmp_path: Path) -> None:
    """插入场次返回正确 scene_id，大于 0。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    assert isinstance(sid, int)
    assert sid > 0


def test_set_active_scene_clears_others(tmp_path: Path) -> None:
    """set_active_scene 后其余场次 is_active 均为 0，目标场次为 1。"""
    dal = DAL(tmp_path / "test.db")
    sid1 = dal.create_scene("Scene_1")
    sid2 = dal.create_scene("Scene_2")
    dal.set_active_scene(sid1)
    dal.set_active_scene(sid2)
    # sid1 应当被清除
    active = dal.get_active_scene_id()
    assert active == sid2
    scenes = dal.list_scenes()
    for s in scenes:
        if s["scene_id"] == sid1:
            assert s["is_active"] == 0
        elif s["scene_id"] == sid2:
            assert s["is_active"] == 1


def test_get_active_scene_id_no_active(tmp_path: Path) -> None:
    """无活跃场次时 get_active_scene_id 返回 None。"""
    dal = DAL(tmp_path / "test.db")
    assert dal.get_active_scene_id() is None


def test_list_scenes_returns_all(tmp_path: Path) -> None:
    """list_scenes 返回已插入的所有场次。"""
    dal = DAL(tmp_path / "test.db")
    dal.create_scene("Scene_A")
    dal.create_scene("Scene_B")
    scenes = dal.list_scenes()
    codes = {s["scene_code"] for s in scenes}
    assert {"Scene_A", "Scene_B"}.issubset(codes)


# ── takes ─────────────────────────────────────────────────────────────────────


def test_start_take_returns_id(tmp_path: Path) -> None:
    """插入 take 返回正确 take_id，大于 0。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    assert isinstance(tid, int)
    assert tid > 0


def test_end_take_sets_end_ts(tmp_path: Path) -> None:
    """end_take 后 get_take 返回的 end_ts 不为 None。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    dal.end_take(tid, 1060.0, "keep")
    take = dal.get_take(tid)
    assert take is not None
    assert take.end_ts == pytest.approx(1060.0)
    assert take.status == "keep"


def test_take_status_check_constraint(tmp_path: Path) -> None:
    """插入非法 status 值触发 CHECK 约束异常。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    with pytest.raises(sqlite3.IntegrityError):
        dal.end_take(tid, 1060.0, "invalid_status")


def test_end_take_preserves_omitted_fields(tmp_path: Path) -> None:
    """end_take 省略 status/notes 时走 preserve-on-None：保留库中原值，只更新 end_ts。

    回归：end_take 曾无条件把未给字段覆盖（status 写死、notes 置 NULL），停录会冲掉
    用户录音中的 Mark 与 memo notes。COALESCE 后 None 即保留。
    """
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    # 录音中标 keep；借一次 end_take 写 notes（status 省略 → 保留 keep）
    dal.set_take_status(tid, "keep")
    dal.end_take(tid, 1010.0, notes="第三条最好")
    mid = dal.get_take(tid)
    assert mid is not None and mid.status == "keep" and mid.notes == "第三条最好"

    # 再 end_take 只更新 end_ts（status/notes 全省略）→ 两者都不被冲掉
    dal.end_take(tid, 1060.0)
    take = dal.get_take(tid)
    assert take is not None
    assert take.end_ts == pytest.approx(1060.0)
    assert take.status == "keep"  # 不回退 tbd
    assert take.notes == "第三条最好"  # 不清成 NULL


def test_takes_unique_scene_take_number_same_suffix(tmp_path: Path) -> None:
    """同场次同 shot 同 take_number 同 take_suffix（均为默认 ''）重复插入触发 UNIQUE 约束异常。

    v4 后四元约束 UNIQUE(scene_id, shot, take_number, take_suffix)。
    使用 raw SQL 直接触发约束（start_take 内部原子分配号，不会产生相同号）。
    """
    db_path = tmp_path / "test.db"
    apply_migrations(db_path)
    conn = _raw_conn(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    sid = conn.execute("INSERT INTO scenes (scene_code) VALUES ('Scene_1');").lastrowid
    conn.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 1, '', 1000.0);",
        (sid,),
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 1, '', 1001.0);",
            (sid,),
        )
        conn.commit()
    conn.close()


def test_takes_unique_allows_different_suffix(tmp_path: Path) -> None:
    """同场次同 shot 同 take_number 但不同 take_suffix 可共存（v4 四元 UNIQUE）。"""
    db_path = tmp_path / "test.db"
    apply_migrations(db_path)
    conn = _raw_conn(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    sid = conn.execute(
        "INSERT INTO scenes (scene_code) VALUES ('S1');"
    ).lastrowid
    conn.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 1, '', 1000.0);",
        (sid,),
    )
    # 同 scene 同 shot 同 number 但 suffix 不同，应该可以插入
    conn.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 1, '+', 1001.0);",
        (sid,),
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM takes WHERE scene_id = ? AND take_number = 1;", (sid,)).fetchone()[0]
    assert count == 2
    conn.close()


def test_list_takes_filter_by_scene_id(tmp_path: Path) -> None:
    """list_takes 按 scene_id 过滤，只返回目标场次的 take。"""
    dal = DAL(tmp_path / "test.db")
    sid1 = dal.create_scene("Scene_1")
    sid2 = dal.create_scene("Scene_2")
    dal.start_take(sid1, "1", 1000.0)
    dal.start_take(sid2, "1", 2000.0)
    takes1 = dal.list_takes(scene_id=sid1)
    assert len(takes1) == 1
    assert takes1[0].scene_id == sid1


def test_get_take_not_found_returns_none(tmp_path: Path) -> None:
    """get_take 不存在的 take_id 时返回 None。"""
    dal = DAL(tmp_path / "test.db")
    assert dal.get_take(99999) is None


def test_update_take_np_output(tmp_path: Path) -> None:
    """update_take_np_output 更新 performer_issues 与 audio_quality，不覆盖 end_ts。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    dal.end_take(tid, 1060.0, "tbd")
    dal.update_take_np_output(
        tid,
        performer_issues=["line_miss"],
        audio_quality="clean",
        status="keep",
    )
    take = dal.get_take(tid)
    assert take is not None
    assert take.audio_quality == "clean"
    assert take.status == "keep"
    assert take.end_ts == pytest.approx(1060.0)  # end_ts 未被覆盖


def test_update_take_np_output_serializes_json_list(tmp_path: Path) -> None:
    """update_take_np_output 接受 list，存库后 get_take 读回仍是 list。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    dal.end_take(tid, 1060.0, "tbd")
    issues: list = ["line_miss", "overlap"]
    dal.update_take_np_output(tid, performer_issues=issues, audio_quality=None, status=None)
    take = dal.get_take(tid)
    assert take is not None
    assert take.performer_issues == issues


def test_update_take_np_output_serializes_json_dict(tmp_path: Path) -> None:
    """update_take_np_output 接受 dict，存库后 get_take 读回仍是 dict。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    dal.end_take(tid, 1060.0, "tbd")
    issues: dict = {"missed": ["line3"], "late_cue": ["line5"]}
    dal.update_take_np_output(tid, performer_issues=issues, audio_quality=None, status=None)
    take = dal.get_take(tid)
    assert take is not None
    assert take.performer_issues == issues


def test_update_take_np_output_none_passes_through(tmp_path: Path) -> None:
    """update_take_np_output 传 performer_issues=None，get_take 读回也是 None。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    dal.end_take(tid, 1060.0, "tbd")
    dal.update_take_np_output(tid, performer_issues=None, audio_quality=None, status=None)
    take = dal.get_take(tid)
    assert take is not None
    assert take.performer_issues is None


# ── take_events ───────────────────────────────────────────────────────────────


def test_insert_take_event_with_valid_json(tmp_path: Path) -> None:
    """合法 JSON payload 正常写入，list_take_events 可查到。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    eid = dal.insert_take_event(tid, "manual.mark", {"mark": "keep"}, 1010.0)
    assert eid > 0
    events = dal.list_take_events(tid)
    assert len(events) == 1
    assert events[0].event_type == "manual.mark"
    assert events[0].payload == {"mark": "keep"}


def test_take_events_payload_json_validation(tmp_path: Path) -> None:
    """非法 JSON payload 触发 CHECK 约束异常（json_valid 约束）。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    # 直接用裸连接插入非法 JSON，绕过 DAL 的 json.dumps 转换
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    conn.execute("PRAGMA foreign_keys = ON;")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO take_events (take_id, event_type, ts, payload) "
            "VALUES (?, 'manual.mark', 1010.0, 'not-valid-json');",
            (tid,),
        )
    conn.close()


def test_list_take_events_filter_by_type(tmp_path: Path) -> None:
    """list_take_events 按 event_type 过滤，只返回匹配事件。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    dal.insert_take_event(tid, "manual.mark", {"mark": "keep"}, 1010.0)
    dal.insert_take_event(tid, "np.write", {"audio_quality": "clean"}, 1020.0)
    marks = dal.list_take_events(tid, event_type="manual.mark")
    assert len(marks) == 1
    assert marks[0].event_type == "manual.mark"


# ── transcript_segments ───────────────────────────────────────────────────────


def test_insert_segment_with_speaker(tmp_path: Path) -> None:
    """含 speaker 字段的片段正常写入，list_segments 可查到正确 speaker。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    seg_id = dal.insert_segment(tid, 1, "SPEAKER_00", "Hello world", 0, 16000)
    assert seg_id > 0
    segs = dal.list_segments(tid)
    assert len(segs) == 1
    assert segs[0].speaker == "SPEAKER_00"


def test_insert_segment_rejects_null_take_id(tmp_path: Path) -> None:
    """传 None 作为 take_id 触发 IntegrityError（NOT NULL 约束）。"""
    _dal = DAL(tmp_path / "test.db")
    # 用裸连接直接插入 NULL take_id
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    conn.execute("PRAGMA foreign_keys = ON;")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO transcript_segments (take_id, ch, text, start_frame, end_frame) "
            "VALUES (NULL, 1, 'hello', 0, 160);"
        )
    conn.close()


def test_insert_segment_ch_check_constraint(tmp_path: Path) -> None:
    """ch 值非 1/2 触发 CHECK 约束异常。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    conn.execute("PRAGMA foreign_keys = ON;")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO transcript_segments (take_id, ch, text, start_frame, end_frame) "
            "VALUES (?, 3, 'hello', 0, 160);",
            (tid,),
        )
    conn.close()


def test_insert_segment_frame_order_check(tmp_path: Path) -> None:
    """end_frame <= start_frame 触发 CHECK 约束异常（end_frame > start_frame）。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    conn.execute("PRAGMA foreign_keys = ON;")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO transcript_segments (take_id, ch, text, start_frame, end_frame) "
            "VALUES (?, 1, 'hello', 1000, 500);",
            (tid,),
        )
    conn.close()


def test_list_segments_filter_by_speaker(tmp_path: Path) -> None:
    """按 speaker 过滤返回正确子集。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    dal.insert_segment(tid, 1, "SPEAKER_00", "Hello", 0, 16000)
    dal.insert_segment(tid, 1, "SPEAKER_01", "World", 16000, 32000)
    segs = dal.list_segments(tid, speaker="SPEAKER_00")
    assert len(segs) == 1
    assert segs[0].speaker == "SPEAKER_00"


def test_list_segments_filter_by_ch(tmp_path: Path) -> None:
    """按 ch 过滤返回正确子集。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    dal.insert_segment(tid, 1, None, "ch1 text", 0, 16000)
    dal.insert_segment(tid, 2, None, "ch2 text", 0, 16000)
    segs_ch1 = dal.list_segments(tid, ch=1)
    assert len(segs_ch1) == 1
    assert segs_ch1[0].ch == 1


# ── scripts 与 script_lines ───────────────────────────────────────────────────


def test_insert_script_auto_version(tmp_path: Path) -> None:
    """同场次多次插入版本号自动递增。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    _scr1 = dal.insert_script(sid, "第一版剧本")
    scr2 = dal.insert_script(sid, "第二版剧本")
    latest = dal.get_latest_script(sid)
    assert latest is not None
    assert latest["script_id"] == scr2


def test_list_all_characters_cross_scene_distinct_sorted(tmp_path: Path) -> None:
    """跨场角色取并集、去重、排序；舞台指示（character=NULL）排除。"""
    dal = DAL(tmp_path / "test.db")
    s1 = dal.create_scene("Scene_1")
    scr1 = dal.insert_script(s1, "场一")
    dal.insert_script_line(scr1, 1, "夏雨", "你来了。")
    dal.insert_script_line(scr1, 2, "顾朗", "嗯。")
    dal.insert_script_line(scr1, 3, None, "（顾朗坐下）")  # 舞台指示，排除
    s2 = dal.create_scene("Scene_2")
    scr2 = dal.insert_script(s2, "场二")
    dal.insert_script_line(scr2, 1, "阿知", "走吧。")
    dal.insert_script_line(scr2, 2, "夏雨", "等等。")  # 跨场重复 → 去重

    chars = dal.list_all_characters()
    assert set(chars) == {"夏雨", "顾朗", "阿知"}  # 并集去重，None 不入
    assert chars == sorted(chars)  # ORDER BY 已排序


def test_list_all_characters_only_latest_version(tmp_path: Path) -> None:
    """同场多版本只算最新版剧本的角色，旧版角色不出现。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    old = dal.insert_script(sid, "旧版")
    dal.insert_script_line(old, 1, "旧角色", "旧台词")
    new = dal.insert_script(sid, "新版")
    dal.insert_script_line(new, 1, "新角色", "新台词")

    chars = dal.list_all_characters()
    assert chars == ["新角色"]


def test_list_all_characters_empty_when_no_scripts(tmp_path: Path) -> None:
    """无任何剧本时返回空列表。"""
    dal = DAL(tmp_path / "test.db")
    dal.create_scene("Scene_1")  # 有场无剧本
    assert dal.list_all_characters() == []


def test_insert_script_line_and_fts_sync(tmp_path: Path) -> None:
    """插入台词行后 FTS5 可立即 MATCH 到（trigram 最短 3 字符 query）。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    scr_id = dal.insert_script(sid, "测试剧本")
    dal.insert_script_line(scr_id, 1, "HERO", "To be or not to be")
    results = dal.match_script_line("not")
    assert len(results) >= 1
    assert any("not" in r.text.lower() for r in results)


def test_match_script_line_fts5_basic(tmp_path: Path) -> None:
    """FTS5 MATCH 基本英文词查询正确返回。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    scr_id = dal.insert_script(sid, "英文台词测试")
    dal.insert_script_line(scr_id, 1, "ACTOR_A", "The quick brown fox jumps")
    dal.insert_script_line(scr_id, 2, "ACTOR_B", "Lazy dogs sleep all day")
    results = dal.match_script_line("fox")
    assert len(results) == 1
    assert "fox" in results[0].text.lower()


def test_match_script_line_fts5_chinese(tmp_path: Path) -> None:
    """FTS5 MATCH 中文子串查询（trigram tokenizer，SQLite >= 3.34）。

    trigram tokenizer 将文本按连续 3 个 unicode codepoint 切分，支持 CJK 子串匹配。
    query 必须 >= 3 个字符才能命中，< 3 个字符的 query 返回空集（trigram 最小粒度限制）。
    本测试在所有支持 trigram 的平台（SQLite >= 3.34）上直接跑，无需 skipif。
    """
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    scr_id = dal.insert_script(sid, "中文剧本")
    dal.insert_script_line(scr_id, 1, "演员甲", "我不想走，请别让我走")
    dal.insert_script_line(scr_id, 2, "演员乙", "好的，我理解你的心情")
    # trigram 最小 3 字符：搜「不想走」匹配含「不想走」的行
    results = dal.match_script_line("不想走")
    assert len(results) >= 1
    assert any("不想走" in r.text for r in results)
    # 搜「我理解」匹配另一行
    results2 = dal.match_script_line("我理解")
    assert len(results2) >= 1
    assert any("我理解" in r.text for r in results2)


def test_delete_script_line_fts_removed(tmp_path: Path) -> None:
    """删除台词行后 FTS5 不再匹配。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    scr_id = dal.insert_script(sid, "测试剧本")
    lid = dal.insert_script_line(scr_id, 1, "HERO", "unique phrase xyzzy")
    # 直接用裸连接删除行，让触发器生效
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    conn.execute("DELETE FROM script_lines WHERE line_id = ?;", (lid,))
    conn.commit()
    conn.close()
    results = dal.match_script_line("xyzzy")
    assert len(results) == 0


# ── take_line_matches ─────────────────────────────────────────────────────────


def test_insert_take_line_match_valid_diff_type(tmp_path: Path) -> None:
    """合法 diff_type 写入正常，list_take_line_matches 可查到。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    scr_id = dal.insert_script(sid, "测试剧本")
    lid = dal.insert_script_line(scr_id, 1, "HERO", "original line")
    mid = dal.insert_take_line_match(tid, lid, "match", {})
    assert mid > 0
    matches = dal.list_take_line_matches(tid)
    assert len(matches) == 1
    assert matches[0]["diff_type"] == "match"


def test_insert_take_line_match_invalid_diff_type(tmp_path: Path) -> None:
    """非法 diff_type 触发 CHECK 约束异常。"""
    dal = DAL(tmp_path / "test.db")
    sid = dal.create_scene("Scene_1")
    tid, _ = dal.start_take(sid, "1", 1000.0)
    scr_id = dal.insert_script(sid, "测试剧本")
    lid = dal.insert_script_line(scr_id, 1, "HERO", "original line")
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    conn.execute("PRAGMA foreign_keys = ON;")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO take_line_matches (take_id, line_id, diff_type, payload) "
            "VALUES (?, ?, 'invalid_type', '{}');",
            (tid, lid),
        )
    conn.close()


# ── active_observers ──────────────────────────────────────────────────────────


def test_upsert_observer_updates_existing(tmp_path: Path) -> None:
    """同 connection_id 二次 upsert 覆盖 name。"""
    dal = DAL(tmp_path / "test.db")
    dal.upsert_observer("conn-abc", "director")
    dal.upsert_observer("conn-abc", "script_supervisor")
    observers = dal.list_observers()
    matching = [o for o in observers if o["connection_id"] == "conn-abc"]
    assert len(matching) == 1
    assert matching[0]["name"] == "script_supervisor"


def test_remove_observer(tmp_path: Path) -> None:
    """remove_observer 后 list_observers 不再含该连接。"""
    dal = DAL(tmp_path / "test.db")
    dal.upsert_observer("conn-1", "director")
    dal.remove_observer("conn-1")
    observers = dal.list_observers()
    assert not any(o["connection_id"] == "conn-1" for o in observers)


def test_list_observers_empty_initially(tmp_path: Path) -> None:
    """新 DAL 初始化后 active_observers 为空（全新数据库，尚无记录）。"""
    dal = DAL(tmp_path / "test.db")
    assert dal.list_observers() == []


def test_purge_volatile_tables_clears_observers(tmp_path: Path) -> None:
    """purge_volatile_tables 显式调用后 active_observers 清空。"""
    from backend.db.lifecycle import purge_volatile_tables

    db_path = tmp_path / "test.db"
    dal = DAL(db_path)
    dal.upsert_observer("conn-1", "director")
    dal.upsert_observer("conn-2", "sound")
    assert len(dal.list_observers()) == 2
    purge_volatile_tables(db_path)
    assert dal.list_observers() == []


# ── audit_log ─────────────────────────────────────────────────────────────────


def test_append_audit_returns_log_id(tmp_path: Path) -> None:
    """审计日志写入并返回 log_id，大于 0。"""
    dal = DAL(tmp_path / "test.db")
    log_id = dal.append_audit("orchestrator", "take.start", {"take_id": 1})
    assert isinstance(log_id, int)
    assert log_id > 0


def test_audit_payload_check_constraint(tmp_path: Path) -> None:
    """非法 JSON payload 触发 CHECK 约束异常（json_valid 约束）。"""
    _dal = DAL(tmp_path / "test.db")
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    conn.execute("PRAGMA foreign_keys = ON;")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO audit_log (actor, action, payload) "
            "VALUES ('orchestrator', 'take.start', 'not-valid-json');"
        )
    conn.close()


# ── DAL 资源管理 ──────────────────────────────────────────────────────────────


def test_dal_close_releases_connection(tmp_path: Path) -> None:
    """DAL.close() 后再操作触发 sqlite3.ProgrammingError。"""
    dal = DAL(tmp_path / "test.db")
    dal.close()
    with pytest.raises(sqlite3.ProgrammingError):
        dal.list_scenes()


def test_dal_as_context_manager(tmp_path: Path) -> None:
    """with DAL(...) as dal 块退出后，连接自动关闭。"""
    with DAL(tmp_path / "test.db") as dal:
        scene_id = dal.create_scene("S01")
        assert isinstance(scene_id, int)
    # 块已退出，连接已关闭
    with pytest.raises(sqlite3.ProgrammingError):
        dal.list_scenes()


# ── get_segment / update_segment_speaker ──────────────────────────────────


def test_get_segment_returns_row(tmp_dal: DAL) -> None:
    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    seg_id = tmp_dal.insert_segment(tid, 1, "SPEAKER_00", "你好", 0, 16000)
    seg = tmp_dal.get_segment(seg_id)
    assert seg is not None
    assert seg.take_id == tid
    assert seg.ch == 1
    assert seg.speaker == "SPEAKER_00"


def test_get_segment_missing_returns_none(tmp_dal: DAL) -> None:
    assert tmp_dal.get_segment(99999) is None


def test_update_segment_speaker_changes_value(tmp_dal: DAL) -> None:
    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    seg_id = tmp_dal.insert_segment(tid, 1, "SPEAKER_00", "你好", 0, 16000)
    affected = tmp_dal.update_segment_speaker(seg_id, "SPEAKER_01")
    assert affected == 1
    seg = tmp_dal.get_segment(seg_id)
    assert seg is not None and seg.speaker == "SPEAKER_01"


def test_update_segment_speaker_to_none(tmp_dal: DAL) -> None:
    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    seg_id = tmp_dal.insert_segment(tid, 1, "SPEAKER_00", "你好", 0, 16000)
    affected = tmp_dal.update_segment_speaker(seg_id, None)
    assert affected == 1
    seg = tmp_dal.get_segment(seg_id)
    assert seg is not None and seg.speaker is None


def test_update_segment_speaker_missing_returns_zero(tmp_dal: DAL) -> None:
    assert tmp_dal.update_segment_speaker(99999, "X") == 0


# ── 2.B：set_take_status ──────────────────────────────────────────────────────


def test_set_take_status_valid_updates_status(tmp_dal: DAL) -> None:
    """set_take_status 成功更新 take.status，并写一条 manual.mark take_event。"""
    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    tmp_dal.end_take(tid, 1060.0, "tbd")
    tmp_dal.set_take_status(tid, "keep")
    take = tmp_dal.get_take(tid)
    assert take is not None
    assert take.status == "keep"


def test_set_take_status_writes_take_event(tmp_dal: DAL) -> None:
    """set_take_status 写一条 event_type='manual.mark' 的 take_event，payload 含新 status。"""
    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    tmp_dal.set_take_status(tid, "ng")
    events = tmp_dal.list_take_events(tid, event_type="manual.mark")
    assert len(events) == 1
    assert events[0].payload == {"status": "ng"}


def test_set_take_status_invalid_raises_value_error(tmp_dal: DAL) -> None:
    """非法 status 值抛 ValueError（应用层校验，不依赖 DB CHECK）。"""
    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    with pytest.raises(ValueError, match="status"):
        tmp_dal.set_take_status(tid, "invalid_status")


# ── 2.B：update_take_meta ─────────────────────────────────────────────────────


def test_update_take_meta_case_a_append_to_existing_scene(tmp_dal: DAL) -> None:
    """情形 A：仅移场（不指定 take_number），追加到目标场 MAX+1。"""
    sid1 = tmp_dal.create_scene("S1")
    sid2 = tmp_dal.create_scene("S2")
    # sid2 已有 take_number=1，移入后应追加为 2
    tmp_dal.start_take(sid2, "1", 2000.0)
    tid, _ = tmp_dal.start_take(sid1, "1", 1000.0)
    tmp_dal.update_take_meta(tid, scene_id=sid2)
    take = tmp_dal.get_take(tid)
    assert take is not None
    assert take.scene_id == sid2
    assert take.take_number == 2


def test_update_take_meta_case_a_append_to_empty_scene(tmp_dal: DAL) -> None:
    """情形 A：移到空场（无 take），take_number=1。"""
    sid1 = tmp_dal.create_scene("S1")
    sid2 = tmp_dal.create_scene("S2")
    tid, _ = tmp_dal.start_take(sid1, "1", 1000.0)
    tmp_dal.update_take_meta(tid, scene_id=sid2)
    take = tmp_dal.get_take(tid)
    assert take is not None
    assert take.scene_id == sid2
    assert take.take_number == 1


def test_update_take_meta_case_a_nonexistent_scene_raises(tmp_dal: DAL) -> None:
    """情形 A：目标 scene 不存在，抛 ValueError。"""
    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    with pytest.raises(ValueError, match="scene"):
        tmp_dal.update_take_meta(tid, scene_id=99999)


def test_update_take_meta_case_b_suffix_when_number_conflict(tmp_dal: DAL) -> None:
    """情形 B：同场换号（目标号已被占用），给被移动的 take 追加 '+' 后缀，不交换。"""
    sid = tmp_dal.create_scene("S1")
    tid1, _ = tmp_dal.start_take(sid, "1", 1000.0)  # take_number=1，占用 (sid,shot="1",1,'')
    tid2, _ = tmp_dal.start_take(sid, "1", 1010.0)  # take_number=2
    # 把 tid2（原号 2）改成 1（已被 tid1 占用）→ tid2 获得 suffix '+'，编号 1
    tmp_dal.update_take_meta(tid2, take_number=1)
    take1 = tmp_dal.get_take(tid1)
    take2 = tmp_dal.get_take(tid2)
    assert take1 is not None
    assert take1.take_number == 1  # take1 编号不变
    assert take1.take_suffix == ""  # take1 suffix 不变
    assert take2 is not None
    assert take2.take_number == 1  # tid2 也改成 1
    assert take2.take_suffix == "+"  # tid2 得到 '+' 后缀


def test_update_take_meta_case_b_double_suffix(tmp_dal: DAL) -> None:
    """情形 B 续：已有 (sid,shot,'1','') 和 (sid,shot,'1','+')，再移一条到 take_number=1 → suffix='++'。"""
    sid = tmp_dal.create_scene("S1")
    _t_a, _ = tmp_dal.start_take(sid, "1", 1000.0)   # (sid,shot="1", number=1,'')
    t_b, _ = tmp_dal.start_take(sid, "1", 1010.0)    # (sid,shot="1", number=2,'')
    t_c, _ = tmp_dal.start_take(sid, "1", 1020.0)    # (sid,shot="1", number=3,'')
    # t_b 移到 1 → (sid,"1",1,'') 被占 → t_b 得 '+'
    tmp_dal.update_take_meta(t_b, take_number=1)
    # t_c 再移到 1 → (sid,"1",1,'') 和 (sid,"1",1,'+') 都被占 → t_c 得 '++'
    tmp_dal.update_take_meta(t_c, take_number=1)
    take_c = tmp_dal.get_take(t_c)
    assert take_c is not None
    assert take_c.take_number == 1
    assert take_c.take_suffix == "++"


def test_update_take_meta_case_c_cross_scene_suffix(tmp_dal: DAL) -> None:
    """情形 C：跨场移动且目标 (scene_id, shot, take_number, '') 已占用 → 追加后缀而非抛异常。"""
    sid1 = tmp_dal.create_scene("S1")
    sid2 = tmp_dal.create_scene("S2")
    tid1, _ = tmp_dal.start_take(sid1, "1", 1000.0)
    # sid2 建一个 take（shot="1", take_number=1）
    tmp_dal.start_take(sid2, "1", 2000.0)
    # 把 tid1 跨场移到 sid2 并指定 take_number=1（已被占用），应追加 '+' 后缀
    tmp_dal.update_take_meta(tid1, scene_id=sid2, take_number=1)
    take1 = tmp_dal.get_take(tid1)
    assert take1 is not None
    assert take1.scene_id == sid2
    assert take1.take_number == 1
    assert take1.take_suffix == "+"


def test_update_take_meta_shot_notes_partial_update(tmp_dal: DAL) -> None:
    """改 shot 和 notes（含空串清空 notes），只改传入字段，其余保持原值。"""
    sid = tmp_dal.create_scene("S1")
    # v4 新签名：shot 作为第二参数（字符串）
    tid, _ = tmp_dal.start_take(sid, "Shot_A", 1000.0)
    # 改 shot，清空 notes（传 ""）
    tmp_dal.update_take_meta(tid, shot="Shot_B", notes="")
    take = tmp_dal.get_take(tid)
    assert take is not None
    assert take.shot == "Shot_B"
    assert take.notes == ""
    # 只传 None 不改字段
    tmp_dal.update_take_meta(tid, shot=None, notes=None)
    take2 = tmp_dal.get_take(tid)
    assert take2 is not None
    assert take2.shot == "Shot_B"   # 保持上次的值


def test_update_take_meta_writes_manual_edit_event(tmp_dal: DAL) -> None:
    """update_take_meta 成功后写一条 event_type='manual.edit' 的 take_event。"""
    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    tmp_dal.update_take_meta(tid, shot="Shot_X")
    events = tmp_dal.list_take_events(tid, event_type="manual.edit")
    assert len(events) == 1
    payload = events[0].payload
    assert "changed_fields" in payload
    assert "shot" in payload["changed_fields"]
    assert "conflict_resolution" in payload


# ── 2.B：delete_take（软删）─────────────────────────────────────────────────


def test_delete_take_soft_deletes_row(tmp_dal: DAL) -> None:
    """delete_take 后 take 行仍存在（软删），deleted_at 被设置，get_take 返回 None（排除软删）。"""
    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    tmp_dal.end_take(tid, 1060.0, "keep")
    tmp_dal.delete_take(tid)
    # get_take 排除软删行，返回 None
    assert tmp_dal.get_take(tid) is None
    # 物理行仍存在，deleted_at 不为 NULL
    row = tmp_dal._conn.execute(
        "SELECT deleted_at FROM takes WHERE take_id = ?;", (tid,)
    ).fetchone()
    assert row is not None
    assert row["deleted_at"] is not None


def test_delete_take_preserves_child_tables(tmp_dal: DAL) -> None:
    """delete_take 软删后，子表数据（transcript_segments/take_events/take_line_matches）保留。"""
    sid = tmp_dal.create_scene("S1")
    scr_id = tmp_dal.insert_script(sid, "剧本")
    lid = tmp_dal.insert_script_line(scr_id, 1, "HERO", "台词文本")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    tmp_dal.insert_segment(tid, 1, "SPEAKER_00", "hello", 0, 16000)
    tmp_dal.insert_take_event(tid, "manual.mark", {"status": "ng"}, 1010.0)
    tmp_dal.insert_take_line_match(tid, lid, "match", {})
    tmp_dal.delete_take(tid)
    # 子表数据仍存在（直接查物理行）
    seg_count = tmp_dal._conn.execute(
        "SELECT COUNT(*) FROM transcript_segments WHERE take_id = ?;", (tid,)
    ).fetchone()[0]
    assert seg_count == 1
    evt_count = tmp_dal._conn.execute(
        "SELECT COUNT(*) FROM take_events WHERE take_id = ?;", (tid,)
    ).fetchone()[0]
    assert evt_count >= 1  # 原始 1 条 + delete_take 写入的 audit take_event 如有
    match_count = tmp_dal._conn.execute(
        "SELECT COUNT(*) FROM take_line_matches WHERE take_id = ?;", (tid,)
    ).fetchone()[0]
    assert match_count == 1


def test_delete_take_writes_audit_log(tmp_dal: DAL) -> None:
    """delete_take 在 audit_log 留下一条 take.delete 记录，含被删 take 快照。"""
    import json

    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    tmp_dal.end_take(tid, 1060.0, "keep")
    tmp_dal.delete_take(tid)
    rows = tmp_dal._conn.execute(
        "SELECT payload FROM audit_log WHERE action='take.delete' ORDER BY ts DESC;"
    ).fetchall()
    assert len(rows) >= 1
    payload = json.loads(rows[0]["payload"])
    assert payload["take_id"] == tid
    assert payload["scene_id"] == sid
    assert payload["take_number"] == 1
    assert payload["status"] == "keep"


def test_delete_take_nonexistent_is_noop(tmp_dal: DAL) -> None:
    """delete_take 传不存在的 take_id 静默 no-op，不抛异常。"""
    tmp_dal.delete_take(99999)  # 不应抛异常


def test_restore_take_clears_deleted_at(tmp_dal: DAL) -> None:
    """restore_take 后 deleted_at 清为 NULL，get_take 重新可见。"""
    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    tmp_dal.end_take(tid, 1060.0, "keep")
    tmp_dal.delete_take(tid)
    assert tmp_dal.get_take(tid) is None  # 软删后不可见
    tmp_dal.restore_take(tid)
    restored = tmp_dal.get_take(tid)
    assert restored is not None
    assert restored.deleted_at is None  # type: ignore[attr-defined]


def test_restore_take_writes_audit_log(tmp_dal: DAL) -> None:
    """restore_take 在 audit_log 写 take.restore 记录。"""
    import json

    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    tmp_dal.delete_take(tid)
    tmp_dal.restore_take(tid)
    rows = tmp_dal._conn.execute(
        "SELECT payload FROM audit_log WHERE action='take.restore' ORDER BY ts DESC;"
    ).fetchall()
    assert len(rows) >= 1
    payload = json.loads(rows[0]["payload"])
    assert payload["take_id"] == tid


def test_list_takes_excludes_soft_deleted(tmp_dal: DAL) -> None:
    """list_takes 默认排除软删行。"""
    sid = tmp_dal.create_scene("S1")
    t1, _ = tmp_dal.start_take(sid, "1", 1000.0)
    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)
    tmp_dal.delete_take(t1)
    takes = tmp_dal.list_takes(sid)
    ids = [t.take_id for t in takes]
    assert t1 not in ids
    assert t2 in ids


def test_get_take_excludes_soft_deleted(tmp_dal: DAL) -> None:
    """get_take 软删后返回 None。"""
    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    tmp_dal.delete_take(tid)
    assert tmp_dal.get_take(tid) is None


def test_take_has_take_suffix_field(tmp_dal: DAL) -> None:
    """Take dataclass 含 take_suffix 字段，默认为空串。"""
    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    take = tmp_dal.get_take(tid)
    assert take is not None
    assert hasattr(take, "take_suffix")
    assert take.take_suffix == ""


def test_take_has_deleted_at_field(tmp_dal: DAL) -> None:
    """Take dataclass 含 deleted_at 字段，未软删时为 None。"""
    sid = tmp_dal.create_scene("S1")
    tid, _ = tmp_dal.start_take(sid, "1", 1000.0)
    take = tmp_dal.get_take(tid)
    assert take is not None
    assert hasattr(take, "deleted_at")
    assert take.deleted_at is None  # type: ignore[attr-defined]


# ── 2.C 新增：next_take_number ────────────────────────────────────────────────


def test_next_take_number_empty_scene_returns_1(tmp_dal: DAL) -> None:
    """空场（没有任何 take）时 next_take_number 返回 1（shot="1" 组）。"""
    sid = tmp_dal.create_scene("scene_ntn_empty")
    assert tmp_dal.next_take_number(sid, "1") == 1


def test_next_take_number_increments(tmp_dal: DAL) -> None:
    """已有 take 1、2 时返回 3（shot="1" 组内）。"""
    sid = tmp_dal.create_scene("scene_ntn_incr")
    tmp_dal.start_take(sid, "1", 1000.0)
    tmp_dal.start_take(sid, "1", 1001.0)
    assert tmp_dal.next_take_number(sid, "1") == 3


def test_next_take_number_soft_delete_highest_reuses(tmp_dal: DAL) -> None:
    """软删最高号后 next_take_number 复用该号（live MAX+1，软删号可复用）。

    复用语义：以 live 行中最大 take_number 为基准，返回 live MAX+1。
    shot="1" 组内 take 1/2/3，软删 3 后 live MAX=2 → next_take_number = 3（复用刚删的 3）。
    """
    sid = tmp_dal.create_scene("scene_ntn_del")
    t1, _ = tmp_dal.start_take(sid, "1", 1000.0)
    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)
    t3, _ = tmp_dal.start_take(sid, "1", 1002.0)
    tmp_dal.end_take(t1, 1010.0, "keep")
    tmp_dal.end_take(t2, 1020.0, "ng")
    tmp_dal.end_take(t3, 1030.0, "keep")
    tmp_dal.delete_take(t3)
    # live MAX = 2（take 3 已软删），下一个复用 3
    assert tmp_dal.next_take_number(sid, "1") == 3


# ── 2.C 新增：get_or_create_scene ────────────────────────────────────────────


def test_get_or_create_scene_new_returns_created_true(tmp_dal: DAL) -> None:
    """新 scene_code 建场返回 created=True，scene_id > 0。"""
    sid, created = tmp_dal.get_or_create_scene("NewScene_1")
    assert created is True
    assert isinstance(sid, int)
    assert sid > 0


def test_get_or_create_scene_existing_returns_created_false(tmp_dal: DAL) -> None:
    """已有 scene_code 再次调用返回 created=False，返回既有 scene_id。"""
    sid1, _ = tmp_dal.get_or_create_scene("Existing_Scene")
    sid2, created = tmp_dal.get_or_create_scene("Existing_Scene")
    assert created is False
    assert sid2 == sid1


def test_get_or_create_scene_does_not_update_existing(tmp_dal: DAL) -> None:
    """重复调用时忽略额外参数，不更新已有行 description。"""
    sid1, _ = tmp_dal.get_or_create_scene("Scene_NoUpdate", description="original")
    sid2, _ = tmp_dal.get_or_create_scene("Scene_NoUpdate", description="changed")
    # 查 description，应仍为 original
    scenes = tmp_dal.list_scenes()
    target = next(s for s in scenes if s["scene_id"] == sid1)
    assert target["description"] == "original"
    assert sid2 == sid1


# ── 复用语义：live MAX+1 + vacate（bug fix 2.x-scene-org）──────────────────────


def test_next_take_number_scene2_reproduction(tmp_dal: DAL) -> None:
    """真实复现场景：shot="1" 组内 live=1，软删 2/2+/2++/3/3+/4 → next_take_number 应返回 2。

    复用语义：live MAX+1，软删号可复用。live 只有 number=1 → next = 2。
    """
    sid = tmp_dal.create_scene("scene2_repro")
    # live take：number=1
    tmp_dal.start_take(sid, "1", 1000.0)
    # 软删的 take：通过连续 start_take（shot="1"）自动拿号 2/3/4
    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)  # → number=2
    t3, _ = tmp_dal.start_take(sid, "1", 1002.0)  # → number=3
    t4, _ = tmp_dal.start_take(sid, "1", 1003.0)  # → number=4
    # 用 DAL 直接插带 suffix 的行（模拟冲突追加的历史行，v4 需指定 shot）
    raw_conn = tmp_dal._conn
    raw_conn.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 2, '+', 1004.0);",
        (sid,),
    )
    raw_conn.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 2, '++', 1005.0);",
        (sid,),
    )
    raw_conn.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 3, '+', 1006.0);",
        (sid,),
    )
    raw_conn.commit()
    # 软删上述 take（t1 保持 live）
    tmp_dal.delete_take(t2)
    tmp_dal.delete_take(t3)
    tmp_dal.delete_take(t4)
    # 也软删带 suffix 的行（直接 UPDATE）
    raw_conn.execute(
        "UPDATE takes SET deleted_at = 9999.0 "
        "WHERE scene_id = ? AND shot = '1' AND take_number IN (2, 3) AND take_suffix != '';",
        (sid,),
    )
    raw_conn.commit()
    # 此时：live=1；软删 2/''/2+/2++/3/''/3+/4 → live MAX = 1 → next = 2（复用）
    assert tmp_dal.next_take_number(sid, "1") == 2


def test_start_take_succeeds_after_vacating_soft_deleted(tmp_dal: DAL) -> None:
    """start_take 通过内部 vacate 解决软删行冲突（复用号 = 新 take 拿干净 ''）。

    shot="1" 组内 take 1 live，take 2 软删 → start_take 复用号 2，成功：
      软删行 (2, '') 被挪到 (2, '+')，新 take 落 (2, '')。
    """
    sid = tmp_dal.create_scene("scene_start_no_collide")
    tmp_dal.start_take(sid, "1", 1000.0)   # → number=1 (live)
    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)  # → number=2
    tmp_dal.delete_take(t2)  # 软删 take 2

    # 复用语义：next_take_number 返回 2（live MAX+1）
    next_num = tmp_dal.next_take_number(sid, "1")
    assert next_num == 2, f"期望 2，实际 {next_num}"

    # start_take 内部 vacate 后不撞 UNIQUE
    new_tid, _ = tmp_dal.start_take(sid, "1", 1002.0)
    take = tmp_dal.get_take(new_tid)
    assert take is not None
    assert take.take_number == 2
    assert take.take_suffix == ""  # 新 take 落干净 ''


def test_update_take_meta_soft_deleted_vacates_on_number_change(tmp_dal: DAL) -> None:
    """手动把号改到被软删行占的 (shot,number,'') → 软删行 vacate（挪到 '+'），被编辑 take 落干净 ''。

    场景：shot="1" 组内 take 1(live)，take 2(软删)。把 take 1 改成 number=2：
      复用语义：软删行 vacate 让出 ''，take 1 落 (2, '') 不加后缀。
    """
    sid = tmp_dal.create_scene("scene_meta_suffix_soft")
    t1, _ = tmp_dal.start_take(sid, "1", 1000.0)   # → number=1 (live)
    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)   # → number=2
    tmp_dal.delete_take(t2)  # 软删 take 2

    # 把 take 1 的编号改成 2，软删行占了 (shot="1", 2,'')，新语义：vacate 后落干净 ''
    tmp_dal.update_take_meta(t1, take_number=2)

    take1 = tmp_dal.get_take(t1)
    assert take1 is not None
    assert take1.take_number == 2
    assert take1.take_suffix == "", f"期望干净 '' 后缀，实际 '{take1.take_suffix}'"


def test_update_take_meta_case_a_append_reuses_soft_deleted(tmp_dal: DAL) -> None:
    """情形 A（仅移场）：目标场已有软删行，append 用 live MAX+1，复用软删号。

    scene1 有 take 1(live)；scene2 有 take 1(live)、take 2(软删)。
    把 take(scene1, 1) 移到 scene2 → live MAX(scene2, shot="1")=1 → 新号=2（复用软删号）。
    """
    sid1 = tmp_dal.create_scene("scene_a_skip_s1")
    sid2 = tmp_dal.create_scene("scene_a_skip_s2")
    t_from, _ = tmp_dal.start_take(sid1, "1", 1000.0)   # scene1 take1
    tmp_dal.start_take(sid2, "1", 1001.0)              # scene2 take1 (live)
    t2s2, _ = tmp_dal.start_take(sid2, "1", 1002.0)      # scene2 take2
    tmp_dal.delete_take(t2s2)  # 软删 scene2 的 take 2

    # 移场（情形 A）：live MAX(scene2, shot="1")=1 → 新号=2（复用），不跳到 3
    tmp_dal.update_take_meta(t_from, scene_id=sid2)

    moved = tmp_dal.get_take(t_from)
    assert moved is not None
    assert moved.scene_id == sid2
    assert moved.take_number == 2, f"期望复用软删号 2，实际 {moved.take_number}"


def test_restore_take_no_unique_conflict_after_vacate(tmp_dal: DAL) -> None:
    """回归：delete take → 新建（复用号，vacate）→ restore 被删的那条 → 不撞 UNIQUE。

    复用语义下 next_take_number 返回 live MAX+1=2，start_take vacate 把旧软删行挪到 '+'，
    新 take 落 (2, '')，restore 后旧 take 在 (2, '+')，不撞新 take 的 (2, '')。
    """
    sid = tmp_dal.create_scene("scene_restore_no_conflict")
    tmp_dal.start_take(sid, "1", 1000.0)   # → number=1 (live)
    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)  # → number=2

    # 软删 t2（号=2）
    tmp_dal.delete_take(t2)

    # next_take_number 复用 2（live MAX+1）
    next_num = tmp_dal.next_take_number(sid, "1")
    assert next_num == 2
    # start_take vacate：t2 被挪到 '+'，新 take 落 (2, '')
    t3, _ = tmp_dal.start_take(sid, "1", 1002.0)

    # restore t2（现在在 (2, '+')）：不撞新 take 的 (2, '')
    tmp_dal.restore_take(t2)

    # 验证两条 take 都可见
    restored = tmp_dal.get_take(t2)
    assert restored is not None
    assert restored.take_number == 2
    assert restored.take_suffix == "+"  # 已被挪到 '+'
    assert restored.deleted_at is None  # type: ignore[attr-defined]

    take_new = tmp_dal.get_take(t3)
    assert take_new is not None
    assert take_new.take_number == 2


# ── reset_all ────────────────────────────────────────────────────────────────


def test_reset_all_clears_all_business_tables(tmp_dal: DAL) -> None:
    """reset_all() 清空全部业务表，含 FTS 影子表（实测）。"""
    # 造数据：scene → take → segment + event；script → script_line；take_line_match
    sid = tmp_dal.create_scene("scene_reset")
    tmp_dal.set_active_scene(sid)
    script_id = tmp_dal.insert_script(sid, "角色：台词", version=1)
    line_id = tmp_dal.insert_script_line(script_id, 1, "角色", "台词")
    take_id, _ = tmp_dal.start_take(sid, "", 100.0)
    tmp_dal.insert_segment(take_id, 1, "SPK_A", "台词", 0, 1000)
    tmp_dal.insert_take_event(take_id, "test.event", {}, 100.0)
    tmp_dal.insert_take_line_match(take_id, line_id, "match", {})
    tmp_dal.upsert_observer("conn_1", "观察者")
    tmp_dal.append_audit("user", "test.action", {})

    # 执行清空
    tmp_dal.reset_all()

    # 断言全部业务表清空
    conn = tmp_dal._conn
    assert conn.execute("SELECT count(*) FROM scenes").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM takes").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM take_events").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM transcript_segments").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM scripts").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM script_lines").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM take_line_matches").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM active_observers").fetchone()[0] == 0
    # FTS 影子表：content table 模式下用 count(*) 读取
    assert conn.execute("SELECT count(*) FROM script_lines_fts").fetchone()[0] == 0


# ── app_settings KV（v8）────────────────────────────────────────────────────────


def test_v8_migration_creates_app_settings_table(tmp_path: Path) -> None:
    """v8 迁移后 app_settings 表存在。"""
    db_path = tmp_path / "test.db"
    apply_migrations(db_path)
    conn = _raw_conn(db_path)
    names = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
    }
    assert "app_settings" in names
    conn.close()


def test_get_setting_missing_returns_none(tmp_dal: DAL) -> None:
    """不存在的 key 返回 None。"""
    assert tmp_dal.get_setting("nonexistent") is None


def test_set_and_get_setting(tmp_dal: DAL) -> None:
    """set_setting 后 get_setting 能读回。"""
    tmp_dal.set_setting("audio_input_device", "MacBook Pro Microphone")
    assert tmp_dal.get_setting("audio_input_device") == "MacBook Pro Microphone"


def test_set_setting_upsert(tmp_dal: DAL) -> None:
    """同一 key 多次 set_setting 覆盖上一次，get_setting 返回最新值。"""
    tmp_dal.set_setting("audio_input_device", "Old Device")
    tmp_dal.set_setting("audio_input_device", "New Device")
    assert tmp_dal.get_setting("audio_input_device") == "New Device"


def test_set_setting_multiple_keys(tmp_dal: DAL) -> None:
    """多个不同 key 独立存储，互不干扰。"""
    tmp_dal.set_setting("key_a", "val_a")
    tmp_dal.set_setting("key_b", "val_b")
    assert tmp_dal.get_setting("key_a") == "val_a"
    assert tmp_dal.get_setting("key_b") == "val_b"


def _build_db_through(db_path: Path, last_version: int) -> None:
    """按顺序执行 v1..last_version 的 migration SQL，造一个到指定版本的真实库（不含更高版本）。

    用于测试增量升级：先到 vN，再 apply_migrations 跑 v(N+1).. 。各 .sql 末尾自设 user_version，
    末尾再显式钉 last_version 兜底（防个别文件没设）。
    """
    import sqlite3 as _sql

    from backend.db.migrations.runner import MIGRATIONS_DIR

    conn = _sql.connect(str(db_path))
    for v in range(1, last_version + 1):
        conn.executescript((MIGRATIONS_DIR / MIGRATION_FILES[v]).read_text(encoding="utf-8"))
    conn.execute(f"PRAGMA user_version = {last_version};")
    conn.commit()
    conn.close()


def test_incremental_upgrade_v8_to_latest(tmp_path: Path) -> None:
    """既有 v8 真实库平滑升级到最新（v9 status_rename + v10 script_uploads）：
    user_version=最新、核心表 + app_settings + script_uploads 都在、DAL 可读写。"""
    db_path = tmp_path / "v8_to_latest.db"
    _build_db_through(db_path, 8)

    apply_migrations(db_path)

    # 断言版本号：增量迁移会一路升到最新已注册版本
    conn = _raw_conn(db_path)
    version = conn.execute("PRAGMA user_version;").fetchone()[0]
    assert version == max(MIGRATION_FILES)

    # 断言表存在
    names = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    }
    assert "app_settings" in names
    assert "takes" in names  # v9 整表重建后仍在
    assert "script_uploads" in names  # v10 新增
    conn.close()

    # 断言可通过 DAL 读写（DAL 自行调用 apply_migrations，幂等）
    dal = DAL(db_path)
    dal.set_setting("audio_input_device", "USB Mic")
    assert dal.get_setting("audio_input_device") == "USB Mic"
    dal.close()


def test_v10_incremental_upgrade_script_uploads(tmp_path: Path) -> None:
    """既有 v8 库平滑升级（经 v9 status_rename）到 v10：script_uploads 表存在且 DAL 可增删查改。

    用 _build_db_through(8) 造真实库（含 takes），确保中途的 v9_status_rename 整表重建不报错。
    """
    db_path = tmp_path / "v8_to_v10.db"
    _build_db_through(db_path, 8)

    apply_migrations(db_path)

    conn = _raw_conn(db_path)
    assert conn.execute("PRAGMA user_version;").fetchone()[0] == max(MIGRATION_FILES)
    names = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
    }
    assert "script_uploads" in names
    conn.close()

    # DAL 可增删查改 script_uploads
    dal = DAL(db_path)
    uid = dal.insert_script_upload("剧本.docx", "内 咖啡馆 日\n罗湘：你好。")
    info = dal.get_script_upload(uid)
    assert info["filename"] == "剧本.docx"
    assert info["status"] == "uploaded"
    assert info["char_count"] > 0
    assert dal.get_script_upload_raw(uid).startswith("内 咖啡馆")
    dal.update_script_upload_status(uid, "parsed", "导入 2 场")
    assert dal.get_script_upload(uid)["status"] == "parsed"
    assert [u["upload_id"] for u in dal.list_script_uploads()] == [uid]
    dal.close()


def test_v9_status_rename_maps_old_values(tmp_path: Path) -> None:
    """v9 数据迁移：旧 keeper→keep、hold→pass（status 列 + note 聚合串 + take_events payload）；
    旧 CHECK 允许 keeper/hold，新 CHECK 只允许 pass/ng/keep/tbd。"""
    import sqlite3 as _sql

    db_path = tmp_path / "v9_data.db"
    _build_db_through(db_path, 8)  # v8：旧 CHECK 含 keeper/hold

    # 在旧库塞 scene + 两条带旧 status 的 take（旧 CHECK 允许）+ manual.note 事件
    conn = _sql.connect(str(db_path))
    conn.execute("INSERT INTO scenes (scene_id, scene_code, is_active) VALUES (1, 'S1', 1);")
    conn.execute(
        "INSERT INTO takes (take_id, scene_id, shot, take_number, start_ts, status, notes) "
        "VALUES (1, 1, '', 1, 0.0, 'keeper', '[t] @keeper 留着'), "
        "       (2, 1, '', 2, 0.0, 'hold', '[t] @hold 过了');"
    )
    conn.execute(
        "INSERT INTO take_events (take_id, event_type, ts, payload) VALUES "
        "(1, 'manual.note', 0.0, '{\"category\": \"keeper\", \"content\": \"留着\"}'), "
        "(2, 'manual.mark', 0.0, '{\"status\": \"hold\"}');"
    )
    conn.commit()
    conn.close()

    apply_migrations(db_path)  # 跑 v9

    conn = _raw_conn(db_path)
    rows = {r["take_id"]: r["status"] for r in conn.execute("SELECT take_id, status FROM takes;")}
    assert rows == {1: "keep", 2: "pass"}  # keeper→keep、hold→pass
    notes = {r["take_id"]: r["notes"] for r in conn.execute("SELECT take_id, notes FROM takes;")}
    assert "@keep" in notes[1] and "@keeper" not in notes[1]
    assert "@pass" in notes[2] and "@hold" not in notes[2]
    payloads = [
        r["payload"] for r in conn.execute("SELECT payload FROM take_events ORDER BY take_id;")
    ]
    assert '"category": "keep"' in payloads[0]
    assert '"status": "pass"' in payloads[1]

    # 新 CHECK：写旧值 keeper 被拒
    try:
        conn.execute("INSERT INTO takes (scene_id, take_number, start_ts, status) "
                     "VALUES (1, 9, 0.0, 'keeper');")
        raise AssertionError("旧 status 'keeper' 不应再被 CHECK 接受")
    except _sql.IntegrityError:
        pass
    conn.close()
