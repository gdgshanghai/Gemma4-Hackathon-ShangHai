# 她健康 · PCOS 伴侣 — Gemma 4 后端

> **赛道 D：Social Good** ｜ 提交目录：`/submissions/2026/D/pcos-companion/`
> 中国第一个 PCOS（多囊卵巢综合征，2026 年 5 月已更名 PMOS）专属的 AI 陪伴式管理小程序后端。

面向 1.7 亿中国 PCOS 患者长期被忽视的**情绪支持空白**与**就医信息不对等**，
用 **Gemma 4** 构建一个「不诊断、只陪伴」的 AI 陪伴者「小暖」，并把所有
不能交给大模型自由发挥的医疗动作下沉为**确定性函数**，由模型**原生函数调用**。

---

## ✨ 它为什么符合技术评分标准

| 评分维度 | 本项目的做法 |
|---------|------------|
| 架构清晰、模块化 | `gemma`（推理/编排/多模态）· `tools`（函数实现）· `safety`（护栏）· `privacy`（数据治理）四层解耦 |
| **深度利用原生函数调用** | 7 个工具以 OpenAI 兼容 `tools` schema 下发，由 Gemma 4 **结构化返回 tool_calls** 并多轮编排，而非把工具塞进 prompt 做字符串匹配 |
| 多模态 | Gemma 4 26B MoE 解析化验单 / B 超报告图片，抽取结构化指标 |
| 端侧部署 | 默认 Gemma 4 4B（Q4 量化）本地推理，敏感对话不出设备 |
| 文档 / 一键启动 | `docker compose up` 或 `./run.sh` 一键拉起；含 `.env.example`、端侧指南、合规文档 |

> 合规巧思：**风险评估、知识问答、危机干预都是函数**——模型只能"调用"，不能"臆造诊断"。

---

## 🚀 快速开始

### 方式一：零 GPU 看效果（推荐评委先跑这个）
```bash
pip install -r requirements.txt
PROFILE_STORE=/tmp/pcos python demo_local.py
```
用模拟的 Gemma 4 函数调用响应跑通完整编排循环（含危机干预），无需显卡。

### 方式二：Docker 一键启动（端侧 Gemma 4 4B）
```bash
cp .env.example .env
docker compose up --build -d
docker compose exec ollama ollama pull gemma-4-4b-it-q4
curl -X POST http://127.0.0.1:9000/chat \
  -H 'Content-Type: application/json' \
  -d '{"openid":"demo","message":"小暖，我月经两个月没来了，好焦虑"}'
```

### 方式三：本机一键脚本
```bash
./run.sh          # 检查 Ollama → 拉模型 → 装依赖 → 起服务 (:9000)
```

### 多模态（云端 26B MoE，需 GPU）
```bash
vllm serve google/gemma-4-26b-moe-it --port 8000   # OpenAI 兼容，含 vision
# 前端在用户授权后传 image_path 与 vision_consent=true 即触发 parse_lab_report
```

---

## 🧩 架构

```
微信小程序 / 端侧前端
        │  POST /chat
        ▼
 FastAPI (src/main.py)  ── 假名化 openid，绝不入库明文
        │
        ▼
 函数调用编排 (src/gemma/function_calling.py)
   1. system(小暖人设) + 历史 + 用户输入
   2. 带 tools 调 Gemma 4  ──►  端侧 4B (Ollama) / 云端 26B MoE (vLLM)
   3. 解析 tool_calls → 本地执行 → 结果回灌 → 再问，直至自然语言回复
        │
        ├── tools/        record_symptom · log_menstrual_period
        │                 assess_pcos_risk(确定性评分,非诊断)
        │                 lookup_pcos_knowledge(指南来源 RAG)
        │                 generate_clinic_checklist · parse_lab_report(多模态)
        │                 escalate_to_crisis_support(强制安全兜底)
        ├── safety/       入口危机词拦截 + 输出红线纠偏
        └── privacy/      AES-GCM 加密 · openid 假名化 · 一键删除
```

详见 [docs/技术报告.md](docs/技术报告.md) 与 [docs/数据合规与隐私保护.md](docs/数据合规与隐私保护.md)。

---

## 🧪 测试
```bash
pip install -r requirements.txt
PYTHONPATH=. pytest tests/ -q
```

## 📁 目录
```
src/gemma/       推理客户端 · 函数调用编排 · 多模态
src/tools/       函数实现 + schema 注册表
src/safety/      安全护栏
src/privacy/     数据治理（加密/假名化/删除）
src/persona/     小暖 system prompt
data/knowledge_base/  指南来源知识库
edge/            端侧部署指南
docs/            技术报告 · 数据合规与隐私保护
demo_local.py    零 GPU 演示
```

## ⚖️ 边界声明
本产品不提供医疗诊断、不开具处方、不替代医生。所有输出标注「仅供参考，建议就医」。
危机情形自动引导心理援助热线 / 急诊。
