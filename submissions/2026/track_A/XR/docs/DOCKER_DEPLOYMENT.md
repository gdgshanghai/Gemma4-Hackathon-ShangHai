# Docker Deployment Guide / Docker 部署指南

## 中文版本

### 1. 部署目标
本文档用于评审在本地复现 XR Gemma 4 Bioinformatics Agent。系统本身由 Web UI、API server、LLM engine 三个本地服务组成；生物信息分析步骤通过 Docker 运行公开工具镜像。

注意：本项目不是完整容器化的 SaaS 部署包。为了方便评审查看源码与日志，Web/API/LLM engine 以本地进程启动，Docker 负责执行分析工具链。

### 2. 前置条件
- macOS 或 Linux
- Docker Desktop 或 Docker Engine
- Node.js 20+
- pnpm 8.15+
- Python 3.10+
- 可访问的 Gemma 4 OpenAI-compatible endpoint。推荐本地 Ollama。

确认命令：
```bash
node --version
pnpm --version
python3 --version
docker --version
docker info
```

### 3. 获取代码与安装依赖
```bash
pnpm install
python3 -m venv packages/llm-engine/.venv
packages/llm-engine/.venv/bin/pip install -r packages/llm-engine/requirements.txt
cp .env.example .env
```

### 4. 配置 Gemma 4
默认 `.env.example`：
```bash
API_PORT=3101
LLM_ENGINE_URL=http://127.0.0.1:8011
GEMMA_BASE_URL=http://127.0.0.1:11434/v1
GEMMA_API_KEY=local-placeholder-token
GEMMA_MODEL=gemma4:latest
```

如果使用 Ollama：
```bash
ollama list
ollama show gemma4:latest
```

如果本地模型 tag 不叫 `gemma4:latest`，修改 `.env`：
```bash
GEMMA_MODEL=<your-gemma4-tag>
```

项目不绑定具体量化版本。本次 review 机器上 `gemma4:latest` 对应 `gemma4:e4b-it-q4_K_M` build，Ollama 报告为 Gemma 4 8B、`Q4_K_M`。

### 5. Docker 镜像清单与用途
| 镜像 | 用途 |
| --- | --- |
| `quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0` | FASTQ 原始 reads 质量检查。 |
| `quay.io/biocontainers/trimmomatic:0.39--hdfd78af_2` | Bulk RNA-seq reads trimming。 |
| `quay.io/biocontainers/fastp:0.23.4--hadf994f_2` | Single-cell FASTQ 预处理。 |
| `quay.io/biocontainers/kallisto:0.51.1--h2b92561_2` | Bulk RNA-seq transcript quantification。 |
| `quay.io/biocontainers/multiqc:1.21--pyhdfd78af_0` | 汇总 QC 报告。 |
| `ghcr.io/getwilds/scanpy:latest` | Single-cell clustering、marker genes 和 cell-state 分析。 |
| `quay.io/biocontainers/bioconductor-limma:3.58.1--r43ha9d7317_1` | Single-cell/proteomics differential analysis。 |
| `quay.io/biocontainers/openms:3.4.1--heb594b5_0` | Proteomics mzML runtime check。 |
| `quay.io/biocontainers/bioconductor-msstats:4.10.0--r43hf17093f_1` | Proteomics MSstats runtime check。 |
| `gemma-demo/pydeseq2-rnaseq:0.1.0` | 本地构建的 bulk RNA-seq differential summary wrapper。 |

### 6. 准备 Docker 工具镜像
```bash
bash scripts/prepare-tool-images.sh
```

该脚本会拉取公开镜像：
- `quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0`
- `quay.io/biocontainers/trimmomatic:0.39--hdfd78af_2`
- `quay.io/biocontainers/fastp:0.23.4--hadf994f_2`
- `quay.io/biocontainers/kallisto:0.51.1--h2b92561_2`
- `quay.io/biocontainers/multiqc:1.21--pyhdfd78af_0`
- `ghcr.io/getwilds/scanpy:latest`
- `quay.io/biocontainers/bioconductor-limma:3.58.1--r43ha9d7317_1`
- `quay.io/biocontainers/openms:3.4.1--heb594b5_0`
- `quay.io/biocontainers/bioconductor-msstats:4.10.0--r43hf17093f_1`

并构建本地 wrapper：
- `gemma-demo/pydeseq2-rnaseq:0.1.0`

评审也可以只运行 `bash scripts/start-dev.sh`：该启动脚本会自动调用 `scripts/prepare-tool-images.sh`，完成镜像下载和本地 wrapper 构建。镜像准备日志写入：

```text
.review-data/logs/prepare-tool-images.log
```

### 7. 启动服务
```bash
bash scripts/start-dev.sh
```

该脚本会先运行 API/Web 构建，再启动后台评审服务：
- LLM engine：`uvicorn app.main:app --port 8011`
- API server：`node dist/index.js`
- Web UI：`vite preview --port 5178`

服务地址：
| 服务 | 地址 |
| --- | --- |
| Web UI | `http://127.0.0.1:5178` |
| API | `http://127.0.0.1:3101` |
| LLM engine | `http://127.0.0.1:8011` |

日志：
```bash
tail -f .review-data/logs/web.log
tail -f .review-data/logs/api.log
tail -f .review-data/logs/llm-engine.log
tail -f .review-data/logs/prepare-tool-images.log
```

### 8. 验证服务
```bash
curl http://127.0.0.1:3101/api/provider
curl http://127.0.0.1:8011/docs
```

验证 Agent planning：
```bash
curl -sS -X POST http://127.0.0.1:3101/api/plan \
  -H 'content-type: application/json' \
  --data '{"prompt":"Run a bulk RNA-seq treatment vs control analysis."}'
```

成功时应能看到：
- `modelPlan.source` 为 `model`
- `modelPlan.agentRun.mode` 为 `native_guided_tool_calling`，或在 endpoint 不返回原生 `tool_calls` 但 schema JSON 成功时显示 `guided_tool_calling`
- `toolCalls` 包含 Gemma 4 在受控 planner loop 中选择的公开工具，例如 `inspect_available_bio_tools` / `inspect_available_workflows`、`select_workflow`、`inspect_workflow_contract`、`inspect_sample_data`、`draft_tool_level_plan`

### 9. 运行 Demo
1. 打开 `http://127.0.0.1:5178`。
2. 在左侧 Conversation 输入或选择预设 prompt。
3. 点击 Send。
4. 在中间 Agent state 查看 Memory、Tool Calls、Public Trace。
5. 在右侧 Progress and results 查看 Docker 执行、结果表和 report。

输出目录：
```text
.review-data/jobs/<jobId>/
```

关键 artifacts：
```text
agent-memory.json
tool-calls.json
agent-trace.json
report.md
```

### 10. 截图运行日志
推荐截图位置：
- 终端执行 `tail -f .review-data/logs/prepare-tool-images.log`，展示 Docker 镜像拉取/构建日志。
- 终端执行 `tail -f .review-data/logs/api.log`，展示 API 启动和任务请求。
- 终端执行 `tail -f .review-data/logs/llm-engine.log`，展示 LLM engine 接收 `/chat` 请求。
- 浏览器打开 Web UI，截图 Agent state、Tool Calls、Memory 和 Progress and results。
- Finder/终端打开 `.review-data/jobs/<jobId>/`，截图 `agent-memory.json`、`tool-calls.json`、`agent-trace.json`。

macOS 可用 `Cmd + Shift + 4` 截图选区；也可以用系统 Screenshot 工具录屏。

### 11. 停止服务
```bash
bash scripts/stop-dev.sh
```

如需确认端口释放：
```bash
lsof -i :5178 -i :3101 -i :8011
```

### 12. 提交前验证
```bash
pnpm check
```

该命令会构建、测试、生成提交包，并检查提交包不包含 `.agentdocs`、`.env`、私有路径、私有镜像、客户数据或生产凭据。

### 13. 故障排查
| 问题 | 处理方式 |
| --- | --- |
| Web 页面打不开 | 检查 `.review-data/logs/web.log` 和 `lsof -i :5178`。 |
| API 无响应 | 检查 `.review-data/logs/api.log` 和 `curl http://127.0.0.1:3101/api/provider`。 |
| LLM engine 无响应 | 检查 Python venv 是否安装依赖，查看 `.review-data/logs/llm-engine.log`。 |
| `/api/plan` 进入 JSON fallback | 先检查 LLM engine 日志中的 native tool call、schema JSON 重试和 `system_grounding` 受控恢复记录；正常兼容路径应显示 `guided_tool_calling`，Tool Calls 可能包含 `model_schema` 或 contract-bounded `system_grounding`，只有公开恢复也不可行时才进入 fallback。 |
| 出现 404 `/v1/chat/completions` | 检查 `GEMMA_BASE_URL` 是否正确，Ollama OpenAI-compatible URL 应为 `http://127.0.0.1:11434/v1`。 |
| 模型不存在 | 运行 `ollama list`，将 `.env` 中 `GEMMA_MODEL` 改为实际存在的 Gemma 4 tag。 |
| Docker 镜像拉取失败 | 检查网络和 Docker 登录状态；查看 `.review-data/logs/prepare-tool-images.log`，重新运行 `bash scripts/prepare-tool-images.sh` 或 `bash scripts/start-dev.sh`。如果 Docker Desktop credential helper 返回异常，脚本会用 `.review-data/docker-config` 中的临时干净配置重试公开镜像拉取。 |
| Docker 执行失败 | 检查 Docker Desktop 是否运行，查看 API log 中的具体 tool step。 |

---

## English Version

### 1. Deployment Goal
This guide helps reviewers reproduce XR Gemma 4 Bioinformatics Agent locally. The system runs three local services, Web UI, API server, and LLM engine, while bioinformatics analysis steps run through Docker public tool images.

This is not a fully containerized SaaS deployment. To keep source code and logs easy to inspect, Web/API/LLM engine run as local processes, and Docker is used for analysis tool execution.

### 2. Prerequisites
- macOS or Linux
- Docker Desktop or Docker Engine
- Node.js 20+
- pnpm 8.15+
- Python 3.10+
- A Gemma 4 OpenAI-compatible endpoint. Local Ollama is recommended.

Check:
```bash
node --version
pnpm --version
python3 --version
docker --version
docker info
```

### 3. Install Dependencies
```bash
pnpm install
python3 -m venv packages/llm-engine/.venv
packages/llm-engine/.venv/bin/pip install -r packages/llm-engine/requirements.txt
cp .env.example .env
```

### 4. Configure Gemma 4
Default `.env.example`:
```bash
API_PORT=3101
LLM_ENGINE_URL=http://127.0.0.1:8011
GEMMA_BASE_URL=http://127.0.0.1:11434/v1
GEMMA_API_KEY=local-placeholder-token
GEMMA_MODEL=gemma4:latest
```

For Ollama:
```bash
ollama list
ollama show gemma4:latest
```

If your local tag is different, edit `.env`:
```bash
GEMMA_MODEL=<your-gemma4-tag>
```

The project is not bound to a specific quantized model tag. On the review machine, `gemma4:latest` maps to the `gemma4:e4b-it-q4_K_M` build, reported by Ollama as Gemma 4 8B with `Q4_K_M` quantization.

### 5. Docker Image Manifest
| Image | Purpose |
| --- | --- |
| `quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0` | Raw FASTQ read quality control. |
| `quay.io/biocontainers/trimmomatic:0.39--hdfd78af_2` | Bulk RNA-seq read trimming. |
| `quay.io/biocontainers/fastp:0.23.4--hadf994f_2` | Single-cell FASTQ preprocessing. |
| `quay.io/biocontainers/kallisto:0.51.1--h2b92561_2` | Bulk RNA-seq transcript quantification. |
| `quay.io/biocontainers/multiqc:1.21--pyhdfd78af_0` | Aggregated QC report. |
| `ghcr.io/getwilds/scanpy:latest` | Single-cell clustering, marker genes, and cell-state analysis. |
| `quay.io/biocontainers/bioconductor-limma:3.58.1--r43ha9d7317_1` | Single-cell/proteomics differential analysis. |
| `quay.io/biocontainers/openms:3.4.1--heb594b5_0` | Proteomics mzML runtime check. |
| `quay.io/biocontainers/bioconductor-msstats:4.10.0--r43hf17093f_1` | Proteomics MSstats runtime check. |
| `gemma-demo/pydeseq2-rnaseq:0.1.0` | Locally built bulk RNA-seq differential summary wrapper. |

### 6. Prepare Docker Tool Images
```bash
bash scripts/prepare-tool-images.sh
```

The script pulls public images:
- `quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0`
- `quay.io/biocontainers/trimmomatic:0.39--hdfd78af_2`
- `quay.io/biocontainers/fastp:0.23.4--hadf994f_2`
- `quay.io/biocontainers/kallisto:0.51.1--h2b92561_2`
- `quay.io/biocontainers/multiqc:1.21--pyhdfd78af_0`
- `ghcr.io/getwilds/scanpy:latest`
- `quay.io/biocontainers/bioconductor-limma:3.58.1--r43ha9d7317_1`
- `quay.io/biocontainers/openms:3.4.1--heb594b5_0`
- `quay.io/biocontainers/bioconductor-msstats:4.10.0--r43hf17093f_1`

It also builds one local wrapper:
- `gemma-demo/pydeseq2-rnaseq:0.1.0`

Reviewers may also run only `bash scripts/start-dev.sh`: the startup script automatically calls `scripts/prepare-tool-images.sh`, so it downloads public images and builds the local wrapper. Image preparation logs are written to:

```text
.review-data/logs/prepare-tool-images.log
```

### 7. Start Services
```bash
bash scripts/start-dev.sh
```

The script builds the API/Web first, then starts review services in the background:
- LLM engine: `uvicorn app.main:app --port 8011`
- API server: `node dist/index.js`
- Web UI: `vite preview --port 5178`

Services:
| Service | URL |
| --- | --- |
| Web UI | `http://127.0.0.1:5178` |
| API | `http://127.0.0.1:3101` |
| LLM engine | `http://127.0.0.1:8011` |

Logs:
```bash
tail -f .review-data/logs/web.log
tail -f .review-data/logs/api.log
tail -f .review-data/logs/llm-engine.log
tail -f .review-data/logs/prepare-tool-images.log
```

### 8. Verify Services
```bash
curl http://127.0.0.1:3101/api/provider
curl http://127.0.0.1:8011/docs
```

Verify Agent planning:
```bash
curl -sS -X POST http://127.0.0.1:3101/api/plan \
  -H 'content-type: application/json' \
  --data '{"prompt":"Run a bulk RNA-seq treatment vs control analysis."}'
```

Expected:
- `modelPlan.source` is `model`
- `modelPlan.agentRun.mode` is `native_guided_tool_calling`, or `guided_tool_calling` when native `tool_calls` are unavailable but schema JSON succeeds
- `toolCalls` includes public tools chosen by Gemma 4 inside the controlled planner loop, such as `inspect_available_bio_tools` / `inspect_available_workflows`, `select_workflow`, `inspect_workflow_contract`, `inspect_sample_data`, and `draft_tool_level_plan`

### 9. Run The Demo
1. Open `http://127.0.0.1:5178`.
2. Type a request in Conversation or select a preset prompt.
3. Click Send.
4. Inspect Memory, Tool Calls, and Public Trace in Agent state.
5. Inspect Docker execution, result tables, and report in Progress and results.

Output directory:
```text
.review-data/jobs/<jobId>/
```

Key artifacts:
```text
agent-memory.json
tool-calls.json
agent-trace.json
report.md
```

### 10. Capture Runtime Log Screenshots
Recommended screenshot sources:
- Run `tail -f .review-data/logs/prepare-tool-images.log` to show Docker image pull/build logs.
- Run `tail -f .review-data/logs/api.log` to show API startup and task requests.
- Run `tail -f .review-data/logs/llm-engine.log` to show LLM engine `/chat` requests.
- Open the Web UI and capture Agent state, Tool Calls, Memory, and Progress and results.
- Open `.review-data/jobs/<jobId>/` and capture `agent-memory.json`, `tool-calls.json`, and `agent-trace.json`.

On macOS, use `Cmd + Shift + 4` for area screenshots or the system Screenshot app for screen recording.

### 11. Stop Services
```bash
bash scripts/stop-dev.sh
```

Confirm ports are free:
```bash
lsof -i :5178 -i :3101 -i :8011
```

### 12. Pre-Submission Check
```bash
pnpm check
```

This command builds, tests, prepares a submission package, and scans it to ensure it excludes `.agentdocs`, `.env`, private paths, private images, customer data, and production credentials.

### 13. Troubleshooting
| Problem | Action |
| --- | --- |
| Web page is unavailable | Check `.review-data/logs/web.log` and `lsof -i :5178`. |
| API is unavailable | Check `.review-data/logs/api.log` and `curl http://127.0.0.1:3101/api/provider`. |
| LLM engine is unavailable | Confirm Python venv dependencies and inspect `.review-data/logs/llm-engine.log`. |
| `/api/plan` enters JSON fallback | Inspect the LLM engine log for native tool-call, schema JSON retry, and `system_grounding` controlled-recovery records; the normal compatibility path should show `guided_tool_calling`, and Tool Calls may include `model_schema` or contract-bounded `system_grounding`. Fallback is used only when public recovery is also unavailable. |
| 404 on `/v1/chat/completions` | Check `GEMMA_BASE_URL`; Ollama OpenAI-compatible URL should be `http://127.0.0.1:11434/v1`. |
| Model tag does not exist | Run `ollama list` and set `GEMMA_MODEL` in `.env` to an existing Gemma 4 tag. |
| Docker image pull fails | Check network and Docker login status; inspect `.review-data/logs/prepare-tool-images.log`, then rerun `bash scripts/prepare-tool-images.sh` or `bash scripts/start-dev.sh`. If Docker Desktop's credential helper returns an error, the script retries public image pulls with a temporary clean config under `.review-data/docker-config`. |
| Docker execution fails | Confirm Docker Desktop is running and inspect the API log for the failing tool step. |
