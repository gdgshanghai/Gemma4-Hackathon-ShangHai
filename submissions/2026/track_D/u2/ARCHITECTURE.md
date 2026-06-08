# U2 架构文档

## 整体设计原则

- **本地优先**：所有用户数据和 AI 推理在设备端完成，不依赖云端服务
- **渐进降级**：Gemma 4 不可用时自动切换安全模板，核心功能不受影响
- **隐私内建**：无账号体系，可选 PIN 加密，一键隐藏

---

## 层次结构

```
┌─────────────────────────────────────────────┐
│              React UI 层                    │
│  pages/  components/  (React 18 + Router)   │
├─────────────────────────────────────────────┤
│              状态管理层                      │
│    store/appStore.ts   store/chatStore.ts    │
│         (Zustand 5)                         │
├────────────────────┬────────────────────────┤
│    业务服务层       │     AI 推理层           │
│  services/         │  workers/              │
│  ├ agent.ts        │  └ gemma.worker.ts     │
│  ├ localAI.ts ─────┼──→ Web Worker + WebGPU │
│  ├ crypto.ts       │     Gemma4ForCondGen   │
│  ├ reports.ts      │     RawImage OCR       │
│  ├ assessments.ts  │                        │
│  ├ risk.ts         │                        │
│  └ trust.ts        │                        │
├────────────────────┴────────────────────────┤
│              数据持久层                      │
│    data/repository.ts  (IndexedDB + idb)    │
│    services/crypto.ts  (AES-GCM 加密)       │
├─────────────────────────────────────────────┤
│              内容层                         │
│  content/knowledge.ts  (本地知识库 6 篇)    │
│  config/model.ts       (模型 ID 配置)        │
└─────────────────────────────────────────────┘
```

---

## Gemma 4 推理流程

### 文本对话

```
用户输入
  → hasCrisisSignal()       危机关键词检测（优先级最高）
  → retrieveKnowledge()     本地知识库检索（关键词 + 全文）
  → buildSystemPrompt()     构建系统提示（含信任状态、知识上下文）
  → localAI.generate()      发送 GENERATE 消息给 Web Worker
      → gemma.worker.ts
          → tokenizer.apply_chat_template()
          → model.generate() + TextStreamer  流式输出
  → updateMessage()         逐 token 更新 UI
```

### 多模态 OCR（报告识别）

```
用户上传图片
  → file.arrayBuffer()      转换为二进制
  → localAI.analyzeImage()  发送 ANALYZE_IMAGE 消息
      → gemma.worker.ts
          → RawImage.fromBlob()             构建图像对象
          → processor(text, [image])        图文联合编码
          → model.generate()                推理（max 512 tokens）
          → outputIds.tolist()[0].slice()   解码新 token
  → parseOcrFields()        正则提取 CD4 / 病毒载量 / 日期 / 机构
```

### 模型 ID 选择策略

```
VITE_GEMMA_MODEL_ID 环境变量（管理员覆盖）
  ↓ 否
MODEL_SOURCE === 'bundled'
  ↓ 是 → BUNDLED_MODEL_FOLDER（本地 /models/ 目录）
  ↓ 否
navigator.userAgent 包含 Android/iPhone/iPad/Mobile
  ↓ 是 → gemma-4-E4B-it-qat-mobile-ONNX  （移动端 QAT 优化）
  ↓ 否 → gemma-4-E4B-it-ONNX             （桌面端完整版）
```

---

## 数据流与隐私边界

```
用户操作
  → IndexedDB (本机)
      ├ 明文存储（默认）
      └ AES-GCM 256 加密存储（PIN 开启后）
          密钥 = PBKDF2(PIN, salt, 210000 iter, SHA-256)
          密钥仅保留在内存 sessionKey 变量，页面关闭即清零

联网操作（仅用户主动触发）：
  A. 模型下载：HuggingFace CDN → 浏览器 Cache API（u2-model-assets）
  B. 公开资讯：Cloudflare Worker → GDELT API（仅公开新闻索引，不含用户数据）
```

---

## 消息协议（Main Thread ↔ Web Worker）

| 方向 | 消息类型 | 载荷 |
|---|---|---|
| → Worker | `INIT` | — |
| → Worker | `GENERATE` | `messages[], maxTokens` |
| → Worker | `ANALYZE_IMAGE` | `buffer, mimeType, prompt` |
| → Worker | `CANCEL` | — |
| ← Worker | `STATE` | `ModelState { status, progress, detail }` |
| ← Worker | `CHUNK` | `id, text`（流式 token） |
| ← Worker | `DONE` | `id, result / ok` |
| ← Worker | `ERROR` | `id, error` |

---

## 危机安全机制

```
用户消息
  → hasCrisisSignal()
      关键词：不想活 / 自杀 / 结束生命 / 活不下去 /
              伤害自己 / 割腕 / 跳楼 / 轻生 / 想死 / 撑不下去
  → 命中：立即返回危机响应，不调用 LLM
           CrisisSheet 展示 12356 / 110 / 120
  → PHQ-9 第 9 题（自伤意念）> 0：同样触发 CrisisSheet
```

---

## PWA 与离线策略

| 资源类型 | 缓存策略 | 说明 |
|---|---|---|
| HTML / JS / CSS / SVG | CacheFirst (SW precache) | 构建时写入 SW precache manifest |
| Gemma 4 模型权重 | CacheFirst 90 天 | Workbox runtime caching，Cache 名 `u2-model-assets` |
| 用户数据 | IndexedDB | 不经过 SW |
| 公开资讯 | NetworkFirst + 本地兜底 | 联网失败用 LOCAL_NEWS |

Service Worker 要求服务器响应头：
```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```
（缺少则 SharedArrayBuffer 不可用，ONNX WASM 多线程无法初始化）

---

## 目录说明

```
u2-app-v1/
├── src/
│   ├── workers/gemma.worker.ts   Gemma 4 Web Worker（Edge 推理核心）
│   ├── services/
│   │   ├── localAI.ts            Worker 生命周期管理
│   │   ├── agent.ts              对话编排、危机检测
│   │   ├── reports.ts            OCR + 字段解析
│   │   ├── crypto.ts             PIN 加密
│   │   ├── assessments.ts        PHQ-9 / GAD-7
│   │   ├── risk.ts               PEP / 常态风险分流
│   │   └── trust.ts              医院信任度推断
│   ├── pages/                    React 页面
│   ├── store/                    Zustand store
│   ├── data/repository.ts        IndexedDB CRUD
│   ├── config/model.ts           模型 ID 与来源配置
│   └── content/knowledge.ts      本地知识库（6 篇文章）
├── worker/                       Cloudflare Worker（可选资讯 API）
├── scripts/fetch-bundled-model.mjs  随包模型下载脚本
├── serve.mjs                     带 COOP/COEP 头的本地静态服务器
├── docs/MODEL_DEPLOYMENT.md      模型部署说明
└── AGENTS.md                     医疗安全边界约束
```
