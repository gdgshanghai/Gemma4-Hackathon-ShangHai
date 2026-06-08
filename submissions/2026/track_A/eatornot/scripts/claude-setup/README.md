# 🍔 EatOrNot Claude Code 终端集成

这个目录包含把 **EatOrNot** 的终端点餐能力分发给所有团队成员所需的配置和脚本。

---

## 包含内容

| 文件 | 说明 |
|------|------|
| `skills/meal-order.md` | Claude Code Skill — 终端点餐/推荐/领券完整流程 |
| `settings.local.json.template` | 权限白名单模板（含 mcd-mcp 等 30+ 工具权限） |
| `install.ps1` | **一键安装脚本** (PowerShell) |

---

## 快速开始

### 1. 安装麦当劳 MCP（终端点餐必需）

终端点餐功能依赖 `mcd-mcp` MCP 服务器。**每个用户需要使用自己的 Token。**

```powershell
# 添加麦当劳 MCP 到你的 Claude Code（用户级配置）
claude mcp add mcd-mcp -s user --transport http `
  --url https://mcp.mcd.cn `
  --header "Authorization: Bearer YOUR_TOKEN"
```

> **如何获取 Token？** 访问 [https://mcp.mcd.cn](https://mcp.mcd.cn) 注册并获取你自己的 API Token。
>
> ⚠️ 请勿使用他人的 Token。Token 关联个人麦当劳账号，涉及订单和支付。

如果暂时没有 Token，可以跳过此步骤——终端点餐会降级使用 Mock 数据。

### 2. 运行安装脚本

```powershell
# 在项目根目录执行
.\scripts\claude-setup\install.ps1
```

这会：
- 创建 `.claude/skills/` 目录
- 复制 `meal-order.md` skill 文件
- 复制 `settings.local.json` 权限配置
- **交互式引导**你配置麦当劳 MCP（如果尚未配置）

### 3. 重启 Claude Code

关闭并重新打开 Claude Code 会话，让 skill 和 MCP 生效。

### 4. 测试

在终端输入：

```
帮我点午餐
```

Claude 应该会自动：
1. 调用 Worker API 获取 3 个 AI 推荐方案
2. 展示方案表格
3. 询问你选择哪个 / 是否下单
4. 查询门店 → 匹配菜品 → 计算价格 → 下单

---

## 定时提醒

### 方式 A：服务端 Cron（推荐，无需 Claude Code 在线）

Worker 已配置 Cloudflare Cron Trigger：

| 餐次 | Cron (UTC) | 北京时间 |
|------|-----------|---------|
| 早餐 | `3 0 * * *` | 08:03 |
| 午餐 | `7 4 * * *` | 12:07 |
| 晚餐 | `3 10 * * *` | 18:03 |

Worker 会在这些时间点：
1. 自动生成 AI 推荐并写入 `meal_reminders` 表
2. 前端通过 `/api/reminders` 轮询获取
3. 浏览器可订阅 Web Push (`/api/push/subscribe`) 接收实时通知

### 方式 B：本地 Claude Code Cron（需要会话在线）

在 Claude Code 中输入：

```
开启饭点提醒
```

这会创建 3 个本地 cron job：
- 早餐 `3 8 * * *`
- 午餐 `7 12 * * *`
- 晚餐 `3 18 * * *`

> ⚠️ 本地 cron 只在 Claude Code 会话存活期间有效。

---

## Skill 触发词

| 你说 | Claude 做什么 |
|------|--------------|
| `帮我点餐` / `我要点麦当劳` | 完整流程：推荐 → 选方案 → 查门店 → 下单 |
| `午餐推荐` / `吃什么` | 只展示 AI 推荐，不下单 |
| `领券` | 自动领取麦当劳可用优惠券 |
| `有什么活动` | 查询麦当劳当月活动日历 |
| `查订单` | 查询最近订单状态 |
| `开启饭点提醒` | 创建本地 cron 定时任务 |
| `关闭提醒` | 删除所有 meal 相关 cron |

---

## 权限说明

`settings.local.json.template` 预授权了以下工具：

- `mcp__mcd-mcp__query-nearby-stores` — 查门店
- `mcp__mcd-mcp__query-meals` — 查菜单
- `mcp__mcd-mcp__calculate-price` — 算价格
- `mcp__mcd-mcp__create-order` — 下单
- `mcp__mcd-mcp__auto-bind-coupons` — 领券
- `mcp__mcd-mcp__campaign-calendar` — 查活动
- ... 以及 Cloudflare 部署/监控相关工具

如果你已有 `settings.local.json`，安装脚本会提示你手动合并权限。

---

## 常见问题

**Q: 为什么 skill 不生效？**
A: 确保：1) 安装脚本已运行；2) Claude Code 已重启；3) 你使用的触发词在 skill 的触发条件列表中。

**Q: mcd-mcp 工具报错 / 连接失败？**
A: 检查：1) 已配置 mcd-mcp（`claude mcp list` 查看是否有 mcd-mcp）；2) Token 有效且未过期；3) 网络可访问 `https://mcp.mcd.cn`。如无 Token，设置 `USE_MOCK_MCP=true` 使用 Mock 数据。

**Q: 如何修改 Worker API 地址？**
A: 编辑 `skills/meal-order.md`，把里面的 `https://eatornot-api.jimmy120070.workers.dev` 替换为你自己的 Worker 域名。

**Q: 服务端 Cron 和本地 Cron 会重复提醒吗？**
A: 不会。服务端 Cron 写入数据库，前端轮询获取；本地 Cron 只在终端输出。两者独立工作。

**Q: 如何获取麦当劳 MCP Token？**
A: 访问 [https://mcp.mcd.cn](https://mcp.mcd.cn) 注册获取。Token 关联你的麦当劳账号，请勿与他人共享。
