# CareerCraft 技能树定义 v1.0

本文档定义了游戏中所有技能节点的核心数据，用于驱动技能树的存储、点亮逻辑以及前端渲染。

数据结构规范

# 每个技能节点 (SkillNode) 应包含以下属性：
| 字段名 | 数据类型 | 必填 | 说明 | 示例 |
| :--- | :--- | :--- | :--- | :--- |
| skill_id | String | 是 | 全局唯一的英文标识符，用于程序逻辑。 | skill_debugging |
| skill_name | String | 是 | 技能的中文显示名称。 | 代码调试 |
| description | String | 是 | 技能的详细描述。 | 能够定位、复现和修复代码中的逻辑错误。 |
| category | String | 是 | 技能分类，用于前端分组。取值：core_software (软件核心), core_data (数据核心), generic (通用)。 | core_software |
| icon | String | 否 | 图标的名称或资源标识，用于前端渲染。 | bug.svg |
| parent_skill_id | String | 否 | 前置技能节点的 skill_id。如果为空，则表示是职业的“入口技能”或独立技能。 | skill_unit_testing |
| experience_to_next_level | Integer | 是 | 从0级升至1级（即“点亮”此技能）所需的经验值。 | 20 |
技能列表
# 1. 职业专属技能 - 软件工程师
| skill_id | skill_name | description | category | icon | parent_skill_id | exp_to_next |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| skill_debugging | 代码调试 | 能够定位、复现和修复代码中的逻辑错误。 | core_software | bug.svg |  | 20 |
| skill_unit_testing | 单元测试 | 能够为功能模块编写有效的单元测试，用于验证和防护。 | core_software | test-tube.svg |  | 20 |
| skill_code_quality | 代码质量 | 编写符合基础规范、可读性高、无安全隐患的代码。 | core_software | code-bracket.svg |  | 15 |
| skill_api_design | API设计 | 能够将模糊的业务需求转化为清晰、规范的API接口定义。 | core_software | api.svg |  | 25 |
| skill_communication | 技术沟通 | 能与非技术角色（如产品经理）有效沟通，澄清需求。 | core_software | chat-bubble.svg |  | 10 |
| skill_refactoring | 代码重构 | 优化现有代码结构，提升可读性、可维护性和可扩展性。 | core_software | puzzle-piece.svg | skill_code_quality | 30 |
| skill_software_design | 软件设计 | 针对新需求，设计合理的模块、类结构和扩展方案。 | core_software | light-bulb.svg | skill_refactoring | 40 |
| skill_perf_troubleshooting | 性能调优 | 定位并解决系统性能瓶颈（如慢查询、N+1问题）。 | core_software | gauge.svg |  | 35 |
| skill_sql_optimization | SQL优化 | 编写高效的SQL语句，并通过索引等手段优化查询性能。 | core_software | database.svg | skill_perf_troubleshooting | 25 |
| skill_incident_response | 事故响应 | 遵循流程处理线上事故，完成根因分析并输出改进报告。 | core_software | fire.svg | skill_perf_troubleshooting | 30 |
# 2. 职业专属技能 - 数据分析师
| skill_id | skill_name | description | category | icon | parent_skill_id | exp_to_next |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| skill_data_cleaning | 数据清洗 | 识别并处理数据中的缺失、异常、重复、格式错误。 | core_data | filter.svg |  | 20 |
| skill_data_quality | 数据质量评估 | 系统性评估数据的准确性、完整性、一致性，并制定清洗规则。 | core_data | check-circle.svg |  | 15 |
| skill_exploratory_analysis | 探索性数据分析 | 对数据进行初步的探查，以了解其分布、关系和潜在模式。 | core_data | magnifying-glass.svg |  | 20 |
| skill_business_insight | 业务洞察 | 从数据中提炼出对商业决策有直接价值的观点和发现。 | core_data | chart-bar.svg |  | 25 |
| skill_data_storytelling | 数据叙事 | 将分析过程和结论组织成结构清晰、论据充分的报告。 | core_data | book-open.svg |  | 20 |
| skill_strategic_recommendation | 策略建议 | 基于分析结论，提出具体、可衡量、可执行的业务建议。 | core_data | flag.svg | skill_business_insight | 30 |
| skill_stakeholder_mgmt | 利益相关者管理 | 理解并平衡不同业务角色（销售、市场、产品）的数据需求。 | core_data | user-group.svg |  | 15 |
| skill_kpi_system_design | 指标体系设计 | 设计能全面衡量业务健康状况的核心指标(KPI)看板。 | core_data | presentation-chart-bar.svg | skill_data_storytelling | 35 |
| skill_dashboard_design | 看板设计 | 将指标体系转化为直观、易用的数据可视化仪表板。 | core_data | tv.svg | skill_kpi_system_design | 30 |
| skill_drill_down_analysis | 下钻分析 | 对宏观问题（如指标下跌）进行多维细分，定位具体问题点。 | core_data | arrow-trending-down.svg |  | 25 |
| skill_root_cause_analysis | 根因分析 | 基于下钻结果，提出有数据支撑的、合理的归因假设。 | core_data | beaker.svg | skill_drill_down_analysis | 30 |
| skill_ab_test_design | AB测试设计 | 设计实验来验证策略的有效性，包括确定指标、样本量计算。 | core_data | adjustments-horizontal.svg | skill_root_cause_analysis | 40 |
| skill_strategy_proposal | 策略提案 | 撰写包含问题、分析、方案、评估的完整策略建议报告。 | core_data | document-text.svg | skill_strategic_recommendation | 35 |
# 3. 职业通用技能 (软技能)
| skill_id | skill_name | description | category | icon | parent_skill_id | exp_to_next |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| skill_logical_rigor | 逻辑严谨性 | 在分析和报告中体现严密的逻辑链条。 | generic | brain.svg |  | 10 |
| skill_critical_thinking | 批判性思维 | 能对数据和既有结论提出合理的质疑和验证。 | generic | eye.svg |  | 10 |
| skill_time_management | 时间管理 | 在模拟的"任务周期"内，合理规划并完成交付。 | generic | clock.svg |  | 10 |
| skill_cross_role_comm | 跨角色沟通 | 与AI扮演的不同角色沟通时，表达清晰、换位思考。 | generic | chat-bubble-left-right.svg |  | 10 |