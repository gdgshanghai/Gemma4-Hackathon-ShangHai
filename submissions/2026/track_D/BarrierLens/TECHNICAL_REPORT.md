# 无碍 BarrierLens 技术报告

> 完整源码与最新文档：https://github.com/timeyour/barrierlens

## 1. 摘要

无碍 BarrierLens 面向 Gemma 4 开发者大赛 2026 上海站赛道 D: AI for Social Good。项目聚焦公共空间无障碍通行风险，将现场照片转化为结构化证据、风险地图、公众倡导摘要和物业巡查整改单。

项目核心不是替代监管，而是降低公众和运营方记录无障碍问题的门槛，让分散发现变成可归档、可复查、可导出的证据链。

## 2. 背景

盲道占用、入口坡道受阻、通行链断点是城市公共空间中高频但容易被忽略的问题。单次微信反馈或投诉往往缺少统一字段、责任归类和后续复查记录，难以沉淀为可持续倡导或自查依据。

BarrierLens 采用“拍照 -> 结构化 -> 归档 -> 导出 -> 复查”的闭环。人负责发现现场，Gemma 4 负责把现场转成治理语言和整改证据。

## 3. Gemma 4 用法

Gemma 4 在项目中承担多模态场景理解和结构化生成：

- 识别三类场景：盲道占用、入口/坡道受阻、通行链断点。
- 输出障碍物、受阻路径、风险等级、影响人群、证据要点。
- 根据记录模式生成两种文本：公众倡导摘要、物业巡查整改单。
- 输出置信度与 `needsHumanReview`，低置信度时提示人工复核。

接口位置：`src/lib/gemma.ts`

当前实现使用 Gemini REST `generateContent` 调用 Gemma 4：

```text
apiKey: GEMINI_API_KEY 或 GEMMA_API_KEY
model: GEMMA_MODEL_NAME，默认 gemma-4-26b-a4b-it
input: text prompt + inlineData image
output: JSON text，经 normalizeResult 归一化为前端 schema
```

**未微调**：仅使用 Gemma 4 预训练能力 + 项目 Prompt 与结构化 JSON 约束，无额外训练或 LoRA。

未配置 `GEMINI_API_KEY` / `GEMMA_API_KEY` 时使用 Mock（`analysisSource=mock`）。生产环境 `ALLOW_MOCK_FALLBACK=false` 时，Gemma 失败会直接报错，不 silent 降级；本地开发环境在 Key 失败时可能返回 `analysisSource=mock_fallback`。

证明链文档（主仓库）：

- [MODEL_PROVENANCE.md](https://github.com/timeyour/barrierlens/blob/main/docs/MODEL_PROVENANCE.md)
- [LOCAL_REPRODUCE.md](https://github.com/timeyour/barrierlens/blob/main/docs/LOCAL_REPRODUCE.md)
- [GEMMA4_DEPLOYMENT.md](https://github.com/timeyour/barrierlens/blob/main/docs/GEMMA4_DEPLOYMENT.md)

## 4. 架构

```text
Next.js 16 App Router
├── 前台页面
│   ├── 证据故事线 / 工作台 (#tool)
│   ├── 三类场景卡片
│   ├── 上传分析工作流
│   ├── Barrier Map 风险地图
│   ├── 本地时间线与整改复查
│   └── 公开案例池 /reports（可选，无需登录）
├── API Route
│   ├── /api/analyze          # 图片 → Gemma 4 / Ollama / Mock
│   ├── /api/reports          # 用户主动公开摘要
│   ├── /api/location/config  # 定位配置（增强）
│   └── /api/health/location  # 定位健康探针
├── 模型层
│   ├── src/lib/gemma.ts      # Gemini REST / Gemma 4
│   ├── src/lib/ollama.ts     # 本地 Ollama（开发复现）
│   └── src/lib/mockAnalysis.ts
├── 本机数据（默认）
│   └── localStorage 记录、复查状态、前后照片
└── 云端（可选，用户主动公开）
    └── Supabase reports + Storage（位置模糊；云端失败不影响本机主流程）
```

隐私与存储设计：

- **不要求登录**；登录仅为多设备同步增强（`NEXT_PUBLIC_AUTH_REQUIRED=false`）。
- **默认本机 localStorage** 保存时间线；原始照片随当次分析请求发送给模型，不默认上传云端。
- **用户勾选同意**后，摘要与必要字段（含现场照片）可写入 Supabase 公开池；**公开位置自动模糊**（lat/lng 置 null）。
- **定位失败不阻断主流程**：可手动输入路名后继续分析、保存与公开。

## 5. 评估计划

| 指标 | 目标 |
|------|------|
| 测试照片 | >= 30 张 |
| 结构化 JSON 成功率 | >= 95% |
| 三场景覆盖 | 盲道、入口/坡道、通行链均覆盖 |
| 平均分析耗时 | <= 8 秒 |
| 用户主流程 | <= 4 步完成一次记录 |

测试命令：

```bash
npm run lint
npm run build
npm run dev
npm run test:multiround
```

## 6. 隐私与合规

BarrierLens 不做自动投诉、不做执法、不替代专业验收。AI 输出是记录和整改建议，需由人复核。

- 核心模型：Gemma 4（`gemma-4-26b-a4b-it`）
- 训练数据：Gemma 4 预训练 + 项目 Prompt，**无额外微调**
- 用户数据：**默认本机**；可选 Supabase 公开池（用户主动、位置模糊）
- Mock：**不代表** Gemma 4 真实识图能力

## 7. 局限与展望

- 真实测试照片数量仍需扩充
- 风险地图为前端示意，非精确 GIS
- 责任方判断为辅助建议，非法律责任认定

## 8. 团队

团队：**小马过河**
