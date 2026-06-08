# EatOrNot ADK App

## 架构概览

```
EatOrNot 系统架构
├── FastAPI Demo (当前运行)
│   ├── Orchestrator Agent (智能调度)
│   ├── Supervisor Agent (方案构建)
│   ├── Debate Engine (圆桌辩论)
│   └── 8 个专业 Agent
│
└── ADK App (Google ADK 集成)
    ├── ADK Agent (决策编排层)
    ├── Skills (领域知识包)
    ├── FoodProvider Tools (食物数据抽象)
    └── MCP Tools (外部服务连接)
```

## 三层架构边界

### 1. Skills — "怎么判断"

**职责**: 封装专业知识和决策规则

**特点**:
- 纯逻辑，不依赖外部服务
- 可复用、可组合
- 包含领域知识、规则、参考数据

**示例**:
```
skills/
├── weight-loss-skill/
│   └── SKILL.md          # 减脂知识：热量计算、营养搭配
├── nutrition-balance-skill/
│   └── SKILL.md          # 营养均衡：蛋白质/脂肪/碳水比例
├── spending-control-skill/
│   └── SKILL.md          # 预算控制：日/周预算分配
└── mcdonalds-order-skill/
    └── SKILL.md          # 麦当劳点餐：套餐搭配规则
```

**Skill 内容示例**:
```markdown
# Weight Loss Skill

## 核心原则
- 每日热量缺口 300-500 kcal
- 蛋白质摄入 >= 1.6g/kg 体重
- 避免含糖饮料

## 麦当劳推荐策略
- 优先选择烤制而非油炸
- 配餐选择沙拉而非薯条
- 饮料选择零度可乐或美式咖啡
```

### 2. MCP Tools — "去哪查"

**职责**: 连接外部服务，获取实时数据

**特点**:
- 封装 API 调用
- 处理认证、错误、重试
- 提供统一的数据格式

**示例**:
```python
# mcp_tools.py

class McDonaldsMCP:
    """麦当劳 MCP 服务连接器"""

    async def get_menu(self) -> list[MenuItem]:
        """获取菜单数据"""
        ...

    async def get_stores(self, location: str) -> list[Store]:
        """查询附近门店"""
        ...

    async def create_order(self, items: list[Item]) -> Order:
        """创建订单"""
        ...
```

### 3. FoodProvider — "数据抽象层"

**职责**: 统一不同餐饮平台的数据接口

**特点**:
- 抽象接口，支持多平台
- 处理数据格式差异
- 支持 Mock 数据

**示例**:
```python
# food_provider_tools.py

class FoodProvider(ABC):
    """餐饮平台抽象接口"""

    @abstractmethod
    async def search(self, query: str) -> list[MenuItem]:
        """搜索菜品"""
        ...

    @abstractmethod
    async def get_nutrition(self, item_id: str) -> Nutrition:
        """获取营养信息"""
        ...

class McDonaldsProvider(FoodProvider):
    """麦当劳数据提供者"""
    ...

class MockProvider(FoodProvider):
    """Mock 数据提供者（开发/测试用）"""
    ...
```

## 边界对比

| 维度 | Skill | MCP Tool | FoodProvider |
|------|-------|----------|--------------|
| **职责** | 怎么判断 | 去哪查 | 数据抽象 |
| **输入** | 用户需求 + 上下文 | API 请求 | 查询请求 |
| **输出** | 决策建议 | 原始数据 | 统一格式 |
| **依赖** | 无外部依赖 | 外部 API | MCP 或 Mock |
| **可替换** | 可组合 | 可替换 | 可扩展 |

## 数据流示例

```
用户: "我想吃麦当劳，我在减肥"

1. Skill 层 (怎么判断)
   - Weight Loss Skill: 分析减脂需求
   - Nutrition Skill: 计算营养目标

2. MCP 层 (去哪查)
   - McDonald's MCP: 获取菜单数据

3. FoodProvider 层 (数据抽象)
   - 统一菜单格式
   - 补充营养信息

4. 决策输出
   - 推荐 3 个方案
   - 解释推荐理由
```

## 与 FastAPI Demo 的关系

当前 FastAPI Demo 实现了完整的业务逻辑，ADK App 是可选的增强层：

| 组件 | FastAPI Demo | ADK App |
|------|--------------|---------|
| Agent 调度 | Orchestrator Agent | ADK Agent |
| 专业知识 | 硬编码在 Agent 中 | Skills 目录 |
| 数据获取 | Mock MCP | FoodProvider + MCP |
| 部署 | 独立运行 | 可选集成 |

## 文件说明

- `agent.py` — ADK 根 Agent 定义
- `skills_loader.py` — 从 /skills 目录加载 SKILL.md
- `mcp_tools.py` — McDonald's MCP 工具层
- `food_provider_tools.py` — FoodProvider 抽象工具

## 使用方式

```python
from adk_app import get_agent_response

response = await get_agent_response(
    "我想吃麦当劳，我在减肥",
    context={"mode": "quick", "budget": 30}
)
```

## 扩展新平台

要添加新的餐饮平台（如美团、饿了么），只需：

1. 实现 `FoodProvider` 接口
2. 添加对应的 MCP Tool
3. 创建平台专属 Skill（可选）

```python
class MeituanProvider(FoodProvider):
    """美团数据提供者"""
    async def search(self, query: str) -> list[MenuItem]:
        # 调用美团 API
        ...
```
