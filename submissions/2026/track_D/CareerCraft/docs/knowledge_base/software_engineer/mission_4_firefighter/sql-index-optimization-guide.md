---
career: software_engineer
mission_id: mission_4_firefighter
skills:
  - skill_sql_optimization
  - skill_perf_troubleshooting
doc_type: cookbook
related_files:
  - orders_table_schema.sql
  - incident_report.md
updated: 2026-05-20
---

# SQL 性能急救：索引使用指南

索引是数据库的"目录"，能极大加速查询。不当使用索引是性能问题的首要元凶。

## TL;DR

- **核心规则**：频繁出现在 `WHERE`、`JOIN`、`ORDER BY` 中的列是建索引的候选。
- **反例**：`orders` 表不加任何索引就执行 `WHERE user_id = ? AND status = ? ORDER BY create_time DESC`，触发百万级全表扫描。
- **在本任务里怎么用**：按 §3 加复合索引 `(user_id, status, create_time DESC)`，在事故报告里量化 `Rows_examined` 与 `Query_time` 的变化。

## 1. 索引是什么

想象一本书后的"索引"页。要查"重构"相关内容，直接翻索引找到页码，而不是一页页翻全书。数据库索引同理。

## 2. 何时需要索引

- 频繁作为 `WHERE` 条件的列（如 `user_id = 123`）。
- 用于 `JOIN` 的列。
- 用于 `ORDER BY` 或 `GROUP BY` 的列。

## 3. 如何为"线上消防员"任务创建索引

问题 SQL：

```sql
SELECT *
FROM orders
WHERE user_id = 12345 AND status = 'ACTIVE'
ORDER BY create_time DESC;
```

分析：

- `WHERE` 条件涉及 `user_id` 和 `status`。
- `ORDER BY` 涉及 `create_time`。

最佳索引策略（复合索引）：

```sql
-- 覆盖三列的索引
CREATE INDEX idx_orders_user_status_createtime
ON orders(user_id, status, create_time DESC);

-- 或者，如果 status 过滤性不高：
CREATE INDEX idx_orders_user_createtime
ON orders(user_id, create_time DESC);
```

解释：索引按 `user_id` 排序，再按 `status`，最后按 `create_time` 降序排列。查询时数据库能直接在索引中定位到 `user_id=12345 AND status='ACTIVE'` 的所有记录，且这些记录已按 `create_time` 排序，无需额外排序操作。

## 4. 索引使用禁忌

- 不要为频繁更新的列建过多索引：每次增删改都需要更新索引，影响写入性能。
- 小表不需要索引：全表扫描可能更快。
- 不要在 `WHERE` 列上使用函数或类型转换，如 `WHERE DATE(create_time) = ?`，这会使索引失效。

## 5. 解释你的优化

在事故报告里，可以这样写：

- **根因**：`orders` 表在 `user_id` 和 `status` 列上缺少索引，导致查询进行了全表扫描（`Rows_examined: 1,000,000`）。
- **修复方案**：添加复合索引 `(user_id, status, create_time)`。该索引能直接定位到特定用户和状态的订单，并利用索引的有序性避免排序。
- **预期效果**：查询时间从 >5 秒降至 <50 毫秒。

## 6. 复合索引设计口诀

复合索引按以下顺序考虑：

1. 等值过滤字段，例如 `user_id`、`status`。
2. 范围过滤字段，例如 `create_time >= ?`。
3. 排序字段，例如 `ORDER BY create_time DESC`。

在 `WHERE user_id = ? AND status = ? ORDER BY create_time DESC` 中，`(user_id, status, create_time)` 能同时服务过滤和排序。

## 7. 报告中应写清楚的证据

事故报告不要只写"加索引优化了"。建议写：

- 慢查询日志中的 `Query_time`。
- `Rows_examined` 与 `Rows_sent` 的差距。
- 原 SQL 的过滤条件和排序字段。
- 新增索引名称和字段顺序。
- 预期收益和潜在写入成本。

## 常见误区

- 加了索引但没验证：必须用 `EXPLAIN` 确认 `key` 字段命中了新索引（详见 [explain-and-slow-query-reading.md](explain-and-slow-query-reading.md)）。
- 复合索引顺序错了：等值列放前面、排序列放最后；顺序错了索引可能用不上排序。
- 选择性差的列放前面（如 `status` 只有 2 种取值），过滤效果差。

## RAG 检索关键词

SQL 索引, 复合索引, 慢查询, user_id status create_time, ORDER BY 优化, EXPLAIN, Rows_examined, idx_orders_user_status_createtime, orders 表, incident_report.md, skill_sql_optimization, skill_perf_troubleshooting, mission_4_firefighter

