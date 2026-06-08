# 学伴精灵 Study Companion

演示视频地址：
https://www.bilibili.com/video/BV18sE36hEhZ/?vd_source=2be4efa5aa74af3c490284bf780aef66

> 让 AI 从屏幕走进现实，在每一次观察、对话与探索中陪伴学习。

**学伴精灵**是一套基于 Gemma 4 多模态能力构建的双端智能学习平台，由 **XR 沉浸式伴学空间**与 **移动端文化知识导览 App** 组成。

平台通过两个场景化 AI 精灵陪伴学习者：

- **小 P（XR 端）**：在 Meta Quest 混合现实空间中陪伴儿童学习英语，通过语音对话、物体识别、跟读练习与虚拟食物互动，将语言学习融入真实环境。
- **小瓷（App 端）**：在手机端识别陶瓷器物，讲解器物名称、釉色、纹饰、工艺与历史文化，并支持语音导览和继续追问。

学伴精灵希望让学习不再局限于教材和搜索框，而是成为一场可以看见、听见、触碰并持续对话的探索。

---

## 项目亮点

- **双端伴学体验**：同时覆盖 Meta Quest XR 与 Flutter 移动端。
- **Gemma 4 多模态理解**：融合文本、图像、音频与现实物体信息。
- **场景化 AI 角色**：使用小 P 和小瓷承载不同学习领域的交互体验。
- **自然语音交互**：支持语音检测、双语识别、语音播报与连续追问。
- **现实环境学习**：通过物体识别、Passthrough Camera 与手机相机理解真实世界。
- **本地与局域网推理**：支持端侧模型或局域网 Gemma 4 服务，兼顾隐私与部署灵活性。
- **游戏化学习反馈**：通过精灵动画、食物生成、喂食和鼓励反馈增强学习动力。

---

## 双端产品架构

```text
                         学伴精灵 Study Companion
                                   |
                 +-----------------+-----------------+
                 |                                   |
          XR 沉浸式伴学端                        移动文化导览端
          Meta Quest / Unity                    Flutter / iOS / Android
                 |                                   |
      小 P：英语对话与现实物体学习             小瓷：陶瓷识别与文化讲解
                 |                                   |
      音频 / 物体 / Passthrough 图像               相机 / 相册 / 语音
                 +-----------------+-----------------+
                                   |
                    Gemma 4 本地或局域网多模态服务
```

两个终端面向不同的学习场景，但共享同一核心理念：让 AI 主动理解学习者所处的环境，并以亲切的角色持续提供解释、引导与反馈。

---

## XR 端：小 P 英语伴学空间

XR 端面向 Meta Quest，将真实环境转化为可互动的英语学习空间。学习者可以直接与 Sparrow 精灵“小 P”说话、指向现实物体提问，并使用英语请求和投喂虚拟食物。

### 核心功能

- **常态语音检测**：检测玩家开始说话后自动录音，并通过预录音减少句首丢失。
- **双语语音识别**：通过豆包 WebSocket ASR 识别中英文。
- **双语 AI 教师**：Gemma 4 以适合儿童的中英双语方式回答问题。
- **双推理后端**：
  - Quest 端 LiteRT-LM 本地 Gemma 4 模型。
  - 局域网 OpenAI-compatible Chat Completions 服务。
- **两种物体识别方式**：
  - Object Detection 与手部指向射线。
  - Passthrough Camera 截图与 Gemma 4 Vision。
- **游戏化食物互动**：
  - 使用 `Please give me a tomato.` 等英语句子生成食物。
  - 使用 `come here` 让小 P 飞向食物。
  - 将食物放到 Mouth Collider，触发进食动画和感谢反馈。
- **精灵行为系统**：支持入场、回到视野、飞向食物、空闲、说话与进食动画。
- **运行状态 UI**：显示网络、ASR、模型、对话文本和录音波形状态。

### XR 交互示例

| 操作或语句 | 小 P 的响应 |
| --- | --- |
| 玩家开始说话 | VAD 自动开始语音识别 |
| 指向物体并询问“这是什么” | 回答物体的中文名与英文名 |
| `Please give me a tomato.` | 在玩家右手上方生成 Tomato |
| `come here` | 飞向最近生成的食物 |
| 将食物放到小 P 嘴边 | 播放进食动画并给予语音反馈 |

### XR 运行流程

```text
麦克风 / VAD
    |
    +-- 豆包 ASR ------> 文本 -------------------+
    |                                          |
    +-- Gemma 4 Audio HTTP ---------------------+--> Gemma 4 --> 对话 / 指令 --> 豆包 TTS

手部指向 + Object Detection --------------------+
Passthrough Camera + Gemma 4 Vision -------------+
```

---

## App 端：小瓷文化知识导览

App 端是一款融合 AI 视觉识别、本地多模态模型与语音交互的陶瓷知识导览工具。用户只需拍摄或选择一张陶瓷图片，小瓷便会生成专业且易懂的器物讲解。

### 核心功能

- **AI 陶瓷识别**：通过相机拍摄或从系统相册选择图片。
- **结构化知识讲解**：生成器物名称、工艺特点、纹饰釉色与历史背景。
- **小瓷语音导览**：支持将生成的讲解内容转换为语音。
- **语音继续追问**：用户可围绕器物继续向小瓷提问。
- **本地模型推理**：连接局域网内的 Gemma 4 多模态服务，减少图片上传至公共云端的需求。
- **中英双语模式**：支持中文与英文识别讲解。
- **明暗主题切换**：提供东方瓷器美学风格的浅色与深色主题。
- **多端图片选择**：支持 iPhone、Android 系统相册与桌面文件选择。

### App 使用流程

1. 打开 App，进入瓷语考古助手首页。
2. 点击 **拍摄**，或从相册中 **选择图片**。
3. 点击 **开始识别（本地模型）**。
4. 查看器物名称、工艺特点与历史讲解。
5. 聆听语音导览，或继续向小瓷语音提问。

---

## 应用场景

### 儿童沉浸式英语学习

小 P 将现实物体、语音对话和游戏化反馈结合起来，让儿童在自然互动中练习英语表达。

### 博物馆与文化场馆导览

用户使用小瓷拍摄展柜中的陶瓷器物，即可获得通俗、生动的 AI 讲解。

### 家庭探索式学习

学习者可以在家中指向物体学习英文，也可以拍摄器物探索历史与传统文化。

### 隐私友好的本地教学

通过 Quest 本地模型或局域网 Gemma 4 服务完成推理，为学校、家庭和展馆提供更灵活的部署方式。

---

## 技术架构

| 领域 | XR 端 | App 端 |
| --- | --- | --- |
| 客户端 | Unity / C# / Meta Quest | Flutter / Dart |
| AI 模型 | Gemma 4 LiteRT-LM 或 LAN HTTP | Gemma 4 多模态 LAN 服务 |
| 视觉输入 | Object Detection、Passthrough Camera | 手机相机、系统相册 |
| 语音输入 | VAD、豆包 ASR、Gemma 4 Audio | `speech_to_text` |
| 语音输出 | 豆包 TTS | `flutter_tts` |
| 网络协议 | OpenAI-compatible Chat Completions | Ollama Chat API |
| 交互特色 | 空间指向、精灵动画、食物互动 | 图像识别、文化讲解、语音追问 |

---

## 环境要求

### XR 端

- Unity `6000.4.3f1`
- Android Build Support、SDK、NDK 与 OpenJDK
- Meta Quest 设备
- Meta XR SDK `201.0.0`
- Universal Render Pipeline `17.4.0`
- Unity OpenXR `1.17.0`
- Meta OpenXR `2.5.0`
- Unity AI Inference `2.3.0`
- 豆包语音服务账号与 ASR/TTS 凭据
- 可选：LiteRT-LM 兼容的 Gemma 4 `.litertlm` 模型
- 可选：支持音频或图像输入的局域网 Gemma 4 服务

### App 端

- Flutter SDK
- Dart SDK
- iOS、Android 或 macOS 运行环境
- 已安装并运行 Gemma 4 多模态模型的局域网服务

---

## 快速开始

### 运行 XR 端

1. 使用 Unity Hub 打开 XR 项目。
2. 将构建平台切换为 Android。
3. 打开 `Assets/Scenes/GemmaTest.unity`。
4. 将 `GemmaTest` 加入 Build Settings，并设为启动场景。
5. 在 `AndroidSpeechInput` 和 `AndroidTextToSpeech` 中配置豆包凭据。
6. 配置本地 Gemma 4 模型或局域网 HTTP 服务。
7. 连接 Quest，构建并运行 APK。

> 完整英语伴学功能需要使用 `GemmaTest.unity`，而不是默认的 `SampleScene.unity`。

### 运行 App 端

安装 Flutter 依赖：

```bash
flutter pub get
```

配置 `config.json`：

```json
{
  "OLLAMA_BASE_URL": "http://你的局域网IP:11434",
  "OLLAMA_MODEL": "你的Gemma4多模态模型名称"
}
```

启动 App：

```bash
flutter devices
flutter run -d <device-id> --dart-define-from-file=config.json
```

确保运行 App 的设备与 Gemma 4 服务位于同一局域网。

---

## 关键配置

### XR 端 Gemma 4 配置

本地模型运行配置：

```text
Assets/Resources/GemmaNpcConfig.json
```

角色提示词：

```text
Assets/Resources/GemmaNpcRolePrompt.txt
```

HTTP 服务配置：

```text
Assets/Resources/GemmaChatRequestConfig.asset
```

局域网接口需兼容：

```http
POST /v1/chat/completions
```

### App 端 Gemma 4 配置

App 通过 `config.json` 配置局域网模型地址和模型名称，并通过聊天接口发送压缩后的图片与提示词。

---

## 项目结构

```text
StudyCompanion/
├── xr/                              # Meta Quest XR 英语伴学端
│   ├── Assets/
│   │   ├── FoodPrefab/
│   │   ├── Resources/
│   │   ├── Scenes/GemmaTest.unity
│   │   └── Scripts/EnglishNpc/
│   └── Packages/
├── app/                             # Flutter 陶瓷文化导览端
│   ├── assets/
│   │   ├── app_icon.png
│   │   └── mascot_xiaoci.png
│   ├── lib/
│   │   ├── main.dart
│   │   ├── splash_screen.dart
│   │   └── home_page.dart
│   ├── config.json
│   └── pubspec.yaml
└── README.md
```

---

## 权限与安全

### 所需权限

- Quest 麦克风、网络、手部追踪与 Passthrough Camera 权限。
- App 相机、相册、麦克风、语音识别与本地网络权限。

### 安全建议

- 不要将真实 API Key、App ID、Access Token 或私有局域网地址提交到公开仓库。
- 已写入 Unity Scene、Prefab 或 Asset 的凭据应在提交前撤销并重新生成。
- 不要直接提交大型 Gemma 4 模型文件，建议使用下载脚本、Release 或 Git LFS。
- AI 识别与讲解结果仅用于学习和导览参考，不构成专业鉴定结论。

---

## 当前限制

- XR 的 Passthrough Vision 与音频直传依赖支持对应多模态格式的 Gemma 4 HTTP 服务。
- Quest 本地 LiteRT-LM 路径目前主要用于文本推理。
- XR 空间交互功能需要在 Quest 真机验证。
- App 的陶瓷识别准确度取决于图片质量与所使用的多模态模型。
- 两端目前共享产品理念与模型能力，尚未实现账号、学习记录与内容的跨端同步。

---

## 产品愿景

传统学习工具往往要求学习者主动寻找答案，而学伴精灵希望让 AI 主动走进学习发生的现场。

在 XR 空间中，小 P 陪伴孩子观察现实、开口表达；在移动端，小瓷陪伴用户发现器物之美、聆听历史回声。不同终端、不同角色，共同构成一个能够理解环境、自然交流并持续鼓励学习者的智能伴学系统。

**所见皆可问，所学皆有伴。**

---

## License

公开发布前，请补充统一的 `LICENSE`，并确认 Meta XR、Sparrow 模型、Food Pack、Gemma 4 模型、字体与其他第三方资源的授权范围。
