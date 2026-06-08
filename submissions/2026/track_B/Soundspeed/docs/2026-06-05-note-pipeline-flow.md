# Note Pipeline 流程图（文本 / 语音 → function calling → Mark）

留档：4.x note 输入工作线的两条流程。配套 PR #29、spec `docs/specs/2026-06-05-voice-note-and-np-refinement.md`。

- **单 Gemma 实例三入口**：文本（`infer_tool`）、语音（`infer_voice_tool`）、L2（`infer_tool`）全走同一个 `LLMService._submit → 单 GemmaClient → 单 MultimodalGemma4Handler`，`_lock` 串行，不开第二个模型。
- **语音 vs 文本只差输入侧**：语音多一个音频哨兵 → WAV bitmap 进 `mtmd_tokenize`；输出侧（grammar 约束 + tool_calls）完全一样，所以语音也吃 schema 强约束。
- **category 名 == status 值**：`pass/ng/keep` 三类的 category 字符串与 take.status 枚举值同名，`_finalize_np` 直接拿 category 当 status 打 Mark（同名耦合，有不变量测试 `test_status_categories_coupling_holds` 守）。

## 1. 调用流（文本 + 语音 note → Mark）

```
┌─────────────────────────── 前端 (5175) ───────────────────────────┐
│  打字: MemoInput ──► POST /api/v1/notes        {text, client_id}   │
│  语音: 按住麦 ─► getUserMedia ─► MediaRecorder ─► blobToWav16kMono  │
│        └──────► POST /api/v1/notes/voice  multipart{wav,client_id} │
└────────────────────────────────┬──────────────────────────────────┘
                                  │ HTTP 202 (fire-and-forget)
┌─────────────────────────── 后端 (8005) ───────────────────────────┐
│ routes/takes.py                                                    │
│   create_note ───────► orchestrator.run_np_async                   │
│   create_voice_note ─► orchestrator.run_np_voice_async             │
│                              │                                     │
│ orchestrator._finalize_np  ◄─┘  (文本/语音共用收尾)                 │
│   ├─ np_runner   = run_np_note (input, svc)        ← 文本           │
│   └─ voice_runner= run_np_voice(input, audio, svc) ← 语音           │
│                              │                                     │
│   build messages: system(职责 + 场镜次规则 + _CATEGORY_GUIDE)       │
│                 + user(当前场/镜/次 + 本场 take 列表 + 备注/音频哨兵) │
│                              ▼                                     │
│   ┌─────────── LLMService (单实例, _lock + PriorityQueue) ───────┐  │
│   │  infer_tool(note_struct)              ← 文本                  │  │
│   │  infer_voice_tool(note_struct, audio) ← 语音                  │  │
│   │     └─► _submit(want_tool_call=True, audio?) ─► worker        │  │
│   │           └─► GemmaClient.create_chat_completion              │  │
│   │                 (tools + 强制 tool_choice + audio?)           │  │
│   │                      ▼  [见 §2 tool-call 流]                  │  │
│   │              tool_calls[0]  (dict)                            │  │
│   └──────────────────────────┬──────────────────────────────────┘  │
│                              ▼                                     │
│   _parse_tool_call ─► json.loads(arguments) ─► _validate_data_dict │
│                              ▼   NPOutput{take_id, category, content}
│   ┌── _finalize_np 收尾 ──────────────────────────────────────┐    │
│   │  dal.insert_note(take_id, category, content)   ─► DB       │    │
│   │  if category ∈ {pass, ng, keep}:                           │    │
│   │      dal.set_take_status(take_id, category)    ─► DB (Mark)│    │
│   │      publish TAKE_CHANGED                                  │    │
│   │  publish NOTE_PROCESSED (含 client_id)                     │    │
│   └────────────────────────────┬──────────────────────────────┘    │
└────────────────────────────────┼──────────────────────────────────┘
                                  │ WebSocket
┌─────────────────────────── 前端 (5175) ───────────────────────────┐
│ useLiveConnection:                                                 │
│   note.processed ─► invalidate ["takes"] + ["take", id]            │
│                     └─► NoteList 移除 pending、显 resolved          │
│   take.changed   ─► applyTakeChanged (内存 patch-merge status)     │
│                     └─► HistoryTakes 状态徽章翻成 KEEP/PASS/NG      │
└────────────────────────────────────────────────────────────────---┘
```

## 2. Tool-call 流（forced function calling 的内部机制）

```
TASK_CONFIG["note_struct"]            backend/llm/config.py
  ├─ tools:       [ build_note_tool() ]          ← tools/note.py
  └─ tool_choice: {type:function, function:{name:"structure_note"}}  ← 强制
        │  (tools/tool_choice 不在 _META_KEYS → 透传给 client)
        ▼
LLMService._submit(want_tool_call=True, audio?)
        │   gen_kwargs = {max_tokens, temperature, tools, tool_choice}
        ▼
worker:  client.create_chat_completion(messages, **gen_kwargs, audio?)
        ▼
MultimodalGemma4Handler.__call__   (单实例 mtmd, llama_chat_format.py)
        │
        ├─① 输入侧: text(+ 音频哨兵→WAV bitmap) 一起 mtmd_tokenize → eval 进 KV
        │          (语音才有 audio chunk；文本零 bitmap)
        │
        └─② 输出侧: 强制 tool_choice 命中 structure_note
                  → 从它的 JSON schema 建 GBNF grammar
                  → create_completion(prompt, grammar=…)  受约束生成
                  ───────────────────────────────
                  structure_note schema（grammar 逼模型只能产出）:
                    { take_id : integer
                      category: enum[ note | issue | pass | ng | keep ]
                      content : string }                  ← tools/note.py
                  中文口语 → category（_CATEGORY_GUIDE 教的）:
                    过/可以用/OK            → pass
                    保/留/留着(含「可以保」) → keep
                    不好/不行/废            → ng
                    收音小/灯光暗/穿帮      → issue
                    其它                   → note
        ▼
result["choices"][0]["message"]["tool_calls"][0]
   = { type:"function",
       function:{ name:"structure_note",
                  arguments:'{"take_id":27,"category":"keep","content":"不错"}' } }
        │  worker: want_tool_call → 取 tool_calls[0]（缺失/空 → LookupError）
        ▼
_parse_tool_call:  json.loads(arguments) ─► _validate_data_dict
        │            (take_id int? category∈5类? content str? 否则 NPParseError)
        ▼
NPOutput{ take_id:27, category:"keep", content:"不错" }
        │
        └─► category ∈ {pass,ng,keep}  ──►  set_take_status → Mark=KEEP
            category ∈ {note,issue}    ──►  不打 Mark
```
