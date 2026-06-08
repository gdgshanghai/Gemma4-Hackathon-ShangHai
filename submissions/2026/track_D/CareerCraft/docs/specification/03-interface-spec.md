<!-- mdformat global-off -->
# 前后端接口详细规格说明书 (Interface Specification v1.0)

本文档详细规定了 CareerCraft (AI驱动的职业模拟沙盒 MVP) 前端与后端之间的全部数据通信接口。提供准确的 HTTP 方法、路由路径、Query/Body 入参说明、状态码及强类型的 JSON 报文结构体示例。

---

## 一、 通信全局约定

### 1. 基础路径 (Base URL)
- **开发环境**：`http://localhost:8000`
- **生产环境**：待定（可依据独立网关或反向代理配置）

### 2. 标准状态码语义 (HTTP Status Codes)
| 状态码 | 描述 | 说明 |
| :--- | :--- | :--- |
| `200 OK` | 请求成功 | 所有正常的业务操作返回结果 |
| `400 Bad Request` | 参数错误 | Query 或 Body 参数非法、缺失 |
| `422 Unprocessable Entity` | 实体校验失败 | 不符合 Pydantic Schema 强制类型校验规范 |
| `500 Internal Server Error` | 服务端异常 | 底层大模型连接超时或解析崩溃 |

### 3. 跨域资源共享 (CORS)
- **CORS 策略**：开发环境 API 支持全量跨域（`Access-Control-Allow-Origin: *`），允许 2D 像素前端服务（如运行在 Vite 默认的 `http://localhost:5173`）发起直接 HTTP 交互与流式对接。

### 4. 统一错误响应格式 (Error Payloads)
当接口返回非 200 系列状态码时，后端采用结构化 JSON 返回错误详情：
- **Pydantic 校验异常 (422 Unprocessable Entity)** 示例：
  ```json
  {
    "detail": [
      {
        "loc": ["body", "role_id"],
        "msg": "field required",
        "type": "value_error.missing"
      }
    ]
  }
  ```
- **业务逻辑或服务端异常 (400 / 500)** 示例：
  ```json
  {
    "detail": "具体的异常原因，例如：'大模型连接超时，请重试'"
  }
  ```

---

## 二、 身份与认证契约 (Identity & Auth Contract)

> 本节为接口级强约束，所有受保护端点必须遵守。后端实现位于
> `backend/app/api/deps.py`，决策记录见 `docs/specification/adr/0001-identity-contract.md`。

### 1. 标识符 (`X-Player-Id`)

- **类型**：HTTP 请求头，值为 UUID v4 字符串（接受大写，服务端归一化为小写）。
- **作用域**：除 `GET /` 健康检查外的所有 `/api/v1/**` 端点。
- **生命周期**：匿名阶段由前端 `frontend/src/services/identity.ts` 在 `localStorage` 中
  生成并持久化；用户切换浏览器/清缓存视为新身份。
- **缺失或非法**：返回 `401 Unauthorized` + 下表结构化错误码。

### 2. 令牌 (`Authorization: Bearer <token>`)

- 预留给账户体系上线后的 JWT 验证路径；当前 `auth_mode=anonymous|hybrid` 下不要求。
- 一旦携带，在 `hybrid` 模式下后端会先尝试 JWT 解析；失败时回退到 `X-Player-Id`，
  但绝不静默忽略——回退仅适用于“当前未实现 JWT”这一明确状态。

### 3. 认证模式 (`AUTH_MODE`)

| 模式 | 默认 | 行为 | 适用阶段 |
| :--- | :--- | :--- | :--- |
| `anonymous` | 否 | 仅接受 `X-Player-Id`，缺失即 401 | 早期 MVP / 离线测试 |
| `hybrid` | ✅ | 优先 JWT；不可用时回落到 `X-Player-Id` | 当前主线（账户体系迁移期） |
| `jwt` | 否 | 仅接受 Bearer JWT；启动期自检若实现缺失则 fail-fast | 账户体系全量上线后 |

切换通过环境变量 `AUTH_MODE` 控制；`jwt` 模式下若 JWT 校验未实现，进程拒绝启动而非
运行时降级，避免“以为开了强认证、实际全部 401”这类静默回归。

### 4. 401 错误码表 (Structured 401 Payload)

所有身份相关 401 必须以下列结构返回，便于前端区分“可一键重试”与“需要重新登录”：

```json
{
  "detail": {
    "code": "identity.missing_player_id",
    "message": "X-Player-Id header is required."
  }
}
```

| `code` | 触发条件 | 前端建议 |
| :--- | :--- | :--- |
| `identity.missing_player_id` | 请求未携带 `X-Player-Id` | 重生成匿名 ID 并自动重试一次 |
| `identity.invalid_player_id` | `X-Player-Id` 非 UUID v4 | 同上 |
| `identity.missing_bearer` | `jwt` 模式下缺 Authorization | 触发登录流程 |
| `identity.jwt_not_implemented` | `jwt` 模式但实现缺失（理论上启动期已拦截） | 上报错误，不重试 |

### 5. 前端重试与流式约束

- 非 SSE 请求遇到 `identity.missing_player_id` / `identity.invalid_player_id` 时，
  `authedFetch` 执行**一次**重试：重置匿名 ID → 重发原请求；其它 401 直接抛给调用方。
- SSE / `text/event-stream` 请求必须通过 `skipAuthRetry: true` 关闭重试，避免半消费
  的流被重复发起。
- 任何情况下都不得形成 401 循环重试。

### 6. 向后兼容与弃用策略

- **新增**字段（如未来加入 `device_id`）使用可选头，老客户端继续 200。
- **变更**头名或错误码必须先在本节登记 `Deprecated since` 与下线版本，至少跨一个
  release 保留旧契约；CHANGELOG 同步记录。
- **删除**任何已发布字段需在 PR 描述中链接 ADR 并标记 `breaking-change`。

---

## 三、 系统与健康检查模块

### 1. 基础健康检查
用于探测后端中枢是否存活及数据库句柄初始化状态。

- **请求方法**：`GET`
- **请求路径**：`/`
- **请求参数**：无
- **响应报文 (200 OK)**：
```json
{
  "status": "healthy",
  "service": "CareerCraft Backend MVP"
}
```

---

## 四、 职业岛屿与资源探索模块

### 1. 获取职业岛屿列表
供前端渲染“职业选择大厅”的世界地图，标识各个岛屿的解锁与简介状态。

- **请求方法**：`GET`
- **请求路径**：`/api/v1/careers`
- **请求参数**：无
- **响应报文 (200 OK, `list[CareerIslandResponse]`)**：
```json
[
  {
    "career_id": "career_data_analyst",
    "name": "数据山脉 (Data Mounts)",
    "description": "专注于数据清洗、探索性分析与商业指标洞察。",
    "unlocked": true
  },
  {
    "career_id": "career_software_engineer",
    "name": "硅屿 (Silicon Isle)",
    "description": "专注于代码重构、单元测试与高并发架构调优。",
    "unlocked": true
  }
]
```
- **数据结构定义 (`CareerIslandResponse`)**：
  | 字段名 | 类型 | 必填 | 说明 |
  | :--- | :--- | :--- | :--- |
  | `career_id` | String | 是 | 岛屿/职业唯一标识符 |
  | `name` | String | 是 | 岛屿中文展示名称 |
  | `description` | String | 是 | 职业偏向简短描述 |
  | `unlocked` | Boolean | 是 | 关卡是否对玩家解锁 |

### 2. 触发 RAG 知识库检索
当用户在任务执行中遇到瓶颈，根据关键词提供 Markdown 教程与代码片段推荐。

- **请求方法**：`GET`
- **请求路径**：`/api/v1/careers/resources`
- **Query 参数**：
  - `query` (String, 必填)：用户遇到的具体问题或搜索关键词。
  - `domain` (String, 选填，默认 `core_data`)：所属领域分类。
- **响应报文 (200 OK, `list[LearningResourceResponse]`)**：
```json
[
  {
    "doc_id": "rag_pandas_grouping",
    "title": "Pandas 分组聚合基础与高级技巧",
    "snippet": "利用 df.groupby('date').agg({'user_id': 'nunique'}) 可以快速获得每日独立去重活跃用户数...",
    "relevance_score": 0.92
  },
  {
    "doc_id": "rag_funnel_viz",
    "title": "Matplotlib / Seaborn 漏斗图绘制指南",
    "snippet": "漏斗图可以通过计算各阶段之间的百分比转化，直观呈现断崖式下跌的具体节点...",
    "relevance_score": 0.85
  }
]
```
- **数据结构定义 (`LearningResourceResponse`)**：
  | 字段名 | 类型 | 必填 | 说明 |
  | :--- | :--- | :--- | :--- |
  | `doc_id` | String | 是 | 检索出的 Markdown 教程片段唯一 ID |
  | `title` | String | 是 | 教程标题 |
  | `snippet` | String | 是 | 与 query 高度相关的文本/代码片段摘要 |
  | `relevance_score` | Float | 是 | 语义相关度评分 (0.00 ~ 1.00) |

---

## 五、 任务调度与成长评估模块

### 1. 动态创建职业任务
请求后端中枢下发高度匹配当前角色与难度的 JSON 任务剧本。

- **请求方法**：`POST`
- **请求路径**：`/api/v1/missions/generate`
- **请求头**：`Content-Type: application/json`
- **Body 入参 (`MissionGenerateRequest`)**：
```json
{
  "role_id": "mentor_ling",
  "difficulty": "beginner"
}
```
- **响应报文 (200 OK, `MissionGenerateResponse`)**：
```json
{
  "mission_id": "mvp_mission_mentor_ling_beginner",
  "title": "分析社区论坛用户活跃度下降原因",
  "description": "近期社区论坛的日活跃用户数出现下滑。请下载配套的原始日志，找出流失发生的核心环节，并在周五前提交分析报告。",
  "mock_data_url": "https://example.com/mock_data/forum_logs_2026.csv",
  "delivery_requirements": [
    "清晰的数据清洗与归因逻辑",
    "包含至少一张用户流失漏斗图",
    "提出两点具体可行的促活建议"
  ]
}
```

### 2. 提交报告与成长评估
将外部完成的报告提交给 AI 同事，获得结构化经验奖励并判定是否触发费曼挑战。

- **请求方法**：`POST`
- **请求路径**：`/api/v1/missions/evaluate`
- **请求头**：`Content-Type: application/json`
- **Body 入参 (`SubmissionEvaluateRequest`)**：
```json
{
  "mission_id": "mvp_mission_mentor_ling_beginner",
  "submission_text": "通过对 forum_logs 的清洗，定位流失发生在手机号验证码阶段，漏斗图见附件..."
}
```
- **响应报文 (200 OK, `SubmissionEvaluateResponse`)**：
```json
{
  "status": "success",
  "feedback": "问题拆解非常清晰，漏斗图准确定位了注册第二步的表单流失高点。建议可行性较强，符合规范要求。",
  "experience_gains": {
    "skill_data_cleaning": 10,
    "skill_exploratory_analysis": 5,
    "skill_business_insight": 5
  },
  "trigger_feynman_challenge": true,
  "feynman_question": "你在报告中提到了按次日留存进行分组聚合。请用最简单的语言向没有技术背景的市场部同事解释一下，什么是次日留存率？"
}
```

---

## 六、 多角色沉浸对话模块 (SSE Protocol)

### 1. 沉浸式角色扮演对话流
基于 Server-Sent Events (SSE) 协议，实现配合打字机音效的流式逐字输出。MVP 支持跨域直接调用。

- **请求方法**：`GET`
- **请求路径**：`/api/v1/agent/chat`
- **请求头**：`Accept: text/event-stream`
- **Query 参数**：
  - `role_name` (String, 选填，默认 `高凌 (Tech Lead)`)：当前扮演的导师或同事显示名。
  - `message` (String, 必填)：用户输入的即时交流文本。
- **通信断帧规约 (Event Stream Data)**：
后端会持续发送一系列单字符的文本帧，每一帧必须符合标准 SSE 报文协议。前端可通过原生 `EventSource` 或流式读取器 (如 `fetch` 的 `ReadableStream`) 持续渐现拼装。

> [!IMPORTANT]
> **标准 SSE 数据帧规范**：
> 1. 每一帧的文本必须具有 `data: ` 前缀，且每一帧之间必须以双换行符 `\n\n` 截断。
> 2. 后端异步流实现中，绝对不能直接返回 `yield char` 的纯文本流，而必须返回符合 `yield f"data: {char}\n\n"` 的完整帧结构。否则会导致前端 standard EventSource 监听器崩溃或无法触发 `onmessage` 监听。

```text
data: 【

data: 高

data: 凌

data: 的

data: 回

data: 复

data: 】

data: 收

data: 到

...
```
