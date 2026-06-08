---
name: meal-order
description: Terminal-based meal reminder and McDonald's ordering flow. Use when user says "帮我点餐", "午餐推荐", "吃什么", "我要点麦当劳", or when meal-time cron fires.
---

# 🍔 EatOrNot 终端点餐

## 触发条件

- 用户说："帮我点餐" / "午餐推荐" / "吃什么" / "我要点麦当劳" / "帮我点午餐"
- Cron 定时触发（早 8:00 / 午 12:00 / 晚 18:00）
- 用户主动问"有什么活动"或"最近有什么优惠"

## 流程

### Step 1: 获取 AI 推荐

调用 Worker API 获取 3 个方案：

```bash
curl -s -X POST http://127.0.0.1:8000/api/recommend \
  -H 'Content-Type: application/json' \
  -d '{"message":"帮我搭配<餐次>","mode":"quick"}'
```

餐次根据当前时间自动判断：
- 6:00-10:00 → 早餐
- 10:00-14:00 → 午餐
- 16:00-20:00 → 晚餐
- 其他时间 → 夜宵

### Step 2: 展示方案

用 Markdown 表格展示 3 个方案，格式：

```
## 🍽️ 智囊团推荐方案

### 方案 1: 💪 {title} ({mode})
| 菜品 | 价格 | 热量 |
|------|------|------|
| ...  | ¥... | ...kcal |

💰 总价: ¥XX | 🔥 总热量: XXkcal
✅ 优点: ...
❌ 缺点: ...
📝 推荐理由: ...

### 方案 2: 💰 {title}
(same format)

### 方案 3: 🎉 {title}
(same format)

---

> 请选择: **1** (自律) / **2** (省钱) / **3** (犒劳) / **换一个** / **跳过**
```

### Step 3: 用户选择后 — 查询门店

如果用户选择了一个方案，查询附近门店：

使用 `mcp__mcd-mcp__query-nearby-stores` 工具：
- beType: 1 (到店自取)
- searchType: 2
- city: 询问用户所在城市
- keyword: 用户输入的位置关键词

展示门店列表让用户选择。

### Step 4: 匹配真实菜品

使用 `mcp__mcd-mcp__query-meals` 获取门店真实菜单：
- storeCode: 用户选的门店
- orderType: 1
- beType: 1

用模糊匹配将推荐方案的菜品名与真实菜单匹配，获取 productCode。
如果匹配不到，让用户确认或替换。

### Step 5: 计算价格

使用 `mcp__mcd-mcp__calculate-price` 验证实际价格：
- storeCode, orderType: 1, beType: 1
- items: 匹配后的菜品列表（含 productCode 和 quantity）

展示实际价格，确认是否下单。

### Step 6: 创建订单

使用 `mcp__mcd-mcp__create-order` 下单：
- storeCode, orderType: 1, beType: 1
- items: 菜品列表
- takeWayCode: 从 calculate-price 返回的 takeWayList 中选择

### Step 7: 展示支付信息

展示订单结果：
- 订单号
- 支付链接
- 提示用户扫码或打开麦当劳 APP 完成支付

## 安全规则

1. **下单前必须确认** — 展示完整菜品和价格后，必须等用户明确说"确认下单"才执行 create-order
2. **价格异常检查** — 如果实际价格与推荐价格差异超过 20%，提示用户
3. **过敏检查** — 如果推荐结果有 safety_warnings，必须高亮展示
4. **不自动下单** — cron 提醒只展示推荐，不会自动下单

## Cron 定时提醒设置

当用户说"开启饭点提醒"或首次使用时，创建 3 个定时任务：

- 早餐提醒: `3 8 * * *`
- 午餐提醒: `7 12 * * *`
- 晚餐提醒: `3 18 * * *`

每个 cron prompt: "饭点到了！执行 meal-order skill：调用 http://127.0.0.1:8000/api/recommend 获取推荐方案，展示给用户并询问是否点餐。"

当用户说"关闭提醒"时，删除所有 meal 相关的 cron job。

## 快捷指令

- "点餐" / "帮我点" → 立即执行完整流程
- "推荐" / "吃什么" → 只展示推荐，不下单
- "查订单" → 使用 mcp__mcd-mcp__query-order 查询
- "领券" → 使用 mcp__mcd-mcp__auto-bind-coupons 自动领券
- "有什么活动" → 使用 mcp__mcd-mcp__campaign-calendar 查询
