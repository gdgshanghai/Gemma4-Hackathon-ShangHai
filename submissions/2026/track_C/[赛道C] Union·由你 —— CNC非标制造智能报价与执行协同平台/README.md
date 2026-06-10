# Union·由你 — CNC AI 工艺大脑

> AI驱动的CNC加工报价与工艺大脑。零门槛，云端/本地模型自动切换。

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Run
python -m uvicorn app.main:app --host 0.0.0.0 --port 7862

# 3. Open
# http://localhost:7862
```

**Windows one-click:**
```cmd
install_windows.bat
```

## Features

- **智能报价** — 24种材料、14种表面处理、精度/五轴/线切割全支持
- **3D预览** — 上传STEP/STP文件自动生成3D预览
- **冲突检测** — 材料×表面处理硬规则（304+阳极氧化❌）
- **One-Click流水线** — 生成→检测→报价→导出一步完成
- **云端/本地模型** — 环境变量自动发现12种云端API，Ollama本地模型自动检测
- **降级机制** — 云端失败自动fallback到本地，零中断

## Model Config

| 方式 | 配置 |
|------|------|
| 云端(自动发现) | 设环境变量: `set DEEPSEEK_API_KEY=sk-xxx` |
| 云端(手动) | 编辑 `config/models.json` |
| 本地 | 安装 [Ollama](https://ollama.com) + `ollama pull gemma-4-26B-A4B-it-Q4_K_M` |

支持的云端API(环境变量自动发现):
`OPENAI_API_KEY` `ANTHROPIC_API_KEY` `DEEPSEEK_API_KEY` `SILICONFLOW_API_KEY` `QWEN_API_KEY` `XAI_API_KEY` `OPENROUTER_API_KEY` `GROQ_API_KEY` `MOONSHOT_API_KEY`

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/quote` | POST | 报价计算 |
| `/api/chat` | POST | AI对话 |
| `/api/one-click` | POST | 全链路流水线 |
| `/api/models` | GET | 模型列表 |
| `/api/models/switch` | POST | 运行时切换模型 |
| `/api/models/fallback` | GET | 降级链 |
| `/api/health` | GET | 健康检查 |
| `/api/audit` | GET | 审计日志 |

## Tech Stack

- **Backend**: FastAPI + Uvicorn
- **3D**: Trimesh + Cascadio (OpenCASCADE)
- **AI**: Ollama (local) / OpenAI-compatible API (cloud)
- **DB**: SQLite (audit + orders + RAG)

## License

MIT

<!-- 作者: timo.cao | 邮箱: miscdd@163.com | 生成: 大帅教练系统 -->
