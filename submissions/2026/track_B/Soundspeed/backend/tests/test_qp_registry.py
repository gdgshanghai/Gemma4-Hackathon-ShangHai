"""QP 工具注册：schema + 真实 executor（executor!=None 首个真实消费者）。"""
from __future__ import annotations

from backend.db.dal import DAL
from backend.llm.tools import registry

_QP_NAMES = ["count_takes", "get_scene_info", "list_characters", "search_script_lines", "query_database"]


def test_qp_tools_registered_with_schema() -> None:
    for name in _QP_NAMES:
        schema = registry.get_tool_schema(name)
        assert schema["function"]["name"] == name


def test_qp_tools_have_real_executor() -> None:
    for name in _QP_NAMES:
        assert registry.get_executor(name) is not None, f"{name} executor 不能为 None（QP Tier 2）"


def test_qp_executor_callable_end_to_end(tmp_path) -> None:
    dal = DAL(tmp_path / "reg.db")
    dal.create_scene("Scene_1")
    executor = registry.get_executor("count_takes")
    res = executor({"scene_ref": "1"}, dal)
    assert res["count"] == 0
    dal.close()


def test_note_tool_still_registered() -> None:
    """4.x note/L2 工具在 QP 追加后仍在——防 _bootstrap 改动误删。"""
    schema = registry.get_tool_schema("structure_note")
    assert schema["function"]["name"] == "structure_note"
    schema2 = registry.get_tool_schema("report_script_analysis")
    assert schema2["function"]["name"] == "report_script_analysis"


def test_list_tools_exact_eight() -> None:
    """注册表恰好 8 个工具，不多不少（防意外重复注册或丢失）。"""
    all_tools = registry.list_tools()
    expected = [
        "report_script_analysis",
        "structure_note",
        "route_memo",
        "count_takes",
        "get_scene_info",
        "list_characters",
        "search_script_lines",
        "query_database",
    ]
    assert all_tools == expected
