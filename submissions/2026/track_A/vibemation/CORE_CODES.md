# 核心代码

## 1. Gemma 4 原生函数调用（Native Function Calling）

### 工具定义（`agent/tools.py`）

以 OpenAI 兼容格式定义 n8n 工作流操作工具。Gemma 4 的 chat template 原生支持 `<|tool_call|>` 标签，无需额外的 prompt hacking。

```python
# 生成工作流工具
N8N_GENERATE_WORKFLOW = {
    "type": "function",
    "function": {
        "name": "generate_n8n_workflow",
        "description": "根据用户需求生成可执行的 n8n 工作流 JSON",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "工作流名称"},
                "nodes": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "n8n 节点列表",
                },
                "connections": {
                    "type": "object",
                    "description": "节点连接关系",
                },
            },
            "required": ["name", "nodes", "connections"],
        },
    },
}

# 修改工作流工具
N8N_MODIFY_WORKFLOW = {
    "type": "function",
    "function": {
        "name": "modify_n8n_workflow",
        "description": "修改已有的 n8n 工作流（增删节点或调整连接）",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add_node", "remove_node", "update_node", "reconnect"],
                },
                "target_node": {"type": "string"},
                "changes": {"type": "object"},
            },
            "required": ["operation", "target_node", "changes"],
        },
    },
}

N8N_TOOLS = [N8N_GENERATE_WORKFLOW, N8N_MODIFY_WORKFLOW, N8N_VALIDATE_WORKFLOW]
```

### Agent 调用循环（`agent/core.py`）

N8nAgent 的核心 `run()` 方法：

```python
class N8nAgent:
    def __init__(self, client: OpenAI, model: str | None = None):
        self.client = client
        self.model = model
        self.memory = ConversationMemory()
        self.system_prompt = (
            "你是 n8n 工作流生成助手。使用提供的工具生成、修改和验证 n8n 工作流 JSON。"
            "每次生成工作流时，请确保节点位置合理（每列间隔 200px），连接关系正确。"
            "支持多轮对话逐步构建复杂工作流。"
        )

    def run(self, user_input: str) -> dict[str, Any]:
        self.memory.add_message("user", user_input)

        messages = [
            {"role": "system", "content": self.system_prompt + tool_hint},
            *self.memory.get_context(),  # 多轮对话记忆
        ]

        # 调用 Gemma 4（OpenAI 兼容格式）
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=N8N_TOOLS,  # 传入工具定义 → 触发 Native Function Calling
            temperature=0.0,
        )

        msg = response.choices[0].message

        # 双格式兼容：
        # 1. OpenAI 标准 tool_calls 格式
        raw_calls = list(msg.tool_calls or [])
        # 2. Gemma 4 原生内联格式 fallback
        if not raw_calls and msg.content:
            raw_calls = parse_tool_calls(msg.content)

        for tc in raw_calls:
            # 解析工具调用 → 执行 → 保存到 memory
            if name == "generate_n8n_workflow":
                workflow = self._build_workflow(args)
                self.memory.update_workflow(workflow)
            elif name == "modify_n8n_workflow":
                workflow = self._modify_workflow(args)
                self.memory.update_workflow(workflow)

        return result
```

### Gemma 4 原生内联格式解析

Gemma 4 可能在 content 中直接嵌入 `<|tool_call|>` 标签（而非 OpenAI 标准格式），`parse_tool_calls` 负责解析：

```python
TOOL_CALL_RE = re.compile(
    r"<\|?tool_call\|\>?call:(\w+)(.*?)<\|?tool_call\|\>?", re.DOTALL
)

def parse_tool_calls(content: str) -> list[dict]:
    """
    解析 Gemma 4 原生内联格式的 tool_call
    
    输入示例:
      <|tool_call|>call:generate_n8n_workflow{
        "name": "My Workflow",
        "nodes": [...],
        "connections": {...}
      }<|tool_call|>
    
    返回:
      [{"name": "generate_n8n_workflow", "arguments": {...}}]
    """
    calls = []
    for m in TOOL_CALL_RE.finditer(content):
        name = m.group(1)
        raw = m.group(2).strip()
        # 提取平衡花括号内的 JSON
        brace_start = raw.find("{")
        json_str, _ = _extract_balanced_braces(raw, brace_start)
        args = json.loads(json_str)
        calls.append({"name": name, "arguments": args})
    return calls
```

### API 客户端（`api/gemma_client.py`）

支持多 Key 轮转，兼容 OpenRouter / 自定义端点：

```python
def get_client(provider: str = "openrouter_26b") -> tuple[OpenAI, str]:
    global _openrouter_idx

    # 自定义 provider（用户自部署的 Gemma 4）
    if provider.startswith("custom_"):
        # 从环境变量查找自定义配置
        custom_list = json.loads(os.environ.get("CUSTOM_PROVIDERS", "[]"))
        for c in custom_list:
            if c.get("id") == provider:
                return OpenAI(base_url=c["baseUrl"], api_key=c["apiKey"]), ""

    # OpenRouter 多 Key 轮转
    if provider == "openrouter_26b":
        _openrouter_idx = (_openrouter_idx + 1) % len(OPENROUTER_CLIENTS)
        return OPENROUTER_CLIENTS[_openrouter_idx], "google/gemma-4-26b-a4b-it"

    return OPENROUTER_CLIENTS[0], "google/gemma-4-26b-a4b-it"
```

## 2. 多轮对话记忆（`agent/memory.py`）

```python
class ConversationMemory:
    def __init__(self, max_turns: int = 20):
        self.history: list[dict] = []
        self.workflow_state: dict | None = None  # 当前工作流状态

    def add_message(self, role, content, tool_calls=None):
        self.history.append({"role": role, "content": content, "tool_calls": tool_calls})

    def update_workflow(self, workflow: dict):
        self.workflow_state = workflow  # 保存工作流供下一轮修改

    def get_context(self) -> list[dict]:
        ctx = list(self.history)
        if self.workflow_state:
            # 注入当前工作流状态，让 LLM 知道已有成果
            ctx.insert(0, {
                "role": "system",
                "content": f"当前工作流状态:\n{json.dumps(self.workflow_state)}"
            })
        return ctx
```

多轮对话流程示例：

```
Turn 1: 用户 → "创建 webhook → 飞书通知"
        Agent → generate_n8n_workflow → 保存 workflow_state
Turn 2: 用户 → "加一个 IF 过滤 main 分支"
        Agent → 读取 workflow_state → modify_n8n_workflow → 更新 state
Turn 3: 用户 → "false 分支加 Slack"
        Agent → 读取 workflow_state → modify_n8n_workflow → 更新 state
```

## 3. 服务端部署与执行（`server.py`）

当部署工作流时，自动将 ManualTrigger 替换为 Webhook，确保可以通过 webhook 远程触发：

```python
def _add_webhook_trigger(wf: dict) -> str:
    """自动添加 Webhook 触发器"""
    for n in wf["nodes"]:
        # 已有 Webhook → 确保 httpMethod=POST
        if n["type"] == "n8n-nodes-base.webhook":
            n.setdefault("parameters", {})["httpMethod"] = "POST"
            return n["parameters"]["path"]

        # ManualTrigger → 替换为 Webhook
        if n["type"] == "n8n-nodes-base.manualTrigger":
            n["type"] = "n8n-nodes-base.webhook"
            n["parameters"] = {"httpMethod": "POST", "path": webhook_path}
            return webhook_path

    # 无触发器 → 插入 Webhook 节点
    nodes.insert(0, webhook_node)
    return webhook_path
```

触发工作流执行：

```python
@app.post("/api/execute-workflow")
def execute_workflow(req: ExecuteRequest):
    api_key = _resolve_n8n_key(req.n8n_url, req.n8n_api_key)
    webhook_url = f"{req.n8n_url}/webhook/{webhook_path}"

    with httpx.Client() as client:
        # POST 到 webhook → n8n 执行工作流 → 返回结果
        resp = client.post(webhook_url, json={"ping": True})
        return {"execution": resp.json(), "message": "工作流已触发执行"}
```
