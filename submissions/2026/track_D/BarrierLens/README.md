# 无碍 BarrierLens · Gemma 4 大赛提交包（赛道 D）

**Gemma 4 开发者大赛 2026 · 上海站 · Track D · AI for Social Good**

| 字段 | 内容 |
|------|------|
| 队伍 | 小马过河 |
| 项目 | 无碍｜让无障碍问题被看见、被记录、被反馈 |
| 主仓库 | https://github.com/timeyour/barrierlens |
| 在线 Demo | https://barrierlens-1utx.vercel.app/#tool |
| Demo 视频（≤5 分钟） | https://www.bilibili.com/video/BV1LtEg6zEqS/ |
| 技术报告 | 本目录 [TECHNICAL_REPORT.md](./TECHNICAL_REPORT.md) |

> 本目录为 **方式 A（Fork & PR）** 提交包。完整源码在独立仓库 `timeyour/barrierlens`；评审请以上表 **Demo + 主仓库 + 视频 + 技术报告** 为准。

---

## 环境要求

- Node.js **20+**
- npm **10+**
- （可选）Gemini API Key，用于真实 Gemma 4 推理

---

## 一键启动（从主仓库）

```bash
git clone https://github.com/timeyour/barrierlens.git
cd barrierlens
npm install
cp .env.example .env.local
# 编辑 .env.local，填入 GEMINI_API_KEY 或 GEMMA_API_KEY
npm run dev
# 浏览器打开 http://127.0.0.1:3000/#tool
```

生产 Demo 已部署，无需本地 Key 也可体验 UI；真实识图需配置 Key 或使用线上 Production（已配 Key）。

---

## Gemma 4 核心调用

- 文件：`src/lib/gemma.ts`（Gemini REST `generateContent`，默认 `gemma-4-26b-a4b-it`）
- 多模态：text prompt + inlineData 图片 → JSON → `normalizeResult`
- **未微调**：预训练 + Prompt / JSON 约束，无 LoRA

证明链（主仓库）：

- [MODEL_PROVENANCE.md](https://github.com/timeyour/barrierlens/blob/main/docs/MODEL_PROVENANCE.md)
- [LOCAL_REPRODUCE.md](https://github.com/timeyour/barrierlens/blob/main/docs/LOCAL_REPRODUCE.md)
- [GEMMA4_DEPLOYMENT.md](https://github.com/timeyour/barrierlens/blob/main/docs/GEMMA4_DEPLOYMENT.md)

---

## 赛道 D · 数据合规与隐私

- 不要求登录；默认 **本机 localStorage** 归档
- 公开池需用户 **勾选同意**；位置 **自动模糊**（lat/lng 置 null）
- 不做自动投诉 / 执法；AI 输出为记录与整改建议，需人工复核
- 详见技术报告第 6 节

---

## 验证命令

```bash
npm run lint
npm run build
npm run test:multiround
```

Production 验收：结果页 banner 显示 `analysisSource=gemma`（非 Mock）。见 [GEMMA4_DEPLOYMENT.md](https://github.com/timeyour/barrierlens/blob/main/docs/GEMMA4_DEPLOYMENT.md)。

---

## PR 信息（组委会）

- **PR 标题**：`[赛道D] 无碍 BarrierLens - 小马过河`
- **Fork 路径**：`submissions/2026/D/BarrierLens/`
- **登记表单**：https://hackathon.googdg.cn/onsite-submit（上传方式选 **A. Official repo Fork & PR**）
