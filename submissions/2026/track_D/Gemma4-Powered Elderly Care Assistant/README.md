# Gemma4 Elderly Care Assistant

赛道：D SocialGood

Gemma4 Elderly Care Assistant 是一个面向独居老人安全照护的多模态 AI Demo。系统将摄像头/视频跌倒检测、麦克风语音确认、上下文无响应时长输入到 Gemma 4 决策层，由 Gemma 4 通过原生函数调用选择继续监测、发起语音确认或触发紧急报警。

## 核心痛点

独居老人跌倒后可能无法及时主动呼救，普通摄像头检测又容易误报。本项目不是只判断“是否跌倒”，而是把视觉、语音和无响应上下文合并，输出可解释的风险分数、行动建议和报警状态。

## 核心代码

重点查看以下文件：

- `ai_backend/services/decision_service.py`：Gemma 4 / Ollama 调用逻辑，包含原生函数调用工具定义 `continue_monitoring`、`start_voice_check`、`trigger_emergency_alert`，并带规则兜底。
- `ai_backend/app.py`：FastAPI 多模态编排入口，连接视觉、语音、Gemma 4 决策与 PHP Dashboard。
- `ai_backend/services/vision_service.py`：OpenCV + YOLO 跌倒/人体检测，支持浏览器摄像头帧和视频上传。
- `ai_backend/services/speech_service.py`：Whisper 语音转写和安全/求助意图识别。
- `backend/api/services/AiUpdateService.php`：接收 AI 后端统一状态并写入 Dashboard 状态。
- `frontend/assets/js/app.js`：摄像头、视频上传、语音录制和实时风险 UI。

## 技术架构

```text
Browser Camera / Video Upload / Microphone
        |
        v
FastAPI AI Backend
        |
        +-- YOLO + OpenCV vision detection
        +-- Whisper speech transcription
        +-- Gemma 4 native function calling decision layer
        |
        v
PHP API state bridge
        |
        v
Web Dashboard: detection boxes, risk score, decision reason, emergency status
```

## Gemma 4 使用方式

默认通过本地 Ollama Chat API 调用 Gemma 4 兼容模型：

```text
POST http://127.0.0.1:11434/api/chat
```

环境变量：

```text
GEMMA_ENABLED=1
GEMMA_MODEL=gemma4:2b
OLLAMA_BASE_URL=http://127.0.0.1:11434
GEMMA_TIMEOUT_SECONDS=8
```

如果现场机器没有 Gemma 4 权重，可临时把 `GEMMA_MODEL` 改为已安装的 Gemma 系列模型名；若 Ollama 不可用，系统会自动使用规则兜底，保证演示流程稳定。

## 环境要求

- Windows 10/11
- Python 3.11
- PHP 8 或 XAMPP PHP
- FFmpeg
- Ollama
- Gemma 4 模型：建议 `gemma4:2b`，也可按现场环境替换为可用 Gemma 4 规格

## 安装依赖

进入项目目录：

```cmd
cd Gemma4-Elderly-Care-Assistant
```

创建并激活 Python 虚拟环境：

```cmd
cd ai_backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

安装或确认 Gemma 模型：

```cmd
ollama pull gemma4:2b
ollama serve
```

如果本地模型名称不同，启动前设置：

```cmd
set GEMMA_MODEL=你的模型名
```

## 启动方式

启动 FastAPI AI 后端：

```cmd
cd ai_backend
.venv\Scripts\activate
uvicorn app:app --host 127.0.0.1 --port 8001 --reload
```

另开一个终端启动 PHP Dashboard：

```cmd
cd Gemma4-Elderly-Care-Assistant
C:\xampp\php\php.exe -S 127.0.0.1:8080 router.php
```

打开：

```text
http://127.0.0.1:8080
```

## 演示流程

1. 打开 Dashboard，授权摄像头。
2. Camera 模式展示正常 person 检测，Risk Score 保持低风险。
3. 做低矮、横向或倒地姿态，展示 suspected fall 和风险上升。
4. 点击 Safety Voice Check，说“我没事”，展示风险下降。
5. 再说“我需要帮助”或 “Help me”，展示高风险和救援动作。
6. 切换 Video Upload 上传跌倒视频，展示更稳定的视频跌倒检测。

## API 检查

```text
GET  http://127.0.0.1:8001/health
POST http://127.0.0.1:8001/vision/frame
POST http://127.0.0.1:8001/upload_video
POST http://127.0.0.1:8001/speech/upload
POST http://127.0.0.1:8001/analyze
GET  http://127.0.0.1:8080/api/status
```

## 已知限制

- 当前 YOLO 跌倒模型主要识别 fall，复杂姿态分类仍可继续训练增强。
- 摄像头实测受角度、光照、取景完整度影响，比赛演示建议保留 Video Upload 作为稳定路径。
- Whisper 依赖麦克风授权和 FFmpeg。
- Gemma 4 调用通过 Ollama 本地服务完成，现场需要提前下载对应模型。
