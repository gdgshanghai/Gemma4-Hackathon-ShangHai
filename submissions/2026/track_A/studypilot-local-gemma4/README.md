# 决赛更新资料包

项目：StudyPilot / 时间规划小助手

本目录是 2026 决赛更新资料包，包含两部分：

- `V11 产品闭环讲清版 PPT`：现场叙事和技术架构说明。
- `V14 真实 Demo 程序内核`：可以在本机运行的完整孩子端、家长端和本地 Gemma 4 链路。

PPT、视频和程序内核来自同一份决赛 Demo 交付清单。程序不使用云模型、远程数据库或运行时 Mock 兜底。

## 现场启动

先在 LM Studio 中手动启动本地服务器，并加载精确模型：

```text
gemma-4-26b-a4b-it
```

启动器只检查 `http://127.0.0.1:1234/api/v0/models`，要求模型处于 `loaded` 状态且能力包含 `tool_use`。它不会启动、停止或修改 LM Studio。

在本资料包根目录运行：

```text
安装决赛Demo依赖.bat
决赛现场预检.bat
启动决赛Demo.bat
```

服务地址：

- API：`http://127.0.0.1:8040`
- 孩子端：`http://127.0.0.1:8041`
- 家长端：`http://127.0.0.1:8042`

需要停止时运行 `停止决赛Demo.bat`。它只停止 StudyPilot 自己记录并验证过的三个服务，不触碰 LM Studio。

## 一键导入

一键导入是现场辅助入口，不是自动决策：

- 孩子端可以载入演示情景和预设作业。
- 家长端可以载入示例作业单和示例观察。
- 点击后仍可人工修改，确认提交后才会写入 Demo 数据库。
- 启动服务不会自动重置已有状态。

对应接口和测试位于：

- `backend/api/routes/demo.py`
- `kid-frontend/src/views/IntakeView.tsx`
- `parent-frontend/src/views/BriefView.tsx`
- `parent-frontend/src/views/CalibrationView.tsx`
- `tests/integration/api/test_demo.py`
- `kid-frontend/src/views/DemoPreset.test.tsx`
- `parent-frontend/src/views/DemoPresets.test.tsx`

## 内核如何工作

1. Gemma 4 将孩子和家长的自然语言转换为严格的候选事实，例如作业标题、完成量、明确分钟和观察样本。
2. Harness 只向模型暴露当前阶段允许的一个工具，校验 Native Function Calling、Schema、调用轮数、重复调用和幂等键，并记录 trace。
3. Python 规则、估时、截止保护、容量恢复和规划器编译最终路线；模型不负责最终排序或日期计算。
4. 状态机和 SQLite 保存版本、确认、未完成任务、家庭校准和跨夜记忆。
5. 孩子端负责盘点、确认、路线调整和复盘；家长端负责学校作业单、家庭校准和晚间结果。

详细代码映射见 `TECHNICAL_REPORT_FINAL_UPDATE.md`。

## 依赖

- Windows PowerShell
- Python 3.13 或更高版本
- Node.js/npm
- 本地 LM Studio 和已加载的 Gemma 4 模型

运行时依赖见 `requirements.txt`，开发测试依赖见 `requirements-dev.txt`。数据库由首次启动时的迁移自动创建，资料包不携带任何本地数据库、日志或模型权重。

## 材料与证据

- `materials/`：V11 正式 PPT、V7 冻结视频、V11 QA/hash 记录。
- `evidence/`：Native Function Calling 预检、失败边界、四场景、家长校准、跨夜生命周期、截止/容量恢复和双端验证。
- `package-allowlist.json`：公开文件的显式来源和目标清单。
- `final-package-manifest.json` 与 `SHA256SUMS.txt`：构建后逐文件校验。

证据描述的是技术行为和合成演示场景，不宣称真实家庭效果。V11 QA 记录如实保留现场彩排记录状态，不用讲稿字数替代真人计时。
