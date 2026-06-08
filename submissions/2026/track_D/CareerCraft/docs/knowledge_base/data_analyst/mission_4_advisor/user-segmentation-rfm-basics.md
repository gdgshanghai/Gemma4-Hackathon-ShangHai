---
career: data_analyst
mission_id: mission_4_advisor
skills:
  - skill_drill_down_analysis
  - skill_business_insight
doc_type: concept
related_files:
  - high_value_users.csv
  - strategy_proposal.md
updated: 2026-05-20
---

# 用户分群与 RFM 模型基础

## TL;DR

- **核心规则**：用 R（最近购买）、F（购买频次）、M（消费金额）三个维度给用户打分，把所有用户切成 8 类，每一类对应一种运营策略。
- **反例**：把"高价值用户"简单定义成"消费金额 Top 10%"，结果发现大半都是一年前买过一次贵东西、早就流失的用户。
- **在本任务里怎么用**：按 §3 给"高价值未复购用户"建立可执行口径，输出 `high_value_users.csv`，并在 `strategy_proposal.md` 里说明每个分群的运营建议。

## 1. 为什么需要分群

不分群的两种灾难：

- **一视同仁**：给所有用户发同一张券，预算浪费在不需要的人身上。
- **凭直觉切分**：用"最近 30 天没下单 + 历史消费 > 1000 元"这种拍脑袋规则，无法解释为什么是 30 天、为什么是 1000。

分群的本质是**用数据回答"该把资源投给谁、为什么"**。

## 2. RFM 三维度

| 维度 | 全称 | 定义 | 业务含义 |
| :--- | :--- | :--- | :--- |
| R | Recency | 距上次购买的天数 | 越小越"活" |
| F | Frequency | 统计窗口内的购买次数 | 越大越"忠诚" |
| M | Monetary | 统计窗口内的总消费金额 | 越大越"值钱" |

通常统计窗口取最近 12 个月。

## 3. 打分与分群（5 分位法）

对每个维度按用户分布打 1–5 分（5 分最佳）：

- R：天数越小分越高。例如所有用户 R 值的 20% 分位 = 5 分。
- F：次数越大分越高。
- M：金额越大分越高。

然后按"高/低"（≥4 为高，≤2 为低，3 为中）切分得到 8 大经典分群：

| 分群 | R | F | M | 运营策略 |
| :--- | :--- | :--- | :--- | :--- |
| 重要价值客户 | 高 | 高 | 高 | VIP 服务、专属权益、维护好不要打扰 |
| 重要保持客户 | 低 | 高 | 高 | 老客户但久未购买，重点唤回 |
| 重要发展客户 | 高 | 低 | 高 | 单次消费高但频次低，培养复购 |
| 重要挽留客户 | 低 | 低 | 高 | 高价值流失用户，召回成本高但 ROI 高 |
| 一般价值客户 | 高 | 高 | 低 | 频繁但客单低，提客单 |
| 一般保持客户 | 低 | 高 | 低 | 老用户但活跃下降 |
| 一般发展客户 | 高 | 低 | 低 | 新用户，培养习惯 |
| 一般挽留客户 | 低 | 低 | 低 | 价值低且流失，低成本触达即可 |

## 4. SQL 示例：计算 RFM

```sql
WITH user_rfm AS (
    SELECT
        user_id,
        DATEDIFF(CURRENT_DATE, MAX(order_date)) AS recency,
        COUNT(DISTINCT order_id) AS frequency,
        SUM(order_amount) AS monetary
    FROM orders
    WHERE order_date >= DATE_SUB(CURRENT_DATE, INTERVAL 12 MONTH)
      AND status = 'PAID'
    GROUP BY user_id
),
scored AS (
    SELECT
        user_id,
        recency, frequency, monetary,
        NTILE(5) OVER (ORDER BY recency DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency)     AS f_score,
        NTILE(5) OVER (ORDER BY monetary)      AS m_score
    FROM user_rfm
)
SELECT
    user_id, recency, frequency, monetary,
    r_score, f_score, m_score,
    CASE
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '重要价值客户'
        WHEN r_score <= 2 AND f_score >= 4 AND m_score >= 4 THEN '重要保持客户'
        WHEN r_score >= 4 AND f_score <= 2 AND m_score >= 4 THEN '重要发展客户'
        WHEN r_score <= 2 AND f_score <= 2 AND m_score >= 4 THEN '重要挽留客户'
        ELSE '其他'
    END AS segment
FROM scored;
```

## 5. "高价值未复购用户"的可执行口径

在本任务，业务方常常说"找出高价值但没复购的用户"。直接照字面做容易翻车。建议这样定义：

| 条件 | 推荐口径 | 为什么 |
| :--- | :--- | :--- |
| 高价值 | 历史累计消费金额位于前 20%（M 分 ≥4） | 排除单笔大额但本质低频的用户 |
| 未复购 | 最近 90 天无下单 且 历史下单次数 ≥2 | 至少买过 2 次才算"原本会复购"，90 天可调 |
| 仍可触达 | 最近 30 天有 App 打开 或 收件箱可达 | 完全流失的用户召回 ROI 太低 |

把这 3 个条件以 `AND` 组合，输出到 `high_value_users.csv`，字段建议：
`user_id, last_order_date, recency_days, total_orders, total_amount, last_active_date, channel`。

## 6. 分群结果如何用于策略提案

在 `strategy_proposal.md` 里，不要只列分群人数，要回答：

- **触达方式**：短信 / Push / 电话 / EDM？依据分群价值选成本。
- **触达内容**：高价值未复购用户应给什么权益？折扣力度多少？
- **预估收益**：召回率假设 × 客单价 × 人数 = 预期 GMV。
- **预算上限**：召回成本不应超过预期 GMV 的 X%。

## 常见误区

- 把 R/F/M 三个维度简单相加成总分。三者业务含义不同，相加会丢失结构。优先按高低组合归类，再看总分。
- 统计窗口选得太短（如 30 天），F 和 M 失真，新用户长期客户都被压成低分。
- 忽视"可触达性"维度。分群再准，触达不到等于零。
- 一次定义后永不更新。业务季节性强时应定期重算。

## RAG 检索关键词

RFM 模型, 用户分群, Recency Frequency Monetary, 高价值用户, 复购用户, 流失召回, NTILE 五分位, 用户运营策略, high_value_users.csv, strategy_proposal.md, skill_drill_down_analysis, skill_business_insight, mission_4_advisor
