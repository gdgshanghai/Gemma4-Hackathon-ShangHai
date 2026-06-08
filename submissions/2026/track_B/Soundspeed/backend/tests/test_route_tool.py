from backend.llm.tools.route import ROUTE_TOOL_NAME, build_route_memo_tool


def test_route_tool_shape():
    tool = build_route_memo_tool()
    assert tool["type"] == "function"
    fn = tool["function"]
    assert fn["name"] == ROUTE_TOOL_NAME == "route_memo"
    params = fn["parameters"]
    assert params["type"] == "object"
    kind = params["properties"]["kind"]
    assert kind["type"] == "string"
    assert kind["enum"] == ["note", "query"]   # 顺序固定
    assert params["required"] == ["kind"]
