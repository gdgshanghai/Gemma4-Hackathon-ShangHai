"""TASK_CONFIG 映射：每个 task_type 的生成参数与元数据。

来源：llm-service-design v1.1 §Task Config 映射。
字段语义见 1.F 实施 spec §5。

注：system prompt 模板由 Pipeline 在构建 messages 时插入（role="system"），
TASK_CONFIG 的 system 字段仅作参考模板，service 层不自动注入。

tools / tool_choice 字段（Tier 1 function calling）：
  service 层会把不在 _META_KEYS 的字段透传给 client.create_chat_completion。
  tools 和 tool_choice 故意不加入 _META_KEYS，由 infer_tool 透传。
  l2_take 的 tools 取自 build_l2_tool()（backend/llm/tools/script.py），该构造器
  只依赖中性的 l2_constants（不 import config / l2_take），无循环 import 风险，
  故此处 module 级直接 import。
  note_struct 的 tools 取自 build_note_tool()（backend/llm/tools/note.py），该构造器
  会 lazy import backend.pipelines.np_note（取 category enum），module 级 eager import
  会触发 config → tools.note → pipelines → config 循环，故经 _build_note_task_config()
  函数级 lazy import 构造。

剧本解析（script_parse）为何不用 grammar / response_format（2026-06-06 实测拍板）：
  实测 grammar（GBNF 约束采样）在 Gemma（~25 万词表）上每 token 多花大量 CPU →
  吞吐从 ~84 tok/s 掉到 ~15 tok/s（5.6×）。故解析热路径**不用 grammar**：代码先按场头
  切分，再让 Gemma 逐行吐 [说话人, 台词]（完整输出 v5，见 sp_script.parse_scene_block）。
  容错解析 + 兜底（解析失败 → 冒号启发式，台词不丢、不崩）。
  tool-calling/grammar 留给只调一两次的路由 / 场记分析，不进逐场热循环。
"""

from backend.llm.tools.route import ROUTE_TOOL_NAME, build_route_memo_tool
from backend.llm.tools.script import (
    build_l2_no_script_tool,
    build_l2_tool,
    build_parse_lines_tool,
)
from backend.llm.tools.transcript import build_qp_tools


def _build_note_task_config() -> dict:
    """构造 note_struct 配置，含 tools/tool_choice（文本/语音 NP forced tool-call，对标 l2_take）。

    note 短（512 token 够）；system 仅参考模板，真 system prompt 由 run_np_note/run_np_voice 组装。
    build_note_tool 函数级 lazy import，避免 config → tools.note → pipelines → config 循环。
    """
    from backend.llm.tools.note import NOTE_TOOL_NAME, build_note_tool  # noqa: PLC0415

    return {
        "max_tokens": 512,
        "temperature": 0.2,
        "priority": 2,
        "system": "将录音师备注归置到正确 take 并结构化为 take_id/category/content。",
        # Tier 1 function calling：强制走 structure_note 工具
        "tools": [build_note_tool()],
        "tool_choice": {
            "type": "function",
            "function": {"name": NOTE_TOOL_NAME},
        },
    }


# task_type -> 配置字典
# 字段：max_tokens, temperature, priority, system, _reserved（可选）；
# l2_take 含 tools/tool_choice（Tier 1 forced FC）；query_session 含 tools/tool_choice（Tier 2 auto 路由）。
TASK_CONFIG: dict[str, dict] = {
    "query_session": {
        "max_tokens": 1024,
        "temperature": 0.3,
        "priority": 1,
        "system": "你是一个场记查询助手，帮助导演和录音师快速查找场记信息。",
        # QP Tier 2 多工具 auto 路由（D-QP-09）。已 rebase 到含 4.x 的 main：
        # query_session/l2_take 仍 eager（只有 note_struct 因 np_note 依赖才 lazy），
        # transcript.py import-neutral，eager 挂 build_qp_tools() 安全，无须 lazy。
        "tools": build_qp_tools(),
        "tool_choice": "auto",
    },
    "l2_take": {
        # v0.2 schema 含 corrected_segments，实测短 take 输出 ~2000 token；
        # 长 take（剧本 100+ 行 / 5+ 分钟转录）需要 4096 上限保底。
        # 配合 n_ctx=8192（client.py），input ~3000 + output 4096 仍有余量。
        "max_tokens": 4096,
        "temperature": 0.2,
        "priority": 2,
        # prompt v1：hill-climb 最优（combined 0.465），见 experiments/2026-05-28-asr-publisher-smoke/prompt_autoresearch/log.md
        "system": (
            "整合 take 信息，生成剧本 diff 和摘要。\n\n"
            "职责：\n"
            "1. 剧本偏差检测：对比剧本台词与转录记录，识别漏词/改词/加词。\n"
            "2. 错别字修正：检查转录文本中的明显错别字（同音字、形近字误识别），输出修正结果到 corrected_segments 字段。\n\n"
            "判定优先（匹配台词时最重要）：\n"
            "- 若某段实录在语义/剧情位置上对应某剧本行（即使措辞差异很大、被大幅改写），判 substitution，"
            "seg_idx 指向该剧本行、detail 写实际说法；只有当实录完全无法对应任何剧本行时，才用 insertion（line_no=-1）。"
            "不要因为用词不同，就把同一句话拆成 insertion + missing。\n"
            "- 例：剧本「[行5] 顾朗：你必须留下来，不然一切都完了。」 实录「[3][顾朗] 哎你别走啊，走了就全完蛋了。」"
            "→ 判 {\"line_no\":5,\"diff_type\":\"substitution\",\"detail\":\"哎你别走啊，走了就全完蛋了\",\"seg_idx\":[3]}，"
            "而不是把 行5 标 missing + 再加一条 insertion。\n\n"
            "输出格式要求（严格遵守）：\n"
            "- 只输出合法 JSON，不要 markdown 代码块，不要注释，不要额外解释。\n"
            "- JSON schema：\n"
            "  {\n"
            '    "script_diff_summary": "<str 或 null>",\n'
            '    "line_matches": [\n'
            '      {"line_no": <int>, "diff_type": "<match|missing|substitution|insertion>", "detail": "<str 或 null>", "seg_idx": [<int>...]}\n'
            "    ],\n"
            '    "corrected_segments": [\n'
            '      {"idx": <int>, "original": "<str>", "corrected": "<str>"}\n'
            "    ]\n"
            "  }\n"
            "- line_matches 只列出 script_lines 提供的行，不自创行号。\n"
            "- insertion 类型（演员台词剧本无对应行）line_no 必须填 -1，禁止填剧本行号。\n"
            "- missing 类型 detail 必须为 null，禁止填任何字符串。\n"
            "- match 类型 detail 必须为 null。\n"
            "- seg_idx 是本行实际对应的转录记录下标数组（0-indexed，见转录记录每段前的序号）："
            "match/substitution 填实际说出该行的转录段下标（一行被拆成多段就填多个）；"
            "missing（漏说）填 []；insertion 填演员多说内容所在的转录段下标。\n"
            "- corrected_segments 每条的 corrected 必须是修正后的字符串，禁止为 null；无法确认修正时直接不输出该条。\n"
            "- corrected_segments 只列出真正有修改的 segment，未改动的不出现；无需修正时输出空列表 []。\n"
            "- idx 是转录记录列表的下标（从 0 开始），对应 user message 中转录记录前的序号。"
        ),
        # Tier 1 function calling（spec §6.1 D-FC-01）
        "tools": [build_l2_tool()],
        "tool_choice": {
            "type": "function",
            "function": {"name": "report_script_analysis"},
        },
    },
    "l2_take_no_script": {
        # 无剧本只做纠错，输出更短，2048 上限足够
        "max_tokens": 2048,
        "temperature": 0.2,
        "priority": 2,
        "system": (
            "整合 take 信息，修正转录错别字。\n\n"
            "职责：\n"
            "检查转录文本中的明显错别字（同音字、形近字误识别），输出修正结果。\n\n"
            "输出格式要求（严格遵守）：\n"
            "- 只调用工具，不额外输出文字。\n"
            "- corrected_segments 只列出真正有修改的 segment，未改动的不出现；无需修正时输出空列表 []。\n"
            "- corrected 必须是修正后的字符串，禁止为 null；无法确认修正时直接不输出该条。\n"
            "- idx 是转录记录列表的下标（从 0 开始），对应 user message 中转录记录前的序号。"
        ),
        "tools": [build_l2_no_script_tool()],
        "tool_choice": {
            "type": "function",
            "function": {"name": "report_corrections_only"},
        },
    },
    "script_parse": {
        # 完整输出（v5，无 grammar）：模型逐行吐 [说话人,台词]。比 classify 准（边吐台词边
        # 判断动作/对白，实测含人名的描述行也能标对）；无 grammar 故快。max_tokens 给足防截断。
        "max_tokens": 4096,
        "temperature": 0.1,
        "priority": 3,
        # 不设 response_format：grammar 在 Gemma 上每 token CPU 开销大（实测 5.6× 慢），不用。
        # prompt v5：强调"即使句子含人名，叙述动作/神态的也是描述"——这是 classify 误判的点。
        "system": (
            "你是剧本解析器。逐行把剧本解析成 [说话人, 内容] 的数组。\n"
            "- 对白行 → [\"角色名\", \"台词\"]\n"
            "- 非对白行（动作、场景描述、舞台指示，即使句子里出现人名）→ [\"\", \"原文\"]\n"
            "判断依据：有「角色：台词」形式、或明显是某人说出口的话，才算对白；"
            "叙述某人动作/神态/场景的是描述。\n"
            "只输出一个 JSON 数组，不要解释。\n\n"
            "示例输入：\n罗湘：我们先聊聊。\n罗湘走到窗边。\n\n"
            "示例输出：\n"
            '[["罗湘", "我们先聊聊。"], ["", "罗湘走到窗边。"]]'
        ),
    },
    "script_parse_fc": {
        # 单场原生 function calling（黑客松展示 + 照片增补/更新对话框的单场基础）：
        # 强制调 report_parsed_lines 工具，输出结构由 forced tool_choice 的 JSON grammar 保证。
        # 只用于单场（一次一调，grammar 成本可忍）；整本逐场热循环仍走 script_parse 快路径
        # （无 grammar），避免每场都付 grammar 开销叠加。
        "max_tokens": 4096,
        "temperature": 0.1,
        "priority": 3,
        "system": (
            "你是剧本解析器。把给定剧本逐行解析，调用 report_parsed_lines 工具报告结果。\n"
            "- 对白行 → speaker 填角色名，text 填台词\n"
            "- 非对白行（动作、场景描述、舞台指示，即使句子里出现人名）→ speaker 填空字符串，text 填原文\n"
            "判断依据：有「角色：台词」形式、或明显是某人说出口的话，才算对白；"
            "叙述某人动作/神态/场景的是描述。\n"
            "逐行输出，顺序与原文一致。"
        ),
        "tools": [build_parse_lines_tool()],
        "tool_choice": {
            "type": "function",
            "function": {"name": "report_parsed_lines"},
        },
    },
    # 照片 → 剧本 OCR（3.x 多模态）：图片逐字转写成纯文本，**不带 tools**（绕开 client.py
    # image+tools 缺口：多模态 handler 不渲染工具声明、带 tools 会误切纯文本 formatter 丢图像）。
    # 转写出的文本随后走 parse_scene_block（无 grammar 快路径；grammar FC 在长 OCR 文本上会超时）
    # 结构化，故此任务只管 OCR、不管结构。
    "script_vision_ocr": {
        # 长页面要给足额度，否则后半页被截断（实测 1536 太狠、漏掉后半场）；越界续写/循环由
        # stop + 代码去重兜，不靠压 max_tokens 限制。
        "max_tokens": 3072,
        "temperature": 0.1,
        "priority": 2,
        # 真正的"重复"病根：模型写完正文后没在回合边界停，越界吐出 <|turn|> 等特殊标记 + 续写。
        # stop 一遇回合标记立刻停（根治越界续写，且更快）；轻 repeat_penalty 兜 token 级小循环。
        # 不用 frequency_penalty——它会扰乱中文 OCR 的合法重复字，且不是越界续写的药。
        "repeat_penalty": 1.1,
        "stop": ["<|turn|>", "<|turn>", "<end_of_turn>", "<start_of_turn>", "<eos>"],
        "system": (
            "你是剧本 OCR 转写器。把这张图片里的剧本内容【逐字】转写成纯文本。\n"
            "- 按从上到下、从左到右顺序，逐行输出角色名、台词、动作/场景描述。\n"
            "- 对白尽量保留「角色：台词」原始格式；**保留场头行**（如「场5 内 咖啡馆 日」）。\n"
            "- 只转写图中真实存在的文字：不翻译、不改写、不总结、不加解释、"
            "**不要重复任何句子、不要编造图中没有的内容**。\n"
            "- 把图中文字转写完即停止，不要续写。"
        ),
        # 无 tools / tool_choice：纯文本输出（OCR 转写），走多模态 handler 处理图像 content。
    },
    # note_struct：带 tools + 强制 tool_choice，文本（run_np_note/infer_tool）与语音
    # （run_np_voice/infer_voice_tool）NP 共用——两者都走 forced tool-call，无 content-mode 调用。
    "note_struct": _build_note_task_config(),
    # 入口调度器：forced 二分类 route_memo(kind: note|query)。route.py import-neutral，
    # eager 挂 build_route_memo_tool() 安全（无 np_note 依赖，无须 lazy）。
    "memo_route": {
        "max_tokens": 16,
        "temperature": 0.1,
        "priority": 1,
        "system": "判断这条 memo 是记录备注还是查询信息。",
        "tools": [build_route_memo_tool()],
        "tool_choice": {
            "type": "function",
            "function": {"name": ROUTE_TOOL_NAME},
        },
    },
    "agent_init": {
        "_reserved": True,
        "max_tokens": 1024,
        "temperature": 0.3,
        "priority": 3,
        # TODO(agent_init 落地时): 补充 5 轮循环 Agent 的 system prompt
        # TASK_CONFIG system 模板需 agent_init 落地时补，当前为占位符
        "system": "You are a helpful assistant.",
    },
    # hop A 纯生成：无 tools / tool_choice / grammar，让模型自发吐 function-call 文本。
    # 工具声明通过 system content 以原生 <|tool>...<tool|> 格式注入（corrected-C3 实证）。
    # max_tokens=256 对齐计划（function-call 输出 50-100 token，256 足够；对齐 Task A2 Step 3）。
    "voice_dispatch_free": {
        "max_tokens": 256,
        "temperature": 0.1,
        "priority": 1,
        "system": "",
        # 无 tools / tool_choice / grammar：纯生成，让模型自发吐 function-call 文本
    },
}
