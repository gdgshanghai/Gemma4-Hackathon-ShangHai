# XR Gemma 4 Agent Technical Report / 技术报告

## 中文版本

### 1. 摘要
XR Lite Version for GDG Gemma 4 Hackathon 2026 是面向 Gemma 4 开发者大赛赛道 A 的公开评审项目。系统展示 Gemma 4 在本地或私有 OpenAI-compatible endpoint 中，通过受控 planner loop、Native/tool-schema tool calling、任务级 Memory、公开工具调用记录和 Docker 可复现执行，把自然语言生物医学分析需求转化为可审计结果。

该提交使用公开 synthetic sample data、公开 workflow contract 和公开 Docker 工具链。评审范围限于本仓库提交内容，不涉及商业版 XR 平台的生产系统、真实客户数据、私有镜像或生产凭据。

### 2. 赛道 A 对齐
| 赛道关注点 | 实现 |
| --- | --- |
| Native Function Calling | LLM engine 透传 `tools`、`tool_choice`、`reasoning_effort`，API 捕获 OpenAI-compatible `tool_calls`。 |
| 多步规划 | Gemma 4 在受控 planner loop 中每轮从 allowed next tools 里选择下一步公开工具，调用 `inspect_available_bio_tools` / `inspect_available_workflows`、`select_workflow`、`inspect_workflow_contract`、`inspect_sample_data`、`draft_tool_level_plan`，为三条公开 workflow 生成具体工具级计划；API 校验后执行固定公开 pipeline，并在执行后追加 `summarize_results` 反思调用。 |
| Memory | `ReviewAgentMemory` 保存 prompt、模型名、workflow、comparison、安全规则、observed public files、tool call IDs。 |
| Tool Calling | `publicToolManifest.ts` 定义公开工具 schema；`tool-calls.json` 和 Web UI 展示调用来源、参数、状态和摘要。 |
| 本地/端侧部署 | 默认连接 Ollama OpenAI-compatible endpoint，分析工具通过本地 Docker 执行。 |
| 可审计性 | 每次任务写出 `agent-memory.json`、`tool-calls.json`、`agent-trace.json`、`report.md`。 |

### 3. 模型选择
系统默认使用：

```bash
GEMMA_BASE_URL=http://127.0.0.1:11434/v1
GEMMA_MODEL=gemma4:latest
```

项目不绑定某个具体 Gemma 4 量化版本。只要 endpoint 兼容 OpenAI chat completion，并最好支持 `tools`，即可替换 `GEMMA_MODEL`。在本提交的验证环境中，Ollama 的 `gemma4:latest` 对应 `gemma4:e4b-it-q4_K_M` build，Ollama 报告信息为：

- family: `gemma4`
- parameters: `8.0B`
- quantization: `Q4_K_M`
- context length: `131072`
- capabilities: completion, vision, audio, tools, thinking

验证过程中，完全自由的多工具 auto agent 在完整链路中的耗时稳定性和边界解释不如受控状态机。因此 runtime 采用 controlled planner loop：每轮 API 只暴露当前状态允许的公开 tool schema，Gemma 4 选择下一步工具并生成参数和工具级计划内容。若 endpoint 不返回 native `tool_calls`，系统会先对当前阶段重试 schema JSON，并标记为 `model_schema`；若兼容端点返回空内容或无效 JSON，API 只允许在当前公开 tool 和 workflow contract 内做 `system_grounding` 受控恢复；只有无法公开恢复时才进入 `JSON fallback`。

### 4. 系统架构
```text
Web UI
  -> API server
    -> Review Agent Runtime
      -> LLM engine adapter
        -> Local/private Gemma 4 OpenAI-compatible endpoint
    -> Public workflow catalog
    -> Docker execution pipelines
  -> .review-data/jobs/<jobId>/ artifacts
```

组件说明：
- `packages/web`：React/Vite Web UI，展示 Conversation、Workflow presets、Agent state、Execution plan、Progress and results。
- `packages/api`：Express API，负责 provider 配置、conversation routing、Agent planning、workflow 执行、artifact 持久化。
- `packages/llm-engine`：Python FastAPI adapter，向 Gemma 4 endpoint 发送 OpenAI-compatible chat/tool calling 请求。
- `demo-data`：公开 synthetic sample datasets。
- `packages/api/tool-images`：评审工作流需要的本地 wrapper image build context。

### 5. Agent Loop
1. 用户输入自然语言分析需求。
2. Conversation router 默认调用 Gemma 4 识别意图；API 仅在模型失败、低置信度或已有任务运行时使用 fast-rule 安全护栏。
3. API 初始化任务和 Agent Memory。
4. Review Agent 进入受控 planner loop：每轮 API 根据状态暴露 allowed next tools，Gemma 4 选择一个公开工具并返回参数。
5. Gemma 4 可查看公开生信工具和公开 workflow catalog，然后调用 `select_workflow` 选择 `bulk_rna_seq`、`single_cell_rna_seq` 或 `proteomics_lfq`。
6. Gemma 4 在 API 允许的顺序内调用 `inspect_workflow_contract` 与 `inspect_sample_data`，查看公开 workflow contract 和 toy data。
7. Gemma 4 调用 `draft_tool_level_plan`，按固定 contract 起草具体生信工具级计划。
8. API 校验 stepId、toolName、toolImage、顺序和依赖关系，只允许公开 workflow。
9. API 执行固定 Docker pipeline，并在执行后让 Gemma 4 通过 `summarize_results` 对公开结果做简短 reflection。
10. UI 和 artifacts 展示 Memory、Tool Calls、Trace、结果表和报告。

### 6. Memory 设计
`ReviewAgentMemory` 是任务级公开记忆，只记录评审需要看到的信息：

```ts
{
  prompt: string
  model: string
  selectedWorkflowKey?: string
  selectedWorkflowName?: string
  comparison?: string
  publicSafetyRules: string[]
  observedToyData: string[]
  toolCallIds: string[]
}
```

Memory 的作用：
- 便于评审确认模型选择的 workflow。
- 便于评审追踪工具调用如何影响 state。
- 记录公开 synthetic sample data 文件，便于评审确认数据来源。
- 记录安全约束，确保所有执行都限制在 public review boundary 内。

### 7. Tool Calling 与来源
每个 tool call 都带有 `origin`：

| Origin | 含义 |
| --- | --- |
| `model_native` | Gemma 4 通过 OpenAI-compatible native tool call 返回。 |
| `model_schema` | 模型未返回 native tool call，但按 tool schema 返回 JSON 参数。 |
| `system_grounding` | API 在当前 allowed tool 和公开 workflow contract 内做受控恢复或 contract grounding；用于兼容端点空响应、无效 JSON 等可恢复情况。 |
| `json_fallback` | Native tool calling、阶段级 schema JSON 和公开 contract 内受控恢复都不可用时的最终 fallback 计划。 |

这能避免评审误解：UI 会清晰标注模型原生调用、schema JSON 兼容调用、系统 grounding 和 fallback 的边界。

### 8. 公开工具列表
- `inspect_available_bio_tools`
- `inspect_available_workflows`
- `inspect_workflow_contract`
- `inspect_sample_data`
- `select_workflow`
- `draft_tool_level_plan`
- `draft_execution_plan`
- `summarize_results`

Gemma 4 当前在 planning 阶段通过受控 planner loop 选择下一步公开工具，参与公开工具查看、workflow 选择、contract inspection、sample inspection 和工具级计划起草。API 会把模型计划校验并编译回公开 workflow contract，确保模型不能自由生成 Docker 命令、自由选择镜像或访问任意路径。

### 9. Docker 执行
三个 workflow 都可在本地执行：
- Bulk RNA-seq：FastQC、Trimmomatic、kallisto、PyDESeq2、MultiQC。
- Single-cell RNA-seq：FastQC、fastp、Scanpy、limma。
- Label-free proteomics：OpenMS、limma、MSstats。

所有输入来自 `demo-data`，输出写入 `.review-data/jobs/<jobId>/`。详细步骤见 `docs/DOCKER_DEPLOYMENT.md`。

### 10. Fallback 策略
当模型 endpoint 不返回 native tool calling、返回空内容、JSON 被截断或请求超时时，系统不会中断评审流程，而是：
1. 先在当前 planner 阶段重试 schema JSON，不直接放弃整条 Agent 链路。
2. schema JSON 成功时，UI 显示 `Guided planner loop`，Tool Calls 标记为 `model_schema`。
3. 若 schema JSON 仍为空或无效，API 只在当前 allowed tool 和公开 workflow contract 内做 `system_grounding` 受控恢复，UI 仍显示 `Guided planner loop`。
4. 只有 native、schema 和受控公开恢复都不可用时，UI 才显示 `JSON fallback`，API 使用公开 JSON planner 或 deterministic fallback。
5. 所有兼容和 fallback 决策仍写入 trace 和 tool calls。
6. 后续执行仍被限制在公开 workflow catalog 和 synthetic sample data 内。

### 11. 隐私与边界
本提交范围不包括：
- 商业版 XR 平台的生产调度架构。
- 私有数据、客户数据、私有镜像。
- 生产凭据、真实 API keys、生产部署系统。
- `.agentdocs` 本地开发辅助文档。

提交包由 `scripts/package-submission.sh` 生成，并由 `scripts/check-review-package.sh` 扫描边界。

### 12. 验证
```bash
pnpm build
pnpm --filter @gemma-demo/api test
pnpm check
```

`pnpm check` 会构建、测试、生成提交包并在提交包中运行边界扫描。

### 13. 已知限制
- 本项目是公开评审提交，不是商业生产系统。
- Native tool calling 能力依赖评审环境中的 Gemma 4 endpoint；不支持时会优先进入可见的 `model_schema` 兼容路径，空响应或无效 JSON 会先在公开 contract 内恢复为 `system_grounding`，最终不可恢复才进入 `JSON fallback`。
- Synthetic sample datasets 很小，只用于可复现技术演示，不代表真实科研结论。

---

## English Version

### 1. Summary
XR Lite Version for GDG Gemma 4 Hackathon 2026 is a public review project for Gemma 4 Track A. It demonstrates how Gemma 4, running behind a local or private OpenAI-compatible endpoint, can use a controlled planner loop, native/tool-schema tool calling, task-scoped Memory, visible Tool Calls, and local Docker execution to turn a natural-language biomedical analysis request into auditable outputs.

This submission uses public synthetic sample data, public workflow contracts, and public Docker tools. The review scope is limited to the submitted repository contents and does not include production XR systems, real customer data, private images, or production credentials.

### 2. Track A Alignment
| Track Focus | Implementation |
| --- | --- |
| Native Function Calling | The LLM engine passes `tools`, `tool_choice`, and `reasoning_effort`; the API captures OpenAI-compatible `tool_calls`. |
| Multi-step planning | Gemma 4 runs inside a controlled planner loop and chooses one allowed next public tool per round, including `inspect_available_bio_tools` / `inspect_available_workflows`, `select_workflow`, `inspect_workflow_contract`, `inspect_sample_data`, and `draft_tool_level_plan`; the API validates the plan before fixed public pipeline execution and appends `summarize_results` after execution. |
| Memory | `ReviewAgentMemory` stores prompt, model, workflow, comparison, safety rules, observed public files, and tool call IDs. |
| Tool Calling | `publicToolManifest.ts` defines public tool schemas; `tool-calls.json` and the Web UI show origin, arguments, status, and summary. |
| Local/private deployment | The default setup connects to Ollama's OpenAI-compatible endpoint and runs computation locally through Docker. |
| Auditability | Each task writes `agent-memory.json`, `tool-calls.json`, `agent-trace.json`, and `report.md`. |

### 3. Model Choice
The default configuration is:

```bash
GEMMA_BASE_URL=http://127.0.0.1:11434/v1
GEMMA_MODEL=gemma4:latest
```

The project is not tied to a specific Gemma 4 quantization tag. Any OpenAI-compatible chat endpoint can be used, preferably with `tools` support. In the validation environment for this submission, Ollama maps `gemma4:latest` to the `gemma4:e4b-it-q4_K_M` build, reported as:

- family: `gemma4`
- parameters: `8.0B`
- quantization: `Q4_K_M`
- context length: `131072`
- capabilities: completion, vision, audio, tools, thinking

Validation showed that a fully free multi-tool auto agent is harder to stabilize and explain in the full API chain. Therefore, the runtime uses a controlled planner loop: the API exposes only the public tool schemas allowed by the current state, while Gemma 4 chooses the next tool and provides arguments and tool-level planning content. If the endpoint does not return native `tool_calls`, the system retries the current stage with schema JSON and marks it as `model_schema`; if the compatible endpoint returns empty content or invalid JSON, the API may recover only within the current public tool and workflow contract as `system_grounding`; only when public recovery is impossible does it enter `JSON fallback`.

### 4. Architecture
```text
Web UI
  -> API server
    -> Review Agent Runtime
      -> LLM engine adapter
        -> Local/private Gemma 4 OpenAI-compatible endpoint
    -> Public workflow catalog
    -> Docker execution pipelines
  -> .review-data/jobs/<jobId>/ artifacts
```

Components:
- `packages/web`: React/Vite Web UI for Conversation, Workflow presets, Agent state, Execution plan, Progress and results.
- `packages/api`: Express API for provider config, conversation routing, Agent planning, workflow execution, and artifact persistence.
- `packages/llm-engine`: Python FastAPI adapter for OpenAI-compatible Gemma 4 chat/tool calls.
- `demo-data`: public synthetic sample datasets.
- `packages/api/tool-images`: local wrapper image build context required by the review workflows.

### 5. Agent Loop
1. The user enters a natural-language analysis request.
2. The conversation router asks Gemma 4 to classify intent first; the API only applies fast-rule guards when the model fails, has low confidence, or a task is already running.
3. The API initializes the task and Agent Memory.
4. The Review Agent enters a controlled planner loop: each round, the API exposes allowed next tools for the current state, and Gemma 4 chooses one public tool with arguments.
5. Gemma 4 can inspect public bioinformatics tools and workflow catalogs, then call `select_workflow` to choose `bulk_rna_seq`, `single_cell_rna_seq`, or `proteomics_lfq`.
6. Gemma 4 calls `inspect_workflow_contract` and `inspect_sample_data` within API-allowed transitions for the selected public workflow and toy data.
7. Gemma 4 calls `draft_tool_level_plan` to draft concrete bioinformatics tool steps under the fixed contract.
8. The API validates stepId, toolName, toolImage, ordering, and dependencies against the public contract.
9. The API executes the fixed Docker pipeline and asks Gemma 4 to call `summarize_results` for public result reflection.
10. The UI and artifacts show Memory, Tool Calls, Trace, result tables, and report.

### 6. Memory Design
`ReviewAgentMemory` is task-scoped public memory:

```ts
{
  prompt: string
  model: string
  selectedWorkflowKey?: string
  selectedWorkflowName?: string
  comparison?: string
  publicSafetyRules: string[]
  observedToyData: string[]
  toolCallIds: string[]
}
```

Memory helps reviewers verify:
- which workflow the model selected;
- how tool calls updated state;
- which public synthetic sample files were observed;
- which safety rules kept execution inside the public review boundary.

### 7. Tool Calling Origins
Each tool call has an `origin`:

| Origin | Meaning |
| --- | --- |
| `model_native` | Gemma 4 returned an OpenAI-compatible native tool call. |
| `model_schema` | The model returned JSON arguments according to a tool schema, without native `tool_calls`. |
| `system_grounding` | The API recovered within the current allowed tool and public workflow contract, or recorded public contract grounding; this covers recoverable empty-response or invalid-JSON compatibility cases. |
| `json_fallback` | The fallback planner was used only when native tool calling, stage-level schema JSON, and contract-bounded public recovery were unavailable. |

This avoids overstating the model behavior: the UI distinguishes native model calls, schema JSON compatibility calls, system grounding, and fallback.

### 8. Public Tools
- `inspect_available_bio_tools`
- `inspect_available_workflows`
- `inspect_workflow_contract`
- `inspect_sample_data`
- `select_workflow`
- `draft_tool_level_plan`
- `draft_execution_plan`
- `summarize_results`

Gemma 4 currently participates through a controlled planner loop: it chooses the next public tool for public tool inspection, workflow selection, contract inspection, sample inspection, and tool-level plan drafting. The API validates and compiles the model plan back to public workflow contracts, so the model cannot freely generate Docker commands, choose arbitrary images, or access arbitrary paths.

### 9. Docker Execution
All three workflows are executable locally:
- Bulk RNA-seq: FastQC, Trimmomatic, kallisto, PyDESeq2, MultiQC.
- Single-cell RNA-seq: FastQC, fastp, Scanpy, limma.
- Label-free proteomics: OpenMS, limma, MSstats.

Inputs come from `demo-data`; outputs are written under `.review-data/jobs/<jobId>/`. See `docs/DOCKER_DEPLOYMENT.md` for detailed deployment steps.

### 10. Fallback Strategy
If the endpoint does not return native tool calling, returns empty content, truncates JSON, or times out:
1. The API first retries the current planner stage with schema JSON instead of abandoning the whole Agent chain.
2. When schema JSON succeeds, the UI marks `Guided planner loop`, and Tool Calls are tagged `model_schema`.
3. If schema JSON is still empty or invalid, the API may recover as `system_grounding` only within the current allowed tool and public workflow contract; the UI still marks `Guided planner loop`.
4. Only when native, schema, and contract-bounded public recovery all fail does the UI mark `JSON fallback`; the API then uses a public JSON planner or deterministic fallback.
5. Compatibility and fallback decisions are still written to trace and tool calls.
6. Execution remains constrained to the public workflow catalog and synthetic sample data.

### 11. Privacy Boundary
The submission scope excludes:
- production orchestration architecture from the commercial XR platform;
- private data, customer data, private images;
- production credentials, real API keys, production deployment systems;
- local development assistant documentation under `.agentdocs`.

The submission package is generated by `scripts/package-submission.sh` and scanned by `scripts/check-review-package.sh`.

### 12. Validation
```bash
pnpm build
pnpm --filter @gemma-demo/api test
pnpm check
```

`pnpm check` builds, tests, creates a clean submission package, and runs the boundary scanner inside that package.

### 13. Known Limitations
- This is a public review submission, not a commercial production system.
- Native tool calling depends on the Gemma 4 endpoint available in the review environment; unsupported endpoints first use the visible `model_schema` compatibility path, empty or invalid responses may recover within the public contract as `system_grounding`, and `JSON fallback` is used only when recovery is impossible.
- Synthetic sample datasets are intentionally small and are not scientific claims.
