# CareerCraft Backend

FastAPI 异步后端,承载多角色 Agent 编排、任务/评估业务逻辑,以及本地 Markdown RAG 知识库检索。

---

## 1. 技术栈

| 维度 | 选型 |
| :--- | :--- |
| 语言 / 运行时 | Python 3.11+ |
| Web 框架 | FastAPI + Uvicorn |
| ORM / DB | SQLAlchemy + SQLite(`careercraft_mvp.db`) |
| 向量库 | ChromaDB(本地持久化,目录见 `chroma_persist_dir`) |
| 配置 | `pydantic-settings`(`.env` + 环境变量) |
| LLM | 统一 `LLMClient` 抽象 + Gemini / OpenAI 兼容 / Anthropic / Ollama 适配器 |
| 测试 | `unittest`(15 用例,~1.6s) |

---

## 2. 快速开始

### 方式一：推荐，用 Docker Compose 启动

在仓库根目录执行：

```bash
cp ../.env.example ../.env
cd ..
docker compose up --build
```

说明：

- `docker compose` 默认读取的是**仓库根目录、与 `docker-compose.yml` 同级**的 `.env`
- 因此 Docker 场景下请优先修改根目录 `.env`，而不是 `backend/.env`
- 当前 Compose 会将后端映射到 `http://localhost:8003`，前端映射到 `http://localhost:8004`
- 当前 Compose 中的 `ENVIRONMENT`、`SQLITE_URL`、`CHROMA_PERSIST_DIR`、`LOG_DIR`、`CORS_ORIGINS` 已在 `docker-compose.yml` 中写死，根目录 `.env` 主要用于 `MOCK_AGENT_OUTPUT`、`LLM_*`、`NEXT_PUBLIC_API_BASE_URL`

启动后访问：

- API：`http://localhost:8003`
- OpenAPI 文档：`http://localhost:8003/docs`
- 前端：`http://localhost:8004`

### 方式二：本地直接运行后端

```bash
cd backend
python -m venv venv
# Windows
.\venv\Scripts\activate
# *nix
source venv/bin/activate

pip install -r requirements.txt

# 离线开发(无需 API Key): .env 中设 MOCK_AGENT_OUTPUT=true，默认即是
python -m app.main
# 等价命令(显式 reload 排除日志):
uvicorn app.main:app --reload --reload-exclude=logs/* --reload-exclude=*.log
```

启动后访问:

- API:`http://127.0.0.1:8000`
- OpenAPI 文档:`http://127.0.0.1:8000/docs`
- 健康检查:`GET /`

---

## 3. 目录结构

```text
backend/
├── app/
│   ├── main.py                # FastAPI 实例、CORS、路由注册、lifespan(建表 + 异步灌库)
│   ├── api/
│   │   ├── deps.py            # FastAPI Dependency(目前仅 get_current_user_id 占位)
│   │   └── v1/                # 路由分片:careers / missions / user / agent
│   ├── core/                  # 基础设施层(无业务逻辑、无业务依赖)
│   │   ├── config.py          # pydantic-settings,全局 settings 单例
│   │   ├── logging_config.py  # dictConfig:root / uvicorn / careercraft.llm 三通道
│   │   ├── paths.py           # 仓库根、docs_dir、data_dir(均带 @cache)
│   │   └── llm/               # LLM 抽象:base / factory / schema / audit + providers/*
│   ├── services/              # 业务逻辑 & 资源加载
│   │   ├── agent.py           # Agent 编排:call_llm / create_mission / evaluate_submission / act_as_role
│   │   ├── mission.py         # 任务生成业务流(写库 + 调 Agent)
│   │   ├── eval.py            # 评估业务流(经验值结算 + 调 Agent)
│   │   ├── rag.py             # Markdown 分块 / ChromaDB 灌库 / 检索
│   │   ├── mission_catalog.py # 按 role 加载 data/missions/*.json(@cache)
│   │   ├── role_prompts.py    # 按 role_id 加载 docs/prompts/system_prompts/*.md(@cache)
│   │   ├── role_mapping.py    # 自由文本角色名 → 规范 role_id
│   │   └── role_replies.py    # 按 role+mission 加载 fallback 回复模板(@cache)
│   ├── data/                  # 业务数据(JSON):
│   │   ├── missions/          #   软件 / 数据双职业的关卡剧本
│   │   └── fallback_replies.json
│   ├── db/session.py          # Engine / SessionLocal / Base
│   └── models/                # ORM (orm.py) + Pydantic (schemas.py)
├── tests/                     # unittest 用例(test_llm / test_eval / test_mission / test_rag)
├── chroma_data/               # ChromaDB 持久化目录(运行时生成)
└── logs/                      # 日志(运行时生成),logs/llm/ 下为审计 JSONL
```

---

## 4. 分层约定

| 层 | 职责 | 不该做的事 |
| :--- | :--- | :--- |
| `api/v1/*` | HTTP 适配:取 Dependency、调 service、组装响应 | 业务规则、直接调 LLM |
| `services/*` | 业务流程 + 资源加载 + Agent 编排(`agent.py` 把 LLM 与数据层粘起来) | 处理 HTTP / FastAPI 概念 |
| `core/llm/*` | LLM SDK 适配 + 审计装饰器 | 任何业务语义 |
| `core/{config,paths,logging_config}` | 全局基础设施单例 | 任何依赖 services 的引用 |

依赖方向:`api → services → core`,反向禁止。`services/role_*` 与 `services/mission_catalog` 都用 `functools.cache`,文件只在首次访问时读盘。

---

## 5. 关键配置项

通过 `.env` 或环境变量加载(详见 [app/core/config.py](app/core/config.py)):

| 配置项 | 默认 | 说明 |
| :--- | :--- | :--- |
| `environment` | `development` | 非 `production` 时启用文件日志(含 LLM 审计 JSONL) |
| `log_dir` | `./logs` | 日志根目录;`logs/llm/` 下为每次 LLM 请求/响应 |
| `sqlite_url` | `sqlite:///./careercraft_mvp.db` | SQLite 路径;设 `database_url` 可覆盖 |
| `chroma_persist_dir` | `./chroma_data` | ChromaDB 落盘目录 |
| `cors_origins` | `["http://localhost:5173"]` | CORS 白名单,生产务必收紧 |
| `docs_dir` | _自动_ | 留空时由 `core/paths.py` 解析仓库根下的 `docs/` |
| `llm_provider` | `gemini` | `gemini` / `openai` / `anthropic` / OpenAI 兼容(配合 `llm_base_url`) |
| `llm_api_key` | _空_ | 留空或 `mock_agent_output=true` 时走离线 stub |
| `llm_model` / `llm_base_url` / `llm_timeout` | _空 / 60_ | 适配器级覆盖；`llm_timeout` 单位为**秒** |
| `llm_retry_on_timeout` | `true` | 仅对超时/连接错误做一次有限退避重试 |
| `mock_agent_output` | `true` | 离线开关;`true` 时所有 Agent 调用走本地仿真 |
| `auth_mode` | `anonymous` | 认证模式: `anonymous`/`hybrid`/`jwt` |
| `jwt_secret` / `jwt_algorithm` | `null` / `HS256` | JWT  |

---

## 6. LLM 与审计

- **工厂**:[app/core/llm/factory.py](app/core/llm/factory.py) `get_llm_client()` 单例缓存,根据 `llm_provider` 构建适配器,统一外包一层 `AuditingLLMClient`。
- **审计**:`AuditingLLMClient` 拦截每次 `chat()`,以 JSONL 写入 `logs/llm/YYYY-MM-DD.jsonl`,字段值超 8KB 自动截断。
- **离线 Stub**:`settings.mock_agent_output=true` 或缺 API Key 时,`core/agent.py` 走本地 fallback(任务取自 `data/missions/*.json`,评估给出确定性 stub 分数),不发起任何外部请求。

---

## 7. 身份解析与迁移策略

当前后端已通过 [app/api/deps.py](app/api/deps.py) 的依赖注入统一身份入口：

- `get_current_identity(request)`：返回标准化身份上下文 `IdentityContext`
- `get_current_user_id(request)`：兼容包装，供现有路由/Service 继续使用 `user_id: str`

默认模式为 `auth_mode=anonymous`，要求请求携带 `X-Player-Id`（UUIDv4）。

认证模式说明：

- `anonymous`：仅接受 `X-Player-Id`
- `hybrid`：优先尝试 `Authorization: Bearer ...`，失败时回退到 `X-Player-Id`（迁移期推荐）
- `jwt`：仅接受 `Authorization: Bearer ...`

---

## 8. 测试

```bash
cd backend
.\venv\Scripts\python.exe -m unittest tests.test_llm tests.test_eval tests.test_mission tests.test_rag
```

- 默认 `MOCK_AGENT_OUTPUT=true`,1~2 秒跑完 15 用例。
- 若需要打真实 LLM(`test_llm_live.py` 等),显式取消 mock 并配置 `llm_api_key`。

---

## 9. 主要 API 端点

| 方法 | 路径 | 用途 |
| :--- | :--- | :--- |
| `GET` | `/api/v1/careers/...` | 职业列表 / 详情 |
| `POST` | `/api/v1/missions/generate` | 生成下一关任务 |
| `POST` | `/api/v1/missions/evaluate` | 提交并评分 |
| `GET` | `/api/v1/user/profile` 等 | 玩家档案 / 技能 / 费曼挑战 |
| `POST` | `/api/v1/agent/chat`(SSE) | 角色扮演对话流 |

完整 schema 见 `/docs`。
