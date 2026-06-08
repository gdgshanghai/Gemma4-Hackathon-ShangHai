# CareerCraft 知识库索引

本目录用于 RAG 向量库和关键词检索入库。

## 1. 知识库分区

### software_engineer

软件工程师职业技能知识，按任务分区。

适合回答调试、单元测试、需求澄清、RESTful API、HTTP 状态码、幂等与鉴权、代码重构、软件设计、N+1 查询、SQL 索引优化、EXPLAIN 解读与事故复盘等问题。

### data_analyst

数据分析师职业技能知识，按任务分区。

适合回答数据清洗、Pandas 操作、业务指标计算、数据叙事、KPI 体系、看板设计、利益相关者访谈、下钻分析、AB 测试、RFM 用户分层等问题。

## 2. 推荐入库策略

使用 Markdown 标题语义切片。

推荐 chunk 大小：

- 目标：300 到 700 tokens。
- 最大：900 tokens。
- 重叠：50 到 100 tokens。

切片时应保留 front matter 字段（`career`、`mission_id`、`skills`、`doc_type`、`related_files`）作为 chunk metadata。`## TL;DR` 段应作为独立高优先级 chunk 入库。

## 3. 推荐检索策略

使用 hybrid search：

- 向量相似度检索用于语义问题。
- BM25 或关键词检索用于术语、接口路径、技能 ID、函数名、状态码等精确查询。

任务页面内检索时，应优先匹配当前 `career`、`mission_id` 和 `skills`。

## 4. 文件统一模板（贡献者必读）

所有 `.md` 文件必须遵循以下结构。违反本规范的文件不进入切片流水线。

### 4.1 文件骨架

````markdown
---
career: data_analyst              # data_analyst | software_engineer
mission_id: mission_1_detective   # 任务文件夹名
skills:                           # 来自 docs/skill_tree_definition.md 的 skill_id 列表
  - skill_data_cleaning
  - skill_data_quality
doc_type: cookbook                # concept | cookbook | checklist | template
related_files:                    # 任务中出现的 Mock 数据 / 交付物文件名
  - promo_data_raw.csv
  - data_cleaning_rules.md
updated: 2026-05-20
---

# 一级标题（文件主题）

## TL;DR

- **核心规则**：一句话讲清楚最重要的方法或结论。
- **反例**：一句话讲清楚最常见的错误做法。
- **在本任务里怎么用**：一句话指向任务交付物中的具体环节。

## 章节一（H2）

…

### 子节（H3，可选）

…

## 常见误区

…

## RAG 检索关键词

关键词1, 关键词2, skill_xxx, mission_id, 交付物名
````

### 4.2 字段含义

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `career` | 是 | 取值 `data_analyst` 或 `software_engineer` |
| `mission_id` | 是 | 与所在文件夹名一致，例如 `mission_2_alchemist` |
| `skills` | 是 | 至少 1 个，取值必须为 `docs/skill_tree_definition.md` 中已定义的 `skill_id` |
| `doc_type` | 是 | `concept`（概念解释）/ `cookbook`（操作手册）/ `checklist`（清单）/ `template`（模板） |
| `related_files` | 否 | 任务剧本中提及的 Mock 数据或交付物文件名，便于按文件名精确检索 |
| `updated` | 是 | ISO 日期 `YYYY-MM-DD` |

### 4.3 写作约定

- **代码块必须围栏化**并带语言标签：```` ```python ````、```` ```java ````、```` ```sql ````、```` ```yaml ````、```` ```bash ````。禁止用缩进伪装代码。
- **标题层级**：文件首行 `# H1`（唯一），章节一律 `## H2`，子节 `### H3`，禁止跨级跳跃，禁止文件中出现第二个 `# H1`。
- **TL;DR 三段式**：核心规则 / 反例 / 在本任务里怎么用。每段一句话，便于切片器把 TL;DR 独立作为高优先级 chunk。
- **专有名词对齐**：Mock 数据文件名、字段名、类名必须与 `docs/career_data_analyst.md` 或 `docs/career_software_engineer.md` 中的剧本一致。
- **检索关键词**：在文末 `## RAG 检索关键词` 段，列出中英术语、关联 `skill_id`、`mission_id` 和 `related_files` 中的文件名。

### 4.4 提交前自查清单

- [ ] front matter 可被 YAML 解析，必填字段非空
- [ ] `skills` 字段每项都能在 `docs/skill_tree_definition.md` 中查到
- [ ] 文件首行是 `# H1`，全文只有 1 个 H1
- [ ] 所有代码块带语言标签
- [ ] 有 `## TL;DR`（三段式）
- [ ] 有 `## 常见误区`
- [ ] 有 `## RAG 检索关键词`

## 5. 下一阶段（切片入库）输入契约

切片器可以信赖以下不变量：

1. 每个 `.md` 文件顶部都有合法 YAML front matter，字段集如 §4.2。
2. 文件按 `## H2` 切分，每个 H2 段自包含、可独立检索。
3. `## TL;DR` 段无论长度，都作为独立 chunk 入库，并赋予高检索权重。
4. 代码块统一围栏化、带语言标签，可被代码搜索器（如 BM25 + 语言过滤）正确识别。
5. front matter 中的 `career`、`mission_id`、`skills`、`related_files` 必须作为 chunk metadata 一同入库，供运行时按当前任务过滤召回。

## 6. 文件清单

下表列出当前知识库全部文件。新增或重命名文件后，应同步更新此表。

### software_engineer

| 路径 | mission | skills | doc_type |
| --- | --- | --- | --- |
| `software_engineer/mission_1_bug_hunter/debugging-basics-strategy.md` | mission_1_bug_hunter | skill_debugging, skill_unit_testing | concept |
| `software_engineer/mission_1_bug_hunter/unit-testing-junit-crash-course.md` | mission_1_bug_hunter | skill_unit_testing, skill_code_quality | cookbook |
| `software_engineer/mission_2_alchemist/requirement-clarification-framework.md` | mission_2_alchemist | skill_communication, skill_api_design | cookbook |
| `software_engineer/mission_2_alchemist/api-design-restful-basics.md` | mission_2_alchemist | skill_api_design, skill_communication | concept |
| `software_engineer/mission_2_alchemist/http-status-codes-meanings.md` | mission_2_alchemist | skill_api_design | concept |
| `software_engineer/mission_2_alchemist/api-idempotency-and-auth-basics.md` | mission_2_alchemist | skill_api_design | concept |
| `software_engineer/mission_3_guardian/code-refactoring-smells-and-solutions.md` | mission_3_guardian | skill_refactoring, skill_code_quality | cookbook |
| `software_engineer/mission_3_guardian/software-design-extension-with-polymorphism.md` | mission_3_guardian | skill_software_design, skill_refactoring | concept |
| `software_engineer/mission_4_firefighter/n-plus-one-query-problem.md` | mission_4_firefighter | skill_perf_troubleshooting, skill_incident_response | concept |
| `software_engineer/mission_4_firefighter/sql-index-optimization-guide.md` | mission_4_firefighter | skill_sql_optimization, skill_perf_troubleshooting | cookbook |
| `software_engineer/mission_4_firefighter/explain-and-slow-query-reading.md` | mission_4_firefighter | skill_incident_response, skill_perf_troubleshooting | cookbook |

### data_analyst

| 路径 | mission | skills | doc_type |
| --- | --- | --- | --- |
| `data_analyst/mission_1_detective/data-cleaning-common-issues.md` | mission_1_detective | skill_data_cleaning, skill_data_quality | concept |
| `data_analyst/mission_1_detective/pandas-basic-operations-cookbook.md` | mission_1_detective | skill_data_cleaning, skill_data_quality, skill_exploratory_analysis | cookbook |
| `data_analyst/mission_2_alchemist/business-metrics-calculations.md` | mission_2_alchemist | skill_business_insight, skill_exploratory_analysis | cookbook |
| `data_analyst/mission_2_alchemist/data-storytelling-framework.md` | mission_2_alchemist | skill_data_storytelling, skill_strategic_recommendation | template |
| `data_analyst/mission_3_designer/stakeholder-interview-framework.md` | mission_3_designer | skill_stakeholder_mgmt, skill_kpi_system_design | template |
| `data_analyst/mission_3_designer/kpi-system-design-principles.md` | mission_3_designer | skill_kpi_system_design, skill_stakeholder_mgmt | concept |
| `data_analyst/mission_3_designer/data-visualization-best-practices.md` | mission_3_designer | skill_dashboard_design, skill_data_storytelling | cookbook |
| `data_analyst/mission_4_advisor/drill-down-analysis-techniques.md` | mission_4_advisor | skill_drill_down_analysis, skill_root_cause_analysis | cookbook |
| `data_analyst/mission_4_advisor/ab-test-design-fundamentals.md` | mission_4_advisor | skill_ab_test_design, skill_strategy_proposal | concept |
| `data_analyst/mission_4_advisor/user-segmentation-rfm-basics.md` | mission_4_advisor | skill_drill_down_analysis, skill_business_insight | concept |

