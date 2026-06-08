---
career: software_engineer
mission_id: mission_4_firefighter
skills:
  - skill_perf_troubleshooting
  - skill_incident_response
doc_type: concept
related_files:
  - OrderService.java
  - incident_report.md
updated: 2026-05-20
---

# 性能杀手：N+1 查询问题

## TL;DR

- **核心规则**：循环里执行 SQL 就是 N+1 嫌疑。改用 `IN` 或 JOIN 一次性取回数据。
- **反例**：日志中出现成百上千条结构相同、只是参数不同的 SQL，响应时间随订单数线性变慢。
- **在本任务里怎么用**：用 §3 的两种修复方案重写 `getRecentOrders`，并在事故报告中说明查询次数从 N+1 降到 1。

## 1. 什么是 N+1 查询

假设你要查询 10 个用户及其所有订单：

- 1 次查询：`SELECT * FROM users WHERE id IN (1,2,...,10);`（获取 10 个用户）
- N 次查询：对每个用户执行 `SELECT * FROM orders WHERE user_id = ?`（10 个用户 = 10 次）

总查询次数 = 1 + N = 11 次。这就是 N+1。

任务代码中：

```java
public List<Order> getRecentOrders(List<Integer> userIds) {
    List<Order> allOrders = new ArrayList<>();
    for (Integer userId : userIds) {              // 循环 N 次
        allOrders.addAll(getOrdersByUserId(userId)); // 每次执行 1 次查询
    }
    return allOrders;
}
```

## 2. 为什么是灾难

- **数据库连接开销**：每次查询都有网络往返、SQL 解析、执行计划生成的开销。
- **并发能力下降**：占用大量数据库连接。
- **响应时间**：如果 N = 1000，就是 1001 次查询，必然超时。

## 3. 解决方案

使用 `IN` 查询或 JOIN 一次性获取所有数据。

### 方案 A：应用层 IN 查询（推荐用于任务修复）

```java
public List<Order> getRecentOrdersFixed(List<Integer> userIds) {
    if (userIds.isEmpty()) {
        return new ArrayList<>();
    }
    String sql = "SELECT * FROM orders "
               + "WHERE user_id IN (:userIds) AND status = 'ACTIVE' "
               + "ORDER BY create_time DESC";
    List<Order> allOrders = jdbcTemplate.query(
        sql, Map.of("userIds", userIds), orderRowMapper);
    return allOrders;
}
```

### 方案 B：数据库层 JOIN

```sql
SELECT o.*
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE u.id IN (1, 2, 3)
  AND o.status = 'ACTIVE'
ORDER BY o.create_time DESC;
```

## 4. 识别 N+1 的信号

- 日志中出现大量结构相同、参数不同的 SQL。
- 接口响应时间随用户数量或订单数量线性变慢。
- 代码里在 `for` 循环中调用 DAO 或 Repository。
- ORM 懒加载在遍历对象关系时触发额外查询。

## 5. 修复方案对比

- 使用 `IN` 查询一次性查出多个用户的订单。
- 使用 JOIN 或批量关联查询。
- 在 ORM 中使用 fetch join 或预加载。
- 对批量查询涉及的过滤和排序字段建立合适索引（详见 [sql-index-optimization-guide.md](sql-index-optimization-guide.md)）。

修复后要比较查询次数和 `Rows_examined`，而不是只看代码变短。

## 6. 如何预防

- 使用 ORM 框架（如 MyBatis、JPA）时，注意懒加载机制，避免在循环中触发查询。
- 代码审查时，警惕“在循环中执行数据库查询”的模式。
- 在事故报告中，这是核心的“根因分析”和“修复方案”。

## 常见误区

- 改成 `IN (?, ?, ?, ...)` 时不限制列表长度，超长 `IN` 列表（>1000）也会拖慢查询。建议分批。
- 用 JOIN 后没注意去重，结果集出现笛卡尔积。
- 修完只看“代码短了”，没量化查询次数与执行时间。

## RAG 检索关键词

N+1 查询, 循环内 SQL, 批量查询, IN 查询, JOIN, 懒加载, 慢查询, Rows_examined, getRecentOrders, OrderService.java, incident_report.md, skill_perf_troubleshooting, skill_incident_response, mission_4_firefighter
