---
career: software_engineer
mission_id: mission_2_alchemist
skills:
  - skill_api_design
  - skill_communication
doc_type: concept
related_files:
  - api-design.md
updated: 2026-05-20
---

# RESTful API 设计基础

## TL;DR

- **核心规则**：把业务模型抽象成资源，用 URL 表达资源、用 HTTP 方法表达操作，文档里写清边界与幂等。
- **反例**：`POST /doCheckIn` 这种动词式 URL，且重复调用会重复发积分。
- **在本任务里怎么用**：用 §3 的两个端点为签到功能写出 `api-design.md`，并在 §6 自查所有边界条件。

## 1. 核心资源与端点

将业务模型抽象为"资源"（Resource），用 URL 路径标识。

- **资源集合**：`/users`（所有用户）
- **单个资源**：`/users/{id}`（ID 为 123 的用户）

## 2. HTTP 方法对应操作 (CRUD)

| 方法 | 含义 | 示例端点 | 操作 |
| :--- | :--- | :--- | :--- |
| **GET** | 读取/查询 | `GET /api/check-in/status` | 查询当前用户的签到状态 |
| **POST** | 创建 | `POST /api/check-in` | 执行一次签到操作 |
| **PUT/PATCH** | 更新（整体/部分） | `PUT /api/users/123` | 更新用户信息 |
| **DELETE** | 删除 | `DELETE /api/users/123` | 删除用户 |

## 3. 设计清晰的签到 API

### POST /api/v1/check-in

- **功能**：执行签到。
- **鉴权**：必须携带用户令牌（如 JWT）。
- **幂等性**：同一自然日重复调用应返回相同结果（如"今日已签到"），不会重复发积分。详见 [api-idempotency-and-auth-basics.md](api-idempotency-and-auth-basics.md)。
- **响应示例**：

```json
{
  "code": 0,
  "message": "签到成功",
  "data": {
    "pointsEarned": 10,
    "continuousDays": 5
  }
}
```

### GET /api/v1/check-in/status

- **功能**：获取当前用户今日签到状态及连续签到信息。
- **响应示例**：

```json
{
  "hasCheckedInToday": true,
  "continuousDays": 3,
  "todaysPoints": 10
}
```

## 4. 与产品经理 Amy 沟通的关键点

在"需求炼金术师"任务中，你需要向 Amy 确认：

- **签到周期**：自然日（0 点重置）还是 24 小时制？
- **连续判定**：如何定义"连续"？昨天没签今天签了，连续天数是 1 还是中断？
- **积分规则**：基础积分多少？连续签到的奖励规则（如第 7 天额外奖励）？
- **异常情况**：已签到后再调用，返回成功还是错误？

清晰的 API 文档就是你与前端、测试、产品达成的共识。详见 [requirement-clarification-framework.md](requirement-clarification-framework.md)。

## 5. api-design.md 推荐结构

- **接口名称**：一句话说明用途。
- **Method + Path**：例如 `POST /api/v1/check-in`。
- **鉴权要求**：是否需要登录态或 Token。
- **请求参数**：字段名、类型、必填、示例、说明。
- **响应字段**：成功响应和失败响应都要写。
- **幂等规则**：重复请求如何处理。
- **边界情况**：已签到、跨天、连续中断、用户未登录。
- **核心逻辑**：用伪代码描述连续签到和积分计算。

## 6. 签到接口边界条件清单

- [ ] 同一自然日重复签到不能重复发积分。
- [ ] 用户昨天未签到，今天签到后连续天数应重置为 1。
- [ ] 用户昨天已签到，今天首次签到后连续天数加 1。
- [ ] 查询状态接口不能改变用户状态。
- [ ] 服务端时间作为签到日期依据，不能相信客户端时间。

## 常见误区

- 用动词命名 URL，如 `/doCheckIn`、`/getStatus`。应使用资源 + HTTP 方法。
- 把所有错误都返回 200 + 业务码。前端难以用 HTTP 层中间件统一处理。
- 不写响应字段的 schema，前端只能"试出来"。

## RAG 检索关键词

RESTful API, 签到接口, 幂等性, POST /api/v1/check-in, GET /api/v1/check-in/status, 请求响应格式, 需求澄清, Amy, api-design.md, skill_api_design, skill_communication, mission_2_alchemist

