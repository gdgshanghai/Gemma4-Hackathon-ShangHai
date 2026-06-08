---
marp: true
theme: glimmer
html: true
paginate: true
size: 16:9
title: Glimmer technical route
description: Two-minute technical route from multimodal training to on-device iOS inference.
---

<!-- _class: cover no-page -->

<div class="cover-layout">
  <div>
    <div class="eyebrow">Hackathon technical route</div>
    <h1>微光 Glimmer</h1>
    <p class="subhead">把 Gemma 4 E4B 多模态模型，训练、压缩、校验并部署到 iPhone 本地推理。</p>
    <div class="pipeline">
      <div class="node">
        <h3>Training</h3>
        <p>video + audio supervised fine-tuning</p>
      </div>
      <div class="arrow">→</div>
      <div class="node">
        <h3>GGUF</h3>
        <p>Q4 language model + BF16 multimodal projector</p>
      </div>
      <div class="arrow">→</div>
      <div class="node">
        <h3>iPhone</h3>
        <p>local classification and explanation loop</p>
      </div>
    </div>
  </div>

  <div class="phone">
    <div class="phone-card">
      <h3>报告结论</h3>
      <div class="phone-line"></div>
      <div class="phone-line"></div>
      <div class="phone-line short"></div>
    </div>
    <div class="phone-play">
      <div class="play-dot"></div>
      <div class="progress-line" style="flex: 1"><span></span></div>
    </div>
    <div class="phone-card" style="margin-top: 148px">
      <div class="phone-line"></div>
      <div class="phone-line short"></div>
    </div>
    <div class="phone-bar"></div>
  </div>
</div>

---

<div class="eyebrow">01 / Training</div>

## Classification is easier than generation

<div class="grid two" style="margin-top: 30px">
  <div class="card">
    <h3>多模态监督</h3>
    <p class="kicker">每个样本由短视频帧、音频和结构化行为标签组成；训练目标不是写长报告，而是稳定预测行为码。</p>
    <div class="check-list">
      <div class="check">Gemma 4 E4B instruction base</div>
      <div class="check">LoRA / QLoRA, rank 32</div>
      <div class="check">video frames + audio path</div>
    </div>
  </div>
  <div class="blue-card">
    <h3>严格 9-bit output</h3>
    <p class="kicker">B01 到 B09 由模型输出；B10 由 app 根据前 9 位确定性派生。</p>
    <div class="bit-code">
      <span>0</span><span>1</span><span>0</span><span>0</span><span>1</span><span>0</span><span>0</span><span>0</span><span>1</span>
    </div>
    <p class="tiny" style="margin-top: 16px">The key move: shrink the generation space before quantization.</p>
  </div>
</div>

---

<div class="eyebrow">02 / Compression</div>

## 混合精度，才跑得动也跑得准

<div class="split-model">
  <div class="model-block">
    <h3>model-Q4_K_M.gguf</h3>
    <p>main language model, about 5.0 GB</p>
  </div>
  <div class="model-block mmproj">
    <h3>mmproj-bf16.gguf</h3>
    <p>vision/audio projector, about 946 MB</p>
  </div>
</div>

<div class="grid two" style="margin-top: 24px">
  <div class="soft-card">
    <h3>为什么保留 BF16 projector</h3>
    <p class="kicker">完全 4bit 会让行为识别能力明显崩掉；端侧方案保留多模态编码路径精度，把压缩集中在 text inference 部分。</p>
  </div>
  <div class="soft-card">
    <h3>端侧解码仍然受控</h3>

```text
root ::= bit bit bit bit bit bit bit bit bit
bit ::= "0" | "1"
```

  </div>
</div>

---

<div class="eyebrow">03 / Parity</div>

## 模型不变，输入也不能漂

<div class="flow">
  <div class="flow-step">
    <div class="num">A</div>
    <h3>Linux / macOS eval</h3>
    <p>ffmpeg / ffprobe prepare media, llama.cpp server, pinned media marker.</p>
  </div>
  <div class="flow-step">
    <div class="num">B</div>
    <h3>iOS native path</h3>
    <p>AVFoundation + CoreImage extract frames, embedded audio, Objective-C++ bridge.</p>
  </div>
</div>

<div class="card" style="margin-top: 24px">
  <div class="grid three">
    <div>
      <div class="pill">media protocol</div>
      <p class="kicker">frames → audio → text</p>
    </div>
    <div>
      <div class="pill">preprocessing</div>
      <p class="kicker">32 frames, 512px, mono 16 kHz WAV</p>
    </div>
    <div>
      <div class="pill">runtime</div>
      <p class="kicker">ctx 8192, temperature 0, top-k 1</p>
    </div>
  </div>
</div>

<p class="caption">We even pull iOS-preprocessed media back to Mac and re-run the full test set.</p>

---

<div class="eyebrow">04 / Evaluation</div>

## 更小的模型，更强的测试表现

<div class="metric-table">
  <div class="metric-row header">
    <div>Runtime</div>
    <div>Parse</div>
    <div>Micro F1</div>
    <div>Macro F1</div>
  </div>
  <div class="metric-row data prior">
    <div>Prior paper best, LLaVA(13B)-ASD</div>
    <div>n/a</div>
    <div>n/a</div>
    <div>0.5977</div>
  </div>
  <div class="metric-row data highlight">
    <div>Full precision LoRA on Linux</div>
    <div>1.0000</div>
    <div>0.6118</div>
    <div>0.6233</div>
  </div>
  <div class="metric-row data">
    <div>GGUF on Mac</div>
    <div>1.0000</div>
    <div>0.5458</div>
    <div>0.5473</div>
  </div>
  <div class="metric-row data">
    <div>GGUF on iOS</div>
    <div>1.0000</div>
    <div>0.5096</div>
    <div>0.5223</div>
  </div>
</div>

<p class="source-note">182 held-out test clips. Prior best: arXiv:2406.02554v1, Table II, LLaVA-ASD with audio captions and speech transcription.</p>

---

<div class="eyebrow">05 / iOS inference design</div>

## Analysis → Explanation：超越分类

<div class="conversation">
  <div class="turn">
    <div class="session-label">Session A</div>
    <h3>Classification</h3>
    <div class="media-strip">
      <span></span><span></span><span></span><span class="audio"></span>
    </div>
    <p>frames + audio + strict 9-bit prompt</p>
    <div class="bit-code" style="transform: scale(0.75); transform-origin: left top">
      <span>0</span><span>0</span><span>1</span><span>0</span><span>1</span><span>0</span><span>0</span><span>0</span><span>0</span>
    </div>
  </div>
  <div class="diagram-arrow">→</div>
  <div class="turn dark">
    <div class="session-label" style="background: rgba(255,255,255,0.14); color: rgba(255,255,255,0.72)">App layer</div>
    <h3>Parse + report</h3>
    <p>parse 9 bits, derive background, generate a parent-readable conclusion.</p>
  </div>
  <div class="diagram-arrow">→</div>
  <div class="turn">
    <div class="session-label">Session B</div>
    <h3>Explanation conversation</h3>
    <div class="media-strip">
      <span></span><span></span><span></span><span class="audio"></span>
    </div>
    <p>prefill same media + parsed result, then answer follow-up questions.</p>
  </div>
  <div class="kv-box">
    <h3>KV cache reuse</h3>
    <p>Later user turns append text only. The model still has the original video/audio context in the local explanation session.</p>
  </div>
</div>

<div class="card" style="margin-top: 26px">
  <p><strong>核心亮点：</strong>一次本地识别，升级成围绕同一视频的本地解释对话。</p>
</div>
