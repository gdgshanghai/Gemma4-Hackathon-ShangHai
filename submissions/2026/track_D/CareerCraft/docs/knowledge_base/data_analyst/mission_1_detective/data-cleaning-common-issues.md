---
career: data_analyst
mission_id: mission_1_detective
skills:
  - skill_data_cleaning
  - skill_data_quality
doc_type: cookbook
related_files:
  - promo_data_raw.csv
  - promo_data_clean.csv
  - data_cleaning_rules.md
updated: 2026-05-20
---

# 数据清洗：识别与处理常见问题

## TL;DR

- **核心规则**：先把"缺失、异常、不一致、重复"四类问题各自识别清楚，再制定可复现的清洗规则，最后才动手清洗。
- **反例**：上来就 `dropna()` 一把梭，或把 `"Null"`/`"N/A"` 字符串当成普通类别。
- **在本任务里怎么用**：用本文 §3 的步骤清洗 `promo_data_raw.csv`，并用 §4 的模板写出 `data_cleaning_rules.md`。

## 1. 常见数据问题类型

### 缺失值 (Missing Values)

- 表现：单元格为空白、`NULL`、`NA`、`NaN`、`-` 等。
- 检查：`df.isnull().sum()` 查看每列缺失数量。
- 处理：
  - 删除：`df.dropna()` 删除含缺失值的行（谨慎，可能丢失信息）。
  - 填充：`df.fillna(value)`。例如用中位数/均值填充数值列，用"未知"填充类别列。

### 异常值 (Outliers)

- 表现：明显偏离数据正常范围的极值（如年龄=200）。
- 检查：
  - 描述性统计：`df.describe()` 看最大最小值。
  - 可视化：箱线图 (Boxplot)。
- 处理：需结合业务判断。可以删除、替换为边界值（如用 99 分位数替换），或保留并注释。

### 不一致格式 (Inconsistent Format)

- 表现：日期列混用 `2026/04/20` 和 `20-Apr-2026`；字符串列包含多余空格。
- 检查：`df['column'].unique()` 查看唯一值。
- 处理：`df['name'].str.strip()` 去空格，`pd.to_datetime` 统一日期。

### 重复数据 (Duplicates)

- 检查：`df.duplicated().sum()`
- 处理：`df.drop_duplicates()`

## 2. 任务"数据侦探"中的问题清单

`promo_data_raw.csv` 包含以下典型问题：

- **编码/格式问题**：`Null`（字符串）出现在数值列，应转为真正的 `NaN`。
- **缺失值**：`registrations` 列同时存在 `N/A`（字符串）和 `Null`。
- **逻辑异常**：`impressions` 为 `Null` 但 `clicks` 为 500，这在业务上不可能。
- **多余空格**：检查列名是否有空格。

## 3. 清洗步骤示例 (Pandas)

```python
import pandas as pd

df = pd.read_csv('promo_data_raw.csv')

# 1. 统一缺失值表示
df.replace(['Null', 'N/A', ''], pd.NA, inplace=True)

# 2. 转换列类型
df['impressions'] = pd.to_numeric(df['impressions'], errors='coerce')
df['registrations'] = pd.to_numeric(df['registrations'], errors='coerce')

# 3. 逻辑清洗：impressions 为空时，clicks 也应视为无效
df.loc[df['impressions'].isna(), 'clicks'] = pd.NA

# 4. 计算转化率（清洗后）
df['conversion_rate'] = (df['registrations'] / df['clicks'] * 100).round(2)
```

## 4. data_cleaning_rules.md 推荐结构

- 原始字段说明：每列代表什么业务含义。
- 问题清单：缺失、异常、重复、格式不一致分别在哪里出现。
- 清洗规则：每个问题如何处理，为什么这样处理。
- 验证方法：清洗后如何确认数据可用。
- 指标计算：注册转化率等核心指标的计算公式。

## 5. 常见误区

- 不要直接删除所有缺失行。删除可能让样本偏差变大，尤其是活动数据本来就少时。
- 不要把字符串 `"Null"`、`"N/A"` 当成普通类别，它们通常代表缺失值，应统一转成真正的空值。
- 不要只清洗数据，不解释规则。分析师交付的是**可复现的清洗逻辑**，不是一份干净 CSV。

## RAG 检索关键词

数据清洗, 缺失值, Null, N/A, 异常值, 重复数据, 格式不一致, promo_data_raw.csv, promo_data_clean.csv, data_cleaning_rules.md, 注册转化率, skill_data_cleaning, skill_data_quality, mission_1_detective

