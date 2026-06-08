# 👾 CAREERCRAFT MVP 部署与开发调试指南 (System Setup & Deployment Manual)

本指南旨在帮助开发团队与后续接手的工程师快速在本地或生产环境拉起 **CareerCraft** (AI 驱动的职业模拟沙盒 MVP) 的前后端服务。本系统融合了复古 2D 像素艺术美学与现代 AI 驱动的核心引擎，实现了沉浸式的职业实战演练。

---

## 🛠️ 系统整体架构拓扑 (Architecture Overview)

```mermaid
graph TD
    %% Frontend Subsystem
    subgraph Frontend [前端像素 UI 系统]
        A[Vite + Vue 3 App] --> B[Pinia 状态存储]
        B --> C[Pixel UI 像素组件库]
        A --> D[EventSource SSE 接收适配器]
    end

    %% Backend Subsystem
    subgraph Backend [后端 FastAPI 异步中枢]
        E[FastAPI API 路由网关] --> F[MissionService 任务服务]
        E --> G[EvaluationService 评审服务]
        E --> H[AgentService 导师交互/SSE]
        F & G & H --> I[Generative Model Adaptor / Gemini API]
    end

    %% Storage Engine
    subgraph Storage [持久化与检索双引擎]
        F & G --> J[SQLAlchemy ORM]
        J --> K[(SQLite / PostgreSQL 双引擎)]
        H --> L[Custom Local RAG / ChromaDB]
    end

    D -- "Server-Sent Events (SSE)" --> H
    A -- "HTTP CRUD" --> E
```

---

## 💻 1. 前端服务搭建 (Frontend Setup)

前端基于 **Vue 3 (TypeScript) + Vite** 构建，完全采用 Vanilla CSS 手写像素视觉系统。

### 📋 前期准备
- **Node.js**: 推荐 v18.0.0 或更高版本 (支持 ES Modules)
- **Package Manager**: `npm` (系统自带) 或 `yarn`

### 🚀 启动步骤
1. 进入前端物理工作目录：
   ```bash
   cd frontend
   ```
2. 安装项目依赖：
   ```bash
   npm install
   ```
3. 启动本地开发热重载服务器 (Vite Dev Server)：
   ```bash
   npm run dev
   ```
   > [!NOTE]
   > 默认启动在 `http://localhost:5173`。Vite 会自动探测端口冲突并向后顺延。

4. 编译生产环境静态资源：
   ```bash
   npm run build
   ```
   > [!TIP]
   > 前端构建已开启严格的 `vue-tsc` 类型检查。打包产物将输出至 `dist/` 文件夹，具有极高的静态压缩率。

---

## 🐍 2. 后端服务搭建 (Backend Setup)

后端基于 **FastAPI** 异步 Web 框架构建，配合 **SQLAlchemy ORM** 实现数据管理，并通过 **ChromaDB** 提供本地 RAG 知识检索。

### 📋 前期准备
- **Python**: 3.11 或更高版本
- **Virtualenv**: 强烈建议使用虚拟环境进行隔离

### 🚀 启动步骤
1. 进入后端物理工作目录：
   ```bash
   cd backend
   ```
2. 创建并激活虚拟环境：
   ```bash
   # MacOS / Linux
   python3 -m venv venv
   source venv/bin/activate

   # Windows
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. 安装依赖包：
   ```bash
   pip install -r requirements.txt
   ```
4. 启动后端 ASGI 服务器 (Uvicorn)：
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   > [!NOTE]
   > 默认启动在 `http://127.0.0.1:8000`。
   >
   > FastAPI 会自动在 `http://127.0.0.1:8000/docs` 渲染出符合 OpenAPI 规范的 Swagger UI 交互式调试文档。

---

## 🛢️ 3. 持久化存储与双引擎切换 (Relational Database Configuration)

本系统采用配置驱动（Configuration-driven）的 **关系型存储双引擎设计**。

### ⚙️ 切换规则
系统通过 `backend/app/core/config.py` 读取环境变量或本地配置。
- **默认状态 (本地单机极速自愈)**：
  如果不配置任何数据库环境变量，系统会自动在 `backend/` 下创建名为 `careercraft_mvp.db` 的本地 **SQLite** 数据库，并通过连接池参数规避多线程竞争。
- **企业级生产模式 (PostgreSQL 迁移)**：
  当用户需要高并发或容器化部署时，只需在环境中注入环境变量 `DATABASE_URL` 即可。

### 📝 环境变量配置示例
在 `backend/` 目录下创建一个 `.env` 文件（或直接在操作系统 shell 中 export）：
```env
# 留空时默认回退到本地 SQLite (sqlite:///careercraft_mvp.db)
DATABASE_URL=postgresql://db_user:db_password@localhost:5432/careercraft
```

> [!IMPORTANT]
> **零管理自愈建表 (Self-Heal Schema)**:
> 无论是 SQLite 还是 PostgreSQL，系统启动时，FastAPI 注册的 `lifespan` 钩子均会自动执行表结构自愈检测。如果物理表不存在，将自动根据 ORM 实体创建全部基础表（`users`、`skill_progress`、`mission_records`），无需工程师手动运行任何 SQL 初始化脚本。

---

## 📚 4. 本地 RAG 向量书架预热 (Local Hashing RAG & ChromaDB)

系统配备了一个 RAG 知识库，用于在玩家与 AI 导师交互时提供垂直领域的专业知识支撑。

### 🔍 运行原理
1. **启动预温**：应用拉起时，FastAPI 的 `lifespan` 会利用 `asyncio.to_thread` 另起一个后台工作线程，扫描 `docs/knowledge_base/` 目录下的物理 Markdown 文档。
2. **唯一 Key 标识**：根据文件物理相对路径自动映射目录，生成完全唯一的分块 chunk ID，防止主键冲突。
3. **确定性 Hashing 特征提取**：系统使用自研的 **128 维 MD5 特征哈希算法**（`CustomHashingEmbeddingFunction`），完全避开了庞大的外部 Python 深度学习模型下载，实现 100% 毫秒级本地计算。
4. **混合检索 (Hybrid Seek)**：采用向量相似度 + 关键词词频加权 (Overlap Frequency Boost) 的混合召回算法，检索出最精准的 Top-3 核心知识，追加注入到大模型系统提示词中。

---

## 🧪 5. 自动化测试矩阵执行 (Standard Library Automated Testing)

为保障国内或企业局域网下“零外网 PyPI 依赖”的极致高可用调试，我们抛弃了对外部测试运行器的强制依赖，完全基于 Python 标准库中的 `unittest` 框架设计了全量单元测试用例。

### 🚀 运行命令
在后端激活虚拟环境后，于 `backend/` 路径下运行：
```bash
./venv/bin/python -m unittest discover -s tests
```

### 🔬 测试用例设计说明
- **[base.py](file:///Users/bkuang/Desktop/projects/careercraft_dev/backend/tests/base.py)**:
  封装了标准的 `unittest.TestCase` 测试基类。每次测试方法运行前，都会动态拉起一个 **内存 SQLite 数据库**（`sqlite:///:memory:`），并在执行结束后自动清空，实现用例级数据沙盒隔离。
- **[test_mission.py](file:///Users/bkuang/Desktop/projects/careercraft_dev/backend/tests/test_mission.py)**:
  对玩家接取任务流程、前序依赖不满足时的状态机保护、以及基于 `(completed_count % 4) + 1` 计算职业阶梯任务的数学规律进行闭环断言。
- **[test_eval.py](file:///Users/bkuang/Desktop/projects/careercraft_dev/backend/tests/test_eval.py)**:
  测试 AI 评审模型返回结构化 JSON 后，玩家累计 XP 及技能节点层级升级的动态经验折算，并检验费曼大白话挑战的触发。
- **[test_rag.py](file:///Users/bkuang/Desktop/projects/careercraft_dev/backend/tests/test_rag.py)**:
  验证特征哈希计算的幂等稳定性、L2 向量归一化规范，以及 Markdown 主标题与二级子标题切割分块的正确性。

---

## ⚠️ 常见故障排除 (Troubleshooting & Tips)

> [!WARNING]
> **1. Uvicorn 启动报错: SQLite Connection multi-thread error**
> - **原因**: 默认多线程下，SQLite 会锁定连接句柄。
> - **自愈**: 系统中已在 `session.py` 中引入 `{"check_same_thread": False}` 规避。请不要删除 `session.py` 中引擎创建时的 `connect_args` 参数。
>
> **2. 首次提问时 RAG 初始化耗时**
> - **改进**: 本地 RAG 已经全部重构为**应用启动时 Lifespan 异步加载**。如果是首次运行，系统日志会输出 `RAG: Populating knowledge base...`。后台线程索引完全不阻塞前端首屏及 API 请求，请在启动时静候 1~2 秒即可完成几百个核心知识分块的写入。
>
> **3. 前端流式打印丢失空格 / 换行混乱**
> - **原因**: SSE（Server-Sent Events）数据帧传输时，如果对整行数据执行 `.trim()` 会直接破坏 Markdown 缩进和英文段落空格。
> - **修复**: 系统已将流解析重构为精准按首个空格或字符切分。请保持 `frontend/src/services/api.ts` 中的流提取表达式结构，切勿再次进行全局 `trim()` 操作。
