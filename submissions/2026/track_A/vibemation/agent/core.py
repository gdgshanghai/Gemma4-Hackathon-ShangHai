import json
import logging
import re
from typing import Any

from openai import OpenAI

from .memory import ConversationMemory
from .tools import N8N_TOOLS

logger = logging.getLogger(__name__)

TOOL_CALL_RE = re.compile(
    r"<\|?tool_call\|\>?call:(\w+)(.*?)<\|?tool_call\|\>?", re.DOTALL
)


def _clean_gemma(s: str) -> str:
    return s.replace("<|\"|>", '"').replace("<|\\\"|>", '"')


def _extract_outer_braces(raw: str, start: int) -> tuple[str, int]:
    depth = 0
    i = start
    while i < len(raw):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1], i + 1
        i += 1
    return raw[start:], len(raw)


def _extract_outer_brackets(raw: str, start: int) -> tuple[str, int]:
    depth = 0
    i = start
    while i < len(raw):
        if raw[i] == "[":
            depth += 1
        elif raw[i] == "]":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1], i + 1
        i += 1
    return raw[start:], len(raw)


def _to_json_str(raw: str) -> str:
    raw = raw.strip()
    parts = []
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == "{":
            block, i = _extract_outer_braces(raw, i)
            parts.append(_to_json_str(block[1:-1]))
        elif c == "[":
            block, i = _extract_outer_brackets(raw, i)
            items = []
            j = 1
            while j < len(block) - 1:
                if block[j] in (",", " ", "\n"):
                    j += 1
                    continue
                if block[j] == "{":
                    item, j = _extract_outer_braces(block, j)
                    items.append(_to_json_str(item))
                elif block[j] == "[":
                    item, j = _extract_outer_brackets(block, j)
                    items.append(_to_json_str(item))
                else:
                    end = j
                    while end < len(block) and block[end] not in (",", "]", "\n"):
                        end += 1
                    items.append('"' + block[j:end].strip().strip('"').replace('"', '\\"') + '"')
                    j = end
            parts.append("[" + ",".join(items) + "]")
        elif c == ":":
            parts.append(":")
        elif c == ",":
            parts.append(",")
        elif c == "<":
            end = raw.find(">", i)
            if end == -1:
                break
            inner_start = end + 1
            inner_end = raw.find("<|", inner_start)
            if inner_end == -1:
                inner_end = raw.find(",", inner_start)
                if inner_end == -1:
                    inner_end = raw.find("}", inner_start)
                    if inner_end == -1:
                        inner_end = len(raw)
            val = raw[end + 1 : inner_end].strip()
            parts.append('"' + val.replace('"', '\\"') + '"')
            i = inner_end
            continue
        elif c in ('"', "'"):
            q = c
            end = raw.find(q, i + 1)
            if end == -1:
                parts.append(c)
            else:
                parts.append('"' + raw[i + 1 : end].replace('"', '\\"') + '"')
                i = end
        elif c not in (" ", "\n"):
            end = i
            while end < len(raw) and raw[end] not in (",", "}", "]", " ", "\n"):
                end += 1
            token = raw[i:end].strip()
            if token in ("true", "false"):
                parts.append(token)
            elif token.isdigit():
                parts.append(token)
            else:
                parts.append('"' + token.replace('"', '\\"') + '"')
            i = end - 1
        i += 1
    j = 0
    while j < len(parts):
        if parts[j] == ":" and j > 0 and j < len(parts) - 1:
            if not parts[j - 1].startswith('"'):
                parts[j - 1] = '"' + parts[j - 1].strip('"') + '"'
        j += 1
    result = "".join(parts)
    return "{" + result + "}" if not result.startswith("{") else result


def _extract_balanced_braces(text: str, start: int = 0) -> tuple[str, int]:
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i+1], i + 1
        i += 1
    return text[start:], len(text)


def parse_tool_calls(content: str) -> list[dict]:
    calls = []
    for m in TOOL_CALL_RE.finditer(content):
        name = m.group(1)
        raw = m.group(2).strip()
        try:
            brace_start = raw.find("{")
            if brace_start >= 0:
                json_str, _ = _extract_balanced_braces(raw, brace_start)
                args = json.loads(json_str)
            else:
                json_str = _to_json_str(raw)
                args = json.loads(json_str)
            calls.append({"name": name, "arguments": args})
        except Exception as e:
            logger.warning(f"Failed to parse tool call {name}: {e}\nRaw: {raw}")
    return calls


class N8nAgent:
    def __init__(
        self,
        client: OpenAI,
        model: str | None = None,
        system_prompt: str | None = None,
    ):
        self.client = client
        self.model = model
        self.memory = ConversationMemory()
        self.system_prompt = system_prompt or (
            "你是 n8n 工作流生成助手。使用提供的工具生成、修改和验证 n8n 工作流 JSON。"
            "每次生成工作流时，请确保节点位置合理（每列间隔 200px），连接关系正确。"
            "支持多轮对话逐步构建复杂工作流。"
            "重要：每次回复时，先用自然语言简要说明你生成的或修改的内容，再调用工具。"
            "不要只输出工具调用而不说话。"
        )

    def _tool_defs_text(self) -> str:
        lines = []
        for t in N8N_TOOLS:
            fn = t["function"]
            params = fn.get("parameters", {})
            props = params.get("properties", {})
            req = params.get("required", [])
            desc = fn.get("description", "")
            lines.append(f"- {fn['name']}: {desc}")
            for k, v in props.items():
                r = " (必填)" if k in req else ""
                d = v.get("description", "")
                lines.append(f"    {k}{r}: {d}")
        return "\n".join(lines)

    def run(self, user_input: str) -> dict[str, Any]:
        self.memory.add_message("user", user_input)
        tool_hint = (
            "\n\n可用工具:\n" + self._tool_defs_text() +
            "\n\n调用格式: <|tool_call|>call:函数名{\"参数名\": \"参数值\"}<|tool_call|>"
        )
        messages = [
            {"role": "system", "content": self.system_prompt + tool_hint},
            *self.memory.get_context(),
        ]

        logger.info(f"[User] {user_input}")
        model = self.model or self._detect_model()

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=N8N_TOOLS,
            temperature=0.0,
        )

        msg = response.choices[0].message
        result = {"content": msg.content, "tool_calls": [], "workflow": None}

        # OpenAI 标准 tool_calls
        raw_calls = list(msg.tool_calls or [])
        # Gemma 4 原生内联格式 fallback
        if not raw_calls and msg.content:
            raw_calls = parse_tool_calls(msg.content)
            result["content"] = TOOL_CALL_RE.sub("", msg.content).strip()

        for tc in raw_calls:
            try:
                if isinstance(tc, dict):
                    name, args_raw = tc["name"], tc["arguments"]
                    args = args_raw if isinstance(args_raw, dict) else json.loads(args_raw)
                else:
                    fn = tc.function
                    name = fn.name
                    args = json.loads(fn.arguments)
                    tc = {"name": name, "arguments": args}

                logger.info(f"[Tool Call] {name}({json.dumps(args, ensure_ascii=False)})")

                if name == "generate_n8n_workflow":
                    workflow = self._build_workflow(args)
                    self.memory.update_workflow(workflow)
                    result["workflow"] = workflow
                elif name == "modify_n8n_workflow":
                    workflow = self._modify_workflow(args)
                    self.memory.update_workflow(workflow)
                    result["workflow"] = workflow

                tool_result = {"status": "ok", "data": args}
            except Exception as e:
                tool_result = {"status": "error", "error": str(e)}

            result["tool_calls"].append({
                "name": tc["name"],
                "arguments": args if 'args' in locals() else tc.get("arguments", str(tc)),
                "result": tool_result,
            })

            self.memory.add_tool_result("", tc["name"], tool_result)

        self.memory.add_message("assistant", msg.content, msg.tool_calls)
        return result

    def _detect_model(self) -> str:
        try:
            models = self.client.models.list()
            if models.data:
                return models.data[0].id
        except Exception:
            pass
        return "gemma-4-E4B-it"

    def _build_workflow(self, args: dict) -> dict:
        return {
            "name": args.get("name", "untitled"),
            "nodes": args.get("nodes", []),
            "connections": args.get("connections", {}),
            "settings": {},
            "version": 2,
        }

    def _modify_workflow(self, args: dict) -> dict:
        current = self.memory.workflow_state or {"nodes": [], "connections": {}}
        op = args.get("operation")
        target = args.get("target_node")
        changes = args.get("changes", {})

        if op == "add_node" and current["nodes"]:
            changes["position"] = [current["nodes"][-1]["position"][0] + 200,
                                   current["nodes"][-1]["position"][1]]
            current["nodes"].append(changes)

        return current

    def export_workflow(self) -> dict | None:
        return self.memory.workflow_state

    def reset(self):
        self.memory.clear()
