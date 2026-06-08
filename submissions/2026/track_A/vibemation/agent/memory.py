import json
from typing import Any


class ConversationMemory:
    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self.history: list[dict] = []
        self.workflow_state: dict | None = None

    def add_message(self, role: str, content: str | None, tool_calls: list | None = None):
        msg = {"role": role}
        if content:
            msg["content"] = content
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.history.append(msg)
        if len(self.history) > self.max_turns * 2:
            self.history = self.history[-self.max_turns * 2:]

    def add_tool_result(self, tool_call_id: str, name: str, result: Any):
        self.history.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result,
        })

    def update_workflow(self, workflow: dict):
        self.workflow_state = workflow

    def get_context(self) -> list[dict]:
        ctx = list(self.history)
        if self.workflow_state:
            ctx.insert(0, {
                "role": "system",
                "content": f"当前工作流状态:\n{json.dumps(self.workflow_state, indent=2, ensure_ascii=False)}\n\n基于此状态进行修改。",
            })
        return ctx

    def clear(self):
        self.history.clear()
        self.workflow_state = None
