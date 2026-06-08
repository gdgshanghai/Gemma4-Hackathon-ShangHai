# 目录结构

| 目录 | 作用 | 进 git |
|------|------|:------:|
| `backend/`     | Python 后端：音频采集、Cactus ASR、take 边界检测、Gemma agent、SQLite 访问 | 是 |
| `frontend/`    | 前端（形式 TBD，大概率浏览器页面）：实时转录显示、场记单 UI | 是 |
| `scripts/`     | 可复用的工具脚本：下载模型、数据预处理、手动跑某个模块 | 是 |
| `experiments/` | 一次性调研实验（如框架 benchmark），每个实验一个 `YYYY-MM-DD-名字/` 子目录，含 README 记结论 | 是（产物除外） |
| `docs/`        | 接口契约、技术报告草稿、本文档 | 是 |
| `data/`        | 录音样本、SQLite 运行库 | 否 |
| `models/`      | Gemma / Cactus 权重 + 下载脚本 | 仅脚本与说明 |

## 约定

- 代码按用途归位：生产代码（会被后端 import）放 `backend/`；可复用工具放 `scripts/`；一次性调研放 `experiments/`；纯试错走 `spike/` 分支不合并。
- 数据库 schema、迁移脚本是源码，放 `backend/` 进 git；`*.db` 运行库不进。
- 模型权重不进 git，靠 `models/` 下的下载脚本获取，脚本里钉死版本。
- 测试夹具放 `backend/tests/fixtures/`，进 git（与 `data/` 下的真实录音区分）。
- 实验代码与小结果进 git；大音频/输出放 `data/` 或实验目录下的 `artifacts/`（均被忽略）。结论必须留痕到实验 README。
- 密钥写进 `.env`，仓库只留 `.env.example`。
