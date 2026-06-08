# gemma4-screening

用 **Gemma 4 多模态（端侧）** 做自闭症**行为视频**早期信号筛查。全程在设备本地运行，健康/儿童数据不离开设备（可飞行模式运行）。

> ⚠️ 本工具仅作**早期信号提示**，不构成诊断。结论需由专业人员评估。

## 当前架构（端侧运行时：llama.cpp GGUF + mtmd）

| 项 | 说明 |
|---|---|
| 运行时 | **llama.cpp b9536 / GGUF / Metal / mtmd**（vendored 为 `ios/Vendor/llama.xcframework`） |
| 模型 | `model-Q4_K_M.gguf` + `mmproj-bf16.gguf`（主模型 + 多模态 projector，合计约 5.9GB，不入库、不随包；首次启动自动下载） |
| 输入 | 视频抽帧（最多 32 帧）→ 音频 WAV（最多 30 秒）→ 中文文字指令 |
| 输出 | 模型只产出 **B01–B09 的 9 位二进制码**（`^[01]{9}$`）；最终 JSON（含 B10）由 **app 端拼装**后渲染为中文报告 |
| 解释对话 | 报告完成后新建一个包含同一批 frames/audio 的 explanation conversation；后续用户只追加文本问题 |
| 设备 | iPhone 真机优先使用 Metal；模拟器/本机编译路径用于集成验证 |

> 当前不再走旧的 `.litertlm` 路径，也不把 GGUF 权重打进 app bundle。旧文件如果还在 `ios/Model/`，不会被当前 `project.yml` 和 `ScreeningService` 引用。

## 接入规范（对齐模型侧官方文档）

抽帧、尺寸、prompt、解码参数严格复现 Mac/Linux GGUF 评估配置，详见仓库根目录的 [`docs/ios_gguf_code9_waudio_integration.md`](../docs/ios_gguf_code9_waudio_integration.md)：

- 抽帧：`frame_count = max(1, min(32, ceil(时长秒)))`；ASD-DS 文件优先使用文件名里的 `end-start` clip 时长；时间戳对齐本地 eval 的 ffmpeg `fps` 采样（`t = i*dur/frame_count`，起点锚定、顺序、覆盖整段）；每帧宽 512、保持比例、偶数高度、RGB、JPEG q95。
- 音频：单声道 16 kHz PCM WAV，最多 30 秒，并裁剪/补零到精确 PCM sample 数。
- 分类顺序：`frames → audio → text instruction`；每段片段**新建 classification conversation，无历史**。
- system / user prompt 逐字使用 `prompts/zh` 中文原文（**不让模型吐 JSON**）。
- 解码：确定性 `temperature=0 / topK=1 / topP=1`，并使用 GBNF grammar 约束正好 9 位。
- 输出：模型回 **9 位二进制码**，端上 `^[01]{9}$` 严格校验 → 拼装 JSON（`B10 = (B01..B09 全 false)`），非法码拦截。
- 解释对话：识别完成后另起一个 **explanation conversation**，初始上下文包含同一批 `frames → audio`、解释 prompt、9-bit code 和 app 解析后的 B01–B10 结果；之后只追加文本问题，不再提供附件入口。

## 状态

- ✅ SwiftPM core contract 测试通过：parser、B10 派生、prompt/media 顺序、采样参数、中文 prompt。
- ✅ iOS package simulator/device triple build 通过：`GlimmerCore` + `AsdGgufNative` + `GlimmerIOS`。
- ✅ 已生成 `ios/Vendor/llama.xcframework`，包含 `libllama`、`ggml`、`ggml-metal`、`ggml-blas`、`mtmd`。
- ✅ 报告页已支持本地解释对话：新建 multimodal explanation session，后续文本追问复用同一 session/KV cache。
- ✅ 已加真机 parity runner：可分别测试预构建 media 目录推理，以及 raw video → iOS preprocessing 的诊断输出。
- ✅ 首次启动自动下载两个 GGUF 权重到 Application Support，支持 `.part` 断点续传和 sha256 校验；同一模型 URL 已校验通过后，升级 app 不会重新下载。

## 目录

- `core/` — 跨平台 SwiftPM core，保存 GGUF 推理合约、prompt、parser 和测试。
- `ios/` — 端侧 SwiftUI app（GGUF）
  - `Package.swift` — SwiftPM package，管理 `GlimmerIOS`、`AsdGgufNative` 和 `llama.xcframework`
  - `App/` — 极薄 iOS app host，只负责 app entrypoint、Info.plist、entitlements、bundle/signing
  - `Sources/GlimmerIOS/ScreeningService.swift` — GGUF 权重定位、system prompt、9 位码解析、解释对话状态
  - `Sources/GlimmerIOS/AsdGgufRunner.swift` — Swift runner，串行后台调用 native bridge
  - `Sources/GlimmerIOS/VideoAudioPreprocessor.swift` — 抽帧 + 音频提取（按 GGUF eval 规范）
  - `Sources/GlimmerIOS/ReportHeaderView.swift` / `ExplanationChatView.swift` — 报告详情与本地文本对话 UI
  - `Sources/GlimmerIOS/ParityTestRunner.swift` — 预构建 media 目录的真机推理 parity runner
  - `Sources/GlimmerIOS/PreprocessParityRunner.swift` — raw video 真机预处理诊断 runner
  - `Sources/AsdGgufNative/` — Objective-C++ bridge，直接调用 llama.cpp / mtmd / grammar sampler
  - `Sources/GlimmerIOS/ReportView.swift` — B01–B10 严格校验 + 报告渲染
  - `Vendor/` — `llama.xcframework`
  - `Resources/ModelManifest.json` — 远程 GGUF URL、size 和 sha256 manifest
- `docs/ios_gguf_code9_waudio_integration.md` — GGUF 接入规范（输入/输出/问题诊断）
- `finetune/` — LoRA 微调脚本与数据格式
- `data/` — 样例数据集

## 模型下载

模型权重**不入库、不随包**。app 首次启动时会读取 `ios/Resources/ModelManifest.json`，把两个 GGUF 下载到沙盒的 `Application Support/GlimmerModels/`：

| 项 | 值 |
|---|---|
| 主模型 | `https://huggingface.co/chenghuzi/glimmer-e4b-asd9-gguf/resolve/main/model-Q4_K_M.gguf` |
| projector | `https://huggingface.co/chenghuzi/glimmer-e4b-asd9-gguf/resolve/main/mmproj-bf16.gguf` |
| 本地路径 | `Application Support/GlimmerModels/model-Q4_K_M.gguf` 和 `Application Support/GlimmerModels/mmproj-bf16.gguf` |
| 大小 | 主模型约 4.9GB，projector 约 946MB |

下载完成后会写入同目录 receipt。只要 manifest 里的 URL 不变，且本地 receipt 与文件 size 匹配，app 升级不会重新下载。若 URL 变化，app 会重新校验本地文件；校验不通过才重新下载。

## 构建（iOS）

### 签名与工程生成

`ios/GemmaScreen.xcodeproj/` 是生成产物，已被 `.gitignore` 忽略。不要手改或提交其中的 `project.pbxproj`、workspace 或 scheme；如果需要改 target、build settings、资源、脚本阶段或 signing 引用，改 `ios/project.yml`，然后重新生成工程。

本机签名配置只放在 `ios/.env`，不入库。首次配置：

```bash
cd ios
cp .env.example .env
```

然后编辑 `.env`：

| 变量 | 说明 |
|---|---|
| `GEMMASCREEN_PRODUCT_BUNDLE_IDENTIFIER` | 主 App bundle id |
| `GEMMASCREEN_DEVELOPMENT_TEAM` | 主 App Apple Developer Team ID |
| `GLIMMER_GALLERY_PRODUCT_BUNDLE_IDENTIFIER` | Gallery target bundle id |
| `GLIMMER_GALLERY_DEVELOPMENT_TEAM` | Gallery target Apple Developer Team ID |

每次 pull 后、`.env` 变化后、或 `project.yml` 变化后，都运行：

```bash
./Scripts/generate-xcodeproj.sh
```

这个脚本会加载 `.env`、校验必填变量，并用 `xcodegen generate` 生成 `GemmaScreen.xcodeproj`。这样签名变更只影响本机 `.env`，不会污染 Git 里的工程配置。

### 真机构建

```bash
cd ios
./Scripts/generate-xcodeproj.sh
xcodebuild -project GemmaScreen.xcodeproj -target GemmaScreen \
  -destination 'id=<DEVICE_UDID>' -allowProvisioningUpdates build
```

本工程的核心代码和 native bridge 由 SwiftPM 管理；`GemmaScreen.xcodeproj` 是由 `project.yml` 生成的 iOS app host，负责 bundle、签名、entitlements 和安装运行。日常可以不打开 Xcode，直接用 `./Scripts/generate-xcodeproj.sh` + `xcodebuild`。

`.env` 保存本机签名配置，不入库；`project.yml` 通过 `${GEMMASCREEN_DEVELOPMENT_TEAM}`、`${GEMMASCREEN_PRODUCT_BUNDLE_IDENTIFIER}` 等变量读取本机值。不同开发者只需要维护自己的 `.env`。

> 当前本机 Xcode 环境可能要求 iOS 26.4 runtime；如果 `xcodebuild` 报 destination 不可用，需要先在 Xcode Components 安装对应 runtime，或切到匹配的 Xcode/设备 SDK。

## 行为标签（B01–B10）

| ID | 行为特征 |
|---|---|
| B01 | 缺乏或回避眼神接触 |
| B02 | 攻击行为 |
| B03 | 对感觉输入反应过度或不足 |
| B04 | 对言语互动缺乏回应 |
| B05 | 非典型语言 |
| B06 | 物体排列 |
| B07 | 自我击打或自伤行为 |
| B08 | 自我旋转或旋转物体 |
| B09 | 上肢刻板动作 |
| B10 | 背景（无明显目标行为） |
