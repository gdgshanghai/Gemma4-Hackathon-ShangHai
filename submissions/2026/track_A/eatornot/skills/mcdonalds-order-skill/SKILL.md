---
name: mcdonalds-order-skill
description: 帮助 Agent 使用 McDonald's MCP 查询菜单、营养、价格和创建订单。
---

# 麦当劳下单技能

当用户想点麦当劳时使用此技能。

## 规则

- 当 USE_MOCK_MCP=true 或 token 不存在时，使用 Mock 数据
- 未经用户明确确认，不得创建真实订单
- 下单前验证商品可用性
- 显示完整价格明细
- 记录所有订单用于追踪

## MCP 工具

| 工具 | 功能 |
|------|------|
| mcd_list_nutrition_foods | 获取菜单（含营养数据） |
| mcd_query_nearby_stores | 查询附近门店 |
| mcd_calculate_price | 计算价格 |
| mcd_create_order | 创建订单 |

## 下单流程

1. 用户选择商品
2. 计算价格
3. 显示确认对话框
4. 用户确认
5. 调用 create_order
6. 记录用餐
7. 更新预算

## 安全检查

- 不自动确认订单
- 显示完整明细
- 检查过敏信息
- 验证预算可负担性
