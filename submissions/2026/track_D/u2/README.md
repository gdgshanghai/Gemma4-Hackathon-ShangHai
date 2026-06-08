# U2 · 病毒归零，恐惧归零

**赛道 D — AI for Social Good｜Gemma 4 Developer Contest 2026**

U2 是一个匿名、本地优先的 HIV 心理健康与健康支持 PWA。Gemma 4 模型完全运行在用户设备的浏览器内（WebGPU），对话、报告识别、风险评估全程不离开本机。

---

## Gemma 4 核心能力利用

| 能力 | 实现位置 | 说明 |
|---|---|---|
| **Edge 推理** | `src/workers/gemma.worker.ts` | `Gemma4ForConditionalGeneration` + WebGPU + Q4F16 量化，完全离线 |
| **多模态 OCR** | `analyzeImage()` in worker | `RawImage.fromBlob()` + 多模态 message 格式识别医学报告图片 |
| **移动端适配** | `EFFECTIVE_MODEL_ID` in worker | UA 检测自动选择 `gemma-4-E4B-it-qat-mobile-ONNX`（移动端）或 `gemma-4-E4B-it-ONNX`（桌面端） |
| **流式输出** | `generate()` + `TextStreamer` | 逐 token 回调，聊天界面实时渲染 |
| **降级机制** | `src/services/agent.ts` | 模型不可用时自动切换确定性安全模板，医疗安全边界始终有效 |

### 为什么选择 Gemma 4

- **隐私第一**：目标用户（HIV 感染者及高危人群）对数据上传极度敏感，模型必须在本机运行
- **E4B 规格**：4B 参数在量化后约 2–4 GB，是浏览器 WebGPU 可承受的上限，同时具备足够的中文理解和共情能力
- **QAT Mobile 变体**：官方提供 `qat-mobile-ONNX`，专为移动端 GPU 优化，无需 Native 开发即可在 iOS Safari / Android Chrome 运行

---

## 快速启动

### 环境要求

- Node.js 18+
- 支持 WebGPU 的浏览器（Chrome 113+ / Edge 113+ / Safari 17.4+）
- 本地开发和演示服务器**必须设置以下 HTTP 响应头**（缺少则 WASM 多线程无法启动）：

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

### 安装与开发

```bash
npm install
npm run dev          # Vite 开发服务器（已自动注入 COOP/COEP）
```

### 生产构建与本地演示

```bash
npm run typecheck    # TypeScript 类型检查
npm test             # 单元测试（Vitest）
npm run build        # 生产构建输出到 dist/

# 带正确 COOP/COEP 头的静态服务器（用于本地演示或 ngrok 穿透）
node serve.mjs
```

> `serve.mjs` 在项目根目录，自动在 4173 端口提供 COOP/COEP 头。

### 模型下载（可选，首次使用由 App 引导）

```bash
# 预下载随包模型（bundled 模式，适合离线分发）
npm run model:prepare

# 随包模式构建
VITE_GEMMA_MODEL_SOURCE=bundled npm run build
```

---

## 技术架构

```
src/
├── workers/
│   └── gemma.worker.ts     # Gemma 4 推理 Web Worker（Edge 核心）
├── services/
│   ├── localAI.ts          # Worker 管理、消息协议
│   ├── agent.ts            # 对话编排、危机检测、知识库检索
│   ├── crypto.ts           # PBKDF2 + AES-GCM PIN 加密
│   └── reports.ts          # 多模态 OCR + 字段结构化解析
├── pages/                  # React 页面（Companion / Health / Support / Settings）
├── store/                  # Zustand 全局状态
├── data/                   # IndexedDB 持久化（idb）
└── config/
    └── model.ts            # 模型 ID 配置（web / mobile / bundled 三种来源）
```

详细架构说明见 [ARCHITECTURE.md](ARCHITECTURE.md)。

---

## 功能概览

- **AI 陪伴**：本地 Gemma 4 聊天、情绪记录、危机信号检测（自动弹出 12356 热线）、动态医院信任状态
- **健康管理**：健康日记、PHQ-9/GAD-7 量表、HIV 风险分流（PEP / 常态）、用药计划与 ICS 日历导出、指标趋势
- **多模态报告**：上传检测报告图片，Gemma 4 本地 OCR 识别 CD4、病毒载量、检测日期等字段
- **隐私设计**：无账号、可选 PIN 加密、一键隐藏伪装为备忘录、数据完全本地

---

## 医疗安全边界

U2 不做 HIV 确诊或排除诊断，不输出感染概率，不提供个体化药物、停药、换药或剂量建议。PEP 流程只做紧急程度分流；报告识别结果必须由用户对照原件确认。

---

## 数据合规与隐私保护（赛道 D: Social Good 补充）

- 无强制注册，不收集姓名、手机号或住址
- 所有健康数据存储在用户本机 IndexedDB，默认不上传
- 模型推理完全在设备本地，对话内容不经过任何服务器
- 联网操作仅两种：用户主动下载模型、用户主动获取公开资讯
- 可选 PBKDF2（210,000 次迭代）+ AES-GCM 256 PIN 加密

---

## 依赖说明

本项目为 Node.js / Web 项目，依赖见 `package.json`（等价于 Python 项目的 requirements.txt）。

主要依赖：

| 包 | 版本 | 用途 |
|---|---|---|
| `@huggingface/transformers` | ^4.2.0 | Gemma 4 ONNX 推理（含 WebGPU 后端） |
| `react` | ^18.3.1 | UI 框架 |
| `zustand` | ^5.0.5 | 全局状态管理 |
| `idb` | ^8.0.3 | IndexedDB 封装 |
| `vite` | ^6.3.5 | 构建工具 |
| `vite-plugin-pwa` | ^1.0.0 | PWA + Service Worker |
