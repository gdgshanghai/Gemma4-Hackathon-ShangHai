# Soundspeed 输入接口架构图：四业务线 × 单实例三模态

> 测绘日期 2026-06-06，行号对齐 `origin/main` = `508e6b1`（#41 剧本导入 text path 合并后）。
> 状态快照：**L2 / NP / QP / SP 文本链路均已合 main**（#25/#37、#29、#39 squash、#41）；SP 视觉（拍照 OCR）仍未进 main。
> 所有 file:line 来自真实代码（6-agent 并行测绘），事实经 DeepSeek 逐条核验（13 条断言无硬错误）。后随 #41 合并重新对齐了 SP 与 client.py 行号。
> 这是 4.x 方案A「单实例三入口」落地后的统一视图，给跨业务线协同（尤其 SP 3.H vision 与 QP handler swap 的收敛）做参考。

---

## 1. 端点 → pipeline → service（每条线的「在哪里」）

```
 业务线     L2 take 后处理        NP 录音师备注                    QP 自然语言查询        SP 剧本导入(文本)
 状态       ✅ main #25/#37       ✅ main #29                      ✅ main #39            ✅ main #41
══════════════════════════════════════════════════════════════════════════════════════════════════════
 HTTP      POST /api/v1/         POST /api/v1/    POST /api/v1/    POST /api/v1/         POST /api/v1/scripts/
 端点       take/end             notes            notes/voice      query                 upload → uploads/{id}/
           takes.py:151         takes.py:325     takes.py:389     query.py:28           parse → import/confirm
           ⚠仅 publish           文本备注          浏览器麦 WAV      require_admin         scripts.py:185/322/367
           take.end,            parse_note 剥     multipart        ───────────           挂载 entrypoint.py:131
           L2 内部触发           @category         ≤10MB            ───────────           upload≠parse(后台轮询)
              │                     │                │                │                     │ upload→extract_text
              │                     │                │                │                     │  (3.F script_extract)
              ▼                     ▼                ▼                ▼                     ▼ parse→逐场:
 pipeline  run_l2_take          run_np_note      run_np_voice     run_qp_query          split_for_parse +
           l2_take.py:380       np_note:207      np_note:259      →run_tool_loop        parse_scene_block
           ├ 有剧本                                                qp_query.py:67        sp_script.py:397/414
           └ 无剧本                                                ≤5 跳·两步走           (唯一调 LLM 处)
              │                     │                │             auto抠名→forced取参     +plan/apply_import
              │                     │                │                │                  script_import.py
 task /    l2_take /            note_struct      note_struct      query_session         script_parse
 tool      l2_take_no_script    structure_note   structure_note   5 工具                 ❗无 tool
 (FC)      report_script_/      (forced)         (forced)         (auto + 动态forced)    纯 content
           corrections(forced)                                    count_takes/get_      (逐行结构化)
              │                     │                │             scene_info/list_         │
              │                     │                │             characters/search_      │
              │                     │                │             script_lines/           │
              │                     │                │             query_database          │
 service   infer_tool           infer_tool       infer_voice_     infer + infer_tool    infer
              │                     │             tool                │                     │
              │ text                │ text           │ audio          │ text                │ text
              ▼                     ▼                ▼                ▼                     ▼
        ┌────────────────────────────────────────────────────────────────────────────────────────┐
        │   GemmaClient.create_chat_completion — 单一 Llama 实例 + 单 MultimodalGemma4Handler       │
        │   backend/llm/client.py:154          （方案A：text/audio/image 三入口共用一份权重）        │
        └────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 共享 `GemmaClient` 的四条分支（架构心脏，收敛点在这）

```
  GemmaClient.create_chat_completion(messages, **kwargs)            client.py:154
  │
  ├─① audio 非 None ?  ─── 是 ──►  多模态 handler（gemma4a 音频投影器）       client.py:160-172
  │       │                        · 哨兵 AUDIO_SENTINEL 取回 WAV 字节 → mtmd eval 进 KV
  │       │                        · CHAT_FORMAT 不渲染 tools；forced 时靠 grammar 焊出 tool_call
  │       │                        · 最先命中并 return，永不触达 ②         用户：🎙 语音 NP
  │      否
  │       ▼
  ├─② kwargs['tools'] 且多模态实例 ? ─ 是 ─► 切到 __init__ 预建缓存的         client.py:178-184
  │       │                                  原生 FunctionGemma formatter
  │       │                                  self._text_tool_handler（会渲染 tools），finally 复位
  │       │                                  · 该 handler 在 __init__ 经 _build_native_tool_handler
  │       │                                    建好缓存（client.py:119-123），运行时只切换不重建
  │       │                                  · 这就是「QP handler swap」，无 QP 专属逻辑
  │       │                                  · _lock 串行兜并发              用户：📝 L2 / 文本 NP / QP
  │      否
  │       ▼
  ├─③ 纯文本兜底  ──────────────►  用 Llama 当前 chat_handler              client.py:185
  │                                  （=初始化时挂的多模态 handler）
  │                                  · 无 tools 的文本请求                  用户：📄 SP 文本(parse_scene_block, infer)
  │
  └─④ 图像 content ?  ─── ❌ 无此分支 ──►  缺口（client.py:176-177 注释警告）   client.py:176
                                          · handler 侧 vision-ready：load_image 委托父类、
                                            image_tokens=1120、n_batch=2048（multimodal.py 已收敛）
                                          · 但 client.py 无入口把 image 喂进来
                                          · ⚠ image+tools 会误落 ② 被换成原生 formatter、丢图像嵌入
                                            → 这正是 3.H 落地要和 QP swap 协同的收敛点
                                          用户：📷 SP 拍照 3.G/3.H（未进 main，探针已移除）

            底座：一份 mmproj-F16.gguf 内含 gemma4a(音频) + gemma4v(图像) 双投影器
            #41 给 _LLAMA_DEFAULTS 加了 flash_attn=True（提速省显存，未碰 swap）  client.py:29-33
```

---

## 3. 状态矩阵（精确到 file:line + 落在哪，对齐 main 508e6b1）

| 线 | 模态 | 入口端点 / 触发 | pipeline | task_type | tool | service | client 分支 | 状态 |
|---|---|---|---|---|---|---|---|---|
| **L2** 有剧本 | 文本 | `POST /take/end`→内部触发 `takes.py:151` | `run_l2_take` `l2_take.py:380` | `l2_take` | `report_script_analysis` forced | `infer_tool` | ② | ✅ main #25/#37 |
| **L2** 无剧本 | 文本 | 同上 | 同上(分叉 `:399`) | `l2_take_no_script` | `report_corrections_only` forced | `infer_tool` | ② | ✅ main #37 |
| **NP** 文本 | 文本 | `POST /notes` `takes.py:325` | `run_np_note` `np_note.py:207` | `note_struct` | `structure_note` forced | `infer_tool` | ② | ✅ main #29 |
| **NP** 语音 | 音频 | `POST /notes/voice` `takes.py:389` | `run_np_voice` `np_note.py:259` | `note_struct` | `structure_note` forced | `infer_voice_tool` | ① | ✅ main #29 |
| **QP** 文本 | 文本 | `POST /api/v1/query` `query.py:28` | `run_qp_query`→`run_tool_loop` `qp_query.py:67` | `query_session` | 5 工具 auto+forced | `infer`+`infer_tool` | ② | ✅ main #39 |
| **QP** 语音 v2 | 音频 | — | — | — | — | — | ①+渲染改造 | 🔮 仅 spec §3.2.1 |
| **SP** 提取 3.F | 文本 | `POST /scripts/upload` `scripts.py:185` | `extract_text` `script_extract.py`(txt/md/docx/pdf) | — | — | 无 LLM | — | ✅ main #41 |
| **SP** 解析 3.B | 文本 | `POST /scripts/uploads/{id}/parse` `scripts.py:322`(后台异步) | `split_for_parse`+`parse_scene_block` `sp_script.py:397/414` | `script_parse` | ❗无(content) | `infer` | ③ | ✅ main #41 |
| **SP** 入库 3.C | — | upload 无冲突直入 / `POST /scripts/import/confirm` `scripts.py:367` | `plan_import`/`apply_import` `script_import.py` | — | — | 无 LLM | — | ✅ main #41 |
| **SP** 视觉 3.G/3.H | 图像 | —（#41 仅 text path，探针已移除） | — | — | — | — | ④ | 🔮 未进 main |

---

## 4. 设计库里的「设计流」（三份 spec）

**① 4.x 方案A — 单实例三入口**（`docs/specs/2026-06-05-voice-note-and-np-refinement.md` §5.1/§5.2）
全后端只有一份 `Llama` + 一个多模态 handler + 一份 `mmproj-F16`（双投影器），按 content 分三入口：**文本**（无投影器，L2／文本 NP／SP 文本 共用）、**音频**（gemma4a，语音 NP）、**图像**（gemma4v，SP 拍照，handler 侧已 vision-ready 但 client 入口未接）。硬约束：不许任何业务线另起第二个模型实例。

**② QP 内核+入口两层**（`docs/specs/2026-06-05-qp-tool-loop.md` §2/§3）
内核层（已交付）= `POST /query` 直连 + `run_tool_loop` 两步走，对 NP 零依赖。入口层（延后）= memo 框 forced 二分类器 `route_memo(note|query)`，落点 `POST /notes`。语音查询走 v2 option 2（模型选工具即分类）。

**③ SP §11 — 唯一横跨两入口的线 + 收敛点**（`docs/specs/2026-06-03-script-import-sp-pipeline.md` §11，#41 已带进 main）
SP 文本走文本入口（**#41 已落生产**），SP 拍照走图像入口（3.G/3.H，**未进 main**），两条都挂同一份共享实例。**3.H vision 接生产 = 4.J vision-ready 实例（4.x owner）+ 3.H 接调用（3.x owner）的收敛点**。

**延后/设计中清单**：QP 入口分类器、QP 语音查询（需给多模态 handler 注入工具声明 = option a）、QP 结构化输出/thinking/alias 表；SP 的 3.G/3.H 视觉接生产、文本 parity 重盖章；`agent_init`（占位）。

**共享原生 FC 编解码已入 main（待接路由）**：#41 带入 `backend/llm/gemma_tools.py`（Gemma4 原生函数调用 parse/encode/dispatch 编解码器）。llama-cpp 会把 `tools=` 渲染进 prompt、Gemma 据此吐 FunctionGemma 格式，但**不解析回标准 tool_calls**，本模块补这层。目前**尚未接任何路由**——QP 现仍用自己的 `_scrape_tool_name` 正则抠名，日后可统一到 `gemma_tools`。

---

## 5. 收敛点（一句话讲透）

现在 **①音频** 和 **②文本+tools** 各自解决了「渲染音频／渲染工具」的一半，**③纯文本** 走 handler 原格式（SP 文本解析就走这条），**④图像入口在 `client.py` 里根本没接线**。等 3.H 要把拍照 OCR 落进生产 service，就得在第④条补分支，而且会撞上和 ②／① 同一个张力——`image + tools` 需要同时渲染图像嵌入和工具声明，单个 handler 都做不到（`client.py:176-177` 注释已标出这个坑）。这就是 QP PR #39 挂给经纬 review 的那条的下游：3.H vision 落地与 QP handler swap 必须在同一个 `GemmaClient` 协同设计，不是 rebase 能自动解决的。

---

## 附：校验与对齐记录

**DeepSeek 逐条核验（2026-06-06）**：13 条断言（端点/pipeline/task/tool/service/状态/收敛点）全部 ✓，含 QP squash 已合 main 的判定（亲自 `git diff` 验三文件为空）。两处精度修正已并入：branch ② 的原生 formatter 是 `__init__` 经 `_build_native_tool_handler`（`client.py:123`）**建好缓存**进 `self._text_tool_handler`，运行时只**切换不重建**；branch ③ 是「用 Llama 当前 chat_handler」而非「用某 CHAT_FORMAT」。

**#41 合并后重新对齐**：经纬 SP 文本链路 #41 合 main 后，本文更新：① SP 全部状态 ⏳→✅（real 端点 `/scripts/upload`、`/uploads/{id}/parse`、`/import/confirm`，挂 `entrypoint.py:131`）+ 新增 3.F `script_extract`；② `client.py` 因 #41 加 `flash_attn` 行号整体 +5，已重锚（create_chat_completion `:154`、swap `:178-184`、音频 `:160-172`、图像缺口注释 `:176-177`）——QP swap 未受影响、完好；③ `gemma_tools.py` 原生 FC 编解码入 main（待接路由）。SP 视觉仍未进 main（#41 仅 text path，探针已移除）。
