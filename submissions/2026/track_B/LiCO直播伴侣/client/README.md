# LiCO 直播伴侣

LiCO（Live COmpanion）直播伴侣是一个面向主播的直播 Agent 软件。项目基于 Blivechat 与 OBS Studio 扩展开发，在原有弹幕展示能力之上，增加了弹幕、画面、音频、礼物和直播状态的多模态采集与分析能力。

客户端运行在主播电脑上，负责 B 站直播间连接、OBS 插件通信、浏览器 UI 展示和本地数据归档；AI 推理服务通常运行在远端 GPU 服务器上，通过 OpenAI 兼容接口提供 Gemma/Qwen 风格的多模态分析能力。

## 功能概览

- B 站直播间弹幕、礼物、舰长、醒目留言监听。
- OBS 插件采集推流事件、截图、麦克风音频和桌面音频。
- 直播中实时生成心理、语音、礼物、画面四类分析结果。
- 支持 Gemma 4 多模态模型进行联合分析。
- 支持直播归档、复盘、时间线和自动切片建议。
- 保留 Blivechat 原有的浏览器源样式生成、自定义表情、插件系统等能力。

## 项目结构

```text
.
├── main.py                         # 本地 Tornado 服务入口
├── api/                            # HTTP/WebSocket API 路由
│   ├── qwen_multimodal.py          # Gemma/Qwen 兼容多模态接口调用
│   ├── obs_bridge.py               # OBS 插件事件、截图、音频接收接口
│   ├── live_archive.py             # 直播归档接口
│   └── plugin.py                   # 插件管理接口
├── services/                       # 后端服务层
│   ├── psych_agent.py              # 心理状态分析 Agent
│   ├── obs_bridge.py               # OBS 状态缓存与广播
│   ├── live_archive.py             # 直播复盘与归档逻辑
│   └── plugin.py                   # 插件进程与 WebSocket 管理
├── frontend/                       # Vue 2 前端
│   ├── src/views/Home/index.vue    # 首页、房间入口、父页面状态
│   ├── src/views/Room.vue          # 直播间 UI 与实时 Agent 面板
│   └── package.json                # 前端依赖和构建脚本
├── obs-blivechat-bridge/           # OBS C++ 插件
│   ├── src/obs-blivechat-bridge.cpp
│   └── CMakeLists.txt
├── plugins/                        # Blivechat 插件
├── blivedm/                        # B 站弹幕连接库
├── data/                           # 本地配置和数据库目录
│   └── config.example.ini          # 配置模板
├── requirements.txt                # Python 依赖
├── QWEN_SETUP.md                   # OpenAI 兼容模型接口配置说明
└── packaging/                      # 打包脚本与 PyInstaller 配置
```

## 运行架构

```text
B 站直播间 / OBS Studio
        │
        │ 弹幕、礼物、推流事件、截图、音频
        ▼
主播电脑本地客户端 127.0.0.1:12450
        │
        │ HTTP / WebSocket / postMessage
        ▼
Vue 前端 + Tornado 后端 + OBS Bridge
        │
        │ OpenAI 兼容接口
        ▼
远端 AI 服务（Gemma 4 多模态模型）
```

业务 UI 只展示模型返回的 `content` 或可解析 JSON。`reasoning` 只写 debug 日志，避免英文推理过程直接展示给用户。

## 最低配置

### 客户端

- 操作系统：Windows 10/11 64 位。
- CPU：4 核以上，推荐 6 核。
- 内存：最低 8GB，推荐 16GB。
- 显卡：不强制要求独显；如需稳定 OBS 推流，推荐独显或硬件编码能力较好的显卡。
- 网络：上行最低 2-5 Mbps，推荐 10 Mbps 以上；优先使用有线网络。
- 软件：OBS Studio 64 位、Python 3.12+、Node.js、现代浏览器。
- 本地端口：默认使用 `127.0.0.1:12450`。

### AI 服务端

- GPU：推荐 NVIDIA H800/A800/A100 或同级 80GB 显存设备。
- CPU：16 核以上。
- 内存：64GB 以上。
- 磁盘：100GB 以上可用空间。
- 系统：Ubuntu 22.04 或兼容 Linux 发行版。
- CUDA：CUDA 12/13 兼容运行环境。

## 客户端安装教程

### 1. 安装基础软件

请先安装：

- Python 3.12 或以上版本。
- Node.js LTS。
- OBS Studio 64 位。
- Git。

Windows 用户建议在 PowerShell 中执行后续命令。

### 2. 安装 Python 依赖

进入项目根目录：

```powershell
cd C:\path\to\blivechat-svn-compare-project
```

安装依赖：

```powershell
pip install -r requirements.txt
```

主要后端依赖包括：

- `tornado`：本地 HTTP/WebSocket 服务。
- `aiohttp`、`httpx`、`openai`：外部模型接口调用。
- `blivedm`：B 站直播弹幕连接。
- `sqlalchemy`：本地数据持久化。
- `pycryptodome`、`cachetools`、`circuitbreaker`：加密、缓存和容错。

### 3. 安装并构建前端

进入前端目录：

```powershell
cd frontend
npm install
npm run build
```

构建产物会输出到 `frontend/dist`，本地 Tornado 服务会加载该目录下的静态资源。

开发调试时可以使用：

```powershell
npm run serve
```

### 4. 创建配置文件

复制配置模板：

```powershell
cd ..
copy data\config.example.ini data\config.ini
```

默认本地监听配置：

```ini
[app]
host = 127.0.0.1
port = 12450
database_url = sqlite:///data/database.db
```

如果需要连接 OpenAI 兼容的 Gemma/Qwen 服务，请在 `data/config.ini` 中配置 `[qwen]` 段。虽然文件名仍保留 `qwen`，当前项目可接入任何 OpenAI 兼容接口。

示例：

```ini
[qwen]
api_key = sk-xxxxxxxxxxxxxxxx
base_url = http://你的AI服务器:6006/v1
model = gemma4-31b-mm
```

也可以通过环境变量提供密钥：

```powershell
$env:DASHSCOPE_API_KEY="你的API密钥"
```

### 5. 启动本地客户端服务

回到项目根目录：

```powershell
python main.py --host 127.0.0.1 --port 12450
```

启动成功后，浏览器访问：

```text
http://127.0.0.1:12450
```

输入 B 站直播间房间号后，客户端会开始监听弹幕。此时基础弹幕功能可用；AI 联合分析依赖 OBS 插件上传画面和音频，以及远端模型服务可用。

## OBS 插件安装教程

OBS 插件位于：

```text
obs-blivechat-bridge/
```

插件负责向本地客户端上报：

- 推流开始/停止事件。
- OBS 截图或截图路径。
- 麦克风、桌面音频或混音采样。
- 分轨配置和直播状态。

### Windows 安装

将编译得到的插件文件复制到 OBS 插件目录：

```text
C:\Program Files\obs-studio\obs-plugins\64bit
```

通常需要复制：

- `obs-blivechat-bridge.dll`
- `obs-blivechat-bridge.pdb`（可选，用于调试）

复制后重启 OBS。

### macOS 安装

macOS 下插件可编译为 `.plugin` bundle。编译后复制到：

```text
~/Library/Application Support/obs-studio/plugins/
```

然后重启 OBS。

### 插件编译说明

插件使用 CMake 构建，依赖：

- CMake 3.28-3.30。
- OBS Studio 开发库。
- libcurl。
- C++17 编译环境。

插件默认将数据上报到：

```text
http://127.0.0.1:12450
```

所以 OBS 和 LiCO 客户端需要运行在同一台主播电脑上。

## 服务端安装教程

AI 服务端负责运行 Gemma 4 多模态模型，并暴露 OpenAI 兼容接口。客户端通过 `base_url` 调用该服务。

推荐服务端监听：

```text
0.0.0.0:6006
```

如果服务端提供了启动脚本，可直接运行：

```bash
cd /root/Gemma
bash start_gemma_api.sh
```

启动脚本通常需要完成：

- 设置 Hugging Face 镜像。
- 设置模型名称。
- 设置 CUDA 动态库路径。
- 启动 Ollama 或模型后端。
- 启动 FastAPI/Uvicorn。
- 将日志写入 `gemma_YYYYMMDD_HHMMSS.log`。

客户端 `data/config.ini` 中的 `base_url` 应指向该服务，例如：

```ini
[qwen]
base_url = http://服务器IP:6006/v1
model = gemma4-31b-mm
```

## 使用流程

1. 启动远端 AI 服务。
2. 启动本地 LiCO 客户端：

   ```powershell
   python main.py --host 127.0.0.1 --port 12450
   ```

3. 打开浏览器访问 `http://127.0.0.1:12450`。
4. 输入 B 站直播间房间号。
5. 安装并启动 OBS 插件。
6. 在 OBS 中开始直播。
7. 客户端开始接收弹幕、OBS 状态、截图和音频，并在右侧展示四类 Agent 分析结果。

## 模型选择说明

项目当前测试重点是 Gemma 4 多模态模型：

- `gemma4-31b-mm`：用于心理、语音、画面、弹幕的联合多模态分析。
- `gemma4-e4b-mm`：可用于轻量 ASR 或低延迟语音观察。
- 规则 fallback：当模型不可用、返回非 JSON 或网络异常时，保证 UI 不空白。

选择 `gemma4-31b-mm` 的原因是直播分析不是单纯文本任务，而是需要同时理解弹幕语义、观众反馈、主播声音、画面场景和直播节奏。31B 规模更适合生成稳定的结构化报告。

## 常见问题

### 为什么代码里还有 Qwen 命名？

这是历史命名遗留。早期项目接入的是 Qwen/OpenAI 兼容接口，因此文件名和配置段保留了 `qwen`。当前客户端调用协议没有本质变化，服务端可以替换为 Gemma 4，只要提供 OpenAI 兼容接口即可。

### 前端没有分析结果怎么办？

请按顺序检查：

1. 本地服务是否启动在 `127.0.0.1:12450`。
2. OBS 插件是否成功加载。
3. OBS 是否已经开始推流。
4. 后端日志中是否收到 `/api/obs/event`、`/api/obs/frame`、`/api/obs/audio`。
5. `data/config.ini` 中 `[qwen]` 的 `base_url`、`api_key`、`model` 是否正确。
6. AI 服务端是否能返回 `delta.content`。

### 为什么会出现上传慢或 ReadError？

截图和音频上传会占用上行带宽。如果 WiFi 上行不稳定，可能出现请求超时、连接中断或 AI 响应延迟。建议：

- 使用有线网络。
- 减小截图大小或上传频率。
- 保证上行带宽 10 Mbps 以上。
- 查看后端日志中的上传速度和 SSE 首包时间。

### OBS 插件没有效果怎么办？

请检查：

- 插件文件是否放在正确的 OBS 插件目录。
- OBS 是否已经重启。
- 本地客户端是否正在运行。
- 防火墙是否阻止本机 `127.0.0.1:12450` 访问。
- 后端日志是否出现 OBS bridge 相关事件。

## 开发命令速查

```powershell
# 启动后端
python main.py --host 127.0.0.1 --port 12450

# 安装 Python 依赖
pip install -r requirements.txt

# 构建前端
cd frontend
npm install
npm run build

# 前端开发服务
npm run serve

# 前端 lint
npm run lint
```

## 打包说明

项目包含 PyInstaller 打包配置：

```text
packaging/blivechat.spec
```

打包时会收集：

- `frontend/dist`
- `data/config.example.ini`
- `data/loader.html`
- `plugins`
- Python 后端依赖和 Blivechat 子模块

Windows 本地分发版可参考 `packaging/` 目录中的脚本和说明。

## 安全注意事项

- 不要将真实 API Key 提交到仓库。
- `data/config.ini` 应只保存在部署机器本地。
- 生产环境对外开放服务时，请不要直接暴露本地管理接口。
- OBS 插件默认只访问 `127.0.0.1:12450`，如需跨机器访问，应额外增加认证与网络隔离。

## 参考文件

- `frontend/src/views/Room.vue`：直播间 UI、四模块 Agent 展示、联合分析触发。
- `frontend/src/views/Home/index.vue`：房间入口、父页面状态、iframe 通信。
- `api/qwen_multimodal.py`：OpenAI 兼容多模态接口、SSE 解析、网络诊断。
- `services/psych_agent.py`：后端心理状态 Agent。
- `services/obs_bridge.py`：OBS 状态缓存与前端广播。
- `services/live_archive.py`：直播归档与复盘。
- `obs-blivechat-bridge/src/obs-blivechat-bridge.cpp`：OBS 插件主体。
