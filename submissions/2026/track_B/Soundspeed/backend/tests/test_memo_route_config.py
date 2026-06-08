from backend.llm.config import TASK_CONFIG
from backend.llm.tools import registry
from backend.llm.tools.route import ROUTE_TOOL_NAME


def test_memo_route_task_config():
    cfg = TASK_CONFIG["memo_route"]
    assert cfg["tool_choice"] == {"type": "function", "function": {"name": ROUTE_TOOL_NAME}}
    names = [t["function"]["name"] for t in cfg["tools"]]
    assert names == [ROUTE_TOOL_NAME]
    assert cfg["priority"] == 1
    assert cfg["max_tokens"] <= 64


def test_memo_route_registered():
    assert registry.get_tool_schema(ROUTE_TOOL_NAME)["function"]["name"] == ROUTE_TOOL_NAME
    assert registry.get_executor(ROUTE_TOOL_NAME) is None
