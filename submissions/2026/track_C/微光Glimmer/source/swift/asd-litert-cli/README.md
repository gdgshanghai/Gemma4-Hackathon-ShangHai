# ASD LiteRT-LM Swift CLI

这个 CLI 用于在 macOS 上加载当前 no-audio `.litertlm` 模型，并对单个视频执行行为标签推理。

## 用法

```bash
cd swift/asd-litert-cli
./run.sh /path/to/video.mp4
```

也可以直接使用 SwiftPM：

```bash
cd swift/asd-litert-cli
swift run asd-litert-cli /path/to/video.mp4
```

如果 SwiftPM 因官方 macOS binary artifact 命名打印诊断，`run.sh` 会在构建完成后直接执行生成的二进制，避免污染 CLI 输出。

默认模型路径：

```text
outputs/gemma4-asd-lora-r32-code9-zh-examples-noaudio-ep5-qlora-loftq-v1-litert-wi8-noaudio/asd-gemma4-code9-qlora-loftq-w8-noaudio.litertlm
```

覆盖模型路径：

```bash
swift run asd-litert-cli \
  --model-path /path/to/model.litertlm \
  /path/to/video.mp4
```

CLI 会读取仓库内现有的 `prompts/zh/system.md` 和 `prompts/zh/user.md`，不会在 Swift 代码里改写 prompt。

## 解释对话 REPL

单视频推理后可以进入解释对话：

```bash
cd swift/asd-litert-cli
./run.sh --explain-repl /path/to/video.mp4
```

流程：

- 先按原流程输出加载时间、raw 9-bit code、中文解析结果。
- CLI 会基于原始分类 system/user prompt 生成解释阶段 prompt，保留标签定义和任务边界，但替换/移除“只能输出 9-bit code”的格式约束。
- CLI 会基于同一批视频帧生成一段短的观察摘要，用于后续自然语言解释。
- CLI 会把 `raw code + 中文解析结果` 作为一条 assistant message 放进解释上下文。
- CLI 自动追加用户问题 `为什么？`，打印模型回复。
- 之后进入交互模式，输入 `/quit` 退出；解释阶段每次回复最多 3 句话，不使用 Markdown，语气尽量自然，不重复 app 层统一附加的免责声明。

解释阶段不会在每一轮重新发送视频帧，避免模型把后续追问当成新的视觉分类请求；它基于已经生成的 raw code、中文解析、视频观察摘要、解释阶段 prompt 和最近文本对话回答。默认保留最近 10 条文本消息：

```bash
./run.sh --explain-repl --history-k 10 --chat-max-output-tokens 512 /path/to/video.mp4
```
