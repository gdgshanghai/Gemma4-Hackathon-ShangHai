import asyncio
import json
import pytest

from backend.pipelines.memo_route import classify_memo


class _StubService:
    def __init__(self, *, kind=None, exc=None):
        self._kind = kind
        self._exc = exc
        self.last_task_type = None

    async def infer_tool(self, messages, task_type, priority=None, timeout=None, tool_choice=None):
        self.last_task_type = task_type
        if self._exc is not None:
            raise self._exc
        return {"function": {"name": "route_memo", "arguments": json.dumps({"kind": self._kind})}}


def test_classify_query():
    svc = _StubService(kind="query")
    assert asyncio.run(classify_memo("第一场拍了多少条", svc)) == "query"
    assert svc.last_task_type == "memo_route"


def test_classify_note():
    assert asyncio.run(classify_memo("这条过了", _StubService(kind="note"))) == "note"


@pytest.mark.parametrize("exc", [asyncio.TimeoutError(), LookupError(), ValueError()])
def test_classify_fail_closed_to_note(exc):
    assert asyncio.run(classify_memo("x", _StubService(exc=exc))) == "note"


def test_classify_bad_kind_fail_closed():
    assert asyncio.run(classify_memo("x", _StubService(kind="garbage"))) == "note"
