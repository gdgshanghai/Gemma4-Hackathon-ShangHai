---
career: software_engineer
mission_id: mission_2_alchemist
skills:
  - skill_api_design
doc_type: concept
related_files:
  - api-design.md
updated: 2026-05-20
---

# 你必须懂的 HTTP 状态码

## TL;DR

- **核心规则**：状态码是给机器读的契约；响应体的 `message` 才是给人看的提示。两者各司其职。
- **反例**：所有响应都返回 `200 OK`，业务错误塞进响应体——客户端无法用通用中间件处理。
- **在本任务里怎么用**：按 §3 和 §5 为签到接口选择正确状态码，并在 `api-design.md` 写清楚选择理由。

## 1. 2xx 成功 (Success)

- **200 OK**：通用成功。GET 请求成功，或 PUT/PATCH 更新成功。
- **201 Created**：资源创建成功。通常在 POST 请求后返回，响应头应包含新资源的 URL（`Location: /api/users/123`）。
- **204 No Content**：请求成功，但响应体无内容。常用于 DELETE 成功。

## 2. 4xx 客户端错误 (Client Error)

请求有问题，客户端需要修改。

- **400 Bad Request**：通用客户端错误，如请求体格式错误、缺少必填字段。
- **401 Unauthorized**：**未认证**。缺少或提供了无效的身份凭证（如 Token 过期）。需重新登录。
- **403 Forbidden**：**无权限**。身份认证通过，但没有访问该资源的权限。
- **404 Not Found**：请求的资源不存在。例如 `GET /api/users/999999`，用户不存在。
- **409 Conflict**：请求与服务器当前状态冲突。例如，用已注册的邮箱再次注册。

## 3. 任务中的应用：签到 API

- 用户**今日首次签到**成功：返回 `201 Created`，响应体附带获得的积分。
- 用户**今日已签到**再次调用：返回 `409 Conflict` 或 `200 OK`，附带提示"今日已签到"（取决于产品定义，但不应再返回 201）。
- 请求**未携带有效 Token**：返回 `401 Unauthorized`。
- 请求的 **URL 路径错误**：返回 `404 Not Found`。

## 4. 5xx 服务器错误 (Server Error)

- **500 Internal Server Error**：通用服务器内部错误。开发者应尽量避免用户看到，并记录详细日志。

## 5. 签到 API 的状态码建议

| 场景 | 推荐状态码 | 说明 |
| :--- | :--- | :--- |
| 查询签到状态成功 | `200 OK` | 普通读取 |
| 首次签到成功 | `201 Created` | 创建一条签到记录 |
| 重复签到（幂等设计） | `200 OK` | 返回当前状态，不报错 |
| 重复签到（冲突设计） | `409 Conflict` | 明确告知不允许重复 |
| 请求参数格式错误 | `400 Bad Request` | 字段缺失或类型错 |
| 未登录或 Token 无效 | `401 Unauthorized` | 拒绝认证 |
| 系统异常 | `500 Internal Server Error` | 后端记录日志 |

## 6. 设计选择说明

状态码没有唯一答案，关键是文档中要说明选择理由。

- 若强调**幂等性**，重复签到返回 `200 OK` 更自然，客户端重复请求不会造成额外副作用。
- 若强调**业务冲突**，重复签到返回 `409 Conflict` 也可以，但响应体必须告诉前端今日状态和已获得积分。

## 常见误区

- 用 `500` 掩盖业务错误。`500` 应仅用于服务器异常，业务规则不通过用 4xx。
- 用 `200 OK` 包装所有失败。前端无法用 HTTP 层中间件统一处理。
- 用 `404` 表达权限不足。应用 `403`，并在文档说明两者区分。

## RAG 检索关键词

HTTP 状态码, 200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 500 Internal Server Error, 幂等, 错误响应, api-design.md, skill_api_design, mission_2_alchemist

