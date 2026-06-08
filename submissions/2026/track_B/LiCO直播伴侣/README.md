# LiCO 直播伴侣

## 项目信息

- 赛道：B Multimodal
- 项目名称：LiCO直播伴侣
- 队伍名称：LiCO
- 演示视频：https://www.bilibili.com/video/BV14KEh6LEjw/

LiCO（Live COmpanion）直播伴侣是一个面向主播的直播 Agent 软件。项目基于 Blivechat 与 OBS Studio 扩展开发，在原有弹幕展示能力之上，增加弹幕、画面、音频、礼物和直播状态的多模态采集与分析能力，并通过 Gemma 4 多模态服务为主播提供实时心理状态分析、直播复盘和自动切片建议。

## 目录结构

```text
.
├── README.md                 # 本提交说明与安装入口
├── requirements.txt          # 客户端与服务端 Python 依赖入口
├── 整体说明.md               # 项目整体说明
├── 视频连接.txt              # 演示视频链接
├── client/                   # 主播本地客户端、Vue 前端、OBS 插件与 Blivechat 扩展
└── server/                   # Gemma 4 多模态服务端与 OpenAI 兼容 API
```

## 环境安装步骤

### 1. 客户端

客户端运行在主播电脑上，推荐 Windows 10/11 64 位、Python 3.12+、Node.js LTS 和 OBS Studio 64 位。

```powershell
cd client
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python main.py --host 127.0.0.1 --port 12450
```

然后按客户端窗口提示输入 B 站直播间房间号，并将 `client/obs-blivechat-bridge` 编译出的 OBS 插件安装到 OBS 插件目录。更详细的 OBS 插件安装、前端调试、配置方式请见 `client/README.md`。

### 2. 服务端

服务端运行在 GPU 服务器上，推荐 Ubuntu 22.04、NVIDIA 48GB-80GB 显存设备、CUDA 12/13 兼容运行环境、Ollama 和 Python 3.11。

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash start_gemma_api.sh
```

默认服务监听 `0.0.0.0:6006`，并提供 OpenAI 兼容接口 `POST /v1/chat/completions`。服务端部署、模型配置、环境变量、压测与回放说明请见 `server/README.md`。

## 核心源码位置

- 客户端入口：`client/main.py`
- 直播间 Agent UI：`client/frontend/src/views/Room.vue`
- 多模态接口调用：`client/api/qwen_multimodal.py`
- 心理状态 Agent：`client/services/psych_agent.py`
- OBS 插件：`client/obs-blivechat-bridge/src/obs-blivechat-bridge.cpp`
- 服务端入口：`server/gemma_api/main.py`
- OpenAI 兼容多模态路由：`server/gemma_api/routers/openai_compat.py`
- Gemma/Ollama 调用封装：`server/gemma_api/services/ollama_client.py`

## 备注

代码中部分文件名仍保留 `qwen` 命名，这是历史接口兼容命名；本次提交的客户端与服务端测试目标为 Gemma 4 多模态模型。
