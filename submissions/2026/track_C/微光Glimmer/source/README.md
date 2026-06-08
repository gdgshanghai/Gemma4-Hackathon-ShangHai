<p align="center">
  <img src="assets/readme/glimmer-icon.png" width="112" alt="Glimmer app icon" />
</p>

<h1 align="center">微光 Glimmer</h1>

<p align="center">
  基于 Gemma 4 E4B 的端侧多模态 ASD 行为早期信号筛查模型与 iOS/macOS 应用。
</p>

<p align="center">
  <a href="https://huggingface.co/chenghuzi/glimmer-e4b-asd9-gguf">GGUF Weights</a>
  ·
  <a href="glimmer-ios/README.md">iOS/macOS App</a>
  ·
  <a href="slides/glimmer-tech-route.md">Technical Route Slides</a>
</p>

> 微光 Glimmer 是筛查支持工具，只识别视频中可观察的行为信号，不提供医学诊断。任何结论都应由专业人员结合完整访谈和临床评估判断。

## TL;DR

微光 Glimmer 把 Gemma 4 E4B 从通用多模态模型微调成一个本地运行的儿童 ASD 相关行为信号识别模型。用户在 iPhone 或 Mac 上选择一段视频，模型在设备本地读取视频帧与音频，输出 B01-B09 的 9 位行为码；应用端再派生 B10 背景标签，生成家长可读的报告，并支持围绕同一段视频继续本地解释对话。

Tech highlights:

- Gemma 4 E4B 多模态监督微调：每个训练样本都把视频帧和音频对齐到同一组结构化行为标签。
- 9-bit 行为码：把开放式生成压缩成稳定的多标签判别问题，降低量化后输出漂移。
- GGUF 混合精度部署：主模型 `Q4_K_M`，多模态 projector 保留 BF16，合计约 5.9 GB。
- grammar-constrained decoding：iOS/macOS 推理阶段强制只生成 9 位 `0/1`。
- local-first app：除首次下载模型权重外，视频文件会留在本地，报告与追问对话也不会离开设备。

## Quick Links

| Item | Where |
| --- | --- |
| Demo video | 随 hackathon 官方提交表单提供。 |
| iOS TestFlight | https://testflight.apple.com/join/5S8qS56v |
| iOS/macOS source code | `glimmer-ios/` |
| GGUF model weights | https://huggingface.co/chenghuzi/glimmer-e4b-asd9-gguf |
| Technical route deck | `slides/glimmer-tech-route.md` |
| Mac/Linux GGUF eval entry | `eval_gguf_llama_cpp.py` |
| Full training entry | `scripts/run_code9_r32_ep10_qlora_loftq_waudio_wi8.sh` |

<p align="center">
  <a href="https://testflight.apple.com/join/5S8qS56v">
    <img src="assets/readme/testflight-qr.png" width="160" alt="Glimmer TestFlight QR code" />
  </a>
</p>
<p align="center">
  <sub>扫码或点击加入微光 Glimmer iOS TestFlight 测试。</sub>
</p>

## 什么是微光 Glimmer

微光 Glimmer 是一个基于 Google Gemma 4 E4B-it 的多模态微调模型，用视频和音频片段识别儿童社交行为中可能出现的 9 类 ASD 相关行为信号。模型权重以 Apache-2.0 形式发布为 GGUF，可在同名 iOS/macOS app 中本地使用，也可通过 macOS/Linux GGUF CLI 路径复现实验评测。

## 背景与动机

我从事自闭症相关的计算神经科学研究，关注如何利用大语言模型作为代理模型，探索自闭症人群语言生成背后的神经机制。在这个过程中，我们反复遇到一个现实问题：ASD 很难靠一次实验室检查直接确诊；它在临床上高度依赖经验丰富的专业人员，需要他们结合行为表现与社交互动方式，再把发育史纳入整体判断。

根据 [CDC ADDM Network 2022 数据](https://www.cdc.gov/autism/data-research/index.html)，约 1/31，即 3.2% 的 8 岁儿童被识别为 ASD。如果把这个比例粗略外推到中国儿童人口规模，会得到一个远高于公开登记统计口径的数字：按约 2.1 亿儿童估算，潜在 ASD 儿童数量约为 680 万；而[公开登记统计口径](https://www.nhc.gov.cn/fys/c100078/202209/0cb5cf9dd3964c0ab46beb31c1be312d.shtml)中的儿童 ASD 数量约为 200 万。这个数量级差异不能简单解释成种族或体质差异，更可能提示从早筛到诊断再到持续服务的资源缺口。

这个缺口尤其发生在行为观察环节。许多早期线索不是聚光灯下的明显异常，而是混在日常互动中的“微光”：孩子可能不看人眼睛，可能反复做同一个动作，也可能对呼唤没有反应；有些孩子会表现出异常的感官反应，出现非典型语言，或者反复排列物体。要稳定识别这些线索，往往依赖医生与治疗师长期积累下来的默会知识。

**微光 Glimmer** 想做的事情，是把这部分行为观察知识中的一小部分先结构化出来，并放到家庭自己的设备上运行。它不能也不应该替代医生；它的目标是帮助家长更早意识到某段行为视频中可能存在需要关注的信号，从而更早地寻求专业机构和医生介入评估与干预。

## What It Detects

模型直接预测 B01-B09，应用端派生 B10：

| ID | 行为信号 |
| --- | --- |
| B01 | 缺乏或回避眼神接触 |
| B02 | 攻击性行为 |
| B03 | 对感官输入反应过强或过弱 |
| B04 | 对语言互动无反应 |
| B05 | 非典型语言 |
| B06 | 排列物品 |
| B07 | 自伤或打自己 |
| B08 | 自转或旋转物体 |
| B09 | 上肢刻板动作 |
| B10 | 背景：未观察到明显目标行为特征 |

模型输出格式固定为 B01-B09 的 9-bit code：

```text
000000000
```

`B10` 不由模型生成。当 B01-B09 全为 `0` 时，app 端确定性设置 `B10=true`。

## Technical Architecture

<p align="center">
  <img src="assets/readme/architecture.svg" alt="Glimmer technical architecture" />
</p>
<p align="center">
  <sub>Diagram source: <a href="assets/readme/architecture.mmd">assets/readme/architecture.mmd</a></sub>
</p>

核心代码路径：

| Path | 作用 |
| --- | --- |
| `asd_ds_dataset.py` | 只读 ASD-DS `DatasetDict` adapter，维护 train/validation/test 边界。 |
| `run_train.py` | 训练 CLI，覆盖 cache 构建和训练，也包含 HF eval 与 merge/export。 |
| `eval_gguf_llama_cpp.py` | macOS/Linux GGUF 评测入口，使用 llama.cpp server 跑 held-out test。 |
| `prompts/zh`, `prompts/en` | 训练和推理 prompt，prompt 内容参与 cache hash。 |
| `scripts/run_code9_r32_ep10_qlora_loftq_waudio_wi8.sh` | 当前音频版 code9 主训练/评测流程脚本。 |
| `glimmer-ios/core` | Swift core contract，定义 prompt contract, media order, parser, sampling settings and GBNF grammar。 |
| `glimmer-ios/ios/Sources/AsdGgufNative` | Objective-C++ native bridge，直接调用 llama.cpp / mtmd / grammar sampler。 |
| `glimmer-ios/ios/Sources/GlimmerIOS` | SwiftUI app 主体，负责模型下载和视频预处理，也负责报告生成与本地解释对话。 |

从训练流程到 GGUF 评测，再到 app 推理，三者共享同一套媒体语义；不同实验可以选择不同的最大帧数，但抽帧方式和缩放规则保持一致，音频格式与模态顺序也保持一致：

- frame sampling: `fps=1.0`，当前 app/GGUF eval contract 最多 32 帧，主训练脚本最多 16 帧，宽度 512，保持比例。
- audio: mono 16 kHz PCM WAV，最多 30 秒。
- modality order: frames -> audio -> text instruction。
- context: `8192` tokens。
- decoding: `temperature=0.0`, `top_k=1`, `top_p=1.0`, max output tokens `16`。

推理阶段使用的 GBNF grammar：

```text
root ::= bit bit bit bit bit bit bit bit bit
bit ::= "0" | "1"
```

## Model and Weights

模型权重不进入 Git 仓库。iOS/macOS app 首次启动时从 manifest 下载两个 GGUF 文件；国内和海外下载源由用户在 app 内选择。

| File | Runtime role | Size | SHA-256 |
| --- | --- | ---: | --- |
| `model-Q4_K_M.gguf` | quantized main model | 5,302,272,992 bytes | `950ef480dd35ab2b48257f9caddfebe4da20ea950e286dd24add559ce284f5ad` |
| `mmproj-bf16.gguf` | multimodal projector | 991,552,096 bytes | `a06cbbb4b6ec363b5068ce23ef37f9ed62ed57288a33860505f7d6153cd4b57e` |

Hugging Face:

```text
https://huggingface.co/chenghuzi/glimmer-e4b-asd9-gguf
```

应用内下载 manifest 位于：

```text
glimmer-ios/ios/Resources/ModelManifest.json
```

## Evaluation

评测集为 held-out test split，共 182 个 clips。训练过程中只使用 train/validation；test 只用于最终报告。

| Runtime | Parse rate | Micro F1 | Macro F1 | Notes |
| --- | ---: | ---: | ---: | --- |
| Full precision LoRA on Linux | 1.0000 | 0.6118 | 0.6233 | BF16 LoRA, unquantized inference. |
| GGUF on macOS | 1.0000 | 0.5458 | 0.5473 | Native-equivalent preprocessing/eval. |
| GGUF on iOS | 1.0000 | 0.5096 | 0.5223 | Real device app runtime. |

作为参照，AV-ASD 论文中 13B LLaVA-ASD 的 best macro F1 为 0.5977；不同数据与设置不能直接等同，但这个结果给出了任务难度的大致量级。微光的重点在于：经过任务化微调和受控解码后，Gemma 4 E4B 这样更小的模型已经能在手机本地运行，并提供可用的行为信号早筛支持。

## Quick Reproduction

### 1. Python environment and checks

Python 依赖由 `uv` 和 `uv.lock` 管理。仓库要求 Python `>=3.12,<3.14`，所有 Python 命令都应通过项目虚拟环境运行。

```bash
uv venv --python 3.12
uv sync
```

基础同步后，可以运行轻量检查：

```bash
./.venv/bin/python -m py_compile \
  run_train.py \
  asd_ds_dataset.py \
  asd_eval_common.py \
  eval_gguf_llama_cpp.py \
  main.py
```

跨平台边界：

- macOS/Linux: 可以运行数据 adapter 和 prompt/parser 检查，也可以运行 GGUF eval 脚本；GGUF eval 还需要本机有 `ffmpeg` / `ffprobe` 和带 `mtmd` 支持的 llama.cpp `llama-server`。
- Linux + NVIDIA CUDA: 完整训练路径需要额外的 CUDA 训练依赖，例如 PyTorch, Transformers, PEFT, bitsandbytes and W&B：

```bash
uv sync --group train-cuda
```

- Linux LiteRT export: 如需复现实验性 LiteRT-LM export，再同步：

```bash
uv sync --group litert-export
```

- iOS/macOS app: SwiftUI app 构建走 Xcode/XcodeGen，不依赖 Python venv；见下方 `Build the App`。

### 2. Download GGUF weights

```bash
mkdir -p outputs/gguf_experiments/gemma4-asd-code9-waudio-step420

huggingface-cli download chenghuzi/glimmer-e4b-asd9-gguf \
  model-Q4_K_M.gguf \
  mmproj-bf16.gguf \
  --local-dir outputs/gguf_experiments/gemma4-asd-code9-waudio-step420
```

### 3. Run GGUF test eval

需要本机有带 multimodal/mtmd 支持的 llama.cpp `llama-server`。如果 binary 不在默认路径，用 `--llama-server-bin` 指定。

```bash
./.venv/bin/python eval_gguf_llama_cpp.py \
  --llama-server-bin outputs/llama.cpp/build/bin/llama-server \
  --model-file outputs/gguf_experiments/gemma4-asd-code9-waudio-step420/model-Q4_K_M.gguf \
  --mmproj-file outputs/gguf_experiments/gemma4-asd-code9-waudio-step420/mmproj-bf16.gguf \
  --split test \
  --prompt-lang zh \
  --audio \
  --constrain-code
```

### 4. Train from local ASD-DS

完整音频版训练流程入口：

```bash
./scripts/run_code9_r32_ep10_qlora_loftq_waudio_wi8.sh
```

关键默认设置：

- base model: `/home/huzi/Downloads/gemma-4-E4B-it`
- dataset: `data/raw/ASD-DS`
- prompt language: `zh`
- LoRA rank: `32`
- max frames: `16` in the training script, `32` in current app/eval contract
- max audio: `30` seconds
- best checkpoint selection: validation macro F1

## Build the App

iOS/macOS 工程由 `xcodegen` 从 `glimmer-ios/ios/project.yml` 生成。签名配置放在本地 `glimmer-ios/ios/.env`，不进入 Git。

```bash
cd glimmer-ios/ios
./Scripts/generate-xcodeproj.sh
```

iOS 真机构建：

```bash
xcodebuild -project GemmaScreen.xcodeproj \
  -scheme GemmaScreen \
  -destination 'platform=iOS,name=<DEVICE_NAME>' \
  -allowProvisioningUpdates \
  build
```

macOS 构建：

```bash
xcodebuild -project GemmaScreen.xcodeproj \
  -scheme GlimmerMac \
  -destination 'platform=macOS,arch=arm64' \
  build
```

`GlimmerMacFull` 也可把两个 GGUF 文件打进 app bundle；普通 `GlimmerMac` 则走下载或本地选择两份 GGUF 文件。

## Privacy and Safety

微光面向的是儿童行为视频，所以默认按最保守的隐私方式设计。用户选择或拍摄的视频会在设备本地完成抽帧和音频处理，随后直接进入本地模型推理；报告生成和后续解释对话也都留在设备上。除首次下载模型权重外，app 不需要上传用户视频或音频，也不会上传报告或聊天内容。

你看到的报告应被理解为“这段视频中观察到了哪些 ASD 相关行为信号”，而不是“孩子是否患有 ASD”。微光不会给出医学诊断，也不能替代医生和治疗师的完整评估。它更适合作为一个早期提醒工具：当某些行为信号反复出现时，帮助家庭更早决定是否寻求专业帮助。

## License

本仓库代码以 MIT License 发布。GGUF 模型权重以 Apache-2.0 License 发布，详见 Hugging Face model card。

## Sources

- Gemma 4 E4B model card: https://huggingface.co/google/gemma-4-E4B
- CDC ASD prevalence data: https://www.cdc.gov/autism/data-research/index.html
- China NHC autism service reference: https://www.nhc.gov.cn/fys/c100078/202209/0cb5cf9dd3964c0ab46beb31c1be312d.shtml
- AV-ASD / LLaVA-ASD reference: https://arxiv.org/abs/2406.02554
