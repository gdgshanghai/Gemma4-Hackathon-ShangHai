---
career: data_analyst
mission_id: mission_4_advisor
skills:
  - skill_drill_down_analysis
  - skill_root_cause_analysis
doc_type: cookbook
related_files:
  - high_value_users.csv
  - strategy_proposal.md
updated: 2026-05-20
---

# 下钻分析：从宏观问题定位微观根因

## TL;DR

- **核心规则**：按"用户维度 × 行为/品类维度"两层下钻，定位最小问题子集，再形成靶心。
- **反例**：只回答"复购率下降了 10 个点"，不告诉业务方是哪群人、哪个品类下降。
- **在本任务里怎么用**：用 §3 的 Pandas 代码下钻 `high_value_users.csv`，把"重灾区"写进 `strategy_proposal.md` 的"问题下钻分析"部分。

## 1. 什么是下钻分析

像用显微镜，从整体数据（如"高价值用户复购率从 35% 降至 25%"）逐层细分，定位到具体问题子集。

## 2. 核心下钻维度

对"高价值用户复购率下降"问题，至少从两个维度交叉下钻：

### 用户维度 (WHO)

- 用户分层：新晋高价值用户（最近 3 个月达成）vs 老牌高价值用户（> 1 年）。
- 用户画像：是否集中在某个年龄层、地域、注册渠道。

### 产品 / 行为维度 (WHAT)

- 品类：是否集中在某品类（奢侈品、电子产品…）。
- 价格带：是不再购买高单价商品，还是低单价商品。
- 交互行为：这些用户最近是否减少了 App 访问频率、浏览时长。

## 3. 如何执行下钻分析（以任务数据为例）

```python
import pandas as pd

df = pd.read_csv('high_value_users.csv')

# 1. 按用户分层和主品类分组计算
drilldown_result = df.groupby(['cohort', 'primary_category']).agg({
    'repurchase_rate_last_month': 'mean',
    'repurchase_rate_current_month': 'mean',
    'browse_time_decline_flag': 'sum',
}).reset_index()

# 2. 计算变化幅度
drilldown_result['repurchase_rate_change'] = (
    drilldown_result['repurchase_rate_current_month']
    - drilldown_result['repurchase_rate_last_month']
)

# 3. 找出"重灾区"
problem_segment = drilldown_result.sort_values('repurchase_rate_change').head(1)
print(problem_segment)
```

假设结果：`cohort='new_hv_user'` × `primary_category='luxury'` 这个细分群体，复购率从 36% 暴跌至 20%，且组内浏览时长普遍下降。

## 4. 得出下钻结论

- **问题核心**：复购率下降主要集中在**新晋高价值用户**购买**奢侈品**的行为上。
- 这为后续归因分析提供精确"靶心"——不需要分析所有用户，而是聚焦于这群"新贵"为什么不再买奢侈品。
- 这是 `strategy_proposal.md` 中"问题下钻分析"部分的核心产出。

## 5. 下钻写法

下钻部分建议按"整体到局部"写：

1. 整体指标变化：高价值用户复购率从多少降到多少。
2. 第一层拆分：按用户分层比较新晋 vs 老高价值用户。
3. 第二层拆分：按品类比较奢侈品、电子产品、美妆等。
4. 交叉定位：找出下降最集中的"用户分层 + 品类"组合。
5. 形成靶心：说明后续策略只针对这群用户。

## 6. 归因假设要求

归因不能只写"用户不喜欢了"。更好的写法：

- **观察**：该人群浏览时长下降，复购率下降。
- **假设**：可能是竞品促销或新品吸引力不足。
- **验证**：通过 AB 测试、用户调研或竞品活动数据进一步验证。

## 常见误区

- 只下钻一个维度（只看用户分层或只看品类），漏掉真正的"重灾区"。
- 找到一个细分就直接下结论，不验证样本量是否足够。
- 归因停留在"用户不喜欢了"，没有可被证伪的假设。

## RAG 检索关键词

下钻分析, 根因分析, 高价值用户, 复购率下降, 用户分层, 品类维度, luxury, browse_time_decline_flag, 归因假设, high_value_users.csv, strategy_proposal.md, skill_drill_down_analysis, skill_root_cause_analysis, mission_4_advisor

