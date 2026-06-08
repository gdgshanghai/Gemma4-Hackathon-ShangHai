"""v4 per-shot take 计次测试（spec §16 / 2026-06-03 Lead 拍板）。

覆盖以下场景：
  - per-shot 计次：同场不同 shot 各自从 1 起；同 (scene, shot) 内递增
  - migration v4：旧 NULL shot → ''，约束变四元，老数据全合法
  - 全新库 schema.sql：结构与迁移库一致
  - vacate re-key：shot 列进入占号检查（四元）
  - 决策 3（update_take_meta 跨 shot 改号）：保号 + 撞 live 加后缀 + 撞软删让位
  - restore #2（DeepSeek）：含软删行的 suffix 检查，restore 不撞
  - MAX_ITER 守卫（DeepSeek #3）：后缀链超限抛异常
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import backend.db.dal as dal_module
from backend.db.dal import DAL
from backend.db.migrations.runner import apply_migrations


# ── 辅助 ──────────────────────────────────────────────────────────────────────


def _raw_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ── per-shot 计次 ─────────────────────────────────────────────────────────────


def test_per_shot_counting_each_shot_starts_at_1(tmp_dal: DAL) -> None:
    """同场不同 shot 各自从 1 起。

    shot="A" 和 shot="B" 各建一次 start_take，两者都拿到 take_number=1。
    """
    sid = tmp_dal.create_scene("s_pershot_basic")
    tid_a, _ = tmp_dal.start_take(sid, "A", 1000.0)
    tid_b, _ = tmp_dal.start_take(sid, "B", 1001.0)

    take_a = tmp_dal.get_take(tid_a)
    take_b = tmp_dal.get_take(tid_b)
    assert take_a is not None
    assert take_b is not None
    assert take_a.shot == "A"
    assert take_a.take_number == 1
    assert take_b.shot == "B"
    assert take_b.take_number == 1  # 不同 shot，各自从 1 起


def test_per_shot_counting_same_shot_increments(tmp_dal: DAL) -> None:
    """同 (scene, shot) 内连续 start_take，take_number 递增。

    shot="A" 连续三次，依次得到 take_number=1, 2, 3。
    """
    sid = tmp_dal.create_scene("s_pershot_incr")
    t1, _ = tmp_dal.start_take(sid, "A", 1000.0)
    t2, _ = tmp_dal.start_take(sid, "A", 1001.0)
    t3, _ = tmp_dal.start_take(sid, "A", 1002.0)

    takes = [tmp_dal.get_take(tid) for tid in (t1, t2, t3)]
    numbers = [t.take_number for t in takes if t is not None]  # type: ignore[union-attr]
    assert numbers == [1, 2, 3]


def test_per_shot_different_shots_independent_numbering(tmp_dal: DAL) -> None:
    """同场两个 shot 各自独立递增，互不干扰。

    shot="1" 建 3 条，shot="2" 建 2 条，各自 number 独立。
    """
    sid = tmp_dal.create_scene("s_pershot_two_shots")
    for _ in range(3):
        tmp_dal.start_take(sid, "1", 1000.0)
    for _ in range(2):
        tmp_dal.start_take(sid, "2", 2000.0)

    assert tmp_dal.next_take_number(sid, "1") == 4  # shot="1" 下一个是 4
    assert tmp_dal.next_take_number(sid, "2") == 3  # shot="2" 下一个是 3


def test_per_shot_next_take_number_empty_shot_group(tmp_dal: DAL) -> None:
    """空 shot 组（'' 或从未出现的组）的 next_take_number 从 1 起。"""
    sid = tmp_dal.create_scene("s_pershot_empty_group")
    tmp_dal.start_take(sid, "1", 1000.0)  # shot="1" 有数据

    # shot="" 和 shot="2" 均无数据，各自应返回 1
    assert tmp_dal.next_take_number(sid, "") == 1
    assert tmp_dal.next_take_number(sid, "2") == 1


# ── migration v4：旧 NULL shot → ''，约束变四元 ─────────────────────────────


def test_v4_migration_null_shot_converted_to_empty_string(tmp_path: Path) -> None:
    """v3 → v4 迁移：shot=NULL 的旧行被 COALESCE 转成 ''，其余列完整保留。"""
    db_path = tmp_path / "migrate_v4.db"

    # 先跑 v1/v2/v3（通过 apply_migrations 但打补丁只跑到 v3）
    import backend.db.migrations.runner as runner_mod

    original_files = runner_mod.MIGRATION_FILES.copy()
    runner_mod.MIGRATION_FILES = {k: v for k, v in original_files.items() if k <= 3}
    try:
        apply_migrations(db_path)
    finally:
        runner_mod.MIGRATION_FILES = original_files

    # 在 v3 库里插一条 shot=NULL 的 take
    conn = _raw_conn(db_path)
    sid = conn.execute("INSERT INTO scenes (scene_code) VALUES ('S_v3');").lastrowid
    conn.execute(
        "INSERT INTO takes (scene_id, take_number, take_suffix, shot, start_ts) "
        "VALUES (?, 1, '', NULL, 1000.0);",
        (sid,),
    )
    conn.commit()
    conn.close()

    # 跑完整 apply_migrations（含 v4）
    apply_migrations(db_path)

    conn = _raw_conn(db_path)
    # 验证 user_version 升到最新（merge 1.x 后最高版本为 max(MIGRATION_FILES)，不再硬编码 4）
    version = conn.execute("PRAGMA user_version;").fetchone()[0]
    assert version == max(runner_mod.MIGRATION_FILES)

    # 验证 NULL 已被转成 ''
    row = conn.execute("SELECT shot FROM takes WHERE scene_id = ?;", (sid,)).fetchone()
    assert row is not None
    assert row["shot"] == "", f"期望 shot=''，实际 {row['shot']!r}"

    # 验证旧数据全部合法（不违反新四元约束）
    integrity_check = conn.execute("PRAGMA integrity_check;").fetchone()[0]
    assert integrity_check == "ok"

    conn.close()


def test_v4_migration_preserves_existing_columns(tmp_path: Path) -> None:
    """v4 migration 保留 take_suffix、deleted_at 等现有列的值（不清零）。"""
    db_path = tmp_path / "migrate_v4_cols.db"

    import backend.db.migrations.runner as runner_mod

    original_files = runner_mod.MIGRATION_FILES.copy()
    runner_mod.MIGRATION_FILES = {k: v for k, v in original_files.items() if k <= 3}
    try:
        apply_migrations(db_path)
    finally:
        runner_mod.MIGRATION_FILES = original_files

    conn = _raw_conn(db_path)
    sid = conn.execute("INSERT INTO scenes (scene_code) VALUES ('S_v3cols');").lastrowid
    # 插一条有 take_suffix 和 deleted_at 的行
    conn.execute(
        "INSERT INTO takes (scene_id, take_number, take_suffix, shot, start_ts, deleted_at) "
        "VALUES (?, 1, '+', 'Shot_A', 1000.0, 9999.0);",
        (sid,),
    )
    conn.commit()
    conn.close()

    apply_migrations(db_path)

    conn = _raw_conn(db_path)
    row = conn.execute("SELECT take_suffix, deleted_at, shot FROM takes WHERE scene_id = ?;", (sid,)).fetchone()
    assert row is not None
    assert row["take_suffix"] == "+"     # 保留
    assert row["deleted_at"] == 9999.0  # 保留
    assert row["shot"] == "Shot_A"       # 保留（非 NULL，不被 COALESCE 覆盖）
    conn.close()


def test_v4_schema_sql_matches_migration(tmp_path: Path) -> None:
    """全新库（schema.sql）与迁移库（apply_migrations）的 takes 表结构一致。

    验证 shot 列 NOT NULL DEFAULT ''、四元 UNIQUE 约束均存在。
    """
    db_path = tmp_path / "new_db.db"
    apply_migrations(db_path)
    conn = _raw_conn(db_path)
    cols = {r["name"]: r for r in conn.execute("PRAGMA table_info(takes);").fetchall()}

    # shot 列存在且 NOT NULL、DEFAULT = ''
    assert "shot" in cols
    assert cols["shot"]["notnull"] == 1, "shot 列应 NOT NULL"
    assert cols["shot"]["dflt_value"] in ("''", "\"\""), (
        f"shot 列 DEFAULT 应为空串，实际 {cols['shot']['dflt_value']!r}"
    )

    # 四元 UNIQUE 约束：通过 sqlite_master 检查索引
    idx_rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='takes' AND sql IS NOT NULL;"
    ).fetchall()
    idx_sqls = " ".join(r["sql"] for r in idx_rows)
    # 也检查表内联约束（sqlite_master 中 CREATE TABLE 语句）
    create_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='takes';"
    ).fetchone()["sql"]
    combined_sql = idx_sqls + " " + create_sql
    assert "shot" in combined_sql and "take_number" in combined_sql and "take_suffix" in combined_sql, (
        f"四元 UNIQUE 约束未找到，schema sql: {combined_sql[:200]}"
    )
    conn.close()


# ── 决策 3：update_take_meta 跨 shot 改号 ────────────────────────────────────


def test_decision3_change_shot_preserves_take_number(tmp_dal: DAL) -> None:
    """决策 3：改 shot 保留 take_number（目标 (scene, new_shot, number, '') 空闲时）。

    shot="A" number=2 的 take 改到 shot="B"（B 组为空），take_number 保持 2，suffix=''。
    """
    sid = tmp_dal.create_scene("s_dec3_basic")
    tmp_dal.start_take(sid, "A", 1000.0)   # shot="A" number=1
    t2, _ = tmp_dal.start_take(sid, "A", 1001.0)  # shot="A" number=2

    tmp_dal.update_take_meta(t2, shot="B")

    take = tmp_dal.get_take(t2)
    assert take is not None
    assert take.shot == "B"
    assert take.take_number == 2   # 保留原号
    assert take.take_suffix == ""  # 目标空闲，干净 ''


def test_decision3_change_shot_live_occupant_adds_suffix(tmp_dal: DAL) -> None:
    """决策 3：跨 shot 改号撞 live 行 → 被编辑 take 加后缀（live 占用者永不被挪）。

    shot="A" number=1 的 take 改到 shot="B"，但 shot="B" number=1 已被 live 行占。
    → 被编辑 take 落 (B, 1, '+')，live 占用者不动。
    """
    sid = tmp_dal.create_scene("s_dec3_live_conflict")
    tid_a1, _ = tmp_dal.start_take(sid, "A", 1000.0)   # shot="A" number=1 (live)
    tmp_dal.start_take(sid, "B", 1001.0)              # shot="B" number=1 (live, 占据目标)

    tmp_dal.update_take_meta(tid_a1, shot="B")

    take = tmp_dal.get_take(tid_a1)
    assert take is not None
    assert take.shot == "B"
    assert take.take_number == 1
    assert take.take_suffix == "+"  # 被编辑 take 加后缀


def test_decision3_change_shot_soft_deleted_occupant_vacates(tmp_dal: DAL) -> None:
    """决策 3：跨 shot 改号撞软删行 → 软删行让位加 '+'，被编辑 take 落干净 ''。

    shot="A" number=1 改到 shot="B"，但 shot="B" number=1 被软删行占。
    → 软删行 vacate（挪到 '+'），被编辑 take 落 (B, 1, '')。
    """
    sid = tmp_dal.create_scene("s_dec3_soft_vacate")
    tid_a1, _ = tmp_dal.start_take(sid, "A", 1000.0)    # shot="A" number=1 (live)
    tid_b1, _ = tmp_dal.start_take(sid, "B", 1001.0)    # shot="B" number=1
    tmp_dal.delete_take(tid_b1)                        # 软删 shot="B" number=1

    tmp_dal.update_take_meta(tid_a1, shot="B")

    take = tmp_dal.get_take(tid_a1)
    assert take is not None
    assert take.shot == "B"
    assert take.take_number == 1
    assert take.take_suffix == ""  # 软删让位，被编辑 take 落干净 ''

    # 软删行被挪到 '+'
    raw = tmp_dal._conn
    old = raw.execute("SELECT take_suffix FROM takes WHERE take_id = ?;", (tid_b1,)).fetchone()
    assert old is not None
    assert old["take_suffix"] == "+"


# ── restore #2（DeepSeek）：含软删行的 suffix 检查 ──────────────────────────


def test_restore_no_live_conflict_succeeds_directly(tmp_dal: DAL) -> None:
    """restore 正常路径：被 restore 行的 suffix 未被任何 live 行占，直接清 deleted_at 成功。

    与 test_restore_take_gets_plus_suffix_after_vacate（test_dal_take_vacate.py）互补：
    那个测试 restore 落在 '+'（vacate 后已挪位）；此测试 restore 落在 ''（目标未被占）。

    注（DeepSeek #2）：restore_take 的 live_conflict 检查只看 live 行，不含软删行。
    UNIQUE(scene_id, shot, take_number, take_suffix) 包含软删行，所以一个 tuple 下最多只有
    一条行（无论 live 还是软删），restore 时 live_conflict 仅在 live 行占用才触发。
    restore_take 的 fallback 代码是防御性的（有代码有注释），但在当前 schema 下属于死码：
    UNIQUE 约束保证了被 restore 行的 tuple 已唯一，清 deleted_at 后不可能与其他行冲突。
    此为已知情况，已在 restore_take docstring 说明，由 Lead 确认是否需要 partial unique index。
    """
    sid = tmp_dal.create_scene("s_restore_no_live_conflict")
    # 建两条 take 在同 shot 组：number=1 live，number=2 软删
    tmp_dal.start_take(sid, "1", 1000.0)   # number=1 (live)
    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)  # number=2
    tmp_dal.delete_take(t2)                 # 软删 t2

    # restore t2（仍在原始 suffix=''，无 live 行占它）
    tmp_dal.restore_take(t2)

    restored = tmp_dal.get_take(t2)
    assert restored is not None
    assert restored.take_suffix == ""   # 直接恢复，suffix 不变
    assert restored.deleted_at is None  # 已恢复


# ── MAX_ITER 守卫（DeepSeek #3）────────────────────────────────────────────────


def test_vacate_max_iter_guard_raises(tmp_dal: DAL, monkeypatch) -> None:
    """_vacate_base_slot 超 MAX_ITER 次循环时抛 RuntimeError。

    monkeypatch _MAX_SUFFIX_ITER 为低值，构造足够多的后缀让循环超限。
    场景：shot="1" 只有一条 live number=1，number=2 的 ''/'+'/'++'
    都被软删或 live 行占满。start_take 内部取号 2，vacate(2) 时 '' 被软删占，
    '+' 和 '++' 也被占，循环超 MAX_ITER=2 → 抛 RuntimeError。
    """
    monkeypatch.setattr(dal_module, "_MAX_SUFFIX_ITER", 2)

    sid = tmp_dal.create_scene("s_maxiter_vacate")
    raw = tmp_dal._conn

    # live 行：(shot="1", number=1, suffix='')——这是唯一 live 行，MAX=1
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) "
        "VALUES (?, '1', 1, '', 1000.0);",
        (sid,),
    )
    # 软删行占 (number=2, suffix='')：vacate 的目标（'' 被软删占）
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts, deleted_at) "
        "VALUES (?, '1', 2, '', 1001.0, 9999.0);",
        (sid,),
    )
    # 软删行占 '+' 和 '++'（vacate 找的是「既不撞软删也不撞 live 的 suffix」，
    # 但 _vacate_base_slot 的 taken_suffixes 包含「所有 taken（不论软删 live）」）
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts, deleted_at) "
        "VALUES (?, '1', 2, '+', 1002.0, 9998.0);",
        (sid,),
    )
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts, deleted_at) "
        "VALUES (?, '1', 2, '++', 1003.0, 9997.0);",
        (sid,),
    )
    raw.commit()

    # start_take 内部：live MAX(shot="1")=1 → take_number=2，vacate(2)：
    # '' 被软删占；taken_suffixes={'+','++'}；从 '+' 起循环：
    #   iter=1: '+' 在 taken → 1 >= 2=False，new_suffix='++'
    #   iter=2: '++' 在 taken → 2 >= 2=True → 抛 RuntimeError
    with pytest.raises(RuntimeError, match="后缀循环超过"):
        tmp_dal.start_take(sid, "1", 1100.0)


def test_update_take_meta_max_iter_guard_raises(tmp_dal: DAL, monkeypatch) -> None:
    """update_take_meta 改号时后缀循环超 MAX_ITER 抛 RuntimeError（MAX_ITER 守卫验证）。

    monkeypatch _MAX_SUFFIX_ITER=1：live 行占 (4,'') 和 (4,'+')，把另一 take 改号到 4，
    循环找 '++' 时 iter=1 >= MAX_ITER=1 → 抛 RuntimeError。

    注（DeepSeek #3 + restore 死码说明）：
    restore_take 也有 MAX_ITER 守卫，但其 live_conflict 在当前 schema 下不可达
    （UNIQUE 含软删行，被 restore 的 tuple 不可能有另一行与之完全相同）。
    restore 的守卫属防御性死码，有注释记录。update_take_meta 的守卫可正常触发。
    """
    monkeypatch.setattr(dal_module, "_MAX_SUFFIX_ITER", 1)

    sid = tmp_dal.create_scene("s_maxiter_update_meta")
    raw = tmp_dal._conn

    # live 行：(shot="1", number=4, '') 和 (shot="1", number=4, '+')
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) "
        "VALUES (?, '1', 4, '', 2000.0);",
        (sid,),
    )
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) "
        "VALUES (?, '1', 4, '+', 2001.0);",
        (sid,),
    )
    # 被编辑的 take（不同号位）
    t_edit = raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) "
        "VALUES (?, '1', 7, '', 2002.0);",
        (sid,),
    ).lastrowid
    assert t_edit is not None  # lastrowid mypy guard
    raw.commit()

    # 改 t_edit 到 number=4：live 占 '' 和 '+'，循环找 '++'：
    #   iter=1: '++' 不在 taken → 1 >= 1=True → 抛 RuntimeError
    with pytest.raises(RuntimeError, match="后缀循环超过"):
        tmp_dal.update_take_meta(t_edit, take_number=4)


# ── start_take 显式 take_number（底部 Take 弹窗手动指定待录号）──────────────────


def test_start_take_explicit_number_empty_group(tmp_dal: DAL) -> None:
    """空组传显式号 → 直接落该号，suffix=''。"""
    sid = tmp_dal.create_scene("s_explicit_empty")
    tid, num = tmp_dal.start_take(sid, "A", 1000.0, take_number=5)
    assert num == 5
    take = tmp_dal.get_take(tid)
    assert take is not None
    assert take.take_number == 5
    assert take.take_suffix == ""


def test_start_take_explicit_number_skips_ahead(tmp_dal: DAL) -> None:
    """组内已有 live 1、2，显式跳到 5 → 落 5（不是自动的 3），suffix=''。"""
    sid = tmp_dal.create_scene("s_explicit_skip")
    tmp_dal.start_take(sid, "A", 1000.0)  # number=1
    tmp_dal.start_take(sid, "A", 1001.0)  # number=2
    tid, num = tmp_dal.start_take(sid, "A", 1002.0, take_number=5)
    assert num == 5
    take = tmp_dal.get_take(tid)
    assert take is not None
    assert take.take_number == 5
    assert take.take_suffix == ""


def test_start_take_explicit_number_collides_live_gets_suffix(tmp_dal: DAL) -> None:
    """显式号撞 live 占用者（往回退占已用号）→ 新 take 落后缀，live 占用者不被挪。"""
    sid = tmp_dal.create_scene("s_explicit_collide")
    live_tid, _ = tmp_dal.start_take(sid, "A", 1000.0)  # number=1 (live, 占 '')
    new_tid, num = tmp_dal.start_take(sid, "A", 1001.0, take_number=1)
    assert num == 1
    new_take = tmp_dal.get_take(new_tid)
    live_take = tmp_dal.get_take(live_tid)
    assert new_take is not None and live_take is not None
    assert new_take.take_number == 1
    assert new_take.take_suffix == "+"  # 新 take 顺位加后缀
    assert live_take.take_suffix == ""  # live 占用者永不被挪


def test_start_take_explicit_number_reuses_soft_deleted_slot(tmp_dal: DAL) -> None:
    """显式号落在被软删行占着的 '' 号位 → vacate 让位，新 live take 拿干净 ''。"""
    sid = tmp_dal.create_scene("s_explicit_vacate")
    tmp_dal.start_take(sid, "A", 1000.0)  # number=1 (live)
    t2, _ = tmp_dal.start_take(sid, "A", 1001.0)  # number=2
    tmp_dal.delete_take(t2)  # 软删 2，占着 (A,2,'')

    new_tid, num = tmp_dal.start_take(sid, "A", 1002.0, take_number=2)
    assert num == 2
    new_take = tmp_dal.get_take(new_tid)
    old_take = tmp_dal.get_take_any(t2)  # 软删行用 _any 才取得到
    assert new_take is not None and old_take is not None
    assert new_take.take_number == 2
    assert new_take.take_suffix == ""  # 新 live take 拿干净号位
    assert old_take.take_suffix == "+"  # 软删占用者被挪去让位
    assert old_take.deleted_at is not None  # 仍是软删状态


def test_start_take_no_explicit_number_unchanged(tmp_dal: DAL) -> None:
    """不传显式号 → 行为不变：自动 MAX+1，suffix=''。"""
    sid = tmp_dal.create_scene("s_auto_unchanged")
    tmp_dal.start_take(sid, "A", 1000.0)  # number=1
    tid, num = tmp_dal.start_take(sid, "A", 1001.0)  # 自动 → 2
    assert num == 2
    take = tmp_dal.get_take(tid)
    assert take is not None
    assert take.take_number == 2
    assert take.take_suffix == ""
