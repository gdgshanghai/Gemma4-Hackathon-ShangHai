# AshPage Android

> **重点链接**
> 
> - 技术报告：[TECHNICAL_REPORT.md](./TECHNICAL_REPORT.md)
> - 演示视频：[Bilibili](https://www.bilibili.com/video/BV1uLEt6rE6S)

AshPage 灰页是一个原生 Android 端侧 Demo，用来验证“离线手写人格陪伴对象”的核心体验。用户在纸面画布上手写内容，App 将画布导出为 PNG bytes，交给本地 LiteRT-LM 多模态模型推理；模型以指定人格生成结构化纸面批注，Android 再把回复渲染回同一张纸上。

这个版本不是 WebView，也不启动本地 HTTP 服务。核心链路全部在 Android 设备本地完成：

1. 从 App 外部文件目录加载 `model.litertlm`。
2. 使用 LiteRT-LM 初始化本地模型，文本和视觉后端走 GPU。
3. 在原生 Android 纸面画布上采集用户手写。
4. 将当前画布导出为 PNG bytes。
5. 把图片 bytes 发送给本地多模态模型。
6. 当用户输入触发时，模型可以调用本地 Agent Skill 工具。
7. 模型返回 JSON canvas DSL。
8. Android 解析 JSON，并把人格回应渲染为纸面批注。

代码中仍保留音频录制能力，主要用于实验；当前实现以 **手写优先** 为主，语音不是主要交互路径。

## 产品定位

AshPage 是一个私密、离线、阅后即焚的情绪出口。项目边界不包括医疗、心理治疗或诊断能力。这里的目标体验是：用户把不想说出口的话写到一张“活纸页”上，然后某个人格在同一张纸上回应。

产品边界：

- 手写是主要输入方式。
- 用户内容不上传后端。
- 当前页面可以在每次交互后清空。
- 人格回应以纸面批注呈现，不使用聊天气泡。
- Agent Skill 已实现。
- Memory 记忆和主动打扰是下一阶段能力。

## 技术架构

```text
原生纸面画布
  -> PNG bytes
  -> LiteRT-LM 本地多模态推理
  -> 可选 Agent Skill 工具调用
  -> JSON canvas DSL
  -> CanvasCommand 解析
  -> 原生纸面批注渲染
```

主要模块：

- `MainActivity.kt`：负责 UI 搭建、模型加载、自动提交、推理生命周期、控制按钮和错误状态。
- `InkCanvasView.kt`：负责手写采集、PNG 导出、等待动效、命令布局和原生纸面渲染。
- `GemmaInference.kt`：负责 LiteRT-LM 引擎初始化、conversation 配置、tool calling、响应解析、JSON 恢复和命令标准化。
- `SkillRegistry.kt`：从 Android assets 加载本地 Skill。
- `SkillToolSet.kt`：将 `loadSkill(name)` 暴露为 LiteRT-LM Android tool。
- `AudioRecorder.kt`：录制 16 kHz 单声道 WAV bytes，用于实验性音频输入。

## 技术复杂度

这个 Demo 不是“写一段 prompt 然后显示模型文本”。它把端侧多模态推理、工具调用、结构化输出和原生画布渲染串成了一个完整闭环，技术复杂度主要体现在：

- **端侧多模态链路**：手写输入不是普通文本，而是 Android 原生画布导出的 PNG bytes；模型需要先做视觉理解，再生成符合人格的纸面回应。
- **LiteRT-LM 本地推理**：模型文件、cache、GPU/CPU backend、图片数量限制和 Android 生命周期都在本地设备上管理，不依赖云端兜底。
- **Agent Skill 工具调用**：App 不把完整 Skill 一次性塞进 prompt，而是先提供 Skill catalog，再通过 `loadSkill(name)` 按需加载完整 `SKILL.md`，减少上下文污染。
- **动态 Skill Registry**：`SkillRegistry` 从 assets 目录扫描 `skills/*/SKILL.md`，解析 frontmatter，生成可供模型选择的本地能力目录。
- **受约束的 Canvas DSL**：模型不能直接输出 UI 坐标，只能输出白名单 JSON command；Android 再把 command 映射为安全纸面元素。
- **响应恢复与安全解析**：`GemmaInference` 会移除 `<think>`、提取合法 JSON、兼容 fallback 字段、标准化非法字段，并在输出不足时补齐可见批注。
- **原生布局引擎**：`InkCanvasView` 需要根据用户手写边界、控件位置、屏幕边缘和元素优先级来放置文本和标记，避免批注重叠、越界或遮挡输入。
- **异步交互状态管理**：自动提交、手动发送、模型加载、等待动效、录音、推理中禁用控件、错误提示都需要在 Android 生命周期内协调。

这些设计让 AshPage 更接近一个端侧 AI 交互系统，而不是一个普通聊天界面。模型负责理解和决策，Android 负责约束、执行和渲染，两者通过稳定的 JSON DSL 和 tool calling 协议连接。

## 本地模型

将 LiteRT-LM 模型放到下面路径：

```txt
/sdcard/Android/data/com.fromink.v2/files/model.litertlm
```

ADB 示例：

```bash
adb shell mkdir -p /sdcard/Android/data/com.fromink.v2/files
adb push model.litertlm /sdcard/Android/data/com.fromink.v2/files/model.litertlm
adb shell ls -lh /sdcard/Android/data/com.fromink.v2/files/model.litertlm
```

Windows 示例：

```powershell
& "C:\Users\bob\AppData\Local\Android\Sdk\platform-tools\adb.exe" shell mkdir -p /sdcard/Android/data/com.fromink.v2/files
& "C:\Users\bob\AppData\Local\Android\Sdk\platform-tools\adb.exe" push "C:\Users\bob\Downloads\gemma-4-E2B-it.litertlm" /sdcard/Android/data/com.fromink.v2/files/model.litertlm
& "C:\Users\bob\AppData\Local\Android\Sdk\platform-tools\adb.exe" shell ls -lh /sdcard/Android/data/com.fromink.v2/files/model.litertlm
```

`GemmaInference` 当前初始化配置：

- `Backend.GPU()` 用于文本。
- `Backend.GPU()` 用于视觉。
- `Backend.CPU()` 用于音频。
- `maxNumImages = 1`。
- 使用 App cache 目录作为 LiteRT-LM cache 路径。

## Agent Skill 工具调用

当前 Android 端实现已经接入本地 Agent Skill，并通过 LiteRT-LM Android tool calling 暴露给模型。

当前流程：

1. `SkillRegistry` 扫描 `app/src/main/assets/skills/*/SKILL.md`。
2. 每个 `SKILL.md` 会解析 frontmatter 中的：
   - `name`
   - `description`
3. `GemmaInference` 将精简后的 Skill catalog 加入 system prompt。
4. `SkillToolSet` 暴露本地工具 `loadSkill(name)`。
5. `createConversationConfig()` 开启：
   - `tools = listOf(tool(skillToolSet))`
   - `automaticToolCalling = true`
6. 当模型识别到明确的方法类请求时，可以调用 `loadSkill("mao-zedong-thought")`。
7. 工具返回完整 `SKILL.md` 内容，供模型在当前轮次使用。

当前内置 Skill：

```txt
app/src/main/assets/skills/mao-zedong-thought/SKILL.md
```

当前 system prompt 会要求模型在用户明确请求毛泽东思想、`矛盾论`、`实践论`、`群众路线`、`调查研究`、`统一战线`、`主要矛盾` 或类似方法论分析时，先调用该 Skill。调用后仍然要保持当前人格和纸面批注风格，不向用户暴露 tool loading 等内部机制。

注意：

- Tool calling 依赖当前加载的 `.litertlm` 模型是否支持 LiteRT-LM tool calls。
- 如果模型不支持工具调用，App 仍可运行，但模型可能不会调用 `loadSkill`。

调试日志：

- `FromInkSkillRegistry`：Skill 加载数量和名称。
- `FromInkSkillTool`：`loadSkill` 命中或未命中。
- `FromInkGemma`：可用 Skill、tool 配置、原始响应、清洗后响应、解析出的 action 和 commands。

## Canvas DSL

模型回复不会被渲染成 HTML 或聊天气泡。模型必须输出一个 JSON object：

```json
{
  "recognized_text": "今天真的很烦",
  "action": "draw",
  "canvas": [
    {
      "type": "text",
      "text": "那就先别装作没事。",
      "target": "input",
      "anchor": "below_input",
      "size": "medium",
      "mood": "quiet",
      "rotate": -4
    },
    {
      "type": "underline",
      "target": "input",
      "anchor": "on_input",
      "mood": "sharp"
    }
  ]
}
```

顶层字段：

- `recognized_text`：识别出的手写或音频内容。
- `action`：`draw` 或 `stay_silent`。
- `canvas`：Android 端需要渲染的纸面批注命令。

支持的 command 类型：

- `text`
- `circle`
- `arrow`
- `underline`
- `dot`
- `small_note`
- `spark`
- `bracket`
- `question_mark`
- `speech_bubble`
- `burst`
- `emphasis_lines`
- `scribble`
- `strike`
- `reaction_mark`

支持的 anchor：

- `above_input`
- `below_input`
- `left_of_input`
- `right_of_input`
- `on_input`
- `paper_margin`
- `top_left`
- `top_right`
- `center`
- `bottom_left`
- `bottom_right`

模型不能输出原始 `x` / `y` 坐标。Android 会把 anchor 映射为安全纸面位置，加入轻微手写抖动，并通过布局候选点避免重叠和越界。

## 响应安全与兜底

`GemmaInference` 做了多层防御：

- 在解析 JSON 前移除 `<think>...</think>`。
- 如果原始文本中混入额外内容，会尝试提取第一个有效 JSON object。
- 兼容 `answer_text`、`fragments` 等 fallback 字段。
- 标准化不支持的 anchor、size、style、target 和 mood。
- 最多展示 6 个 command。
- 当识别文本非空时，确保一定有可见纸面回应。
- 当模型返回的 freestyle command 太少时，补充 focus mark。
- 只有完全空白或纯噪声输入才使用 `stay_silent`。

`InkCanvasView` 也做了渲染保护：

- PNG 导出前计算用户输入边界。
- 优先放置主文本。
- 将重点标记放在输入附近。
- 使用安全布局槽位和 fallback 候选点。
- 不接受模型直接控制原始坐标。
- 避开控制按钮和屏幕边缘。

## 构建

可以用 Android Studio 打开 `Android_v2`，也可以在 Android 工具链配置完成后运行：

```powershell
cd D:\Projects\FromInk\Android_v2
.\gradlew.bat assembleDebug
```

Android 配置：

- `compileSdk = 35`
- `minSdk = 26`
- `targetSdk = 35`
- `applicationId = "com.fromink.v2"`
- Kotlin JVM target `17`
- LiteRT-LM 依赖：
  `com.google.ai.edge.litertlm:litertlm-android:latest.release`

Assets 加载路径：

```kotlin
assets.srcDirs("src/main/assets", "../../frontend/assets")
```

这样 Android App 可以同时读取字体资源和本地 Skill。

部署说明：

- 本项目是 Android 端侧应用，不使用 Docker 部署。
- 运行时依赖本地 `.litertlm` 模型文件和 Android 设备，不依赖服务器。
- 实际部署路径就是按上面的 Gradle 构建步骤执行，再通过 `adb push model.litertlm` 放置模型文件。

硬件与环境：

- 测试手机：小米 13
- 测试平板：小米平板 Pro 7
- 目标平台：Android
- 构建方式：Android Studio 或 `.\gradlew.bat assembleDebug`
- Java / Kotlin 运行目标：JDK 17 / JVM target 17

## 手动验收

手写演示路径：

1. 在小米手机上安装并启动 App。
2. 确认状态从 `Loading model...` 变为 `Ready: model.litertlm`。
3. 在画布上手写一句情绪表达，例如：`今天真的很烦，不想理任何人`。
4. 等待 3 秒自动提交，或点击右下角发送按钮。
5. 确认等待点出现。
6. 确认画布上出现简短中文人格回应和纸面标记。
7. 点击清空，确认上一轮页面消失。

Agent Skill 冒烟测试：

1. 写一个明确触发 Skill 的输入，例如：`用主要矛盾分析一下我现在为什么这么烦`。
2. 提交手写内容。
3. Debug build 下查看 Logcat：
   - `FromInkGemma` 中出现 available skills。
   - `FromInkSkillTool` 中出现 `loadSkill called`。
   - `FromInkSkillTool` 中出现 `loadSkill hit name=mao-zedong-thought`。
4. 确认可见回复仍然简短、像纸面批注，而不是长篇论文。

可选音频测试：

1. 点击麦克风按钮开始录音。
2. 说一句短句。
3. 再次点击麦克风按钮停止录音。
4. 确认 App 将 WAV bytes 发送给本地模型，并渲染回应。

音频是次要实验能力，不作为主要交互路径。

## 后续计划

当前实现已经包含 Agent Skill 加载和 tool calling。下一阶段重点：

- **Memory 记忆**：本地、可重置的摘要和偏好状态，不保存完整原文。
- **主动打扰**：用户主动开启的本地提醒或人格问候，支持静默时间和频率控制。
- **人格包**：用本地 JSON 组合 tone、边界、默认 Skill 和 canvas 风格。
- **阅后即焚动效**：清空页面时加入褪色、灰烬或墨迹消散效果。
- **发布文档**：补充硬件演示步骤、模型来源说明和一键 debug build 指令。
