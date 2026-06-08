---
career: software_engineer
mission_id: mission_2_alchemist
skills:
  - skill_api_design
doc_type: concept
related_files:
  - api_design.md
updated: 2026-05-20
---

# API 幂等性与鉴权基础

## TL;DR

- **核心规则**：写操作必须幂等——同一请求重复执行多次，结果与执行一次相同；所有受保护接口必须鉴权。
- **反例**：用户点了两次"提交订单"，系统创建两个订单并扣两次款；或匿名调用 `DELETE /users/123` 删除任意用户。
- **在本任务里怎么用**：在 `api_design.md` 里为写接口加 `Idempotency-Key` 头或基于业务唯一键去重，并在每个接口明确鉴权方式（Bearer Token / API Key）。

## 1. 为什么需要幂等

网络是不可靠的：

- 客户端按钮防抖失败，连点两次。
- 网络抖动导致客户端超时重试，但服务端其实成功了。
- 网关/代理层重试。

如果接口不幂等，会产生重复订单、重复扣款、重复发券——业务事故。

## 2. 幂等性按 HTTP 方法

- `GET`：天然幂等（只读）。
- `PUT` / `DELETE`：按定义幂等——多次执行结果与一次相同。
- `POST`：默认**不**幂等，需要应用层保证。
- `PATCH`：不一定幂等（取决于实现）。

## 3. POST 接口的幂等方案

### 方案 A：业务唯一键去重

如果业务本身有自然唯一性（如订单号、外部交易号），用它做去重：

```sql
CREATE UNIQUE INDEX uk_orders_external_id ON orders(external_order_id);
```

插入时若违反唯一约束，返回已存在的资源而不是报错。

### 方案 B：Idempotency-Key 头（通用方案）

客户端为每次"业务请求"生成唯一 key（如 UUID），通过请求头传递：

```http
POST /api/v1/orders
Idempotency-Key: 7b3f9a2c-1e4d-4f8b-9c3a-2d6e8f1b4c5d
Authorization: Bearer eyJhbGciOi...
Content-Type: application/json

{
  "items": [{"sku": "A001", "qty": 2}],
  "amount": 199.00
}
```

服务端：

1. 查询 `idempotency_keys` 表，若 key 已存在：返回上次的响应（同 status、同 body）。
2. 若不存在：执行业务逻辑，把 `(key, response_status, response_body)` 写入表，设置 TTL（如 24h）。
3. 步骤 1/2 要在事务或锁保护下进行，防止并发重复。

```sql
CREATE TABLE idempotency_keys (
    key VARCHAR(64) PRIMARY KEY,
    user_id BIGINT NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    response_status INT,
    response_body TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);
```

注意：要校验同一 key 的请求体哈希一致，避免用同一 key 提交不同内容。

## 4. 鉴权基础

### 4.1 Bearer Token（推荐用于用户态接口）

```http
GET /api/v1/users/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

- Token 通常是 JWT，包含 user_id、过期时间、签名。
- 服务端验证签名 + 过期时间 → 取出 user_id → 进入业务。
- Token 应有较短过期（如 2h），配合 refresh token 续期。

### 4.2 API Key（推荐用于服务间调用）

```http
POST /api/v1/internal/sync
X-API-Key: sk_live_abc123...
```

- 长期凭证，存于服务端配置/密钥管理服务。
- 建议绑定 IP 白名单 + 调用频率限制。

### 4.3 鉴权失败的响应

| 场景 | 状态码 | 含义 |
| :--- | :--- | :--- |
| 没带 Token | 401 Unauthorized | 未认证 |
| Token 无效/过期 | 401 Unauthorized | 未认证 |
| Token 有效但无权限 | 403 Forbidden | 已认证但无权访问 |

## 5. 在 api_design.md 中怎么写

每个写接口都要明确：

- **鉴权方式**：Bearer Token / API Key / 无（公开接口）。
- **权限要求**：例如"调用者必须是订单所属用户或运营角色"。
- **幂等策略**：业务唯一键 / `Idempotency-Key` 头 / 无（仅读接口）。
- **重复请求行为**：返回首次响应？返回 409 Conflict？

示例接口段：

```markdown
### POST /api/v1/orders

- 鉴权：Bearer Token（必须）
- 权限：任何已登录用户
- 幂等：客户端必须传 `Idempotency-Key`，24 小时内同 key 返回首次响应
- 限流：单用户 10 次/分钟
```

## 常见误区

- 把"客户端按钮防抖"当成幂等方案。前端防抖只解决一部分场景，网络重试无法覆盖。
- `Idempotency-Key` 表不设 TTL，无限增长。
- 用 GET 接口做写操作（如 `GET /api/delete?id=1`），既破坏 REST 语义又绕过浏览器/代理的安全假设。
- 把 Token 放 URL 里，会被记进日志和 Referer。永远放 Header。

## RAG 检索关键词

幂等性, idempotency, Idempotency-Key, Bearer Token, JWT, API Key, 鉴权, 401 403, 重复请求, 业务唯一键, api_design.md, skill_api_design, mission_2_alchemist
