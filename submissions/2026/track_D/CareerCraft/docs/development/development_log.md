<!-- mdformat global-off -->
# CareerCraft 开发进展与演进记录 (Development Log)

本文档用于统一记录 CareerCraft (AI驱动的职业模拟沙盒 MVP) 的开发迭代里程碑、核心架构决策与后续跟进待办，便于开发团队和后续接手的工程师快速对齐上下文。

---

## 🚩 [2026-06-03] 里程碑 12：Subagent 分层、任务物料生成编排与 artifact 感知评审落地

本里程碑围绕「把 LLM 能力拆成可编排阶段」与「让任务真正带有本地可追踪物料」两条主线推进，对应提交 `4d644fb` 与 `e265cd8`，按实现顺序分为 7 块改动，并记录 1 组后续跟进项：

### 1. 统一 Subagent 契约与观测元数据 (`refactor(backend)`)
- **新增 `app/services/agents/base.py`**：抽象出 `Subagent` 协议、`SubagentResult`、`SubagentError` 与三类上下文 `MissionContext` / `EvaluationContext` / `FeynmanContext`，把「单个 LLM 阶段如何执行」与「上层如何编排」解耦。
- **`invoke_with_fallback()` 统一兜底入口**：所有 subagent 失败时只跨出 `SubagentError`，orchestrator 统一捕获并调用 `fallback()`；同时记录 `subagent.ok` / `subagent.fallback` 日志、耗时 `elapsed_ms` 与 `used_fallback` 标记，便于后续定位真实 LLM 抖动。
- **`stopwatch()` 小工具**：统一计算毫秒级耗时，让任务生成、评审、费曼挑战的观测字段格式保持一致。

### 2. LLM IO 从 legacy agent 中抽离 (`agents/llm_io.py`)
- **`call_llm` / `call_llm_json` 搬入 canonical helper**：后续 subagent 不再依赖旧的 `app.services.agent`，而是统一走 `app.services.agents.llm_io`。
- **保留双重有界重试策略**：结构化 JSON 调用继续支持 schema violation 一次提示重试、瞬时网络错误一次退避重试，复用 5 月 30 日落地的严格结构化输出能力。
- **`llm_disabled()` 集中判断离线模式**：`settings.mock_agent_output` 或缺少 `llm_api_key` 时，subagent 直接走本地 fallback，避免每个业务函数重复判断。
- **`unwrap_to_required_keys()` 增加有界解包**：容忍模型把任务字段包进 `task` / `context` / `deliverables` 等容器，但最多递归 3 层；找不到必需字段则 fail-fast 到 fallback。

### 3. 任务、评审、费曼三类 Subagent 拆分 (`agents/subagents/*`)
- **`MissionSpecSubagent`**：从旧 `agent.create_mission` 中拆出任务规格生成阶段。LLM 输出仍受 `title / description / mock_data_url / delivery_requirements` schema 约束，离线时读取 `mission_catalog`，兜底时返回通用 fallback 任务。
- **`MissionArtifactSubagent`**：新增任务物料生成阶段，要求 LLM 返回 `{filename, mime_type, content}`，MIME 类型必须在白名单内，内容硬限制 64 KiB；失败时从 `backend/app/data/missions/samples/` 复制内置样例。
- **`SubmissionEvaluateSubagent`**：从旧评审函数中拆出结构化评审阶段，保留按职业构造 `experience_gains` 白名单 schema、数据分析/软件工程两套离线 fallback，以及提交文本 6000 字符截断保护。
- **`FeynmanReviewSubagent`**：把 `/user/feynman/submit` 里的内联 LLM 调用抽为单阶段 subagent，保留离线通关反馈与异常 fallback。
- **测试覆盖**：新增 `backend/tests/test_agents.py`，覆盖 subagent 正常路径、fallback 路径、schema 解包、物料大小/MIME 限制与费曼评审输出等核心契约。

### 4. Mission / Evaluation / Feynman Orchestrator 接入 (`services/orchestrators/*`)
- **`MissionOrchestrator`**：把任务生成流程固定为 `spec → artifact → storage`。先生成任务规格，再把规格写回 `MissionContext`，随后生成物料并落入本地存储。
- **物料存储键命名空间**：`_storage_key(user_id, mission_id)` 生成 `{user_id}__{mission_id}`，避免多个玩家做同一个 catalog mission 时互相覆盖文件。
- **`MissionGenerationResult` 扩展结果**：除任务字段外，返回 `mock_data_filename`、`used_spec_fallback`、`used_artifact_fallback`，为数据库持久化和排障日志提供上下文。
- **`EvaluationOrchestrator`**：在 `settings.eval_use_artifact_context` 开启且记录存在本地文件名时，读取任务物料节选注入 `EvaluationContext.artifact_excerpt`，让评审能同时看任务描述、玩家提交和原始物料。
- **`FeynmanOrchestrator`**：把费曼挑战统一包进 `invoke_with_fallback()`，消除 API 层对 LLM 异常处理的直接感知。

### 5. Composition Root 与 FastAPI 依赖注入 (`services/factory.py`)
- **新增 `app/services/factory.py`**：集中装配 `MissionSpecSubagent`、`MissionArtifactSubagent`、`SubmissionEvaluateSubagent`、`FeynmanReviewSubagent` 与 `LocalArtifactStorage`。
- **`get_artifact_storage()` 使用 `@lru_cache(maxsize=1)`**：存储适配器作为进程级无状态单例复用。
- **API 依赖可覆盖**：`get_mission_orchestrator()` / `get_evaluation_orchestrator()` / `get_feynman_orchestrator()` 通过 FastAPI `Depends` 注入，测试可用 `app.dependency_overrides` 替换具体编排器。

### 6. 任务物料持久化、静态服务与数据库自愈 (`feat(backend)`)
- **`MissionRecord.mock_data_filename` 新增**：ORM 记录本地生成物料文件名；历史行允许为空，新任务同时保存 `mock_data_url` 与 `mock_data_filename`。
- **启动时 schema 自愈**：`main.py` 新增 `_self_heal_schema()`，在 `base.metadata.create_all()` 后检查 `mission_records` 是否缺少 `mock_data_filename`，缺失则执行幂等 `ALTER TABLE`，解决 SQLite 老库不会自动加列的问题。
- **静态挂载 `/mock_data`**：FastAPI 挂载 `generated_dir()`，`LocalArtifactStorage.build_url()` 生成的公开 URL 与静态路径对齐，新生成的 CSV / Python 文件可直接从浏览器下载。
- **新增生成样例文件**：`backend/app/data/generated/00000000-0000-4000-8000-000000000001__mvp_mission_data_1__mvp_mission_data_1.csv` 与 `...__mvp_mission_software_1__UserService.py` 进入版本库，用于演示和回归验证 artifact 路径。

### 7. Service 与 API 层改造收口
- **`mission.generate_mission()` 接收 `MissionOrchestrator`**：service 层只负责关卡序号计算、废弃旧 active 任务、写入新 `MissionRecord`；LLM 与物料逻辑全部交给 orchestrator。
- **`eval.evaluate_user_submission()` 接收 `EvaluationOrchestrator`**：评审前读取 active mission 的描述和 `mock_data_filename`，让 artifact excerpt 有机会进入 LLM prompt；评审后继续执行职业白名单过滤、任务状态更新、XP 累加与技能进度写入。
- **`/api/v1/missions/generate|evaluate` 注入编排器**：API 层由直接调用 legacy agent 改为依赖 factory 提供的 orchestrator。
- **`/api/v1/user/feynman/submit` 改走 `FeynmanOrchestrator`**：端点保留 mission 查找、状态落库与 `strip_text_artifacts()` 清洗，LLM 评语生成下沉到 subagent。
- **回归测试更新**：`test_eval.py` 与 `test_mission.py` 适配 orchestrator 注入和 artifact-aware 行为，`test_llm.py` 保持底层 LLM helper 契约不回退。

### 8. 已知待跟进
- **legacy `app.services.agent` 仍保留兼容 shim**：当前已把核心 LLM 阶段迁入 subagent，但旧模块仍承担向后兼容入口；后续可在 API/测试完全迁移后删除。
- **SQLite 自愈只覆盖新增列**：`_self_heal_schema()` 当前只处理 `mission_records.mock_data_filename`，未来若字段继续演进，应引入更系统的 migration 机制。
- **artifact excerpt 截断策略仍较粗**：评审只读取物料文本节选，适合 CSV/源码/日志等文本物料；若后续支持二进制附件，需要扩展 storage 与 prompt 摘要策略。

---

## 🚩 [2026-05-30] 里程碑 11：LLM 容错链路硬化、按职业经验白名单、玩家身份契约升级与 API 数据合同收紧

本里程碑围绕「让 LLM 输出真正可信」与「让前后端身份/数据合同可演进」两条主线推进，按提交顺序分为 8 块改动：

### 1. LLM 解析容错与 `chat_json` 默认实现 (`refactor(llm)`)
- **`app/core/llm/parsing.py` 新增**：统一处理三种历史毛病——LLM 偶发的 Markdown 代码栅（` ```json ... ``` `）、首尾噪音文本、字段名/枚举值的轻微越界。提供：
  - `extract_json_payload(raw)`：剥栅 + 定位首个平衡的 `{...}` / `[...]` 块；
  - `strip_text_artifacts(raw)`：折叠空行、去除尾随说明，用于非结构化 free-form 文本。
- **`LLMClient.chat_json(prompt, system, json_schema)` 提升为基类默认实现**：在 `base.py` 中走「`chat()` → `extract_json_payload` → `json.loads`」三段式，任何子类（Gemini / OpenAI-like / Anthropic）无需各自重写。失败时统一抛 `LLMOutputFormatError`，保留原始 raw 便于日志审计。
- **效果**：DashScope 等国产网关偶发的 `"```json\n{...}\n```"` 输出从「业务层 500」收敛为「parsing 层一次清洗即过」，三个适配器删除了各自重复的 fence-stripping 代码。

### 2. 日志切片策略调整 (`chore(logging)`)
- **`TimedRotatingFileHandler` → `RotatingFileHandler`**：原按天切片在长周期闲置时会产生大量空文件且重启后切片基准重置；改为按 `maxBytes` + `backupCount` 大小切片，磁盘占用可控、与容器化重启策略更兼容。
- 文件名从 `app.log.YYYY-MM-DD` 改为 `app.log` + `app.log.1/.2/...`，便于 `tail -f` 和日志收集器统一抓取。

### 3. 结构化玩家身份契约：`X-Player-Id` + Hybrid 模式 (`feat(auth)`)
- **`app/api/deps.py` 升级 `get_current_user_id`**：
  - 优先读取请求头 `X-Player-Id`（前端在 `localStorage` 中持久化）；
  - 缺省回退到旧的 `"default_player"`，保留 MVP 演示零配置体验（hybrid 模式）；
  - 通过 `settings.auth_require_player_id` 开关可强制必须携带头，便于联调隔离多账户。
- **前端 `api.ts` 全量注入 `X-Player-Id`**：`request()` 工具函数集中读取 `playerStore.playerId` 并写入请求头，避免每个接口分散 `headers` 拼装。
- **`PlayerIdPanel.vue` 新增**：右上角玩家身份小窗，支持查看 / 编辑 / 一键生成新 UUID。`pinia` `playerStore` 把 ID 同步到 `localStorage`，刷新不丢。
- **意义**：把「身份从何而来」的决策点从后端单点收敛到「前端 store + header」一条链路，为后续接入真实 JWT 留好接口与 UI 心智模型，业务代码无需再次改造。

### 4. `.gitignore` 修正：放行 `backend/app/core/llm/` 源文件 (`fix(gitignore)`)
- 历史规则误把 `app/core/llm/` 目录整体忽略（曾用于本地实验脚本目录），导致里程碑 9 落地的 `base.py / factory.py / parsing.py / providers/*.py` 在 `git status` 看不见，新机克隆缺失关键模块。
- 改为精确忽略 `backend/app/core/llm/__pycache__/`、`*.pyc` 等产物，正式源文件全部纳入版本控制。

### 5. 玩家身份面板增加关闭按钮 (`feat: add close button to player id panel`)
- `PlayerIdPanel.vue` 加入像素风「✕」按钮 + `localStorage` 持久化「已关闭」状态，避免每次刷新都强制弹出，照顾老用户体感。
- 关闭后仍可通过顶栏头像气泡再次唤起，UX 不退化。

### 6. LLM 严格 `json_schema` 模式 + 双重有界重试 + 异常窄化 (`feat(llm)`)
- **`OpenAICompatibleAdapter` 协议升级**：新增 `_supports_strict_schema(base_url)` 识别 DashScope / OpenAI / DeepSeek / Moonshot 等支持 `response_format=json_schema` 的端点，优先走 strict 模式；不支持的端点退回原 `json_object` + prompt schema_hint 注入。
- **异常窄化**：仅在捕获 `openai.BadRequestError` 时降级到 `json_object`（并 `logger.warning("strict json_schema rejected by %s, falling back...", base_url, e)`），其余 timeout / 鉴权 / 网络异常一律抛 `LLMProviderError`，把重试决策权交还上层，杜绝「strict 被静默吞掉、用户却以为模型胡说」的隐性故障。
- **`LLMClient.chat_json` 加强 Liskov 后置条件**：`base.py` 在拿到 `json_schema` 时调用 `parsing.validate_against_schema(parsed, schema)`，保证任何 adapter 实现的契约一致；违规抛 `LLMOutputFormatError("schema violation at <path>: ...")`，错误路径直接指向首个不合规字段。
- **`call_llm_json` 双重有界重试**：
  1. schema 违规重试 1 次（把错误路径回灌进 prompt，引导模型改字段）；
  2. 瞬时网络错误（`_is_transient_network_error`）退避重试 1 次。
  两项分别由 `settings.llm_retry_on_schema_violation` / `llm_retry_on_timeout` 开关控制。
- **配置扩充**：`llm_timeout` 默认 `30 → 60`；新增三态 `llm_use_json_schema_response_format`（`None` 自动、`True/False` 强制），排错时可绕过 base_url 启发式。
- **依赖与文档**：`requirements.txt` 新增 `jsonschema`；`.env.example` 同步新字段并附 5 大网关切换示例。
- **回归测试**：`test_llm.py` 新增 3 类共 9 例——`TestOpenAIAdapterSchemaInjection`、`TestOpenAIAdapterExceptionHandling`（timeout 不触发 fallback；BadRequest 才 fallback）、`TestCallLLMJsonSchemaRetry`。

### 7. 按职业过滤 `experience_gains` 白名单 (`feat(eval)`)
- **SSOT 技能目录**：新增 `app/services/skill_catalog.py`，定义 `DATA_ANALYST_SKILLS`（11 项）/ `SOFTWARE_ENGINEER_SKILLS`（10 项）frozenset 与 `CAREER_SKILLS` 字典；提供：
  - `allowed_skills_for(career_id) -> frozenset[str]`；
  - `infer_career_id(mission_id, role_id, fallback)`：按 `mvp_mission_data_*` / `mvp_mission_software_*` 前缀 → 导师 `role_id` token → 兜底，三段式收敛。
- **`agent.evaluate_submission` 重写**：根据 `career_id` 动态构造 `_build_eval_schema(career_id)`，把 `experience_gains` 的 key `enum` 收敛到本职业技能集合，并 `additionalProperties: false`；同时为两职业各预置离线 fallback / error fallback 模板。
- **`eval_service` 前置路由 + 后置过滤**：进入 LLM 前用 `infer_career_id` 锁定职业；构造 `SubmissionEvaluateResponse` 前再次丢弃不在白名单内的键，确保 ORM 落库的 XP **永远归属正确职业岛屿**——杜绝了过去「软件工程师任务里 LLM 偶发给数据清洗加 XP」的串台。
- **Pydantic v2 强校验**：`EvaluationExperienceGains = RootModel[dict[str, int]]`，搭配 `@field_validator("root", mode="before")` 在 Pydantic 强制类型之前剔除 `bool` 与负值，规避 `"5"→5`、`True→1` 之类的隐式 coerce。
- **`MissionRecord.experience_gains` property 通用化**：不再写死技能列表，改为 `{k: v for k, v in raw.items() if isinstance(v, int) and not isinstance(v, bool)}`，由上游负责白名单职责。
- **回归测试**：`test_eval.py` 新增 `TestSoftwareEngineerEvaluation`（验证 SE 任务 ID 推断职业 + DA 键被剔除）；`test_schemas.py`（新）覆盖 `EvaluationExperienceGains` 三态拒绝矩阵 + `MissionRecordResponse` 兼容历史 `mock_data_url`。

### 8. API 数据契约容错与统一 (`fix(api)`)
- **`MissionGenerateResponse.mock_data_url` 收紧为 `HttpUrl`**：彻底拒绝 LLM 偶发返回的空串 / 相对路径，问题在生成端就被拦截而不是流到前端表现层。
- **`MissionRecordResponse._normalize_legacy_mock_data_url`**：before-validator 把库里存量的非法 URL（空串 / 非 http 前缀）归一为 `None`，避免老数据导致 `GET /user/sync` 整体 500（向后兼容）。
- **`submit_feynman_challenge` 走结构化响应**：新增 `FeynmanSubmitResponse`，路由内 `strip_text_artifacts(feedback_text)` 去除 LLM 自带代码栅与多余空行，前端可直接渲染、不再各自做清洗。

### 9. 已知待跟进
- **DashScope 真机首响应惩罚**：strict schema 模式下若 DashScope 对某些模型实际不支持 `response_format=json_schema`，会触发一次 BadRequest + fallback；目前仅 `warning` 级日志，可考虑加 base_url + model 维度缓存把「该组合不支持」结果记住，省一次往返。
- **schema 违规重试上限**：`call_llm_json` 当前最多重试 1 次，连续两次违规直接抛出。生产观察一段时间后可按抖动率决定是否提到 2 次。
- **`X-Player-Id` 仍是不可验真的字符串**：hybrid 模式便于本地多账户调试，但生产暴露前必须接入真实鉴权（JWT / Bearer Token），并在 `deps.py` 做单点替换；前端 store + header 链路已无需再动。
- **`evaluate_user_submission` 找不到 `mission_id` 时仍静默累加 XP**：里程碑 10 已记录，本里程碑未一并处理；待身份鉴权落地后统一改 `404`，避免恶意构造串号刷 XP。

---

## 🚩 [2026-05-29] 里程碑 10：单租户接缝抽离、agent/models 分层重构与运维硬化

### 1. agent 模块从 core/ 下沉到 services/ 并拆分静态资产
- **职责复位**：原 `app/core/agent.py`（486 行）承担了 LLM 编排 + 静态任务大纲 + 角色提示词 + 角色名映射 + fallback 回复五件事，违反「core 只放跨域基础设施」的分层约定。本次将其搬迁为 `app/services/agent.py` 并拆出 4 个数据驱动模块：
  - `services/mission_catalog.py`：8 大关卡静态规格（原内联 dict）
  - `services/role_mapping.py`：导师中文名 ↔ `role_id` 映射
  - `services/role_prompts.py`：从 `docs/prompts/system_prompts/*.md` 动态读取系统提示
  - `services/role_replies.py`：离线 fallback 回复模板
- **资源外置**：导师 fallback 文案从源码硬编码迁移到 `app/data/fallback_replies.json`，业务和文案彻底解耦。
- **agent.py 瘦身**：保留 `call_llm` / `create_mission` / `evaluate_submission` / `act_as_role` 四个真正的编排函数，行数压缩到原来的不到一半，单一职责清晰。

### 2. models 层正名：`models/models.py` → `models/orm.py`
- **消除重名地狱**：`from app.models import models` 这种写法既容易和 SQLAlchemy 自身的 `models` 概念混淆，又让 IDE 跳转歧义。统一改为 `from app.models import orm as models`。
- **取消 `__init__.py` re-export**：`app/models/__init__.py` 不再隐式导出 `User / SkillProgress / MissionRecord`，强制调用方写明子模块，避免循环依赖隐患。docstring 明确写出新约定。
- **全量调用点更新**：6 个业务文件 + 2 个测试同步切换，零回归。

### 3. 单租户接缝 `get_current_user_id` 落地（auth 预埋）
- **新建 `app/api/deps.py`**：定义 `get_current_user_id() -> str` 作为唯一的玩家身份解析点。MVP 阶段仍返回 `"default_player"`，但已经把"身份从何而来"这个决策点从 6 处分散硬编码收敛到 1 处。
- **API 层依赖注入**：`/api/v1/missions/generate`、`/api/v1/missions/evaluate`、`/api/v1/agent/chat`、`/api/v1/user/sync|career|skills/upgrade|feynman/submit` 全部改为 `Depends(get_current_user_id)`。
- **service 层签名外显**：`mission_service.generate_mission()` / `eval_service.evaluate_user_submission()` 新增 `user_id: str` 形参，删除函数体内的 `user_id = "default_player"`。后续接入真实 JWT/Session 只需改 `deps.py` 一处，service / API 全部零改动。

### 4. 安全与配置硬化
- **CORS 收紧**：`allow_origins=["*"]` 改为读取 `settings.cors_origins`（默认 `["http://localhost:5173"]`），生产环境只需 `.env` 改一行。
- **资产路径集中**：新增 `app/core/paths.py`，提供 `docs_dir()` / `data_dir()` 两个 `@cache` helper，并通过 `settings.docs_dir` 支持 override。`services/rag.py` 不再 `os.path.join(..., "../../../docs/knowledge_base")` 这种脆弱的相对路径手算，便于后续打包/容器化部署。
- **logger 替换 print**：`services/rag.py`、`api/v1/user.py` 中残留的 `print(...)` 全部改为模块级 `logger.warning/exception(...)`，与里程碑 9 的日志治理对齐。

### 5. 多配角系统提示词补全
- 在 `docs/prompts/system_prompts/` 下新增 5 份角色设定，对齐里程碑 7 中扩充的下拉配角列表：`pm_amy.md`（产品经理）、`stakeholder_product.md`、`stakeholder_sales.md`、`colleague_marketing.md`、`colleague_operations.md`。
- 这些 prompt 通过 `role_prompts.get_system_prompt()` 按需懒加载，无需重启服务即可生效。

### 6. 已知待跟进
- `get_current_user_id` 目前仍是单租户占位实现，正式接入鉴权前不建议把后端暴露到非本机环境；建议下一里程碑接入最小可用的 header/Bearer Token 校验。
- `evaluate_user_submission` 在 `mission_id` 找不到对应记录时仍会静默累加 XP，待真实鉴权落地后应改为 `404`。
- `act_as_role` 在拼装 system prompt 时仍直接注入 `delivery_requirements_json` 原始字符串，可在下一次小修中改用 ORM 的 `.delivery_requirements` 解码 property。

---

## 🚩 [2026-05-26] 里程碑 9：LLM 多提供商策略模式重构、统一异步接口与日志体系治理

### 1. 策略 + 工厂模式 LLM 抽象层落地 (Strategy + Factory Pattern)
- **新增 `app/core/llm/` 包**：把原本写死 Gemini 的 `urllib` 调用重构为「**统一接口 + 策略适配器 + 单例工厂**」三件套，目录结构 `base.py` / `factory.py` / `schema.py` / `providers/{gemini,openai_like,anthropic}.py`。
- **统一异步接口**：`LLMClient` ABC 定义 `async chat(prompt, system, json_schema) -> str`；`json_schema` 不为空时强制返回合法 JSON 字符串。预留 `stream_chat()` 抽象方法供后续真流式扩展。
- **官方 SDK 兜底**：三个适配器分别基于 `google-genai`、`openai`、`anthropic` 官方 SDK，自动获得重试、超时、token 计数等能力。`requirements.txt` 同步锁定版本下限。

### 2. 三个适配器精简到位、一档打通五大云厂商
- **`GeminiAdapter`**：使用 `genai.Client().aio.models.generate_content()`，schema 走 `response_mime_type` + `response_schema`，内部由 `to_gemini_schema()` 把标准小写 type 翻译为 Gemini 必须的大写格式（`object`→`OBJECT` 等）。
- **`OpenAICompatibleAdapter`**：使用 `AsyncOpenAI`，通过 `LLM_BASE_URL` 一键切换 OpenAI 官方、阿里千问 DashScope、DeepSeek、Moonshot、MiniMax、Ollama 本地等任意 OpenAI 协议端点。JSON 模式采用 `{"type":"json_object"}` + prompt 提示词组合，最大化兼容 DashScope 等不支持 strict json_schema 的国产网关。
- **`AnthropicAdapter`**：结构化输出走 `tool_use` 强制单工具模拟，把 JSON Schema 包成 `tools=[{"input_schema": ...}]` + `tool_choice={"type":"tool"}`，从响应的 `tool_use.input` 反序列化回 JSON。
- **架构瘦身**：删除了早期版本里 8 个 provider 别名（qwen / deepseek / moonshot / ollama 等）以及 `BASE_URL_PRESETS` / `sub_provider` 等冗余字段，让 `_PROVIDERS` 注册表收敛到 3 个核心项，新增厂商只需改 `.env` 一行。

### 3. 配置体系收敛与凭据兜底
- **5 个统一字段**：`app/core/config.py` 引入 `llm_provider` / `llm_api_key` / `llm_model` / `llm_base_url` / `llm_timeout`，彻底替换历史的 `gemma_api_key` / `gemini_base_url` / `gemini_model` 三项分散字段（已在本次清理中删除）。
- **Ollama 免 key 走法**：当 `LLM_API_KEY` 为空但 `LLM_BASE_URL` 已配（本地自托管场景），工厂自动填占位 key 以满足 SDK 校验。
- **单例缓存与大小写归一**：`get_llm_client()` 用 `@lru_cache(maxsize=1)` 返回单例，避免每次请求重建 HTTP client；`settings.llm_provider.lower()` 确保 `Gemini` / `gemini` / `GEMINI` 等写法都生效。
- **`.env` 文档化**：注释里直接给出五大国产/海外厂商的 `LLM_BASE_URL` 复制即用，降低切换心智成本。

### 4. agent.py 重构：去同步包装、统一异步入口、日志治理
- **删除 `call_gemini_api` 同步包装**：原 `asyncio.run()` 包装在 FastAPI 已运行事件循环里会崩（`RuntimeError: cannot be called from a running event loop`）；新版 `async def call_llm()` 直接供 `create_mission` / `evaluate_submission` / `act_as_role` 三处业务函数 `await`。
- **`print` → `logging`**：全文件 5 处裸 `print` 全部替换为 `logger.warning(...)` / `logger.exception(...)`，采用占位符延迟格式化、不绑异常变量等标准库推荐写法。预期降级路径用 `warning`、意料外异常用 `exception`（自动捕栈），FastAPI/uvicorn root logger 自动接管。
- **Schema 标准化**：业务函数中两处 JSON Schema 由 Gemini 大写格式（`"OBJECT"` / `"STRING"` 等）统一改写为标准小写 JSON Schema，跨厂商共用同一份定义。

### 5. 完整离线测试矩阵 + 选择性集成测试
- **`tests/test_llm.py` 10 个用例**（运行 0.006 秒，纯 mock，0 网络依赖）：
  - `TestSchemaNormalization`：验证小写→大写嵌套转换、原 schema 不被破坏；
  - `TestFactoryDispatch`：覆盖三大 provider 分发、自定义 base_url（千问 DashScope）、Ollama 无 key 模式、未配 key 异常、未知 provider 异常、单例缓存、大小写不敏感共 8 条；
  - `TestCallLLMWiring`：验证 `agent.call_llm` 透传到底层 `client.chat`。
- **`tests/test_llm_live.py` 真打通烟雾测试**：默认 `@unittest.skipUnless(os.getenv("RUN_LIVE_LLM"), ...)` 跳过，需要时 `set RUN_LIVE_LLM=1` 触发。3 条用例分别验证（a）配置解析正确、（b）普通对话通路、（c）`json_schema` 结构化输出可被 `json.loads`。实测 DashScope + Qwen 模型在 prompt 标注字段名时返回完全合规的 JSON。
- **全套测试通过**：`python -m unittest discover -s tests` 全绿，原 `test_eval.py` / `test_mission.py` / `test_rag.py` 在重构下保持零回归。

---

## 🚩 [2026-05-23] 里程碑 8：应用启动时异步 RAG 书架索引、数据库双引擎及前端空格流式渲染修复

### 1. 异步启动与 RAG 书架预热 (Lifespan Startup & Async RAG Indexing)
- **FastAPI Lifespan 引入**：引入 `lifespan` 钩子代替传统的 `startup`/`shutdown` 事件，在服务启动时自动运行表结构自愈，无需手动维护建表 SQL。
- **异步非阻塞索引**：在 `lifespan` 中利用 `asyncio.to_thread` 另起后台工作线程，扫描并读取 `docs/knowledge_base/` 中的物理 Markdown 文档。该设计将原本耗时数秒的 RAG 书架初始化转入后台完成，避免阻塞主事件循环，实现 API 服务“瞬时启动、秒级可用”。

### 2. 关系型存储双引擎支撑 (Relational DB Dual-Engine Switch)
- **配置驱动切换**：在 `app/core/config.py` 中拓展 `database_url` 环境变量字段，默认留空。
- **动态驱动适配**：在 `app/db/session.py` 中重构数据库引擎初始化逻辑。未配置 `DATABASE_URL` 时，系统自动回退到本地高兼容的单机 SQLite 并安全控制并发锁；一旦检测到环境变量包含 PostgreSQL 等标准 DSN 字符串，即自动切换为企业级双引擎架构，实现零成本平滑迁移。

### 3. 前端 SSE 空格与缩进流式渲染修复 (Frontend SSE Typography Fix)
- **精准断帧流解析**：修复了 `frontend/src/services/api.ts` 中打字机动画对于行首/行内连续空格及换行符吞噬的问题。废除对数据帧整行的 `.trim()` 盲目过滤，采用精细提取规则剥离 `data: ` 前缀，原汁原味地保留了英文单词边界、换行和 Markdown 代码块缩进。

### 4. 离线自动化单元测试矩阵 (100% Offline Testing Suite)
- **标准库 Unittest 矩阵**：为适应高度严苛的离线或公司内网 package 依赖限制，不引入 pytest 等外部测试运行器，基于 Python 标准库中的 `unittest` 框架设计了全套单元测试。
- **单元测试场景全覆盖**：
  - `test_mission.py`：测试任务自动创建、阶梯式前置依赖任务判定（`(completed_count % 4) + 1` 规律）与多角色自愈。
  - `test_eval.py`：测试 AI 评审多维结构化报告解析、经验 XP 折算累加、以及费曼挑战激活判定。
  - `test_rag.py`：验证 L2 向量归一化规范、确定性 Hashing 离线哈希计算，以及 Markdown 标题级分块切割精准度。
- **NumPy 兼容性对齐**：重构测试比对断言，采用逐个元素比对，彻底避开了 ChromaDB 底层返回 numpy 类型与 unittest 列表直接对比导致的 Truth Value 歧义报错。

### 5. 绿色构建与部署手册落地 (Build Green & Setup Manual)
- **2D 像素风部署手册**：将空白的 `docs/development/setup-guide.md` 全量填充为保姆级部署调试指南。
- **全量编译双绿通过**：前端 `npm run build`、后端 `py_compile` 及标准库测试全绿通过，保证了项目的 100% 安全健康。

---

## 🚩 [2026-05-21] 里程碑 7：阶梯式任务晋升、多维角色扮演与确定性 RAG 书架升级

### 1. 阶梯式关卡顺序晋升 (Task 1 ➔ Task 4)与费曼状态自愈
- **费曼通关状态更新**：在 `/feynman/submit` 中，通关费曼挑战后将状态自愈修改为 `"completed"`，使任务真正完结。
- **动态阶梯生成**：在 `mission.py` 中自动查询 SQLite 中当前职业已通关的任务数，利用 `(completed % 4) + 1` 锁定任务阶段，并分发对应阶梯任务。
- **高保真任务大纲**：在 `agent.py` 的 `create_mission` 中实现了包括 `UserService`、`api-design`、`CouponService`、`N+1 SQL`等 8 大关卡的本地高保真 fallback 离线库。

### 2. 上下文感知的多角色扮演 (Context-Aware Multi-role Dialogue)
- **动态上下文注入**：`act_as_role` 在收到用户消息时，自动拉取数据库中的 active 任务。如果存在，将任务描述与交付标准格式化追加至 Gemini 提示词中，赋予 AI 导师针对当前实战内容给予具体、贴合指导的能力。
- **企业级多配角扩充**：在 `get_system_prompt` 中补充了市场专员、运营经理、销售总监、产品经理的全部系统设定与口头禅，并提供完整的 fallback 回复模板。

### 3. 确定性 Hashing 向量化与 Hybrid 混合检索
- **MD5 确定性特征哈希**：引入 `hashlib.md5` 替换系统自带的易随重启变动的 `hash()`，完美锁定了向量特征值。
- **RAG 子树遍历与唯一 chunk ID**：采用 `os.walk` 遍历子集，并结合相对物理路径生成完全不冲突的 chunk 唯一键值。
- **关键字词频加权 (Hybrid Seek)**：在 `query_knowledge_base` 中加入与查询词词频重叠的加权 boost，极大增强了垂直领域的召回精度。

### 4. 前端交互响应与编译双重绿化
- **availableMentors 配角扩增**：在数据分析大厅增加了 5 位可选角色的头像与元数据展示。
- **切换监听 (Dropdown Switcher)**：加入了 `watch` 监听器，每次选择新导师时，Pinia 都会获得该角色特定的首句问候，打造浸入式体验。
- **绿色双检构建**：后端 Python py_compile 以及前端 `npm run build` 全量检测通过，实现 100% 零编译警告构建。

---

## 🚩 [2026-05-21] 里程碑 6：SQLite 关系型数据库持久化与前端 Pinia 状态双向全量同步

### 1. SQLAlchemy 关系型数据库 ORM 实体设计与自愈初始化
- **核心表定义**：在 `backend/app/models/models.py` 中，定义了三大关系型数据库实体：
  - `users`：持久化玩家账号属性（包含默认 `"default_player"` ID、累计总 XP 以及当前活跃职业岛屿 `current_career_id`）；
  - `skill_progress`：保存每个技能节点（如代码调试、数据清洗）的当前 manual `level` 与 `experience` 经验点，加持联合唯一索引；
  - `mission_records`：多维记录生成的任务参数（标题、描述、测试 CSV 链接、JSON 格式交付物规范、用户提交文本、AI 老师多维反馈、以及费曼挑战的状态与追问内容）。
- **零管理表自愈**：在 `backend/app/main.py` 启动阶段，引入 `base.metadata.create_all(bind=engine)` 在应用拉起时自动检测并建表，免去繁琐的人工迁移负担。

### 2. 后端 CRUD 路由开发与核心服务双向注入
- **任务接取持久化**：重构了 `MissionService`。当玩家接取任务时，系统会自动在数据库生成一条包含下载链接、交付物要求的 `"active"` 状态任务记录，并将前序未完结任务置为 `"failed"`。
- **评审与经验值结算**：重构了 `EvaluationService`。大模型下发多维评审报告后，系统会自动更新任务文本与反馈、对各个技能节点进行经验增量更新、累加玩家账户 `total_xp`，并在触发费曼挑战时标记 `"feynman_active"`。
- **同步与 CRUD API**：新增 `/api/v1/user/sync`（拉取并初始化玩家数据与进行中任务）、`/api/v1/user/career`（保存活跃职业岛屿）、`/api/v1/user/skills/upgrade`（手动升级技能并扣减经验）、以及 `/api/v1/user/feynman/submit`（提交费曼大白话解释，由 Gemini 语义打分并平滑归档当前任务）。

### 3. 前端 Pinia 状态树双向无缝数据恢复 (Reload Restoration)
- **API 接口打通**：在 `frontend/src/services/api.ts` 中新增全套数据库 CRUD 方法。
- **全量状态重建**：在 `App.vue` 挂载阶段（`onMounted`），前端向后端拉取玩家最新进度：
  - 调用 `userStore.syncFromBackend` 恢复所处岛屿及累计经验；
  - 调用 `skillStore.syncFromBackend` 结合基础经验，依公式 `Math.round(base * Math.pow(1.3, level))` 实时重建各层级升级经验进度；
  - 调用 `missionStore.syncFromBackend` 完全恢复未完结的任务详情、未提交或已提交并处于费曼追问状态下的交互界面。
- **高级 UX 秒恢复**：玩家如果在任务进行中或费曼挑战弹窗阶段刷新页面，系统能自动定位进度并跳过世界地图、直达特定的工作区与问题弹窗，提供 100% 极具沉浸感的沙盒留存体验。

## 🚩 [2026-05-21] 里程碑 5：全量沉浸式像素风前端及本地 RAG/Gemini 后端核心实现落地

### 1. 复古 2D 像素风前端开发与构建绿化
- **像素 UI 库**：搭建了 100% 自研的 Vanilla CSS 像素视觉系统，开发了 `PixelButton` (带 Web Audio 8位电音)、`RetroDialog` (RPG 弹窗)、`PixelProgressBar` (分段健康经验条) 等基础组件。
- **动态交互页面**：实现了职业大厅 (`LobbyView`)、导师中枢 (`CareerHubView` 含 SVG 动态技能连线) 与报告实验室 (`MissionInteractionView` 含费曼追问对话框)。
- **零警告编译**：全面清理了未使用变量与类型声明冲突，通过 `npm run build` 100% 成功输出高压缩包。

### 2. 本地 RAG 向量书架引擎全量激活 (ChromaDB + Custom Hashing)
- **零下载向量计算**：设计了自定义 128 维特征哈希嵌入函数 (`CustomHashingEmbeddingFunction`)，摆脱了外部大模型库下载的体积负担与网络限制，实现 100% 本地极速自愈。
- **自动分块索引**：开发了段落结构化切割解析器，在应用启动或初次查询时，自动扫描并加载 `docs/knowledge_base/` 下的所有 Markdown 文档对齐 RAG 标准。
- **高匹配过滤**：实现符合 Pydantic 数据契约的 Top-3 语义相似度召回并附带匹配度评分。

### 3. Gemma/Gemini 核心大模型中枢原生对接
- **免依赖原生请求**：利用 Python 原生 `urllib` 构建极简且高鲁棒性的 Generative API RESTful 适配器。
- **JSON 强约束**：通过传入严格的 JSON Schema 与 `responseMimeType`，强制大模型进行结构化逻辑判定（支持任务描述生成与包含头衔鞭策的多维评审报告）。
- **个性化系统指令**：动态读取 `docs/prompts/system_prompts/` 文件夹下对应的导师设定（如高凌或郑莹），无缝承接特定角色人格。

---

## 🚩 [2026-05-21] 里程碑 4：分支合并、流式接口标准对齐与文档规格审计

### 1. 通信流式接口标准修复 (SSE Align)
- **原因**：通过审计发现，之前 `app/core/agent.py` 的流式输出虽然被声明为 Server-Sent Events (SSE) 协议，但实际仅为简单的裸字符串推送，不兼容标准浏览器 SSE 规范。
- **改进**：对 `/api/v1/agent/chat` 接口的流式包进行了重构封装，在后端路由中利用异步适配器对输出字符进行 `data: {char}\n\n` 标准数据帧格式化，确保前端 `EventSource` 等客户端能无缝拉起与解析，消除了潜在的联调隐患。

### 2. 物理目录规范化与文档同步审计
- **拼写纠正**：将原物理存储目录 `docs/knowlege base` 更改为符合标准蛇形命名、且拼写正确的 `docs/knowledge_base/`，并在全量文档及后续 RAG 读取逻辑中完成了路径引用的同步纠正。
- **系统文档审计**：
  - 更新了系统设计文档 `02-system-design.md`，同步了 `create_mission` API 的 `role_id` 入参，并明确了 SQLite 和 ChromaDB 存储架构的协作分工。
  - 升级了接口规格文档 `03-interface-spec.md`，追加了对于 SSE 标准帧的前后端通信协议警告，细化了 `/api/v1/careers` 系列接口的 Pydantic 强类型 Response Schema，并标准化了业务错误响应的 JSON 数据契约。

---

## 🚩 [2026-05-12] 里程碑 3：职业关卡一语料材料包及专职导师提示词落地

### 1. 专职导师 Prompts 全量落地
在 `docs/prompts/system_prompts/` 路径下落地了核心角色扮演系统提示词：
- `mentor_ling.md` (硅屿技术主管 - 高凌)
- `mentor_ying.md` (洞察之屿资深数据分析专家 - 郑莹)

### 2. 职业第一阶段剧本材料丰富化
在 `docs/prompts/data_task1/` 和 `docs/prompts/software_task1/` 目录下为首个任务引入了完善的实战物料：
- **`交付物范例.md`**：提供真实场景下的代码/报告标杆。
- **`角色扩展语料库.md`**：提供特定角色场景中的即时反馈，以便大模型具备高度仿真的人格。
- **`评估反馈语料库.md`**：包含多维评审话术库，赋能 Agent 极其精准与结构化的评价。
- **职业基础剧本**：由 `docs/career_software_engineer.md` 和 `docs/career_data_analyst.md` 驱动，形成了 3-4 个阶梯式演进任务。

---

## 🚩 [2026-05-10] 里程碑 2：后端框架代码初始化与存根实现 (MVP v1.0.0)

### 1. 工程结构落地
在项目根目录下创建了独立的 `backend/` 异步服务工程目录树：
- **环境依赖**：声明了 `requirements.txt` (包含 fastapi, pydantic, sqlalchemy, chromadb 等) 与 `pyproject.toml` 格式化规范。
- **核心配置**：实现 `app/core/config.py`，基于 `pydantic_settings` 统一管理 SQLite 连接字符串与全局开关。
- **数据契约**：实现 `app/models/schemas.py`，声明了任务生成、成果评审等高鲁棒性的强类型请求与响应实体。
- **持久化连接**：实现 `app/db/session.py`，配置了非阻塞的 SQLite 引擎池与轻量级 ChromaDB 客户端句柄。

### 2. Gemma 4 多角色 Agent 存根对接 (Stub Implementation)
根据 MVP 演示与前端极速联调的需求，在 `app/core/agent.py` 中完成了零延迟的固定 Mock JSON 存根逻辑：
- **`create_mission`**：固定输出“分析社区论坛用户活跃度下降原因”的详细任务描述、Mock CSV 下载链接及交付要求。
- **`evaluate_submission`**：固定返回多维反馈报告、技能点数增量（如数据清洗 +10）并随机触发费曼挑战。
- **`act_as_role`**：提供了标准 SSE 协议兼容的打字机流式问候生成器。

### 3. 聚合路由与主入口拉起
- 实现了模块化路由树：`api/v1/careers.py`, `api/v1/missions.py`, `api/v1/agent.py`。
- 在 `app/main.py` 中聚合路由并开启 CORS 跨域支持，通过本地 `python -m py_compile` 的全量编译验证，确保零语法错误。

### 4. 前后端通信接口规格落地
- 产出了详细的通信说明书：[docs/specification/03-interface-spec.md](../specification/03-interface-spec.md)。
- 明确界定了包含健康检查、资源搜索、任务生成评估与 SSE 沉浸式断帧（`\n\n`）在内的 5 大模块全量通信数据结构体示例。

---

## 🚩 [2026-05-10] 里程碑 1：前后端系统框架设计书确立

### 1. 架构规范产出
产出了系统规格设计书：[docs/specification/04-architecture-framework.md](../specification/04-architecture-framework.md)。
- **技术栈敲定**：前端采用 Vite + Vue 3 (搭配 Vanilla CSS 打造经典 2D 像素艺术风格)；后端采用 FastAPI 支撑高并发与结构化输出。
- **分层规划**：明确界定了前端视图、像素 UI 库、Pinia 状态机与服务层；后端路由、业务服务、Agent调度中枢与关系型/向量双引擎持久层。
- **拓扑与时序**：利用标准 Graphviz DOT 语法绘制了系统拓扑图与核心业务流转闭环。

---

## 🚀 后续开发推进指南 (Next Steps)

目前核心的前后端系统、真实大模型 Agent 适配与 ChromaDB 100% 本地 RAG 向量书架引擎均已全量实现，后续的长期开发建议围绕以下维度进行演进：

1. **富集职业剧本与任务线**：
   - 参照 `career_software_engineer.md` 与 `career_data_analyst.md` 中的剧本标准，引入更多阶段的中高级甚至全新职业维度关卡。
   - 为新任务编写配套的高质量 Markdown 最佳实践教程，放入 `docs/knowledge_base/` 中。当系统重启时，RAG 引擎将自动读取并分块索引，实现无缝扩容。
2. **多角色联调与高级 RAG 优化**：
   - 为更多 AI 配角（如产品经理 Amy、挑剔的外部客户等）建立标准 Markdown 系统提示词，在大语言模型评估或对话时注入不同的角色上下文。
   - 对 Hashing 向量分词权重与 Top-K 检索算法进行精细化召回调优。
3. **数据持久层迁移 (SQLite -> PostgreSQL)**：
   - 目前采用的轻量单文件 SQLite 已能支撑全套 MVP 闭环。未来当用户规模扩大时，可通过修改 `app/core/config.py` 中的 settings 连接串，将 SQLAlchemy 底座无缝平滑迁移至企业级 PostgreSQL 数据库。
