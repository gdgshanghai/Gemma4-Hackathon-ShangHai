# ADR 0001: Identity & Auth Contract for CareerCraft MVP

- Status: Accepted
- Date: 2026-05-30
- Deciders: Backend & Frontend leads
- Tags: identity, auth, api-contract

## Context

CareerCraft 早期版本以匿名 `X-Player-Id`（UUID v4）作为唯一身份标识，前端在 `localStorage`
中持久化。随后规划引入完整账户体系（邮箱 + JWT），但当前阶段：

1. 后端尚未实现 JWT 校验与刷新逻辑；
2. 已有客户端、E2E 脚本、文档全部依赖 `X-Player-Id`；
3. 同时存在多处隐式的身份解析（不同路由各自读取 header），缺乏统一错误码。

直接“一刀切”改为强制 JWT 会立即打破现有契约，但若不在协议层留出迁移位，则账户体系
落地时又会引发新一轮接口级 breaking change。

## Decision

1. **统一身份解析为单一依赖入口**：所有路由通过 `Depends(get_current_user_id)`
   消费 `IdentityResolver` 协议（Strategy Pattern），实现替换不影响调用方。
2. **三种 `AUTH_MODE` 互斥可切**：`anonymous` / `hybrid` / `jwt`，默认 `hybrid`。
   - `hybrid` 优先尝试 JWT，失败回落到 `X-Player-Id`，兼顾迁移期老/新客户端。
   - `jwt` 模式下若 JWT 实现缺失，**进程启动时即报错**（fail-fast），避免“以为强认证、
     实际全部 401”。
3. **结构化 401 错误码**：`{"detail": {"code": "identity.*", "message": "..."}}`，
   前端据此判断“可一次性重试（匿名）”与“需触发登录（JWT）”。
4. **前端契约**：`authedFetch` 对 `identity.missing_player_id` /
   `identity.invalid_player_id` 做且仅做一次重试；SSE 调用显式 `skipAuthRetry`。
5. **文档级冻结**：身份契约写入 `docs/specification/03-interface-spec.md` 第二章，
   任何破坏性变更必须更新本 ADR 与该章节，并在 PR 中标记 `breaking-change`。

## Consequences

### Positive

- 单一身份入口让授权策略（黑名单、配额、审计）有了清晰的拦截点。
- `hybrid` 默认值保证迁移期前后端可独立演进；切换到 `jwt` 是一行配置 + 重启。
- 结构化错误码消除了“前端 401 → 全局退出登录”这类粗暴行为，可针对匿名 ID
  失效做无感重试。
- fail-fast 杜绝了“配置选了 `jwt` 但功能没做” 的静默回归。

### Negative / Trade-offs

- `hybrid` 模式下 JWT 路径失败会回落，可能掩盖配置错误；通过 `identity_resolution_failed`
  结构化日志可观测，但需运维关注日志而非依赖 5xx 告警。
- 维护两套契约（header + Bearer）增加测试矩阵；通过 `tests/test_identity_contract.py`
  端到端覆盖来抵消。

### Neutral

- 未来若引入第三种身份（如 OAuth），按 Strategy Pattern 新增 Resolver 即可，
  无需触碰路由代码。

## Links

- Code: `backend/app/api/deps.py`
- Tests: `backend/tests/test_deps.py`, `backend/tests/test_identity_contract.py`
- Spec: `docs/specification/03-interface-spec.md` §二
- Frontend: `frontend/src/services/api.ts`, `frontend/src/services/identity.ts`
