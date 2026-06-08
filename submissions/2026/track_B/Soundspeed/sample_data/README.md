# Sample Data — Soundspeed 多模态演示素材

这些素材用于让评审快速复现 Soundspeed 的**文本 / 图像 / 语音三模态融合**效果。
全部由同一个 **Gemma 4 E4B** 实例处理（文本理解、剧本 OCR、原生音频输入），
详见上级目录的 `TECHNICAL_REPORT.md`。

> 运行环境与安装见上级目录 `README.md`（一台 Apple Silicon Mac 即可全离线运行）。
> 模型权重不随仓库提交，首次运行自动从 HuggingFace 拉取
> `unsloth/gemma-4-E4B-it-GGUF`（`Q4_K_M` + `mmproj-F16`）。

## 目录

```
sample_data/
├── script/
│   └── script-excerpt_jiyi-de-wendu.txt     # 文本模态：剧本片段
└── audio/
    ├── voice-query_first-scene-takes.wav     # 语音模态：自然语言查询
    └── voice-note_third-take-low-volume.wav  # 语音模态：口述备注
```

## 1. 文本模态 — 剧本理解 / 结构化

`script/script-excerpt_jiyi-de-wendu.txt`

节选自虚构电影剧本《记忆的温度》（完整 27 场）。包含场号、内外景、角色、
对白、动作描述等典型剧本结构，正是 Soundspeed 需要解析、分场入库、并与
现场实录比对的对象。

- **对应能力**：剧本导入分场（`POST /api/v1/scripts/*`）、实录↔剧本比对（L2）
- **对应报告**：§3、§4.2（原生函数调用全栈贯穿）

## 2. 图像模态 — 剧本照片 OCR

本目录未附剧本照片样本（现场拍摄照片含场地信息，不随公开仓库提交）。
图像链路的设计与兜底见 **§4.4 视觉：照片直接更新剧本**：剧本照片经同一个
Gemma 4 视觉投影器逐页 OCR（`IMAGE_TOKENS=1120` 高分辨率档），再经
`difflib` 与旧版增量合并后入库（`POST /api/v1/scenes/{id}/script/diff`）。
评审可用任意一张中文剧本照片走该端点复现。

## 3. 语音模态 — 原生音频输入（真正的多模态体现）

两段 WAV **不经转写，原始字节直接进入 Gemma 4**，由模型直接“听懂”口语意图
（§4.5）。注意：录音的逐字转写走 Whisper，**不经过 Gemma**；Gemma 的音频
能力专门用于“直接听懂用户口述的查询/备注”。

| 文件 | 中文原意 | 类型 | 期望行为 |
|------|---------|------|---------|
| `voice-query_first-scene-takes.wav` | “第一场拍了多少条” | 查询(QP) | 模型听懂 → 调 `get_scene_info` → 播报第一场镜次数 |
| `voice-note_third-take-low-volume.wav` | “这一条不错，但是第三条的声儿有点小” | 备注(NP) | 模型听懂 → `structure_note` 结构化归档（保留 / 音量偏低） |

- **对应能力**：语音调度器两跳 tool-loop（hop A 听懂意图 → hop B 强制取参数执行）
- **对应报告**：§4.5、§4.6
