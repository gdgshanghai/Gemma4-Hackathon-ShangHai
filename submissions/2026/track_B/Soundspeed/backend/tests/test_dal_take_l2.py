"""1.H DAL 扩展测试：update_take_l2_output / insert_take_line_matches / list_script_lines。

TDD 红阶段：先写失败测试，等 feat commit 实现。
"""
from __future__ import annotations

import time

from backend.db.dal import DAL


# ---------------------------------------------------------------------------
# update_take_l2_output
# ---------------------------------------------------------------------------


def test_update_take_l2_output_persists_script_diff(tmp_dal: DAL) -> None:
    """调 update_take_l2_output 后 get_take 返回的 script_diff 是 dict。"""
    scene_id = tmp_dal.create_scene("s1")
    take_id, _ = tmp_dal.start_take(scene_id, "1", time.time())

    script_diff = {
        "script_diff_summary": "演员漏说第2行",
        "line_matches": [{"line_no": 1, "diff_type": "match", "detail": None}],
    }
    tmp_dal.update_take_l2_output(take_id, script_diff)

    take = tmp_dal.get_take(take_id)
    assert take is not None
    assert isinstance(take.script_diff, dict)
    assert take.script_diff["script_diff_summary"] == "演员漏说第2行"
    assert take.script_diff["line_matches"][0]["line_no"] == 1


def test_update_take_l2_output_none_clears_diff(tmp_dal: DAL) -> None:
    """传 None 写入 NULL，get_take 返回 script_diff=None。"""
    scene_id = tmp_dal.create_scene("s2")
    take_id, _ = tmp_dal.start_take(scene_id, "1", time.time())

    # 先写一个值
    tmp_dal.update_take_l2_output(take_id, {"script_diff_summary": "有内容"})
    # 再写 None
    tmp_dal.update_take_l2_output(take_id, None)

    take = tmp_dal.get_take(take_id)
    assert take is not None
    assert take.script_diff is None


# ---------------------------------------------------------------------------
# insert_take_line_matches
# ---------------------------------------------------------------------------


def test_insert_take_line_matches_bulk(tmp_dal: DAL) -> None:
    """批量写入 take_line_matches，list_take_line_matches 返回对应记录。

    matches 每项需含 line_id（FK to script_lines）/ line_no / diff_type / detail。
    caller 负责在传入前做 line_no → line_id 映射。
    """
    scene_id = tmp_dal.create_scene("s3")
    take_id, _ = tmp_dal.start_take(scene_id, "1", time.time())
    script_id = tmp_dal.insert_script(scene_id, "剧本文本")
    line_id_1 = tmp_dal.insert_script_line(script_id, line_no=1, character="A", text="行一")
    line_id_2 = tmp_dal.insert_script_line(script_id, line_no=2, character="B", text="行二")

    matches = [
        {"line_no": 1, "line_id": line_id_1, "diff_type": "match", "detail": None},
        {"line_no": 2, "line_id": line_id_2, "diff_type": "substitution", "detail": "漏词"},
    ]
    tmp_dal.insert_take_line_matches(take_id, matches)

    results = tmp_dal.list_take_line_matches(take_id)
    assert len(results) == 2


def test_insert_take_line_matches_skips_insertion_line_no_minus1(tmp_dal: DAL) -> None:
    """line_no==-1 的 insertion 行跳过，不写入 take_line_matches。"""
    scene_id = tmp_dal.create_scene("s4")
    take_id, _ = tmp_dal.start_take(scene_id, "1", time.time())
    script_id = tmp_dal.insert_script(scene_id, "剧本文本")
    line_id_1 = tmp_dal.insert_script_line(script_id, line_no=1, character="A", text="行一")
    line_id_3 = tmp_dal.insert_script_line(script_id, line_no=3, character="C", text="行三")

    matches: list[dict] = [
        {"line_no": 1, "line_id": line_id_1, "diff_type": "match", "detail": None},
        {"line_no": -1, "line_id": None, "diff_type": "insertion", "detail": "演员自由发挥"},
        {"line_no": 3, "line_id": line_id_3, "diff_type": "missing", "detail": None},
    ]
    tmp_dal.insert_take_line_matches(take_id, matches)

    results = tmp_dal.list_take_line_matches(take_id)
    # line_no=-1 的 insertion 跳过，只写 2 条
    assert len(results) == 2


# ---------------------------------------------------------------------------
# list_script_lines
# ---------------------------------------------------------------------------


def test_list_script_lines_returns_dicts(tmp_dal: DAL) -> None:
    """插入 3 行 script_lines，list_script_lines 返回 list of dict 含 line_no / line_id / character / text。"""
    scene_id = tmp_dal.create_scene("s5")
    script_id = tmp_dal.insert_script(scene_id, "原始台词")

    tmp_dal.insert_script_line(script_id, line_no=1, character="主角", text="我不走。")
    tmp_dal.insert_script_line(script_id, line_no=2, character="配角", text="你必须走。")
    tmp_dal.insert_script_line(script_id, line_no=3, character=None, text="（沉默）")

    lines = tmp_dal.list_script_lines(script_id)

    assert len(lines) == 3
    assert all(isinstance(ln, dict) for ln in lines)
    assert lines[0]["line_no"] == 1
    assert lines[0]["character"] == "主角"
    assert lines[0]["text"] == "我不走。"
    assert "line_id" in lines[0]
    assert lines[2]["character"] is None

    # 按 line_no ASC
    assert [ln["line_no"] for ln in lines] == [1, 2, 3]


def test_list_script_lines_empty(tmp_dal: DAL) -> None:
    """没有台词行时 list_script_lines 返回空 list。"""
    scene_id = tmp_dal.create_scene("s6")
    script_id = tmp_dal.insert_script(scene_id, "空剧本")

    lines = tmp_dal.list_script_lines(script_id)
    assert lines == []
