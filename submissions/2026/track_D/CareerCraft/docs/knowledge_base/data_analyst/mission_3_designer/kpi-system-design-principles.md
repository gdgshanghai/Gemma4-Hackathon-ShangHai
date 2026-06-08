---
career: data_analyst
mission_id: mission_3_designer
skills:
  - skill_kpi_system_design
  - skill_stakeholder_mgmt
doc_type: concept
related_files:
  - user_acquisition_funnel.csv
  - dashboard_design.md
updated: 2026-05-20
---

# 数据看板设计：KPI 体系搭建原则

## TL;DR

- **核心规则**：好的看板不是图表堆砌，是**战略的视觉化**——按"利益相关者诉求 → 漏斗指标 → 模块化布局"三步设计。
- **反例**：把所有指标堆在一张大图，销售、市场、产品都看不到自己要的。
- **在本任务里怎么用**：用 §1 把销售/市场/产品诉求翻译成指标，用 §3 的模块布局写出 `dashboard_design.md`。

## 1. 理解利益相关者

不同角色关注点不同，你的任务是与销售、市场、产品沟通，提炼他们的核心问题：

- **销售**：最终结果。付费用户数、总收入、客单价、销售漏斗底部转化率。
- **市场**：获客效率。曝光量、点击率 (CTR)、注册转化率、获客成本 (CAC)、渠道贡献。
- **产品**：用户体验与留存。注册成功率、功能使用率、用户留存率、用户满意度 (CSAT/NPS)。

## 2. 用户获取漏斗的核心指标

典型电商用户获取漏斗：

```text
曝光 (Impressions) → 点击 (Clicks) → 注册 (Registrations) → 付费 (Paying Users)
```

对应指标：

- **点击率 (CTR)** = Clicks / Impressions
- **注册转化率** = Registrations / Clicks
- **付费转化率** = Paying Users / Registrations
- **整体转化率** = Paying Users / Impressions
- **获客成本 (CAC)** = 渠道花费 / Paying Users
- **平均客单价** = Revenue / Paying Users

## 3. 看板布局设计（模块化）

一个优秀的看板通常分区域呈现：

- **顶部概览 (Summary Cards)**：核心 KPI 实时值及日/周环比。如：今日付费用户数、总获客成本、平均客单价。
- **核心漏斗可视化 (Funnel Chart)**：直观展示从曝光到付费各环节的用户数和转化率，快速定位流失环节。
- **维度下钻 (Breakdown by Dimension)**：
  - 按渠道：柱状图对比各渠道 (Search, Social, Direct) 的付费用户数和 CAC。
  - 按时间趋势：折线图展示核心指标（如付费用户数）过去 7/30 天的变化。
- **明细数据表 (Detail Table)**：展示各渠道/日期的详细数据，支持排序和筛选。

## 4. 利益相关者到指标的映射

设计看板时，把角色诉求翻译成指标：

| 角色 | 核心指标 |
| :--- | :--- |
| 销售总监 | 付费转化率、收入、客单价 |
| 市场经理 | 曝光、点击率、获客成本、渠道 ROI |
| 产品经理 | 注册转化率、流失环节、次日留存 |

一个统一看板不等于把所有指标堆在一起，而是让不同角色都能找到自己的决策入口。

## 5. dashboard_design.md 推荐结构

- **看板目标**：一句话总结（如"监控用户获取效率，优化渠道投放"）。
- **核心指标列表**：至少 4 个，覆盖转化、成本、收入。
- **布局草图描述**：参考 §3 模块化区域。
- **图表示例数据**：例如计算漏斗各环节用户数：

```python
funnel_data = {
    '曝光': 100000 + 80000 + 20000,
    '点击': 5000 + 4000 + 1000,
    '注册': 1000 + 600 + 300,
    '付费': 100 + 60 + 30,
}
```

## 6. dashboard_design.md 检查清单

提交前确认：

- [ ] 有一句话看板目标。
- [ ] 至少 4 个核心指标，覆盖转化、成本、收入。
- [ ] 布局说明清楚，读者知道每个区域看什么。
- [ ] 图表数据能从原始 CSV 计算出来。
- [ ] 指标口径明确，例如 CAC = 成本 / 付费用户 或 成本 / 注册用户。

## 常见误区

- 不要让三方需求互相覆盖，做"折中"看板，结果谁都不满意。模块化分区才是正解。
- 不要把 CAC 算成"总成本 / 总用户"而不区分付费/注册，口径错误会误导决策。
- 不要遗漏时间维度。无趋势的看板只能看快照，无法发现拐点。

## RAG 检索关键词

KPI 体系, 指标体系, 用户获取漏斗, CTR, CAC, 付费转化率, 客单价, 利益相关者管理, dashboard_design.md, user_acquisition_funnel.csv, skill_kpi_system_design, skill_stakeholder_mgmt, mission_3_designer

