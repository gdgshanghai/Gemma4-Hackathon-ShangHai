"""query_session 挂 QP tools + tool_choice=auto（D-QP-09 eager）。"""
from __future__ import annotations

from backend.llm.config import TASK_CONFIG


def test_query_session_has_qp_tools() -> None:
    cfg = TASK_CONFIG["query_session"]
    names = [t["function"]["name"] for t in cfg["tools"]]
    assert names == [
        "count_takes",
        "get_scene_info",
        "list_characters",
        "search_script_lines",
        "query_database",
    ]


def test_query_session_tool_choice_auto() -> None:
    # auto 跳：模型自选工具（不是 forced）
    assert TASK_CONFIG["query_session"]["tool_choice"] == "auto"
