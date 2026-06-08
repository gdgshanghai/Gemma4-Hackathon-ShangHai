"""DAL note 方法（insert_note / list_notes）的测试用例。

TDD 红-绿节奏：先写测试，确认失败，再实现方法。
"""
from __future__ import annotations

import pytest

from backend.db.dal import DAL


@pytest.fixture
def dal(tmp_path):
    """每个测试一个临时 sqlite DAL，自动 close。"""
    d = DAL(tmp_path / "test.db")
    yield d
    d.close()


@pytest.fixture
def take_id(dal):
    """创建 scene + take，返回 take_id。"""
    dal._conn.execute("INSERT INTO scenes (scene_code, is_active) VALUES ('3A', 1)")
    scene_id = dal._conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    dal._conn.execute(
        "INSERT INTO takes (scene_id, take_number, start_ts, status) VALUES (?, 1, 1000.0, 'tbd')",
        (scene_id,),
    )
    dal._conn.commit()
    return dal._conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── insert_note ──────────────────────────────────────────────────────────────


def test_insert_note_creates_event(dal, take_id):
    """insert_note 后 take_events 中有一条 event_type='manual.note' 的记录。"""
    eid = dal.insert_note(take_id, "issue", "开头有飞机声", "开头有飞机声", 1686580201.0)
    assert isinstance(eid, int)
    assert eid > 0

    events = dal.list_take_events(take_id, event_type="manual.note")
    assert len(events) == 1
    assert events[0].event_type == "manual.note"
    assert events[0].payload["category"] == "issue"
    assert events[0].payload["content"] == "开头有飞机声"
    assert events[0].payload["raw_text"] == "开头有飞机声"


def test_insert_note_updates_takes_notes(dal, take_id):
    """insert_note 后 takes.notes 不为空，含时间戳和内容。"""
    dal.insert_note(take_id, "issue", "开头有飞机声", "开头有飞机声", 1686580201.0)

    row = dal._conn.execute(
        "SELECT notes FROM takes WHERE take_id = ?", (take_id,)
    ).fetchone()
    assert row is not None
    notes = row["notes"]
    assert notes is not None
    # 应包含时间戳格式和类别标记
    assert "[2023-06-12T14:30:01" in notes
    assert "@issue" in notes
    assert "开头有飞机声" in notes


def test_insert_note_append_aggregation(dal, take_id):
    """插入两条 note 后 takes.notes 包含两行。"""
    dal.insert_note(take_id, "issue", "开头有飞机声", "开头有飞机声", 1686580201.0)
    dal.insert_note(take_id, "note", "灯光调整", "灯光调整", 1686580265.0)

    row = dal._conn.execute(
        "SELECT notes FROM takes WHERE take_id = ?", (take_id,)
    ).fetchone()
    assert row is not None
    notes = row["notes"]
    assert notes is not None
    # 两行应都存在
    assert "@issue" in notes
    assert "开头有飞机声" in notes
    assert "@note" in notes
    assert "灯光调整" in notes
    # 第一行的 ts 应出现在第二行之前
    idx_first = notes.index("@issue")
    idx_second = notes.index("@note")
    assert idx_first < idx_second


def test_insert_note_empty_content(dal, take_id):
    """content 为空时不追加内容文本（仅 [ts] @category）。"""
    dal.insert_note(take_id, "keep", "", "keep mark", 1686580201.0)

    row = dal._conn.execute(
        "SELECT notes FROM takes WHERE take_id = ?", (take_id,)
    ).fetchone()
    assert row is not None
    notes = row["notes"]
    assert notes is not None
    assert "@keep" in notes
    # 确认 @keep 后面就是行尾（没有多余文本）
    assert notes.strip().endswith("@keep")


# ── list_notes ───────────────────────────────────────────────────────────────


def test_list_notes_returns_all(dal, take_id):
    """list_notes 返回所有 note 事件。"""
    dal.insert_note(take_id, "issue", "问题1", "问题1", 100.0)
    dal.insert_note(take_id, "note", "笔记1", "笔记1", 200.0)

    notes = dal.list_notes(take_id)
    assert len(notes) == 2
    assert notes[0].event_type == "manual.note"
    assert notes[1].event_type == "manual.note"
    # 按 ts 升序
    assert notes[0].ts < notes[1].ts


def test_list_notes_filter_by_category(dal, take_id):
    """list_notes(category='issue') 只返回 issue 类别的 note。"""
    dal.insert_note(take_id, "issue", "问题1", "问题1", 100.0)
    dal.insert_note(take_id, "note", "笔记1", "笔记1", 200.0)

    issues = dal.list_notes(take_id, category="issue")
    assert len(issues) == 1
    assert issues[0].payload["category"] == "issue"

    notes = dal.list_notes(take_id, category="note")
    assert len(notes) == 1
    assert notes[0].payload["category"] == "note"


def test_list_notes_empty_take(dal, take_id):
    """无 note 的 take 返回空列表。"""
    result = dal.list_notes(take_id)
    assert result == []
