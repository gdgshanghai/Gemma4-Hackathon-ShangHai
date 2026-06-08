# Soundspeed

**面向电影同期录音部门的本地离线 AI 场记助手。**

Soundspeed 由 **Gemma 4 E4B 多模态智能体**驱动，支持文本、语音、拍照等多种输入方式，实现片场信息的实时结构化处理。无论是同步录音、口头备注还是拍摄剧本照片，Gemma 4 都能自动提取场次、镜次、Take 编号、演员、NG/Keeper 状态等核心元数据，并通过 function calling 写入本地数据库。内置辅助语音识别与说话人分离模型，实现基础的录音实时转写。支持剧本文本/照片的行级比对、备注归档、自然语言查询及自动导出场记单。结构化数据可无缝对接 BWF/iXML 音频元数据，后期可一键生成报表，贯穿录音至剪辑的全流程离线闭环协作。

## 演示视频

**[▶ 观看 Demo（运行 Gemma 4 的电影同期录音本地 Agent）](Demo_Soundspeed.mp4)**（点击在 GitHub 内置播放器观看，视频随仓库提交于本目录）

---

**[技术选型与架构细节（TECHNICAL_REPORT）](TECHNICAL_REPORT.md)**

---

## 环境要求

| 组件 | 版本 / 说明 |
| --- | --- |
| Python | **3.12+** |
| Node.js | **≥ 20.19**（推荐 22 LTS），含 npm |
| 操作系统 | macOS（Apple Silicon，推荐）/ Windows 10+；纯 CPU 亦可运行（较慢） |
| 磁盘 | 预留 **约 7–8 GB** 给模型权重（首次运行自动下载） |
| 网络 | 仅**首次**下载模型权重需要联网；之后全程离线运行 |
| HuggingFace token | **可选**，仅说话人分离（pyannote）需要；不配则自动跳过分离，其余功能不受影响 |

> macOS 上若 `llama-cpp-python` / `pywhispercpp` 需要本地编译，请先装 Xcode Command Line Tools：`xcode-select --install`（多数情况直接装 PyPI 预编译 wheel，无需此步）。

---

## 快速开始

本项目用 [uv](https://docs.astral.sh/uv/) 管理 Python 环境与依赖（`pyproject.toml` + `uv.lock` 已按平台锁定）。按你的系统照下面**一条**完整路径走到底即可。

后端通过**环境变量**配置（`.env` 不会自动加载，需在 shell 中导出）：开发模式 `SOUNDSPEED_DEV=1` 用固定 token `devtoken` 并自动播种一个演示场次；也可用 `ADMIN_TOKEN=你的密钥` 自定义；两者都不设则随机生成一个 token 打印到控制台。

### macOS（Apple Silicon）

```sh
# 1. 装 uv（已装可跳过）
brew install uv

# 2. 获取代码
git clone https://github.com/yedianyang/Soundspeed.git
cd Soundspeed

# 3. 装后端依赖：自动建 .venv、缺 Python 3.12 一并下载
#    llama-cpp-python / pywhispercpp 的 wheel 自带 Metal，torch 取 MPS wheel，无需额外加速
uv sync

# 4. 启动后端（开发模式）
SOUNDSPEED_DEV=1 uv run python -m backend.api

# 5. 另开终端起前端
cd frontend
npm install
npm run dev
```

### Windows

```powershell
# 1. 装 uv（已装可跳过）
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. 获取代码
git clone https://github.com/yedianyang/Soundspeed.git
cd Soundspeed

# 3. 装后端依赖：自动建 .venv、缺 Python 3.12 一并下载；torch 已装成 CUDA（cu128）版
uv sync

# 4. 仅 NVIDIA 显卡：装 llama-cpp / pywhispercpp 的 CUDA 变体（纯 CPU 跳过这步）
uv run python scripts/install_accel.py

# 5. 启动后端（开发模式，二选一）
#    纯 CPU：
$env:SOUNDSPEED_DEV = "1"; uv run python -m backend.api
#    NVIDIA（上一步装过 CUDA，必须带 --no-sync，否则下次同步会把 CUDA wheel 还原成 CPU 版）：
$env:SOUNDSPEED_DEV = "1"; uv run --no-sync python -m backend.api

# 6. 另开终端起前端
cd frontend
npm install
npm run dev
```

**启动后（两个平台一致）：**

- 后端监听 `http://127.0.0.1:8000`（健康检查 `GET /healthz`）。
- **首次启动会自动从 HuggingFace 下载模型权重**（Gemma 4 E4B GGUF + 多模态投影器，共数 GB；以及 Whisper 模型），下载期间前端显示 `downloading / loading` 状态。
- 前端打开 `http://localhost:5173/admin`，进入「设置」对话框，填入管理员 token（开发模式即 `devtoken`）保存即可开始使用。
- 启用说话人分离（可选）：先在 HuggingFace 接受 pyannote 模型条款并拿到 token，启动后端时带上 `SOUNDSPEED_HF_TOKEN=hf_xxx`。

---

## 常用环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `ADMIN_TOKEN` | 随机生成 | REST/WS 鉴权 token（前端「设置」需填同一个） |
| `SOUNDSPEED_DEV` | — | `=1` 使用固定 token `devtoken` + 挂载调试端点 + 空库时播种演示场 |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | 监听地址/端口 |
| `SOUNDSPEED_DB` | `./data/soundspeed.db` | SQLite 数据库路径（自动创建） |
| `SOUNDSPEED_PROFILE` | — | 运行档位：`import`（Gemma 占算力做解析/视觉）/ `record`（让算力给 ASR、Gemma 退 CPU） |
| `SOUNDSPEED_HF_TOKEN` | — | pyannote 说话人分离所需；不配则跳过分离 |
| `SOUNDSPEED_LIVE_ASR` | 启用 | `=0` 关闭实时转写 |
| `SOUNDSPEED_DIARIZATION` | 启用 | `=0` 关闭说话人分离 |
| `SOUNDSPEED_ASR_MODEL` | `large-v3-turbo-q8_0` | Whisper 模型大小 |
| `SOUNDSPEED_AUDIO_DEVICE` | 首个可用 | 指定输入设备索引或名称 |

完整列表见 [`backend/api/__main__.py`](backend/api/__main__.py) 顶部 docstring。

---

## 验证安装（可选）

跑后端测试套件确认环境就绪：

```sh
uv run pytest backend/tests -q
```

测试依赖（pytest / pytest-asyncio / httpx）已随 `uv sync` 装好。核心逻辑用 `StubClient` 替身覆盖，无需 GPU/真实权重即可跑；预期约 **1000+ 用例通过**。

---

## 进阶：局域网手机 / 平板 HTTPS 访问（仅 macOS）

> 本机开发不需要这步。仅当你要用手机或 iPad 同 Wi-Fi 经 **HTTPS** 访问（浏览器的录音 / 拍照 / 上传需要安全上下文）时才配置。

前置：`brew install mkcert caddy`

一键配置（每台 Mac 各跑一次）：

```sh
./scripts/setup-https.sh
```

脚本会探测本机 `.local` 主机名 → 用 mkcert 生成证书 → 写 `frontend/.env.production` → 从 `Caddyfile.template` 渲染本机 `Caddyfile`（用 8443 高端口，免 sudo）。生成的 `certs/`、`Caddyfile`、`frontend/.env.production` 都被 gitignore。

然后分三步起服务：

```sh
cd frontend && npm install && npm run build && cd ..   # 前端生产构建
SOUNDSPEED_DEV=1 uv run python -m backend.api           # 起后端
caddy run --config ./Caddyfile                          # 另开终端起 Caddy
```

手机同 Wi-Fi 打开脚本末尾打印的 `https://<本机名>.local:8443/admin`，在「设置」手填 token（开发模式即 `devtoken`）。

手机需信任本机 mkcert 根 CA（否则 wss 连不上）：把 `$(mkcert -CAROOT)/rootCA.pem` 传到手机安装；iOS 还需到 设置 > 通用 > 关于本机 > 证书信任设置 打开「完全信任」。

完整说明见 [`docs/2026-06-07-https-lan-mobile-runbook.md`](docs/2026-06-07-https-lan-mobile-runbook.md)。

---

## 项目结构

```text
Soundspeed/
├── backend/            FastAPI 后端
│   ├── api/            REST + WebSocket 路由、启动入口（python -m backend.api）
│   ├── core/           事件编排 orchestrator / session / events
│   ├── llm/            Gemma 4 客户端、多模态 handler、LLMService、工具 schema
│   ├── pipelines/      L2(实录↔剧本) / NP(备注) / QP(查询) / SP(剧本解析) / 语音调度
│   ├── audio/          音频输入采集与声道处理（ASR 链路上游）
│   ├── vad/            语音活动检测：按端点把音频流切成语音段
│   ├── asr/            Whisper 实时转写
│   ├── diarization/    Pyannote 说话人分离与回填
│   ├── db/             DAL / schema / migrations
│   └── tests/          约 1000+ 用例
├── frontend/           React + Vite + TypeScript（npm run dev → :5173）
├── scripts/            install_accel.py（GPU 加速兜底）/ detect_device.py 等
├── docs/               架构与设计文档、技术报告、平台 runbook
├── requirements.txt    后端运行依赖（与 pyproject 同源；非 uv 环境的 pip 兜底）
└── pyproject.toml      项目元信息与依赖（uv / pip 同源）
```

---

## 故障排查

- **首次启动很慢 / 前端一直 `downloading`**：在下载模型权重（数 GB），耐心等待；确认能访问 HuggingFace。
- **说话人分离没生效**：需 `SOUNDSPEED_HF_TOKEN` 且已在 HuggingFace 接受 pyannote 模型条款；否则会自动跳过（其余功能正常）。
- **Windows 上 Gemma 跑在 CPU、很慢**：运行 `uv run python scripts/install_accel.py` 装 CUDA 版（之后启动后端记得带 `--no-sync`），参见 [`docs/2026-06-02-windows-llama-cpp-runbook.md`](docs/2026-06-02-windows-llama-cpp-runbook.md)。
- **8GB 显存设备录制时卡顿**：用 `SOUNDSPEED_PROFILE=record` 启动，把显存让给 Whisper/Pyannote。
- **前端调不通后端（401）**：确认前端「设置」里填的 token 与后端启动时一致。

---

## 许可

Apache-2.0
