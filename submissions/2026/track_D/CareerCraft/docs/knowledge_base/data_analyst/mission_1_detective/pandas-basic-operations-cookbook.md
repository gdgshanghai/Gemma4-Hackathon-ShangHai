---
career: data_analyst
mission_id: mission_1_detective
skills:
  - skill_data_cleaning
  - skill_data_quality
  - skill_exploratory_analysis
doc_type: cookbook
related_files:
  - promo_data_raw.csv
  - promo_data_clean.csv
updated: 2026-05-20
---

# Pandas 基础操作速查手册

## TL;DR

- **核心规则**：先 `read_csv` → `info()` / `describe()` 快速摸底，再按"统一缺失值 → 转类型 → 业务清洗 → 计算指标 → 保存"五步走。
- **反例**：跳过 `info()` 直接清洗，事后才发现 `clicks` 还是字符串列，分母全错。
- **在本任务里怎么用**：用 §8 的标准流程清洗 `promo_data_raw.csv`，生成 `promo_data_clean.csv` 并算出整体注册转化率。

## 1. 数据读取与查看

```python
import pandas as pd

# 读取 CSV
df = pd.read_csv('promo_data_raw.csv')

# 查看前 5 行
df.head()

# 查看基本信息：列名、非空数量、类型
df.info()

# 描述性统计：计数、均值、标准差、分位数
df.describe()
```

## 2. 处理缺失值

```python
# 检查每列缺失值数量
df.isnull().sum()

# 删除任何包含缺失值的行
df_cleaned = df.dropna()

# 用特定值填充缺失值
df_filled = df.fillna(0)

# 用前一行的值填充
df_filled = df.fillna(method='ffill')

# 用列的平均值填充
df['impressions'].fillna(df['impressions'].mean(), inplace=True)
```

## 3. 数据类型转换

```python
# 将列转换为数值类型，无法转换的设为 NaN
df['clicks'] = pd.to_numeric(df['clicks'], errors='coerce')

# 转换为字符串
df['campaign'] = df['campaign'].astype(str)
```

## 4. 字符串清洗

```python
# 去除字符串两端的空格
df['campaign'] = df['campaign'].str.strip()

# 将所有字符转为小写
df['campaign'] = df['campaign'].str.lower()

# 替换字符串
df['campaign'] = df['campaign'].str.replace('Spring Sale', 'Spring_Promo')
```

## 5. 计算新列

```python
# 计算点击率 (CTR)
df['ctr'] = (df['clicks'] / df['impressions'] * 100).round(2)

# 计算注册转化率
df['conversion_rate'] = (df['registrations'] / df['clicks'] * 100).round(2)
```

## 6. 筛选与排序

```python
# 筛选 impressions > 10000 的行
df_large = df[df['impressions'] > 10000]

# 多条件筛选
df_filtered = df[(df['campaign'] == 'Spring Sale') & (df['clicks'] > 500)]

# 按某列降序排序
df_sorted = df.sort_values('clicks', ascending=False)
```

## 7. 保存数据

```python
# 保存为 CSV，不保存索引
df_cleaned.to_csv('promo_data_clean.csv', index=False)
```

## 8. 数据侦探任务常用流程

处理 `promo_data_raw.csv` 时，建议按以下顺序：

1. `read_csv` 读取数据。
2. `replace` 统一缺失值标记（`Null`、`N/A`、`""` → `pd.NA`）。
3. `to_numeric` 转换数值列。
4. `isna().sum()` 检查缺失情况。
5. 用业务规则处理不可能的数据（如 `impressions` 为空时 `clicks` 也置空）。
6. 计算注册转化率。
7. `to_csv` 输出清洗结果。

## 9. 验证清洗结果

清洗完成后至少检查：

- 数值列是否真的变成数值类型（`df.dtypes`）。
- 点击量、注册数是否大于曝光量（业务上不合理）。
- 核心指标是否没有除零或空值异常。
- 输出文件是否不包含多余索引列。

## 常见误区

- 不要在没看 `info()` 的情况下直接 `dropna()`，可能误删大部分行。
- 不要用全局均值填充数值列，更稳健的是按分组（如城市、品类）的中位数填充。
- 不要忘记 `to_csv` 的 `index=False`，否则下一次读入会多一列。

## RAG 检索关键词

Pandas, read_csv, replace, to_numeric, isna, dropna, fillna, drop_duplicates, to_csv, 数据清洗, promo_data_raw.csv, promo_data_clean.csv, 注册转化率, skill_data_cleaning, skill_data_quality, skill_exploratory_analysis, mission_1_detective

