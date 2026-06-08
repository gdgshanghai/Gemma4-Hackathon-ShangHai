---
career: data_analyst
mission_id: mission_2_alchemist
skills:
  - skill_business_insight
  - skill_exploratory_analysis
doc_type: cookbook
related_files:
  - product_sales_summary.csv
  - insight_report.md
updated: 2026-05-20
---

# 电商核心业务指标计算指南

## TL;DR

- **核心规则**：先算"销售额占比 + 环比增长 + 平均单价"三组指标，再做"高/低 × 高/低"四象限交叉，洞察才有支撑。
- **反例**：只看环比增长 100% 就建议全力投入，结果发现品类绝对值很小、对业务无意义。
- **在本任务里怎么用**：用 §1 公式从 `product_sales_summary.csv` 算出关键指标，按 §3 模式提炼洞察，写进 `insight_report.md`。

## 1. 销售额与销量分析

给定 `product_sales_summary.csv`，可以计算：

### 销售额占比

公式：品类销售额 / 总销售额 × 100%

```python
total_revenue = df['current_month_sales_revenue'].sum()
df['revenue_share_pct'] = (
    df['current_month_sales_revenue'] / total_revenue * 100
).round(1)
```

### 环比增长率 (Month-over-Month, MoM)

```python
df['sales_revenue_mom_growth'] = (
    (df['current_month_sales_revenue'] - df['last_month_sales_revenue'])
    / df['last_month_sales_revenue'] * 100
).round(1)
```

### 平均单价 (ASP)

```python
df['average_unit_price_calculated'] = (
    df['current_month_sales_revenue'] / df['current_month_sales_volume']
)
```

## 2. 任务中可计算的指标

| 指标 | 计算公式 | 业务意义 |
| :--- | :--- | :--- |
| 销售额占比 | 品类销售额 / 总销售额 | 识别核心贡献品类（现金牛） |
| 销量占比 | 品类销量 / 总销量 | 识别流量/走量品类 |
| 平均单价 | 销售额 / 销量 | 判断品类定位（高端/低端） |
| 销售额环比增长 | (本月-上月)/上月 | 判断增长趋势，识别明星品类 |
| 销量环比增长 | (本月-上月)/上月 | 判断需求变化 |

## 3. 从指标到洞察的四象限

| 占比 | 增长 | 解读 | 行动建议示例 |
| :--- | :--- | :--- | :--- |
| 高 | 高 | 明星品类（如数码配件） | 加大投入、做组合销售 |
| 高 | 低/负 | 成熟品类，警惕衰退 | 找原因、防止流失 |
| 低 | 高 | 潜力品类 | 小规模测试放大 |
| 低单价 + 高销量 | — | 引流品类（如服装） | 捆绑销售提升客单价 |
| 高单价 + 低销量 | — | 利润品类 | 定向推送给高价值用户 |

示例洞察：

> 数码配件销售额占比 33%，环比增长 65%，是当前增长引擎；服装品类销量占比高但单价低，是主要流量来源。

## 4. 指标解释模板

写分析报告时，不要只贴计算结果。可以用这个结构：

- **现象**：哪个品类在什么指标上突出。
- **证据**：给出销售额占比、环比增长、销量或客单价。
- **解释**：这代表什么业务含义。
- **行动**：建议下个月怎么做。

示例：

> 数码配件本月销售额占比最高且环比增长最快，说明该品类同时具备规模和增速。建议下月加大资源投入，并与手机等高客单商品做组合销售，提升整体客单价。

## 常见误区

- 环比增长高不代表绝对贡献大。小品类从 1 万增长到 2 万也是 100%，但可能不值得大量资源。
- 销售额高不代表利润高。报告中如果没有利润数据，应避免直接下利润结论。
- 不要罗列所有指标，只保留能支撑洞察的关键 2–3 个。

## RAG 检索关键词

销售额占比, 销量占比, 平均单价, ASP, 环比增长, MoM, 品类分析, 业务洞察, product_sales_summary.csv, insight_report.md, skill_business_insight, skill_exploratory_analysis, mission_2_alchemist

