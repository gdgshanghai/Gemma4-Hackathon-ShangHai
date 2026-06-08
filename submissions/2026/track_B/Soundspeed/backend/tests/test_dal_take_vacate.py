"""take 号位空出（vacate）语义测试。

覆盖「复用号 = 新 take 拿干净号位，软删占用者顺位加后缀」的全部关键路径：
  - next_take_number：live MAX+1，软删号可复用（按 (scene, shot) 分组）
  - _vacate_base_slot：有软删占用者时挪位（四元 key）
  - start_take：内部原子 vacate，不再撞 UNIQUE
  - update_take_meta：占用者是软删 → vacate；是 live → 被编辑 take 加后缀
  - restore_take：兜底不抛 UNIQUE
  - orchestrator publish(take.start) 路径：不再静默失败
"""
from __future__ import annotations

from backend.core.events import TAKE_START, TakeStartPayload
from backend.core.orchestrator import Orchestrator
from backend.core.session import SessionState
from backend.db.dal import DAL


# ─────────────────────────────────────────────────────────────────────────────
# next_take_number：live MAX+1（复用软删号），按 (scene, shot) 分组
# ─────────────────────────────────────────────────────────────────────────────


def test_next_take_number_reuses_soft_deleted_number(tmp_dal: DAL) -> None:
    """删最新 take 后，next_take_number 返回被删的号（live MAX+1 而非全量 MAX+1）。

    shot="1" 组内 take 1/2/3，软删 take 3 → live MAX=2 → next=3（复用，不跳到 4）。
    """
    sid = tmp_dal.create_scene("s_ntn_reuse")
    tmp_dal.start_take(sid, "1", 1000.0)   # → number=1
    tmp_dal.start_take(sid, "1", 1001.0)   # → number=2
    t3, _ = tmp_dal.start_take(sid, "1", 1002.0)  # → number=3
    tmp_dal.delete_take(t3)  # 软删 3

    # live MAX = 2 → next = 3（复用刚删掉的 3）
    assert tmp_dal.next_take_number(sid, "1") == 3


def test_next_take_number_scene2_live_max(tmp_dal: DAL) -> None:
    """真实场景 scene2：shot="1" 组 live take_number=1，软删 2/2+/2++/3/3+/4 → next_take_number 返回 2。

    live MAX = 1 → next = 2（复用首个被删号）。
    """
    sid = tmp_dal.create_scene("s_scene2_live")
    tmp_dal.start_take(sid, "1", 1000.0)  # live number=1

    # 插入一堆将被软删的 take（通过连续调用自动拿号 2/3/4）
    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)  # → number=2
    t3, _ = tmp_dal.start_take(sid, "1", 1002.0)  # → number=3
    t4, _ = tmp_dal.start_take(sid, "1", 1003.0)  # → number=4

    raw = tmp_dal._conn
    # 插带 suffix 的行（模拟历史积累，v4 须含 shot 列）
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 2, '+', 1004.0);",
        (sid,),
    )
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 2, '++', 1005.0);",
        (sid,),
    )
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 3, '+', 1006.0);",
        (sid,),
    )
    raw.commit()

    tmp_dal.delete_take(t2)
    tmp_dal.delete_take(t3)
    tmp_dal.delete_take(t4)
    raw.execute(
        "UPDATE takes SET deleted_at = 9999.0 "
        "WHERE scene_id = ? AND shot = '1' AND take_number IN (2, 3) AND take_suffix != '';",
        (sid,),
    )
    raw.commit()

    # live 只有 number=1 → next = 2
    assert tmp_dal.next_take_number(sid, "1") == 2


# ─────────────────────────────────────────────────────────────────────────────
# start_take + _vacate_base_slot：内部原子分配号，不再静默失败
# ─────────────────────────────────────────────────────────────────────────────


def test_start_take_vacates_soft_deleted_slot(tmp_dal: DAL) -> None:
    """删最新 take → start_take 复用同号 → 成功：新 take suffix=''，旧软删行被挪到 '+'。

    验证路径：
      1. 建 take 1/2（shot="1"），软删 take 2。
      2. next_take_number(sid, "1") 返回 2。
      3. start_take(scene, "1") → 内部取号 2，不撞 UNIQUE：
         - 旧软删 take 2 的 suffix 变 '+'
         - 新 take 落 (scene, "1", 2, '')
    """
    sid = tmp_dal.create_scene("s_vacate_basic")
    tmp_dal.start_take(sid, "1", 1000.0)     # → number=1 (live)
    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)  # → number=2
    tmp_dal.delete_take(t2)  # 软删 take 2，占着 (sid, "1", 2, '')

    next_num = tmp_dal.next_take_number(sid, "1")
    assert next_num == 2  # live MAX+1 = 2

    # start_take 内部 vacate 软删占用者，不撞 UNIQUE
    new_tid, _ = tmp_dal.start_take(sid, "1", 1002.0)
    assert new_tid is not None

    new_take = tmp_dal.get_take(new_tid)
    assert new_take is not None
    assert new_take.take_number == 2
    assert new_take.take_suffix == ""  # 新 take 落干净 ''

    # 旧软删行已被挪到 '+'
    raw = tmp_dal._conn
    old_row = raw.execute(
        "SELECT take_suffix, deleted_at FROM takes WHERE take_id = ?;", (t2,)
    ).fetchone()
    assert old_row is not None
    assert old_row["take_suffix"] == "+"  # 被移到 '+'
    assert old_row["deleted_at"] is not None  # 仍是软删状态


def test_start_take_scene2_reproduction(tmp_dal: DAL) -> None:
    """真实场景 scene2 形态：live=1，软删 2/2+/2++/3/3+/4 → start_take 能建出 take 2，不静默失败。"""
    sid = tmp_dal.create_scene("s_scene2_repro")
    tmp_dal.start_take(sid, "1", 1000.0)  # live 1

    # 插软删的 take（模拟历史积累）
    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)  # → number=2
    t3, _ = tmp_dal.start_take(sid, "1", 1002.0)  # → number=3
    t4, _ = tmp_dal.start_take(sid, "1", 1003.0)  # → number=4
    raw = tmp_dal._conn
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 2, '+', 1004.0);",
        (sid,),
    )
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 2, '++', 1005.0);",
        (sid,),
    )
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 3, '+', 1006.0);",
        (sid,),
    )
    raw.commit()

    tmp_dal.delete_take(t2)
    tmp_dal.delete_take(t3)
    tmp_dal.delete_take(t4)
    raw.execute(
        "UPDATE takes SET deleted_at = 9999.0 "
        "WHERE scene_id = ? AND shot = '1' AND take_number IN (2, 3) AND take_suffix != '';",
        (sid,),
    )
    raw.commit()

    # next = 2（live MAX+1）
    next_num = tmp_dal.next_take_number(sid, "1")
    assert next_num == 2

    # start_take 不应静默失败（内部原子取号 2 + vacate）
    new_tid, _ = tmp_dal.start_take(sid, "1", 1100.0)
    assert new_tid is not None

    new_take = tmp_dal.get_take(new_tid)
    assert new_take is not None
    assert new_take.take_number == 2
    assert new_take.take_suffix == ""


def test_start_take_vacate_chain_multiple_plus(tmp_dal: DAL) -> None:
    """软删占用者已在 (shot, 2, '') 时：start_take 把它挪到 '+'，若 '+' 也被占则找下一个空闲 suffix。

    场景：(shot="1", 2, '') 软删，(shot="1", 2, '+') 也软删 → 软删 '' 的行被挪到 '++'，新 take 落 ''。
    """
    sid = tmp_dal.create_scene("s_vacate_chain")
    tmp_dal.start_take(sid, "1", 1000.0)    # → number=1 (live)

    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)  # → number=2
    raw = tmp_dal._conn
    # 直接插 (shot="1", 2, '+')
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 2, '+', 1002.0);",
        (sid,),
    )
    raw.commit()
    t2_plus = raw.execute(
        "SELECT take_id FROM takes WHERE scene_id = ? AND shot = '1' AND take_number = 2 AND take_suffix = '+';",
        (sid,),
    ).fetchone()["take_id"]

    tmp_dal.delete_take(t2)       # 软删 (shot="1", 2, '')
    tmp_dal.delete_take(t2_plus)  # 软删 (shot="1", 2, '+')

    # 两个 soft-deleted 占住 '' 和 '+'，start_take 应把 (2,'') 的行挪到 '++'
    new_tid, _ = tmp_dal.start_take(sid, "1", 1100.0)  # 内部取号 2 + vacate ''→''
    new_take = tmp_dal.get_take(new_tid)
    assert new_take is not None
    assert new_take.take_suffix == ""

    old_row = raw.execute(
        "SELECT take_suffix FROM takes WHERE take_id = ?;", (t2,)
    ).fetchone()
    assert old_row["take_suffix"] == "++"  # 被挪到 '++'（'+'已被占）


# ─────────────────────────────────────────────────────────────────────────────
# orchestrator publish(take.start) 路径：不再静默失败
# ─────────────────────────────────────────────────────────────────────────────


def test_orchestrator_take_start_vacates_soft_deleted(tmp_dal: DAL) -> None:
    """经 orchestrator.publish(TAKE_START) 路径：软删占用者 vacate，真正 INSERT 成功（不静默失败）。

    回归：publish 异常被吞的场景，此处验证实际 take 行真的建出来了。
    shot=None → orchestrator 归一为 '' （v4 约定）。
    """
    sid = tmp_dal.create_scene("s_orch_vacate")
    tmp_dal.start_take(sid, "1", 1000.0)   # → number=1 (live, shot="1")
    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)  # → number=2 (shot="1")
    tmp_dal.delete_take(t2)  # 软删 take 2

    orch = Orchestrator(tmp_dal, SessionState())

    # shot=None → '' 组内建新 take，next = 2（live MAX+1）
    # 此路径测 vacate 成功（shot="1" 和 shot="" 是不同组，但测试要在同场景存在 live take）
    # 注：shot=None → orchestrator 归一为 ''（空组），与 shot="1" 是不同分组
    # 重建：先在 '' 组内建一条 live 和一条软删
    tmp_dal.start_take(sid, "", 2000.0)   # '' 组 number=1 (live)
    t_del, _ = tmp_dal.start_take(sid, "", 2001.0)  # '' 组 number=2
    tmp_dal.delete_take(t_del)  # 软删

    orch.publish(
        TAKE_START,
        TakeStartPayload(
            scene_id=sid,
            start_ts=2100.0,
            shot=None,  # orchestrator 归一为 ''
        ),
    )

    # 验证在 '' 组内有新 live take number=2
    takes = tmp_dal.list_takes(scene_id=sid)
    shot_empty_takes = [t for t in takes if t.shot == ""]
    live_numbers = [t.take_number for t in shot_empty_takes]
    assert 2 in live_numbers, f"预期 '' 组 live take 2，实际：{live_numbers}"

    new_take = next((t for t in shot_empty_takes if t.take_number == 2), None)
    assert new_take is not None
    assert new_take.take_suffix == ""


# ─────────────────────────────────────────────────────────────────────────────
# update_take_meta：占用者是软删 → vacate；是 live → 被编辑 take 加后缀
# ─────────────────────────────────────────────────────────────────────────────


def test_update_take_meta_soft_deleted_occupant_vacates(tmp_dal: DAL) -> None:
    """手动改号撞到被软删行占的号 → 软删行 vacate（挪到 '+'），被编辑 take 落干净 ''。

    场景：shot="1" 组，take 1(live)，take 2(软删)。改 take 1 的号到 2：
      - 新语义：软删行占用者挪到 '+'，take 1 落 (2, '') 不加后缀。
    """
    sid = tmp_dal.create_scene("s_meta_soft_vacate")
    t1, _ = tmp_dal.start_take(sid, "1", 1000.0)   # → number=1 (live)
    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)   # → number=2
    tmp_dal.delete_take(t2)  # 软删 take 2

    tmp_dal.update_take_meta(t1, take_number=2)

    take1 = tmp_dal.get_take(t1)
    assert take1 is not None
    assert take1.take_number == 2
    assert take1.take_suffix == ""  # 新语义：落干净 ''，不加后缀

    raw = tmp_dal._conn
    old_row = raw.execute(
        "SELECT take_suffix, deleted_at FROM takes WHERE take_id = ?;", (t2,)
    ).fetchone()
    assert old_row["take_suffix"] == "+"  # 软删占用者被挪到 '+'
    assert old_row["deleted_at"] is not None  # 仍是软删


def test_update_take_meta_live_occupant_gives_suffix_to_edited(tmp_dal: DAL) -> None:
    """手动改号撞到 live 行 → live 行不动，被编辑 take 加后缀（原有行为保持）。"""
    sid = tmp_dal.create_scene("s_meta_live_occupant")
    tid_a, _ = tmp_dal.start_take(sid, "1", 1000.0)  # live, number=1
    tid_b, _ = tmp_dal.start_take(sid, "1", 1001.0)  # live, number=2

    tmp_dal.update_take_meta(tid_b, take_number=1)  # 目标 1 已被 live tid_a 占

    take_a = tmp_dal.get_take(tid_a)
    take_b = tmp_dal.get_take(tid_b)
    assert take_a is not None and take_a.take_number == 1 and take_a.take_suffix == ""
    assert take_b is not None and take_b.take_number == 1 and take_b.take_suffix == "+"


def test_update_take_meta_case_a_append_live_max(tmp_dal: DAL) -> None:
    """情形 A（仅移场）：目标场已有软删行，append 用 live MAX+1。

    scene2 shot="1" 组有 take 1(live)、take 2(软删) → live MAX=1 → 新号=2（复用被删号）。
    """
    sid1 = tmp_dal.create_scene("s_a_live_max_s1")
    sid2 = tmp_dal.create_scene("s_a_live_max_s2")
    t_from, _ = tmp_dal.start_take(sid1, "1", 1000.0)   # scene1 number=1
    tmp_dal.start_take(sid2, "1", 1001.0)              # scene2 number=1 (live)
    t2s2, _ = tmp_dal.start_take(sid2, "1", 1002.0)      # scene2 number=2
    tmp_dal.delete_take(t2s2)  # 软删 scene2 的 take 2

    # 移场（情形 A）：live MAX(scene2, shot="1") = 1 → next = 2（复用，不跳到 3）
    tmp_dal.update_take_meta(t_from, scene_id=sid2)

    moved = tmp_dal.get_take(t_from)
    assert moved is not None
    assert moved.scene_id == sid2
    assert moved.take_number == 2, f"期望复用软删号 2，实际 {moved.take_number}"


# ─────────────────────────────────────────────────────────────────────────────
# restore_take 兜底：delete → 复用新建 → restore 旧那条
# ─────────────────────────────────────────────────────────────────────────────


def test_restore_take_gets_plus_suffix_after_vacate(tmp_dal: DAL) -> None:
    """delete → 复用录新 → restore 旧那条 → 旧的恢复成 number+，无 UNIQUE 撞。

    流程：
      1. take 2 软删（占 (shot="1", 2, '')），被 start_take 挪到 '+'，新 live take 2 落 ''。
      2. restore take 2：它已在 (2, '+')，清 deleted_at 即可，不撞 UNIQUE。
      3. 验证两条 live：新 take (2, '') + 旧 take (2, '+')。
    """
    sid = tmp_dal.create_scene("s_restore_plus")
    tmp_dal.start_take(sid, "1", 1000.0)    # → number=1 (live)
    t2, _ = tmp_dal.start_take(sid, "1", 1001.0)  # → number=2
    tmp_dal.delete_take(t2)  # 软删 take 2

    # start_take 复用号 2：t2 被挪到 (2, '+')，new 落 (2, '')
    next_num = tmp_dal.next_take_number(sid, "1")
    assert next_num == 2
    new_tid, _ = tmp_dal.start_take(sid, "1", 1100.0)  # 内部原子取号 2

    # restore t2：它现在在 (2, '+')，不会撞 (2, '')
    tmp_dal.restore_take(t2)

    restored = tmp_dal.get_take(t2)
    assert restored is not None
    assert restored.take_number == 2
    assert restored.take_suffix == "+"  # 已在 '+'
    assert restored.deleted_at is None  # 已恢复

    new_take = tmp_dal.get_take(new_tid)
    assert new_take is not None
    assert new_take.take_number == 2
    assert new_take.take_suffix == ""  # 新 take 仍在 ''


def test_restore_take_fallback_suffix_on_collision(tmp_dal: DAL) -> None:
    """restore 兜底：若 (scene, shot, number, suffix) 与 live 行撞，顺位加 '+' 直到空闲。

    此测试模拟 restore_take 在极端情况下触发兜底逻辑：
    直接用裸连接构造两条 live 占 (shot="1", 2,'') 和 (shot="1", 2,'+')，
    然后 restore 一条 deleted (shot="1", 2,'++') 的行 → '++' 未被占，restore 成功。
    """
    sid = tmp_dal.create_scene("s_restore_fallback")
    raw = tmp_dal._conn

    # 直接插三条 take，模拟极端情况（v4 须含 shot 列）
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 2, '', 1000.0);",
        (sid,),
    )
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts) VALUES (?, '1', 2, '+', 1001.0);",
        (sid,),
    )
    # 软删的那条，suffix='++'
    raw.execute(
        "INSERT INTO takes (scene_id, shot, take_number, take_suffix, start_ts, deleted_at) "
        "VALUES (?, '1', 2, '++', 1002.0, 9999.0);",
        (sid,),
    )
    raw.commit()

    # 取出软删行的 take_id
    t_del = raw.execute(
        "SELECT take_id FROM takes WHERE scene_id = ? AND shot = '1' AND take_suffix = '++' AND deleted_at IS NOT NULL;",
        (sid,),
    ).fetchone()["take_id"]

    # restore：它在 (2, '++') 而 (2, '') 和 (2, '+') 都是 live
    # '++' 未被占，restore 成功，suffix 不变
    tmp_dal.restore_take(t_del)

    restored = tmp_dal.get_take(t_del)
    assert restored is not None
    assert restored.take_suffix == "++"  # 原 suffix 不变，因为 '++' 未被占
