# AshPage Android

> **Highlights**
> 
> - 中文说明: [README_zh.md](./README_zh.md)
> - Technical Report: [TECHNICAL_REPORT.md](./TECHNICAL_REPORT.md)
> - Demo Video: [Bilibili](https://www.bilibili.com/video/BV1uLEt6rE6S)

AshPage is a native Android prototype for an offline handwritten persona
companion. The user writes on a paper-like canvas, the app sends the canvas image
to a local LiteRT-LM multimodal model, and the model responds as a persona by
returning structured paper annotation commands.

This version is not a WebView app and does not start a local HTTP server. The
full demo loop runs on the Android device:

1. Load `model.litertlm` from the app external files directory.
2. Initialize LiteRT-LM with GPU text and vision backends.
3. Capture handwriting from a native Android paper canvas.
4. Export the active canvas to PNG bytes.
5. Send image bytes to the local multimodal model.
6. Let the model use the local Agent Skill tool when the prompt calls for it.
7. Parse the model's JSON canvas DSL response.
8. Render the persona reply back onto the native canvas as handwritten paper
   annotations.

Audio recording code still exists for experimentation, but the current
implementation is handwriting-first. Voice input remains a secondary path.

## Product Framing

AshPage is designed as a private, offline, ephemeral emotional outlet. Project
scope does not include medical, therapy, or diagnosis capabilities. The intended
experience is closer to writing to a live paper page: the user writes something
they do not want to say out loud, and a persona responds on the same paper.

Key product constraints:

- Handwriting is the primary input.
- User content is not uploaded to a backend.
- The active page can be cleared after each interaction.
- Persona replies are rendered as paper annotations, not chat bubbles.
- Agent Skill is implemented; Memory and proactive nudges are future work.

## Architecture

```text
Native paper canvas
  -> PNG bytes
  -> LiteRT-LM local multimodal inference
  -> optional Agent Skill tool call
  -> JSON canvas DSL
  -> CanvasCommand parser
  -> native paper annotation renderer
```

Main components:

- `MainActivity.kt`: UI assembly, model loading, auto-submit scheduling,
  inference lifecycle, controls, and error states.
- `InkCanvasView.kt`: handwriting capture, PNG export, waiting effect, command
  layout, and native paper rendering.
- `GemmaInference.kt`: LiteRT-LM engine setup, conversation config, tool calling,
  response parsing, JSON recovery, and command normalization.
- `SkillRegistry.kt`: loads bundled skills from Android assets.
- `SkillToolSet.kt`: exposes `loadSkill(name)` as a LiteRT-LM Android tool.
- `AudioRecorder.kt`: records 16 kHz mono WAV bytes for experimental audio
  input.

## Technical Complexity

This demo is not a simple prompt-to-text prototype. It combines on-device
multimodal inference, Android tool calling, structured model output, defensive
parsing, and native canvas rendering into one local interaction loop.

The main technical challenges are:

- **On-device multimodal pipeline**: handwriting is captured as native canvas
  strokes, exported as PNG bytes, interpreted by a local vision-language model,
  and converted into persona-specific paper annotations.
- **LiteRT-LM local runtime**: model file placement, cache path, GPU/CPU
  backends, image limits, and Android lifecycle errors are all handled on the
  device without a backend fallback.
- **Agent Skill tool calling**: the system prompt includes only a compact skill
  catalog; the model can call `loadSkill(name)` to fetch the full `SKILL.md`
  only when the current user input needs it.
- **Dynamic Skill Registry**: `SkillRegistry` scans `skills/*/SKILL.md` from
  Android assets, parses frontmatter, and builds a local capability catalog for
  the model.
- **Constrained Canvas DSL**: the model cannot control raw UI coordinates. It
  returns whitelisted JSON commands, and Android maps them into safe paper
  elements.
- **Response recovery and validation**: `GemmaInference` strips thinking blocks,
  extracts valid JSON from noisy output, accepts fallback fields, normalizes
  invalid values, and adds fallback marks when the model output is incomplete.
- **Native layout engine**: `InkCanvasView` places text and marks around the
  user's handwriting while avoiding screen edges, controls, overlap, and
  unreadable layouts.
- **Async state coordination**: auto-submit, manual send, model loading, waiting
  animation, audio recording, disabled controls during inference, and error
  messages are coordinated inside the Android lifecycle.

These choices make AshPage closer to an on-device AI interaction system than a
chat UI. The model decides what should happen, while Android constrains,
executes, and renders the result through JSON DSL and tool calling contracts.

## Local Model

Put a LiteRT-LM model at:

```txt
/sdcard/Android/data/com.fromink.v2/files/model.litertlm
```

ADB example:

```bash
adb shell mkdir -p /sdcard/Android/data/com.fromink.v2/files
adb push model.litertlm /sdcard/Android/data/com.fromink.v2/files/model.litertlm
adb shell ls -lh /sdcard/Android/data/com.fromink.v2/files/model.litertlm
```

Windows example:

```powershell
& "C:\Users\bob\AppData\Local\Android\Sdk\platform-tools\adb.exe" shell mkdir -p /sdcard/Android/data/com.fromink.v2/files
& "C:\Users\bob\AppData\Local\Android\Sdk\platform-tools\adb.exe" push "C:\Users\bob\Downloads\gemma-4-E2B-it.litertlm" /sdcard/Android/data/com.fromink.v2/files/model.litertlm
& "C:\Users\bob\AppData\Local\Android\Sdk\platform-tools\adb.exe" shell ls -lh /sdcard/Android/data/com.fromink.v2/files/model.litertlm
```

`GemmaInference` initializes LiteRT-LM with:

- `Backend.GPU()` for text.
- `Backend.GPU()` for vision.
- `Backend.CPU()` for audio.
- `maxNumImages = 1`.
- app cache directory as the LiteRT-LM cache path.

## Agent Skill Tool Calling

The current Android implementation registers local Agent Skills through
LiteRT-LM Android tool calling.

Current flow:

1. `SkillRegistry` scans `app/src/main/assets/skills/*/SKILL.md`.
2. Each `SKILL.md` is parsed for frontmatter metadata:
   - `name`
   - `description`
3. `GemmaInference` adds a compact skill catalog to the system prompt.
4. `SkillToolSet` exposes a local `loadSkill(name)` tool.
5. `createConversationConfig()` enables:
   - `tools = listOf(tool(skillToolSet))`
   - `automaticToolCalling = true`
6. When the model detects a matching method request, it can call
   `loadSkill("mao-zedong-thought")`.
7. The tool returns the full `SKILL.md` content to the model for that turn.

Bundled skill:

```txt
app/src/main/assets/skills/mao-zedong-thought/SKILL.md
```

The current system prompt instructs the model to call this skill when the user
explicitly asks for Mao Zedong Thought, `矛盾论`, `实践论`, `群众路线`, `调查研究`,
`统一战线`, `主要矛盾`, or similar method-driven analysis. The skill should be
used as an analytical aid while preserving the active persona and concise paper
annotation style.

Important limitation:

- Tool calling depends on the loaded `.litertlm` model supporting LiteRT-LM tool
  calls. If the model does not support tools, the app still runs, but
  `loadSkill` may never be invoked.

Debug logs:

- `FromInkSkillRegistry`: loaded skill count and names.
- `FromInkSkillTool`: `loadSkill` hits and misses.
- `FromInkGemma`: available skills, tool configuration, raw response, sanitized
  response, parsed action, and parsed commands.

## Canvas DSL

Model responses are not rendered as HTML or chat bubbles. The model must output
one JSON object:

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

Top-level fields:

- `recognized_text`: recognized handwriting or audio content.
- `action`: `draw` or `stay_silent`.
- `canvas`: annotation commands rendered by Android.

Supported command types:

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

Supported anchors:

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

The model must not output raw `x`/`y` coordinates. Android maps anchors to safe
paper positions, applies handwritten jitter, resolves overlap through layout
candidates, and keeps rendered elements inside the canvas.

## Response Safety And Recovery

`GemmaInference` includes several defensive steps:

- Removes `<think>...</think>` blocks before JSON parsing.
- Extracts the first valid response-like JSON object if the raw text has extra
  wrapper text.
- Accepts fallback fields such as `answer_text` or `fragments`.
- Normalizes unsupported anchors, sizes, text styles, targets, and moods.
- Caps visible commands to six items.
- Ensures non-empty recognized text produces a visible paper response.
- Adds fallback focus marks when the model returns too few freestyle commands.
- Uses `stay_silent` only for truly blank or pure-noise input.

`InkCanvasView` also protects rendering:

- Computes the original input bounds before PNG export.
- Prioritizes primary text placement.
- Places focus marks near the input.
- Uses safe layout slots and fallback candidates.
- Avoids raw model-controlled coordinates.
- Keeps controls and screen edges clear.

## Build

Open `Android_v2` in Android Studio, or run Gradle from this directory when the
Android toolchain is configured:

```powershell
cd D:\Projects\FromInk\Android_v2
.\gradlew.bat assembleDebug
```

Android configuration:

- `compileSdk = 35`
- `minSdk = 26`
- `targetSdk = 35`
- `applicationId = "com.fromink.v2"`
- Kotlin JVM target `17`
- LiteRT-LM dependency:
  `com.google.ai.edge.litertlm:litertlm-android:latest.release`

Assets are loaded from:

```kotlin
assets.srcDirs("src/main/assets", "../../frontend/assets")
```

This keeps bundled fonts and local skills available to the Android app.

Deployment note:

- This project is an Android on-device app and does not use Docker deployment.
- Runtime depends on a local `.litertlm` model file and Android hardware, not a
  backend service.
- The deployment path is the Gradle build above plus `adb push model.litertlm`
  to place the local model file.

Hardware and environment:

- Test phone: Xiaomi 13
- Test tablet: Xiaomi Pad Pro 7
- Target platform: Android
- Build path: Android Studio or `.\gradlew.bat assembleDebug`
- Java / Kotlin target: JDK 17 / JVM target 17

## Manual Test

Handwritten demo path:

1. Install and run the app on the Xiaomi phone.
2. Confirm the status changes from `Loading model...` to
   `Ready: model.litertlm`.
3. Write a short emotional sentence on the canvas, for example:
   `今天真的很烦，不想理任何人`.
4. Wait 3 seconds for auto-submit, or tap the lower-right send icon.
5. Confirm the waiting dots appear.
6. Confirm the canvas shows a concise Chinese persona reply plus paper marks.
7. Tap clear and confirm the previous page disappears.

Agent Skill smoke test:

1. Write a prompt that clearly asks for a supported method, for example:
   `用主要矛盾分析一下我现在为什么这么烦`.
2. Submit the handwriting.
3. In a debug build, check Logcat for:
   - available skills in `FromInkGemma`
   - `loadSkill called` in `FromInkSkillTool`
   - `loadSkill hit name=mao-zedong-thought`
4. Confirm the visible reply is still concise and paper-like, not a long essay.

Optional audio test:

1. Tap the mic icon to start recording.
2. Say a short sentence.
3. Tap the mic icon again to stop recording.
4. Confirm the app sends WAV bytes to the local model and renders a response.

Audio is a secondary experimental capability and not the primary interaction
path.

## Future Work

Current implementation includes Agent Skill loading and tool calling. Future work
should focus on:

- **Memory**: local, user-resettable summaries and preference state; no full
  transcript storage.
- **Proactive nudges**: opt-in local reminders or persona check-ins with quiet
  hours and per-persona frequency controls.
- **Persona packages**: JSON-backed local personas that combine tone,
  boundaries, default skills, and canvas style.
- **Ephemeral animation**: page fade, ash, or ink-dissolve effects when clearing
  the page.
- **README / release packaging**: clearer hardware demo steps, model source
  notes, and one-command debug build instructions.
