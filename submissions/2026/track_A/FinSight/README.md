# FinSight 项目总览

`FinSight` 是本地研究工作台的前后端整合项目。它把财报下载、PDF 解析、Wiki 研究资产、智能分析、事实核查、持续跟踪、法务合规和多智能体聊天统一到一个 React 工作台中。

## 0. 2026-05-29 全量检查结论

本 README 按项目真实路径和当前运行状态更新。比赛规则只作为关注点，本项目文档的主线仍是“系统能做什么、如何运行、数据在哪里、证据如何回溯”。

### 0.1 当前主链路

| 环节 | 当前路径 | 运行状态 | 说明 |
| --- | --- | --- | --- |
| 主工作台前端 | `/home/maoyd/finsight/finall_all_front_0516/front` | `:5173` 正在运行 | React/Vite 工作台，覆盖搜索下载、解析、分析、核查、跟踪、法务、设置 |
| 聚合后端 | `/home/maoyd/finsight/backend` | `:10081/health` 正常 | 统一代理 Wiki、Hermes、多轮聊天、工作流、设置和下载文件管理 |
| PDF 下载服务 | `/home/maoyd/report-finder-service` | `:8000/health` 正常 | 巨潮资讯 A 股公告查询、最近财报筛选、本地下载 |
| PDF 解析服务 | `/home/maoyd/finsight/pdf2md_web` | `:5000/api/health` 正常 | MinerU/VLM 上游均健康，财务规则版本 `financial_rules_v14` |
| Wiki 知识库 | `/home/maoyd/wiki` | 10 家公司、50 个生成结果 | 当前前端和 Agent 的主知识库，不是 `finsight/wiki` 归档目录 |
| PostgreSQL 入库层 | `/home/maoyd/DB` | 本机 PostgreSQL 进程存在 | `document_full.json -> pdf2md schema`，作为证据增强和三表查询层 |
| 法律检索库 | Milvus `ic_legal_scanner` | Milvus 进程存在 | 法务助手默认使用 hybrid_search 检索法规依据 |
| 本地大模型 | Gemma4 vLLM `:8006` / Qwen3.6 vLLM `:8004` | 按需启动 | Gemma4 是本地主模型，设置页、语义增强和本地 Hermes 切换默认指向 `:8006`；Qwen3.6 保留为备用/手动切换模型 |

### 0.2 Hermes 智能体状态

| 智能体 | Profile 路径 | 端口 | 当前职责 |
| --- | --- | --- | --- |
| 财报问答 | `/home/maoyd/.hermes/profiles/finsight_assistant` | `8642` | 入口型问答、指标查询、证据溯源 |
| 智能分析 | `/home/maoyd/.hermes/profiles/finsight_analysis` | `8651` | 14 章年度财务诊断报告生成与质量门禁 |
| 事实核查 | `/home/maoyd/.hermes/profiles/finsight_factchecker` | `8649` | 分析报告事实、计算、证据链和风险遗漏核查 |
| 持续跟踪 | `/home/maoyd/.hermes/profiles/finsight_tracking` | `8650` | 跟踪事项、指标面板、预警、更新记录、综合跟踪报告 |
| 法务合规 | `/home/maoyd/.hermes/profiles/finsight_legal` | `8652` | Milvus 法规检索、合规问答、HTML 法律意见书 |

五个业务 gateway 均已通过 `/health` 检查。Hermes `state.db` 中保留各自会话与全文检索索引；这些数据库用于运行状态和历史检索，不作为对外提交材料正文。

### 0.3 数据资产实测快照

| 数据资产 | 路径 | 当前检查结果 |
| --- | --- | --- |
| PDF 解析任务库 | `/home/maoyd/finsight/pdf2md_web/tasks.db` | 216 条任务，全部 `completed` |
| Wiki 公司库 | `/home/maoyd/wiki/companies` | 10 家公司；每家公司 1 份 2025 年报；各有 3 个 metrics JSON 和 11 个 semantic JSON |
| 生成报告 | `/home/maoyd/wiki/companies/*/{analysis,factcheck,tracking,legal}` | 当前统计 50 个 HTML 结果：analysis 24、factcheck 11、tracking 11、legal 4 |
| 派生财务指标库 | `/home/maoyd/wiki/derived/financial_metrics.db` | 10 家公司、10 份报告、1111 条三表指标、0 条校验异常 |
| 聚合后端 SQLite | `/home/maoyd/finsight/backend/data/pet.db` | 437 条前端聊天消息、301 条互动日志、5 个成就定义 |
| KupasEval 语料 | `/home/maoyd/finsight/eval_datasets` | 100 条样本、10 家公司、10 个评测维度 |

### 0.4 决赛核心维度对应

| 评分维度 | 项目中最应展示的证据 |
| --- | --- |
| 创新性 25% | PDF 解析到可审计证据链、Wiki 语义层、多智能体分工、法务 Milvus 检索、KupasEval 评测语料闭环 |
| 技术难度 25% | 多服务编排、MinerU/VLM 解析、财务规则 `v14`、PDF 页码/bbox 溯源、PostgreSQL 证据增强、Hermes Runs SSE 恢复 |
| 完成度 20% | 5173 工作台可跑通完整链路，10 家公司数据闭环，五个 Agent gateway 健康，216 个解析任务完成 |
| 商业价值 15% | 面向 A 股年报研究、投研助理、合规初筛、持续跟踪预警和可审计报告生产，能降低研报生成与复核成本 |

### 0.5 评委技术说明

FinSight 的技术实现路径可以概括为“官方披露文件 -> 可审计结构化数据 -> Wiki/数据库证据层 -> 多智能体报告与复核 -> 前端工作台交互”。项目不是把大模型直接接到 PDF 上生成文本，而是先把年报拆成可定位、可验证、可复用的数据资产，再让不同智能体在明确边界内调用这些资产。

#### 技术架构

| 层级 | 组件 | 技术职责 |
| --- | --- | --- |
| 交互层 | React/Vite 主工作台 | 提供下载、解析、分析、核查、跟踪、法务、设置和聊天入口；通过 Vite 代理屏蔽多服务端口 |
| 聚合层 | FastAPI `backend` | 统一 API Gateway、Wiki 文件服务、Hermes Runs 代理、SSE 流式输出、工作流编排、健康状态汇总 |
| 文档处理层 | `report-finder-service` + `pdf2md_web` | 从巨潮下载官方 PDF，调用 MinerU/VLM 解析，并生成 Markdown、JSON、页码、bbox、质量报告和财务抽取结果 |
| 知识层 | `/home/maoyd/wiki` + PostgreSQL `pdf2md` schema | 保存公司目录、报告入口、metrics、evidence、semantic、document_full、三大表明细和证据引用 |
| 智能体层 | Hermes profiles | `assistant`、`analysis`、`factchecker`、`tracking`、`legal` 分工处理问答、分析、审校、跟踪和合规意见 |
| 检索与模型层 | Gemma4/Qwen3.6 vLLM、Milvus、reranker、Hermes provider | Gemma4 承担本地主模型调用，Qwen3.6 作为备用模型；支持 LLM 语义增强、法规 hybrid_search、事实核查与多轮问答生成 |
| 评测层 | `/api/eval/e2e` + `eval_datasets` | 将端到端链路暴露给 KupasEval，覆盖指标抽取、证据忠实度、风险识别和跟踪事项 |

#### 技术栈

| 分类 | 采用技术 | 选择原因 |
| --- | --- | --- |
| 前端 | React 19、TypeScript 6、Vite 8、Tailwind CSS v4、lucide-react、recharts | 快速构建复杂工作台，支持多页面路由、响应式布局、可视化和开发代理 |
| 聚合后端 | FastAPI、uvicorn、SQLModel、SQLite、httpx、sse-starlette | 适合多路由聚合、异步 HTTP 调用、SSE 流式通信和本地轻量状态保存 |
| PDF 解析 | Flask、MinerU API、VLM 服务、pypdf、SQLite 队列 | 兼顾本地任务管理、上游模型解析、结果缓存、重试和人工复核 |
| 数据存储 | Wiki 文件系统、PostgreSQL、Milvus、SQLite | 文件系统便于审计和演示，PostgreSQL 承载结构化证据，Milvus 支持法规语义召回，SQLite 保存本地状态 |
| 智能体 | Hermes Runs API、Kimi provider、MiniMax fallback、本地 Gemma4/Qwen3.6 | 多智能体可独立维护规则、模型和上下文；Gemma4 是本地主模型，Qwen3.6 保留 fallback |
| 评测 | KupasEval 语料、JSONL/CSV、E2E API | 将业务链路转成可评测样本和可复现实验接口 |

#### 数据处理流程

1. 用户在 `/search` 输入公司名或代码，`report-finder-service` 解析证券主体并从巨潮官方接口筛选年报 PDF。
2. PDF 下载到本地 `downloads/` 后，用户在 `/parse` 上传或选择该文件，`pdf2md_web` 写入 SQLite 任务队列。
3. 解析服务调用 MinerU/VLM 生成 Markdown、content list、图片、表格、页码、bbox 和上游模型输出。
4. 质量引擎补齐页码标记、表格索引、目录、脚注、图片语义、附注链接和 `document_full.json`。
5. 财务抽取模块识别三大表、主要会计数据和关键财务指标，执行单位归一、勾稽校验、异常提示和来源绑定。
6. 聚合后端工作流把核心产物导入 `/home/maoyd/wiki/companies/<company_id>`，再生成语义层并导入 PostgreSQL。
7. 五个 Hermes Agent 基于 Wiki、PostgreSQL、Milvus 和报告产物生成问答、分析报告、核查报告、跟踪报告和法律意见书。
8. 前端报告页通过统一 `ReportViewer` 展示 HTML，并把右侧专属 Agent 的对话上下文绑定到当前公司和当前报告。
9. `/api/eval/e2e` 将同一链路封装为评测接口，供 KupasEval 检查回答质量、证据忠实度和流程完整性。

#### 算法与模型

| 模块 | 算法/模型 | 作用 |
| --- | --- | --- |
| 公司解析与公告筛选 | 巨潮 `topSearch/query`、`hisAnnouncement/query`、本地候选排序 | 将自然语言公司输入映射到官方公告 PDF，过滤非目标报告 |
| PDF 结构恢复 | MinerU + VLM + 页码/bbox 对齐规则 | 将非结构化 PDF 转为可阅读 Markdown 与可机器处理 JSON |
| 表格与财务抽取 | 规则特征、表名/上下文匹配、财务项目别名、单位归一、三表勾稽公式 | 识别资产负债表、利润表、现金流量表和关键指标，并验证公式一致性 |
| 质量诊断 | schema 版本、候选表评分、缺页/空表/表头异常/指标缺失检测 | 提示需要人工复核的解析风险，避免错误数据进入分析 |
| 语义层构建 | 规则分段、evidence/segment/claim 绑定、本地 Gemma4 语义增强，Qwen3.6 备用 | 将年报内容转成业务画像、风险、事件、声明和复核队列 |
| 报告分析 | Hermes `finsight_analysis`、14 章模板、证据包、质量门禁 | 生成经营诊断型年度分析，不输出投资评级或目标价 |
| 事实核查 | 六维审校、财务公式复核、证据链校验、verdict 规则 | 对分析报告进行独立复核，输出 `approve/request_changes/block` |
| 持续跟踪 | 指标阈值、事项抽取、预警分级、更新记录合并 | 把一次性分析转成后续观察清单和预警系统 |
| 法务检索 | Milvus hybrid_search、关键词+向量+条款号召回、RRF、reranker | 让法务意见引用本机法规库，而不是模型记忆 |
| 聊天运行时保护 | SSE active run 恢复、重复输出检测、工具失败循环检测、引用链接补全 | 提升长任务稳定性，减少智能体陷入逐页扫描或工具错误循环的风险 |

#### 价值闭环

FinSight 的创新点在于把金融智能体从“会写报告”推进到“能被审计地写报告”：每个关键结论都尽量回到 PDF 页、表格、Markdown 行、Wiki evidence 或数据库记录。技术难度集中在多服务编排、PDF 结构恢复、财务口径校验、多智能体边界和可追溯引用；完成度体现为当前工作台已能展示 10 家公司、216 个解析任务、50 个 HTML 结果和五个健康 Agent；商业价值则落在投研、合规、审计底稿和企业私有化知识工作台四类场景。

当前项目不是单体应用，而是一个本地多服务系统：

- 主前端：React + Vite，负责所有页面和交互。
- 聚合后端：FastAPI，负责 Wiki 文件服务、聊天代理、工作流导入、设置、状态和本地 SQLite 数据。
- 外部 PDF 下载服务：`/home/maoyd/report-finder-service`，负责查询/下载 A 股公告 PDF。
- PDF 解析服务：`/home/maoyd/finsight/pdf2md_web`，负责 PDF 转 Markdown、结构化抽取、表格溯源和财务校验。
- Hermes Agent 网关：多个 profile 分别服务财报问答、分析、核查、跟踪、法务。

## 1. 当前结论

### 1.1 实际使用的前后端

| 层级 | 当前实际路径 | 默认端口 | 说明 |
| --- | --- | --- | --- |
| 主前端 | `/home/maoyd/finsight/finall_all_front_0516/front` | `5173` | 当前 UI 工作台，包含法务合规页和新版 agent 头像 |
| 聚合后端 | `/home/maoyd/finsight/backend` | `10081` | 当前主后端，Vite 重点代理到这里 |
| 旧前端 | `/home/maoyd/finsight/front` | 同源或静态端口 | 单页聊天 HTML，保留作兼容/调试，不是主 UI |
| PDF 下载服务 | `/home/maoyd/report-finder-service` | `8000` | 外部依赖项目，主前端 `/api/v1/*` 代理到它 |
| PDF 解析服务 | `/home/maoyd/finsight/pdf2md_web` | `5000` | 当前主目录内服务，主前端 `/pdfapi/*` 代理到它 |

### 1.2 当前支持的业务页面

| 前端路由 | 页面 | 主要依赖 | 说明 |
| --- | --- | --- | --- |
| `/` | 工作平台 | `/api/wiki/*` | 汇总 Wiki 公司、报告数量、近期任务 |
| `/search` | 搜索下载 | `report-finder-service :8000` + 聚合后端下载文件代理 | 查询财报公告、批量下载、查看/删除已下载 PDF |
| `/parse` | 财报解析 | `pdf2md_web :5000` + `/api/workflow/*` | 上传或选择已下载 PDF，解析、溯源、导入 Wiki/DB |
| `/analysis` | 智能分析 | `/api/wiki/*` + `/api/analysis/chat/*` | 展示 HTML 分析报告，右侧分析助手 |
| `/verify` | 事实核查 | `/api/wiki/*` + `/api/factchecker/chat/*` | 展示 HTML 核查报告，右侧核查助手 |
| `/tracking` | 持续跟踪 | `/api/wiki/*` + `/api/tracking/chat/*` | 展示 HTML 跟踪报告，右侧跟踪助手 |
| `/legal` | 法务合规 | `/api/wiki/*` + `/api/legal/chat/*` | 展示 HTML 法律意见书，右侧法务助手 |
| `/chat` | 财报问答助手 | `/api/chat/*` | 独立全屏普通问答 |
| `/settings` | 设置 | `/api/settings/*`、`/api/system/status` | 服务连接、本地/云端模型测试、系统状态 |
| `/help` | 帮助 | 前端本地 | 操作说明 |

## 2. 整体架构

```text
Browser http://localhost:5173
  |
  |-- /api/chat
  |-- /api/wiki
  |-- /api/analysis
  |-- /api/factchecker
  |-- /api/tracking
  |-- /api/legal
  |-- /api/settings
  |-- /api/system
  |-- /api/downloads
  |-- /api/workflow
  |-- /api/source, /api/pdf_page
  |       -> /home/maoyd/finsight/backend FastAPI :10081
  |
  |-- /api/v1/*
  |       -> report-finder-service FastAPI :8000
  |
  `-- /pdfapi/*
          -> pdf2md_web Flask :5000 (/api/*)

FastAPI :10081
  |
  |-- SQLite: backend/data/pet.db
  |-- Wiki: /home/maoyd/wiki/companies
  |-- Downloads: /home/maoyd/report-finder-service/downloads
  |-- PDF2MD source proxy: http://127.0.0.1:5000
  |
  |-- Hermes finsight_assistant :8642
  |-- Hermes finsight_factchecker :8649
  |-- Hermes finsight_tracking :8650
  |-- Hermes finsight_analysis :8651
  `-- Hermes finsight_legal :8652
```

## 3. 端口与健康检查

| 服务 | 端口 | 必需性 | 健康检查 |
| --- | --- | --- | --- |
| Vite 主前端 | `5173` | 必需 | `curl -s http://localhost:5173` |
| 聚合后端 FastAPI | `10081` | 必需 | `curl -s http://localhost:10081/health` |
| PDF 下载服务 | `8000` | 搜索下载页必需 | `curl -s http://localhost:8000/health` |
| PDF 解析服务 | `5000` | 财报解析页必需 | `curl -s http://localhost:5000/api/health` |
| Hermes assistant | `8642` | 普通聊天必需 | `curl -s http://localhost:8642/health` |
| Hermes factchecker | `8649` | 事实核查助手必需 | `curl -s http://localhost:8649/health` |
| Hermes tracking | `8650` | 跟踪助手必需 | `curl -s http://localhost:8650/health` |
| Hermes analysis | `8651` | 分析助手必需 | `curl -s http://localhost:8651/health` |
| Hermes legal | `8652` | 法务助手必需 | `curl -s http://localhost:8652/health` |
| MinerU API | `8003` | PDF 解析上游 | 由 pdf2md `/api/health` 汇总 |
| VLM API | `8002` | PDF 解析上游 | 由 pdf2md `/api/health` 汇总 |
| 本地 Gemma/Qwen vLLM | Gemma4 `8006` / Qwen3.6 `8004` | 模型设置测试、LLM 语义增强、本地 Hermes 配置 | OpenAI-compatible `/v1/chat/completions`；Gemma4 是默认本地主模型 |

## 4. 推荐启动方式

### 4.1 一键启动部分服务

项目根目录提供 `start_all.sh`，会启动：

- PDF 下载服务 `:8000`
- 聚合后端 `:10081`
- 主前端 `:5173`

```bash
cd /home/maoyd/finsight
./start_all.sh
```

注意：这个脚本不会启动 Hermes gateway、PDF 解析服务、MinerU、VLM 或本地大模型。

### 4.2 手动启动聚合后端

```bash
cd /home/maoyd/finsight/backend
uv sync
WIKI_ROOT=/home/maoyd/wiki uv run uvicorn main:app --reload --host 0.0.0.0 --port 10081
```

### 4.3 手动启动主前端

```bash
cd /home/maoyd/finsight/finall_all_front_0516/front
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### 4.4 启动 PDF 下载服务

```bash
cd /home/maoyd/report-finder-service
.venv/bin/python -m uvicorn report_finder_service.app:app --host 127.0.0.1 --port 8000
```

### 4.5 启动 PDF 解析服务

```bash
cd /home/maoyd/finsight/pdf2md_web
HOST=127.0.0.1 PORT=5000 ./run.sh
```

### 4.6 启动 Hermes Agent

不同业务助手依赖不同 Hermes profile。按需分别启动：

```bash
hermes profile use finsight_assistant
hermes gateway start

hermes profile use finsight_analysis
hermes gateway start

hermes profile use finsight_factchecker
hermes gateway start

hermes profile use finsight_tracking
hermes gateway start

hermes profile use finsight_legal
hermes gateway start
```

聚合后端调用 Hermes 的默认鉴权为：

```text
Authorization: Bearer change-me-local-dev
```

## 5. 目录结构

```text
finsight/
  README.md                         # 本总览
  start_all.sh                      # 启动 8000 + 10081 + 5173
  backend/                          # 聚合 FastAPI 后端
  finall_all_front_0516/
    README.md                       # 前端容器目录说明
    front/                          # 当前主 React/Vite 前端
    fron_template/                  # 模板/历史目录
  front/                            # 旧单页聊天 HTML
  tools/                            # 头像生成、抠图、动画、对比图脚本
  test/                             # 占位测试包
  wiki/                             # 项目内历史归档/样例数据，不是主 Wiki 根目录
  agent-avatar-archive-20260520/    # 当前确认版 agent 头像归档
  agent-avatar-archive-20260520.tar.gz
```

主 Wiki 数据不在本项目目录内，而在：

```text
/home/maoyd/wiki
```

主 PDF 下载服务与主 PDF 解析服务也在本项目目录外：

```text
/home/maoyd/report-finder-service
/home/maoyd/finsight/pdf2md_web
```

## 6. 数据目录与产物

| 数据 | 默认路径 | 产生者 | 消费者 |
| --- | --- | --- | --- |
| Wiki 公司库 | `/home/maoyd/wiki/companies` | PDF 解析导入、Agent 生成报告、脚本 | 聚合后端、前端报告页 |
| 聚合后端 SQLite | `/home/maoyd/finsight/backend/data/pet.db` | 聚合后端 | 聊天历史、宠物状态、成就 |
| 下载 PDF | `/home/maoyd/report-finder-service/downloads` | PDF 下载服务 | 搜索下载页、财报解析页、聚合后端下载文件代理 |
| PDF 解析结果 | `/home/maoyd/finsight/pdf2md_web/results` | PDF 解析服务 | 财报解析页、工作流导入 |
| PDF 解析任务库 | `/home/maoyd/finsight/pdf2md_web/tasks.db` | PDF 解析服务 | 财报解析页、工作流导入 |
| 头像前端资源 | `finall_all_front_0516/front/public/pet` | tools 脚本/人工确认 | 当前 UI |
| 头像归档 | `agent-avatar-archive-20260520` | 人工确认后归档 | 资产恢复/迁移 |

## 7. Vite 代理分发

代理配置位于：

```text
/home/maoyd/finsight/finall_all_front_0516/front/vite.config.ts
```

关键规则：

| 前端请求前缀 | 转发目标 | 说明 |
| --- | --- | --- |
| `/api/chat` | `http://127.0.0.1:10081` | 普通问答 |
| `/api/wiki` | `http://127.0.0.1:10081` | Wiki 公司/报告 |
| `/api/analysis` | `http://127.0.0.1:10081` | 分析助手 |
| `/api/factchecker` | `http://127.0.0.1:10081` | 核查助手 |
| `/api/tracking` | `http://127.0.0.1:10081` | 跟踪助手和跟踪业务 API |
| `/api/legal` | `http://127.0.0.1:10081` | 法务助手 |
| `/api/eval` | `http://127.0.0.1:10081` | KupasEval / E2E 评测接口 |
| `/api/settings` | `http://127.0.0.1:10081` | 模型配置 |
| `/api/system` | `http://127.0.0.1:10081` | 系统状态 |
| `/api/downloads` | `http://127.0.0.1:10081` | 已下载 PDF 文件代理 |
| `/api/workflow` | `http://127.0.0.1:10081` | PDF 结果导入 Wiki/DB |
| `/api/source`、`/api/pdf_page` | `http://127.0.0.1:10081` | PDF 溯源可读代理 |
| `/api/*` | `http://127.0.0.1:8000/*` | PDF 下载服务，去掉 `/api` 前缀 |
| `/pdfapi/*` | `http://127.0.0.1:5000/api/*` | PDF 解析服务，改写为 `/api` |

因为 `/api` 兜底会转发到 `8000`，新增聚合后端路由时必须在兜底 `/api` 之前添加更具体的代理前缀。

## 8. 聚合后端 API 总览

聚合后端所有 router 都挂在 `/api` 下。

### 8.1 聊天类 API

普通问答：

```text
POST   /api/chat
POST   /api/chat/stream
POST   /api/chat/stop
GET    /api/chat/active
GET    /api/chat/active/stream
GET    /api/chat/history
GET    /api/chat/sessions
POST   /api/chat/session
POST   /api/chat/session/{session_id}
DELETE /api/chat/session
```

业务 Agent 具备相同结构，只是前缀不同：

```text
/api/analysis/chat/*
/api/factchecker/chat/*
/api/tracking/chat/*
/api/legal/chat/*
```

### 8.2 Wiki 与报告

```text
GET    /api/wiki/companies/list
GET    /api/wiki/companies/recent-results
GET    /api/wiki/reports/search
GET    /api/wiki/companies/{company_dir}/reports
GET    /api/wiki/companies/{company_dir}/factchecks
GET    /api/wiki/companies/{company_dir}/trackings
GET    /api/wiki/companies/{company_dir}/legals
GET    /api/wiki/companies/{path}
DELETE /api/wiki/companies/{company_dir}/{result_type}/{filename}
```

可删除的 `result_type` 包括 `analysis`、`factcheck`、`tracking`、`legal`，且仅限 HTML 报告。

### 8.3 PDF 解析工作流

```text
GET  /api/workflow/task/{task_id}/status
GET  /api/workflow/task/{task_id}/preflight
POST /api/workflow/task/{task_id}/wiki-import
POST /api/workflow/task/{task_id}/semantic
POST /api/workflow/task/{task_id}/db-import
POST /api/workflow/task/{task_id}/run-remaining
GET  /api/workflow/job/{job_id}
```

用途：检查解析产物包、把报告入口和轻量 manifest 导入 Wiki，生成语义层，或将全量解析信息导入 PostgreSQL。Wiki 不作为全量解析产物仓库；全量信息保留在 `/home/maoyd/finsight/pdf2md_web/results/<task_id>` 和 PostgreSQL `pdf2md` schema 中。

`POST /api/workflow/task/{task_id}/semantic` 会先运行规则层脚本，再按设置页本地模型配置调用 Gemma4 做 LLM 语义增强。当前默认本地主模型为 `Gemma-4-26B-A4B-it-NVFP4`，OpenAI-compatible 地址为 `http://127.0.0.1:8006/v1`；需要时可在设置页切到 Qwen3.6 `http://127.0.0.1:8004/v1`。规则层输出仍在 `semantic/*.json`；模型增强层单独写入：

```text
/home/maoyd/wiki/companies/<company_id>/semantic/llm/<report_id>/
  enrichment.json
  business_profile.json
  claims.json
  risks.json
  events.json
  review_queue.json
  extraction_log.json
```

模型结果不覆盖规则事实；每条正式结果必须绑定已有 `segment_id` 和 `evidence_id`。

### 8.4 PDF 来源可读代理

```text
GET  /api/source/{task_id}/table/{table_index}
GET  /api/source/{task_id}/page/{page_number}
GET  /api/pdf_page/{task_id}/{page_number}
POST /api/source/{task_id}/table/{table_index}/correction
```

这些接口代理 `pdf2md_web :5000`，并在浏览器接受 HTML 时包装成可读页面。

### 8.5 设置、状态、下载、宠物

```text
GET    /api/settings/llm
PUT    /api/settings/llm
POST   /api/settings/llm/test
GET    /api/system/status
GET    /api/downloads/reports
GET    /api/downloads/report-file
DELETE /api/downloads/report-file
GET    /api/pet/state
POST   /api/pet/feed
POST   /api/pet/play
POST   /api/pet/rest
GET    /api/achievements
GET    /api/eval/e2e/health
POST   /api/eval/e2e
```

## 9. Agent 与头像资产

当前前端专业 agent 头像由 `AgentAvatar.tsx` 映射：

| Agent | API 前缀 | Hermes profile | 前端头像 |
| --- | --- | --- | --- |
| 分析助手 | `/api/analysis` | `finsight_analysis` | `public/pet/agent-drafts/finsight-analysis-avatar-animated-transparent.webp` |
| 核查助手 | `/api/factchecker` | `finsight_factchecker` | `public/pet/agent-drafts/finsight-factchecker-avatar-animated-transparent.webp` |
| 跟踪助手 | `/api/tracking` | `finsight_tracking` | `public/pet/agent-drafts/finsight-tracking-avatar-animated-transparent.webp` |
| 法务助手 | `/api/legal` | `finsight_legal` | `public/pet/agent-drafts/finsight-legal-avatar-animated-transparent.webp` |
| 普通财报助手 | `/api` | `finsight_assistant` | `public/pet/finsight-avatar-animated.webp` |

已确认版头像归档：

```text
/home/maoyd/finsight/agent-avatar-archive-20260520
/home/maoyd/finsight/agent-avatar-archive-20260520.tar.gz
```

## 10. 配置环境变量

| 变量 | 默认值 | 使用者 | 说明 |
| --- | --- | --- | --- |
| `WIKI_ROOT` | `/home/maoyd/wiki` | 聚合后端 | Wiki 根目录 |
| `REPORT_DOWNLOADS_ROOT` | `/home/maoyd/report-finder-service/downloads` | 聚合后端 | 已下载 PDF 根目录 |
| `PDF2MD_API_BASE` | `http://127.0.0.1:5000` | 聚合后端 | PDF 来源代理目标 |
| `PDF2MD_PROXY_TIMEOUT` | `60` | 聚合后端 | PDF 来源代理超时 |
| `PDF2MD_ROOT` | `/home/maoyd/finsight/pdf2md_web` | 工作流 | PDF 解析服务根目录 |
| `PDF_RESULTS_ROOT` | `/home/maoyd/finsight/pdf2md_web/results` | 工作流 | PDF 解析结果目录 |
| `WIKISET_ROOT` | `/home/maoyd/wiki/wikiset` | 工作流 | Wiki 构建脚本目录 |
| `SEMANTIC_SCRIPT` | `/home/maoyd/wiki/wikiset/extract_company_semantics.py` | 工作流 | 语义抽取脚本 |
| `LLM_SEMANTIC_SCRIPT` | `/home/maoyd/wiki/wikiset/llm_semantic_enrichment.py` | 工作流 | 本地模型语义增强脚本 |
| `LLM_SEMANTIC_ENABLED` | `true` | 工作流 | 是否默认生成 LLM 语义增强层 |
| `LLM_SEMANTIC_REQUIRED` | `true` | 工作流 | LLM 增强失败时是否让语义步骤失败 |
| `LLM_SEMANTIC_TIMEOUT` | `900` | 工作流 | LLM 增强脚本超时秒数 |
| `DB_IMPORT_SCRIPT` | `/home/maoyd/DB/PROGRAM/import_document_full_to_postgres.py` | 工作流 | PostgreSQL 导入脚本 |
| `FINSIGHT_CONFIG_DIR` | `backend/.finsight` | 设置页 | LLM 设置文件位置 |
| `FINSIGHT_LOCAL_LLM_BASE_URL` | `http://127.0.0.1:8006/v1` | 设置页、LLM 语义增强 | 本地主模型地址，默认 Gemma4 |
| `FINSIGHT_LOCAL_LLM_MODEL` | `Gemma-4-26B-A4B-it-NVFP4` | 设置页、LLM 语义增强 | 本地主模型名 |
| `FINSIGHT_QWEN36_LLM_BASE_URL` | `http://127.0.0.1:8004/v1` | 设置页备用预设 | Qwen3.6 备用模型地址 |
| `FINSIGHT_QWEN36_LLM_MODEL` | `Qwen3.6-35B-A3B-FP8` | 设置页备用预设 | Qwen3.6 备用模型名 |

## 11. 常见问题

### 11.1 工作台公司列表为空

检查：

```bash
curl -s http://localhost:10081/api/wiki/companies/list
ls -la /home/maoyd/wiki/companies
```

如果 `/home/maoyd/wiki/companies` 不存在或为空，前端不会有报告可展示。

### 11.2 搜索下载页接口 404

确认 `report-finder-service :8000` 已启动。前端 `/api/v1/*` 不是发给聚合后端，而是被 Vite 转给 `8000`。

### 11.3 财报解析页接口失败

确认 `pdf2md_web :5000` 已启动，并且 MinerU/VLM 健康：

```bash
curl -s http://localhost:5000/api/health
```

### 11.4 右侧业务助手一直转圈

确认对应 Hermes gateway 已启动：

```bash
curl -s http://localhost:8651/health   # analysis
curl -s http://localhost:8649/health   # factchecker
curl -s http://localhost:8650/health   # tracking
curl -s http://localhost:8652/health   # legal
```

### 11.5 法务页能打开但助手报错

法务报告列表依赖 `/api/wiki/companies/{company}/legals`，法务聊天依赖 `/api/legal/chat/stream` 和 Hermes `finsight_legal :8652`。报告展示正常不代表 Hermes 法务助手也已启动。

### 11.6 修改 Vite 代理后无效

Vite 代理配置只在 dev server 启动时读取。修改 `vite.config.ts` 后需要重启 `npm run dev`。

## 12. 文档入口

| 文档 | 内容 |
| --- | --- |
| `backend/README.md` | 聚合后端详细说明 |
| `finall_all_front_0516/README.md` | 当前前端容器目录说明 |
| `finall_all_front_0516/front/README.md` | 当前主前端详细说明 |
| `front/README.md` | 旧单页聊天 HTML |
| `pdf2md_web/README.md` | PDF 解析、溯源、质量报告和财务抽取服务 |
| `eval_datasets/README.md` | KupasEval / 端到端评测语料 |
| `tools/README.md` | 头像资产生成和归档工具 |
| `test/README.md` | 占位测试包说明 |
| `backend/hermes-api-multi-turn.md` | Hermes API 多轮对话记录 |
| `/home/maoyd/wiki/README.md` | 主 Wiki 知识库、公司目录、metrics/evidence/semantic 和多智能体产物 |
| `/home/maoyd/DB/README.md` | PostgreSQL `pdf2md` schema、入库脚本、查询 API 和结构化证据层 |
| `/home/maoyd/.hermes/profiles/finsight_assistant/README.md` | 普通财报问答 Agent |
| `/home/maoyd/.hermes/profiles/finsight_analysis/README.md` | 智能分析 Agent |
| `/home/maoyd/.hermes/profiles/finsight_factchecker/README.md` | 事实核查 Agent |
| `/home/maoyd/.hermes/profiles/finsight_tracking/README.md` | 持续跟踪 Agent |
| `/home/maoyd/.hermes/profiles/finsight_legal/README.md` | 法务合规 Agent |
| `/home/maoyd/.hermes/profiles/finsight_legal/milvus/README.md` | 法务 Milvus 法规向量库、embedding/reranker、1024 维向量和 hybrid_search 流程 |
| `/home/maoyd/report-finder-service/README.md` | 外部 PDF 下载服务 |
