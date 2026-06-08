# EatOrNot 踩坑记录

## 1. Google ADK MCP 工具调用失败

### 问题描述

```
McpTool.run_async() missing 1 required keyword-only argument: 'tool_context'
```

### 原因分析

Google ADK 的 `McpTool` 设计为在 Agent 内部使用，需要完整的 `ToolContext`（包含 `InvocationContext`）才能调用。直接从外部调用 `McpTool.run_async()` 会因为缺少上下文而失败。

```python
# ❌ 错误方式：直接使用 ADK 的 McpToolset
from google.adk.tools import McpToolset

toolset = McpToolset(connection_params=...)
tools = await toolset.get_tools()
result = await tools['list-nutrition-foods'].run_async(args={})  # 缺少 tool_context
```

### 解决方案

改用 MCP 官方 Python SDK 直接连接，绕过 ADK 的封装：

```python
# ✅ 正确方式：使用 MCP SDK 直接连接
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(url, headers=headers) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool('list-nutrition-foods', {})
```

### 关键文件

- `apps/api/adk_app/mcp_tools.py`

---

## 2. MCP 返回数据解析失败

### 问题描述

MCP 服务器返回的不是纯 JSON，而是带有 AI 说明的文本：

```
# API Response Information

Below is the response from an API call...

## Original Response

{"success":true,"code":200,"data":"[160]{productName,calories,...}:\n  麦辣鸡腿堡,480,..."}
```

直接用 `json.loads()` 解析会失败。

### 原因分析

麦当劳 MCP 服务器使用了 AI 增强的响应格式，返回的内容包含：
1. Markdown 格式的说明文档
2. 嵌套的 JSON（`data` 字段是字符串）
3. CSV 格式的菜品数据（带表头）

### 解决方案

实现多层解析策略：

```python
def _parse_mcp_response(text: str) -> dict | list | None:
    """解析 MCP 返回的带有 AI 说明的 JSON 数据"""
    # 1. 尝试直接解析 JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. 从文本中提取 JSON（正则匹配）
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None


def _parse_csv_items(csv_text: str) -> list[dict]:
    """解析 CSV 格式的菜品数据"""
    lines = csv_text.strip().split('\n')

    # 跳过第一行（数量信息 [160]）
    # 第二行是表头 {productName,calories,...}:
    header_line = lines[1]
    headers = [h.strip() for h in header_line.replace('{', '').replace('}:', '').split(',')]

    # 解析数据行
    items = []
    for line in lines[2:]:
        values = [v.strip() for v in line.split(',')]
        # 转换为标准格式...

    return items
```

### 数据格式示例

```csv
[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
  麦辣鸡腿堡,null,1288,308,16,16,24,781,213
  巨无霸,null,1618,387,23,21,25,846,243
```

---

## 3. MCP 连接上下文管理错误

### 问题描述

```
RuntimeError: Attempted to exit cancel scope in a different task than it was entered in
```

### 原因分析

MCP 的 `streamablehttp_client` 使用 `anyio` 的任务组管理连接，如果在不同的 asyncio 任务中创建和销毁连接，会导致上下文不匹配。

```python
# ❌ 错误方式：缓存 session 导致上下文问题
_mcp_session = None

async def _get_mcp_session():
    global _mcp_session
    if _mcp_session is None:
        read, write, _ = await streamablehttp_client(url).__aenter__()
        session = ClientSession(read, write)
        await session.__aenter__()
        _mcp_session = session  # 缓存的 session 在不同任务中使用会出错
    return _mcp_session
```

### 解决方案

使用 `@asynccontextmanager` 每次调用都创建新连接：

```python
# ✅ 正确方式：使用上下文管理器
@asynccontextmanager
async def _mcp_connection():
    settings = get_settings()

    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def _call_mcp_tool(tool_name: str, args: dict = None):
    async with _mcp_connection() as session:
        if session is None:
            return None
        result = await session.call_tool(tool_name, args or {})
        return result
```

### 注意事项

- MCP 连接不适合长时间缓存
- 每次工具调用创建新连接是更稳定的做法
- 如果需要连接池，考虑使用 `asyncio.Pool` 或其他方案

---

## 4. Windows 控制台编码问题

### 问题描述

```
UnicodeEncodeError: 'gbk' codec can't encode character '\U0001f4aa' in position 10
```

### 原因分析

Windows 默认使用 GBK 编码，而 MCP 返回的数据包含 Unicode 字符（如 emoji 💪），导致输出时编码失败。

### 解决方案

1. **输出到文件时指定编码**：
```python
with open('output.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False)
```

2. **设置环境变量**（临时）：
```bash
set PYTHONIOENCODING=utf-8
```

3. **在代码中处理**：
```python
import sys
sys.stdout.reconfigure(encoding='utf-8')
```

---

## 5. Pydantic 模型验证错误 (422)

### 问题描述

```
POST /api/order/draft 返回 422 Unprocessable Entity
```

### 原因分析

请求体格式与 Pydantic 模型定义不匹配：

```python
class OrderDraft(BaseModel):
    user_id: str
    plan_id: str  # 必填字段
    items: list[MenuItem] = []
    estimated_price: float = 0.0
    estimated_calories: float = 0.0
```

测试时发送的 JSON 缺少 `plan_id` 字段。

### 解决方案

确保请求体包含所有必填字段：

```json
{
  "user_id": "demo-user",
  "plan_id": "test-plan-001",
  "items": [
    {"name": "Big Mac", "item_code": "A001", "price": 25.0}
  ]
}
```

---

## 经验总结

### 1. ADK vs MCP SDK

| 场景 | 推荐方案 |
|------|----------|
| Agent 内部调用 | 使用 ADK 的 McpToolset |
| 独立服务调用 | 使用 MCP SDK 直接连接 |
| 测试/调试 | 使用 MCP SDK + curl |

### 2. 错误处理最佳实践

```python
async def safe_mcp_call(tool_name: str, args: dict = None):
    """带 fallback 的 MCP 调用"""
    try:
        # 尝试真实 MCP
        result = await call_real_mcp(tool_name, args)
        if result:
            return result
    except Exception as e:
        logger.error(f"MCP call failed: {e}")

    # 回退到 mock
    return call_mock_fallback(tool_name, args)
```

### 3. 数据解析策略

面对未知格式的 API 响应：
1. 先尝试直接解析（可能是纯 JSON）
2. 用正则提取 JSON 部分
3. 识别特殊格式（CSV、Markdown 等）
4. 记录原始响应以便调试

### 4. 依赖版本

```txt
# requirements.txt
mcp>=1.27.0          # MCP 官方 SDK
google-adk>=2.1.0    # Google ADK（可选）
fastapi>=0.100.0
pydantic>=2.0.0
```

---

## 调试命令速查

```bash
# 测试 MCP 连接
python -c "
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import asyncio

async def test():
    async with streamablehttp_client('https://mcp.mcd.cn', headers={'Authorization': 'Bearer TOKEN'}) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print(f'Tools: {len(tools.tools)}')

asyncio.run(test())
"

# 测试 API 端点
curl -X POST http://localhost:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo-user","message":"test"}'

# 查看服务日志
uvicorn main:app --reload --log-level debug
```
