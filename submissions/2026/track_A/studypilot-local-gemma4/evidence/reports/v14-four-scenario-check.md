# V14 四场景功能检查

- 执行时间：2026-07-12 20:06:47 +08:00
- 代码提交：`bd59a7db72daa0c0a6e4602501703f2242e13b72`
- 本地模型：`gemma-4-26b-a4b-it`，`Q4_K_M`
- 运行入口：`scripts/run_v14_demo_checks.ps1`

| 检查 | 结果 |
| --- | --- |
| LM Studio loaded / tool-use / 两轮 Native FC 预检 | PASS |
| 正常多学科盘点，真实 Gemma 4 | PASS，1 test |
| 增量补充不丢任务 | PASS，1 test |
| 数学加练超载由孩子取舍 | PASS，1 test |
| 第一晚偏差改变第二晚估时 | PASS，1 test |

最终结果：`4/4` 合成功能场景通过。真实 Gemma 场景耗时约 8 秒；其余三条
使用确定性 API / SQLite 测试，避免重复模型生成干扰业务事实。

本页只说明这四条指定场景在本次代码与本机模型下通过。它不是 benchmark、
真实儿童试用结果、成绩改善证据或普适成功率。
