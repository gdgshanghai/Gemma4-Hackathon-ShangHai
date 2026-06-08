# XR Gemma 4 Bioinformatics Agent

## 中文说明

### 项目定位
XR Lite Version for GDG Gemma 4 Hackathon 2026 是为赛道 A 准备的公开评审项目。它展示 Gemma 4 如何在本地或私有 OpenAI-compatible endpoint 中，把自然语言生物医学分析需求转化为可审计的公开工作流：模型在受控 planner loop 中逐轮选择下一步公开工具，查看公开生信工具、选择 workflow、查看公开 workflow contract 与 toy data、起草具体工具级计划，API 再基于公开 synthetic sample data 和固定 Docker 工具链执行分析，并由 Gemma 4 对结果进行简要解释。

本仓库提供评审所需的源码、样例数据、文档和启动脚本。评审范围限于本仓库提交内容；商业版 XR 平台的生产系统、真实客户数据、私有镜像和生产凭据不属于本次提交范围。

### 提交材料清单
- 核心代码：`packages/llm-engine`、`packages/api`、`packages/web`
- 技术报告：`docs/TECHNICAL_REPORT.md`，中英双语
- Docker 部署指南：`docs/DOCKER_DEPLOYMENT.md`，中英双语
- 5 分钟演示视频：`xr_gdg_gemma4_2026.mov`
- 边界说明：`REVIEW_BOUNDARY.md`
- 一键启动脚本：`scripts/start-dev.sh`
- 提交包生成与检查：`scripts/package-submission.sh`、`scripts/check-review-package.sh`

### 提交要求覆盖
| 提交要求 | 覆盖情况 |
| --- | --- |
| 核心代码 | 已包含 Web、API、LLM engine、Agent runtime、public tool manifest 和 Docker pipeline。 |
| 5 分钟以内演示视频 | `xr_gdg_gemma4_2026.mov` |
| 技术报告 | `docs/TECHNICAL_REPORT.md` 已提供中英双语版本。 |
| README 一键启动或 Docker 指南 | README 包含快速启动；`docs/DOCKER_DEPLOYMENT.md` 提供详细 Docker 部署指南。 |
| Agent Memory 与 Tool Calling 展示 | Web UI 的 Agent state、`agent-memory.json`、`tool-calls.json` 和 `agent-trace.json` 均可展示。 |
| 评审维度：Innovation / Technical Execution / Real-World Impact / Presentation | 生物医学本地 Agent 场景体现创新与现实价值；`pnpm check`、Docker 执行和 artifacts 体现技术完成度；README、技术报告、演示脚本支持清晰展示。 |

### 赛道 A 技术对齐
| 要求 | 实现位置 |
| --- | --- |
| Gemma 4 调用逻辑 | `packages/llm-engine/app/main.py` 通过 OpenAI-compatible `/v1/chat/completions` 调用本地 Gemma 4 endpoint。 |
| Native Function Calling | LLM engine 透传 `tools`、`tool_choice`、`reasoning_effort`；`packages/api/src/reviewAgentRuntime.ts` 记录模型 tool calls。 |
| 多步规划 | Gemma 4 在受控 planner loop 中从 API 暴露的 allowed next tools 中选择下一步，调用 `inspect_available_bio_tools` / `inspect_available_workflows`、`select_workflow`、`inspect_workflow_contract`、`inspect_sample_data`、`draft_tool_level_plan`，为三条公开 workflow 生成具体生信工具级计划；API 校验后执行固定公开 pipeline。 |
| Agent Memory | `ReviewAgentMemory` 记录 prompt、模型名、workflow、comparison、安全规则、observed files 和 tool call IDs；任务结束写入 `.review-data/jobs/<jobId>/agent-memory.json`。 |
| Tool Calling | 公开工具 schema 位于 `packages/api/src/publicToolManifest.ts`；UI 和 `tool-calls.json` 展示 tool name、origin、arguments、status、result summary。 |
| 可审计执行 | 任务时间线、Docker tool runs、结果表和 report 都在 Web UI 与 `.review-data/jobs/<jobId>/` 中保留。 |
| 本地/端侧友好 | 默认使用 Ollama OpenAI-compatible endpoint；所有样例数据均包含在仓库内，计算由本地 Docker 执行。 |

### 已包含内容
- React/Vite Web UI：对话入口、Agent state、执行计划、进度和结果展示。
- Express API：provider 配置、conversation routing、review agent planning、任务执行和 artifact 输出。
- Python LLM adapter：OpenAI-compatible Gemma 4 chat 和 tool calling 适配。
- 三个公开 synthetic sample workflows：bulk RNA-seq、single-cell RNA-seq、label-free proteomics。
- 公开 Docker 工具链：FastQC、Trimmomatic、fastp、kallisto、MultiQC、Scanpy、limma、OpenMS、MSstats，以及一个本地 PyDESeq2 wrapper image。

### 不包含内容
- 商业版 XR 平台的生产调度、权限、缓存、数据库或部署系统。
- 私有数据、客户数据、私有容器镜像、生产凭据或真实 API key。
- 本地开发辅助文档 `.agentdocs`；提交包生成脚本会排除该目录。

### 环境要求
- macOS 或 Linux
- Node.js 20+ 与 pnpm 8.15+
- Python 3.10+
- Docker Desktop 或 Docker Engine
- 本地或私有 Gemma 4 OpenAI-compatible endpoint。默认示例使用 Ollama：`http://127.0.0.1:11434/v1`

### 快速启动
详细 Docker 依赖、镜像准备、服务验证和故障排查见 `docs/DOCKER_DEPLOYMENT.md`。

```bash
pnpm install
python3 -m venv packages/llm-engine/.venv
packages/llm-engine/.venv/bin/pip install -r packages/llm-engine/requirements.txt
cp .env.example .env
bash scripts/start-dev.sh
```

`scripts/start-dev.sh` 会先构建 API 和 Web UI，自动拉取/构建 Docker 工具镜像，然后在后台启动 LLM engine、API server 和 Web preview 服务。

打开：
```text
http://127.0.0.1:5178
```

停止服务：
```bash
bash scripts/stop-dev.sh
```

日志位置：
```text
.review-data/logs/web.log
.review-data/logs/api.log
.review-data/logs/llm-engine.log
.review-data/logs/prepare-tool-images.log
```

截图建议见 `docs/SCREENSHOTS.md`。运行日志可直接打开上述 `.log` 文件或用 `tail -f` 截图；Agent artifacts 截图位于 `.review-data/jobs/<jobId>/agent-memory.json`、`tool-calls.json` 和 `agent-trace.json`。

### 模型配置
`.env.example` 默认使用 Ollama 的 OpenAI-compatible endpoint：

```bash
GEMMA_BASE_URL=http://127.0.0.1:11434/v1
GEMMA_API_KEY=local-placeholder-token
GEMMA_MODEL=gemma4:latest
```

项目不绑定某个具体 Gemma 4 量化版本，只要求 endpoint 支持 OpenAI-compatible chat completion，最好支持 `tools`。在本提交的验证环境中，Ollama 的 `gemma4:latest` 映射到 `gemma4:e4b-it-q4_K_M` build，Ollama 报告为 Gemma 4 family、8.0B parameters、`Q4_K_M` quantization。若评审环境的 Gemma 4 tag 不同，可在 `.env` 中修改 `GEMMA_MODEL`。

### Demo Prompt
```text
Run a bulk RNA-seq treatment vs control analysis with QC, counting, differential summary, and report.
```

UI 中还提供 single-cell RNA-seq 和 label-free proteomics 预设。所有 workflow 都使用仓库内公开 synthetic sample data。

### 运行后可检查的 artifacts
```text
.review-data/jobs/<jobId>/agent-memory.json
.review-data/jobs/<jobId>/tool-calls.json
.review-data/jobs/<jobId>/agent-trace.json
.review-data/jobs/<jobId>/report.md
```

### 验证与提交包检查
```bash
pnpm check
```

该命令会：
1. 构建 API 与 Web。
2. 运行 API 测试。
3. 生成干净提交包到 `.review-data/submission/XR-Gemma4-Agent`。
4. 在提交包中运行边界扫描，确认不包含 `.agentdocs`、`.env`、私有路径、私有镜像、客户数据或生产凭据。

如需手动生成提交包：
```bash
bash scripts/package-submission.sh
cd .review-data/submission/XR-Gemma4-Agent
bash scripts/check-review-package.sh
```

### 服务端口
| 服务 | 默认地址 | 用途 |
| --- | --- | --- |
| Web UI | `http://127.0.0.1:5178` | 评审界面 |
| API | `http://127.0.0.1:3101` | Provider 配置、任务、Agent artifacts |
| LLM engine | `http://127.0.0.1:8011` | OpenAI-compatible Gemma 4 adapter |

### 许可与边界
本公开评审项目使用 GNU General Public License version 3 only（GPL-3.0-only）。完整许可证文本见 `LICENSE`。许可证覆盖本仓库内代码和 synthetic sample data；未包含在仓库中的生产服务、私有数据、私有镜像、凭据和未公开商业材料不属于授权范围。XR 名称、标识和品牌资产不授权作商标使用，除非是为合理说明本仓库来源所必需。

Copyright 2026 LIANG Weiyin @ XR.

---

## English

### Project Scope
XR Lite Version for GDG Gemma 4 Hackathon 2026 is a public review project prepared for Track A. It shows how Gemma 4 running behind a local or private OpenAI-compatible endpoint can turn a natural-language biomedical analysis request into an auditable public workflow: the model uses a controlled planner loop to choose the next public tool, inspect public bioinformatics tools, select a workflow, inspect the public workflow contract and toy data, and draft a concrete tool-level plan; the API validates that plan and executes public synthetic sample data with fixed Docker tools, then Gemma 4 summarizes the computed result.

This repository provides the source code, sample data, documentation, and startup scripts needed for review. The review scope is limited to the submitted repository contents; production XR systems, real customer data, private images, and production credentials are outside this submission.

### Submission Materials
- Core code: `packages/llm-engine`, `packages/api`, `packages/web`
- Technical report: `docs/TECHNICAL_REPORT.md`, bilingual
- Docker deployment guide: `docs/DOCKER_DEPLOYMENT.md`, bilingual
- Five-minute demo video: `xr_gdg_gemma4_2026.mov`
- Review boundary statement: `REVIEW_BOUNDARY.md`
- One-command startup script: `scripts/start-dev.sh`
- Submission packaging and boundary scan: `scripts/package-submission.sh`, `scripts/check-review-package.sh`

### Submission Requirement Coverage
| Requirement | Coverage |
| --- | --- |
| Core code | Includes Web, API, LLM engine, Agent runtime, public tool manifest, and Docker pipelines. |
| Demo video within five minutes | `xr_gdg_gemma4_2026.mov` |
| Technical report | `docs/TECHNICAL_REPORT.md` provides bilingual content. |
| README startup or Docker guide | README includes Quick Start; `docs/DOCKER_DEPLOYMENT.md` provides a detailed Docker deployment guide. |
| Agent Memory and Tool Calling visibility | The Web UI Agent state plus `agent-memory.json`, `tool-calls.json`, and `agent-trace.json` expose the logic. |
| Judging dimensions: Innovation / Technical Execution / Real-World Impact / Presentation | The local biomedical Agent use case supports innovation and impact; `pnpm check`, Docker execution, and artifacts support technical execution; README, technical report, and demo script support presentation. |

### Track A Alignment
| Requirement | Implementation |
| --- | --- |
| Gemma 4 integration | `packages/llm-engine/app/main.py` calls a local Gemma 4 endpoint through OpenAI-compatible `/v1/chat/completions`. |
| Native Function Calling | The LLM engine passes `tools`, `tool_choice`, and `reasoning_effort`; `packages/api/src/reviewAgentRuntime.ts` records model tool calls. |
| Multi-step planning | Gemma 4 runs inside a controlled planner loop: each round it chooses one allowed next public tool, including `inspect_available_bio_tools` / `inspect_available_workflows`, `select_workflow`, `inspect_workflow_contract`, `inspect_sample_data`, and `draft_tool_level_plan`; the API validates the plan before fixed public pipeline execution. |
| Agent Memory | `ReviewAgentMemory` records prompt, model, workflow, comparison, safety rules, observed files, and tool call IDs; it is written to `.review-data/jobs/<jobId>/agent-memory.json`. |
| Tool Calling | Public tool schemas live in `packages/api/src/publicToolManifest.ts`; the UI and `tool-calls.json` show tool name, origin, arguments, status, and result summary. |
| Auditable execution | Timeline events, Docker runs, result tables, and reports are visible in the Web UI and under `.review-data/jobs/<jobId>/`. |
| Local/private deployment | The default setup uses Ollama's OpenAI-compatible endpoint; sample data is included and computation runs locally through Docker. |

### Included
- React/Vite Web UI for conversation, Agent state, execution plan, progress, and results.
- Express API for provider configuration, conversation routing, review-agent planning, task execution, and artifact output.
- Python LLM adapter for OpenAI-compatible Gemma 4 chat and tool calling.
- Three public synthetic sample workflows: bulk RNA-seq, single-cell RNA-seq, and label-free proteomics.
- Public Docker toolchain: FastQC, Trimmomatic, fastp, kallisto, MultiQC, Scanpy, limma, OpenMS, MSstats, plus one local PyDESeq2 wrapper image.

### Not Included
- Production orchestration, permission, cache, database, or deployment systems from the commercial XR platform.
- Private data, customer data, private container images, production credentials, or real API keys.
- Local development assistant documentation under `.agentdocs`; the submission packaging script excludes that directory.

### Requirements
- macOS or Linux
- Node.js 20+ and pnpm 8.15+
- Python 3.10+
- Docker Desktop or Docker Engine
- A local or private Gemma 4 OpenAI-compatible endpoint. The default example uses Ollama at `http://127.0.0.1:11434/v1`.

### Quick Start
For Docker image preparation, service verification, and troubleshooting, see `docs/DOCKER_DEPLOYMENT.md`.

```bash
pnpm install
python3 -m venv packages/llm-engine/.venv
packages/llm-engine/.venv/bin/pip install -r packages/llm-engine/requirements.txt
cp .env.example .env
bash scripts/start-dev.sh
```

`scripts/start-dev.sh` first builds the API and Web UI, automatically pulls/builds Docker tool images, then starts the LLM engine, API server, and Web preview service in the background.

Open:
```text
http://127.0.0.1:5178
```

Stop services:
```bash
bash scripts/stop-dev.sh
```

Logs:
```text
.review-data/logs/web.log
.review-data/logs/api.log
.review-data/logs/llm-engine.log
.review-data/logs/prepare-tool-images.log
```

See `docs/SCREENSHOTS.md` for recommended screenshots. Runtime logs can be opened directly from the `.log` files above or captured with `tail -f`; Agent artifact screenshots are under `.review-data/jobs/<jobId>/agent-memory.json`, `tool-calls.json`, and `agent-trace.json`.

### Model Configuration
The default `.env.example` targets Ollama's OpenAI-compatible endpoint:

```bash
GEMMA_BASE_URL=http://127.0.0.1:11434/v1
GEMMA_API_KEY=local-placeholder-token
GEMMA_MODEL=gemma4:latest
```

The project is not tied to a specific Gemma 4 quantization tag. It needs an OpenAI-compatible chat endpoint, preferably with `tools` support. In the validation environment for this submission, Ollama maps `gemma4:latest` to the `gemma4:e4b-it-q4_K_M` build, reported as Gemma 4 family, 8.0B parameters, and `Q4_K_M` quantization. If the review environment uses a different Gemma 4 tag, edit `GEMMA_MODEL` in `.env`.

### Demo Prompt
```text
Run a bulk RNA-seq treatment vs control analysis with QC, counting, differential summary, and report.
```

The UI also provides single-cell RNA-seq and label-free proteomics presets. All workflows use included public synthetic sample data.

### Review Artifacts
```text
.review-data/jobs/<jobId>/agent-memory.json
.review-data/jobs/<jobId>/tool-calls.json
.review-data/jobs/<jobId>/agent-trace.json
.review-data/jobs/<jobId>/report.md
```

### Validation And Submission Package
```bash
pnpm check
```

This command:
1. Builds the API and Web UI.
2. Runs API tests.
3. Creates a clean submission package under `.review-data/submission/XR-Gemma4-Agent`.
4. Runs a boundary scan inside the package to ensure it excludes `.agentdocs`, `.env`, private paths, private images, customer data, and production credentials.

Manual package generation:
```bash
bash scripts/package-submission.sh
cd .review-data/submission/XR-Gemma4-Agent
bash scripts/check-review-package.sh
```

### Services
| Service | Default URL | Purpose |
| --- | --- | --- |
| Web UI | `http://127.0.0.1:5178` | Reviewer-facing interface |
| API | `http://127.0.0.1:3101` | Provider config, tasks, Agent artifacts |
| LLM engine | `http://127.0.0.1:8011` | OpenAI-compatible Gemma 4 adapter |

### License And Boundary
This public review project is released under the GNU General Public License version 3 only (GPL-3.0-only). See `LICENSE` for the full license text. The license covers the code and synthetic sample data included in this repository. Production services, private datasets, private images, credentials, deployment secrets, and unpublished commercial materials that are not included here are outside the licensed submission scope. The XR name, marks, and brand assets are not licensed for trademark use except as needed for reasonable source identification.

Copyright 2026 LIANG Weiyin @ XR.
