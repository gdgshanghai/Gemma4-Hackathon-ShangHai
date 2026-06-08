---
career: software_engineer
mission_id: mission_4_firefighter
skills:
  - skill_incident_response
  - skill_perf_troubleshooting
doc_type: cookbook
related_files:
  - incident_report.md
  - slow_query.log
updated: 2026-05-20
---

# EXPLAIN 与慢查询日志阅读指南

## TL;DR

- **核心规则**：`EXPLAIN` 告诉你"这条 SQL 怎么跑"，慢查询日志告诉你"哪些 SQL 跑得慢"。两者结合定位性能瓶颈。
- **反例**：只看应用日志说"接口慢了"，凭直觉加索引，加完没验证，问题依然存在。
- **在本任务里怎么用**：用 §2 解读慢查询日志找到嫌疑 SQL，用 §3 的 `EXPLAIN` 字段确认是全表扫描，再用 §5 的复盘模板把过程写进 `incident_report.md`。

## 1. 排障的标准动作

```
用户报告慢 → 查应用日志拿到慢接口 → 查慢查询日志找到慢 SQL
         → EXPLAIN 分析执行计划 → 提出修复（索引/SQL 改写）
         → 修复后再次 EXPLAIN + 压测验证 → 写复盘
```

跳过任何一步都可能"看起来修了"，实际没修。

## 2. 慢查询日志怎么读

MySQL 慢查询日志典型条目：

```
# Time: 2026-05-20T10:23:15.123456Z
# User@Host: app_user[app_user] @ [10.0.1.5]
# Query_time: 5.234561  Lock_time: 0.000123  Rows_sent: 50  Rows_examined: 1000000
SET timestamp=1716200595;
SELECT * FROM orders
WHERE user_id = 12345 AND status = 'ACTIVE'
ORDER BY create_time DESC
LIMIT 50;
```

关键字段：

| 字段 | 含义 | 红灯阈值 |
| :--- | :--- | :--- |
| `Query_time` | 执行总耗时（秒） | >1s 需关注，>5s 必须处理 |
| `Lock_time` | 等锁时间 | 长 → 锁竞争问题 |
| `Rows_sent` | 实际返回的行数 | 与业务期望对比 |
| `Rows_examined` | 扫描的行数 | 与 `Rows_sent` 比值 >100 → 索引失效嫌疑 |

任务里如果看到 `Rows_examined: 1,000,000` 而 `Rows_sent: 50`，说明数据库扫了 100 万行才挑出 50 行——典型的缺索引。

## 3. EXPLAIN 字段速查

```sql
EXPLAIN SELECT *
FROM orders
WHERE user_id = 12345 AND status = 'ACTIVE'
ORDER BY create_time DESC
LIMIT 50;
```

输出示例：

```
+----+-------------+--------+------+---------------+------+---------+------+---------+-----------------------------+
| id | select_type | table  | type | possible_keys | key  | key_len | ref  | rows    | Extra                       |
+----+-------------+--------+------+---------------+------+---------+------+---------+-----------------------------+
|  1 | SIMPLE      | orders | ALL  | NULL          | NULL | NULL    | NULL | 1000000 | Using where; Using filesort |
+----+-------------+--------+------+---------------+------+---------+------+---------+-----------------------------+
```

重点字段：

| 字段 | 含义 | 警示信号 |
| :--- | :--- | :--- |
| `type` | 访问类型 | `ALL`（全表扫描）= 红灯；`ref`/`range` 可接受；`const`/`eq_ref` 最佳 |
| `possible_keys` | 可用索引 | `NULL` = 完全没有索引 |
| `key` | 实际使用的索引 | `NULL` = 没用上索引 |
| `rows` | 估算扫描行数 | 与表总行数相近 = 全表扫描 |
| `Extra` | 额外信息 | `Using filesort` = 文件排序；`Using temporary` = 临时表；都意味着开销 |

加索引后再次 `EXPLAIN`，期望看到：

- `type` 变成 `ref` 或 `range`
- `key` = `idx_orders_user_status_createtime`
- `rows` 大幅下降
- `Extra` 中没有 `Using filesort`

## 4. 三个最常见的诊断结论

### 结论 A：缺索引
- 信号：`type=ALL`、`key=NULL`、`rows` 接近全表。
- 修复：加索引（详见 [sql-index-optimization-guide.md](sql-index-optimization-guide.md)）。

### 结论 B：索引存在但用不上
- 信号：`possible_keys` 有候选，`key=NULL`。
- 常见原因：`WHERE` 列上用了函数 / 类型不匹配 / 复合索引最左前缀未命中。
- 修复：改写 SQL 或调整索引顺序。

### 结论 C：N+1 查询
- 信号：单条 SQL 不慢，但日志里出现成百上千条结构相同的 SQL。
- 修复：合并为批量查询（详见 [n-plus-one-query-problem.md](n-plus-one-query-problem.md)）。

## 5. 事故复盘模板

```markdown
## 事故复盘：订单列表接口超时

### 1. 现象
- 时间：2026-05-20 10:20–10:35
- 影响：订单列表接口 P99 从 200ms 飙升到 8s，5% 用户超时

### 2. 定位过程
- 10:25 应用日志显示 `GET /orders` 大量超时
- 10:28 慢查询日志命中 SQL：`SELECT * FROM orders WHERE user_id=? AND status=? ORDER BY create_time DESC`
- 10:30 EXPLAIN 显示 `type=ALL`, `Rows_examined=1,000,000`

### 3. 根因
`orders` 表未在 `(user_id, status, create_time)` 上建复合索引，全表扫描。

### 4. 修复
```sql
CREATE INDEX idx_orders_user_status_createtime
ON orders(user_id, status, create_time DESC);
```

### 5. 验证
- EXPLAIN: `type=ref`, `key=idx_orders_user_status_createtime`, `rows=120`
- 压测：P99 从 8s 降至 45ms

### 6. 改进项
- [ ] 接入慢查询告警（阈值 1s）
- [ ] 上线前对新接口必跑 EXPLAIN
- [ ] DBA Review 流程加入复合索引顺序检查
```

## 常见误区

- 只看 `Query_time` 不看 `Rows_examined`，可能错过潜在隐患（数据量增长后才爆发）。
- `EXPLAIN` 仅给估算，行数与实际可能差异较大；用 `EXPLAIN ANALYZE`（MySQL 8.0+）可看真实执行。
- 修复后不验证 EXPLAIN 命中新索引就关闭事故。

## RAG 检索关键词

EXPLAIN, 慢查询日志, slow_query.log, Query_time, Rows_examined, Rows_sent, type ALL, Using filesort, Using temporary, 事故复盘, incident_report.md, skill_incident_response, skill_perf_troubleshooting, mission_4_firefighter
