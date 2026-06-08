"""hop A 辅助工具：工具声明文本渲染 + system prompt 组装。

核心：extract_tool_declarations_text() 从 GGUF chat_template 提取
原生 <|tool>...<tool|> 声明块（vocab_only 加载，秒级），注入 system content。
Gemma4ChatHandler.CHAT_FORMAT 把 system 折进首个 user turn，模型在原生格式下
自发吐出规范 function-call（corrected-C3 + e2e 双重实证）。

实现参考：experiments/2026-06-06-voice-dispatch-spike/probe_c3_text_decl.py
           experiments/2026-06-06-voice-dispatch-spike/probe_qp_voice_e2e.py
"""
from __future__ import annotations

import functools
import os
import re
from pathlib import Path

from backend.llm.tools.note import NOTE_TOOL_NAME, build_note_tool
from backend.llm.tools.transcript import build_qp_tools

# note 工具名集合（hop A 命中后走 note 分支终结，不进 run_tool_loop）
NOTE_TOOL_NAMES: tuple[str, ...] = (NOTE_TOOL_NAME,)

# QP 工具名集合（hop A 命中后走 query 分支续跳）
QP_TOOL_NAMES: tuple[str, ...] = tuple(
    t["function"]["name"] for t in build_qp_tools()
)


@functools.lru_cache(maxsize=1)
def extract_tool_declarations_text() -> str:
    """从 GGUF chat_template 提取 6 工具的原生 <|tool>...<tool|> 声明块。

    vocab_only=True 加载（不上 Metal，秒级），仅读 tokenizer/metadata。
    渲染 6 工具声明到 dummy messages，正则提取所有 <|tool>...<tool|> 块拼接返回。
    详见 probe_c3_text_decl.py extract_tool_declarations_text()。

    lru_cache(maxsize=1)：GGUF chat_template 运行时不变，结果安全缓存。
    首次调用后直接返回缓存字符串，避免每次语音请求重新加载 GGUF metadata（秒级开销）。
    RuntimeError 路径不被缓存（lru_cache 不缓存异常），失败后可重试。
    """
    from llama_cpp import Llama  # noqa: PLC0415
    from llama_cpp.llama_chat_format import Jinja2ChatFormatter  # noqa: PLC0415

    model_path = os.environ.get(
        "GEMMA_MODEL_PATH",
        str(Path(__file__).resolve().parents[2] / "models" / "gemma-4-E4B-it-Q4_K_M.gguf"),
    )

    # vocab_only：不上 Metal，不做 KV cache，仅读 tokenizer/metadata
    llm_vocab = Llama(model_path=model_path, vocab_only=True, verbose=False)
    template = llm_vocab.metadata.get("tokenizer.chat_template", "")
    if not template:
        raise RuntimeError("GGUF 无 tokenizer.chat_template")

    def _tok_text(token_id: int) -> str:
        try:
            return llm_vocab.detokenize([token_id], special=True).decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            return ""

    bos = _tok_text(llm_vocab.token_bos()) or "<bos>"
    eos = _tok_text(llm_vocab.token_eos()) or "<eos>"
    formatter = Jinja2ChatFormatter(template=template, bos_token=bos, eos_token=eos)

    # 6 个工具：QP 5 + structure_note（与 probe_c3_text_decl.py 完全对齐）
    all_tools = [*build_qp_tools(), build_note_tool()]

    # 最小 messages：system + user（只需 trigger 模板渲染工具声明区块）
    messages_min = [
        {"role": "system", "content": "PLACEHOLDER_SYSTEM"},
        {"role": "user", "content": "PLACEHOLDER_USER"},
    ]
    rendered = formatter(messages=messages_min, tools=all_tools)
    full_prompt = rendered.prompt

    # 提取所有 <|tool>...<tool|> 块（含标记本身，供注入 system content）
    tool_blocks = re.findall(r"<\|tool\>.*?<tool\|>", full_prompt, re.DOTALL)
    if not tool_blocks:
        raise RuntimeError("找不到 <|tool>...<tool|> 块，模板格式异常，检查 full_prompt")

    return "".join(tool_blocks)


def build_hop_a_system(scene_context: str = "") -> str:
    """组装 hop A 的 system prompt：任务说明 + 工具声明（原生格式）+ 场次目录。

    scene_context: 场次目录文本（从 _build_scene_catalog(dal) 取，如
    "Scene 1: 大堂 / Scene 2: 走廊"），注入后模型可用具体场次 ID 填参数。
    对齐 probe_qp_voice_e2e.py system_content 组装格式。
    """
    tool_decl_text = extract_tool_declarations_text()
    scene_section = f"\n\n{scene_context}" if scene_context else ""
    return (
        "你是场记查询助手。只回答数据库里查到的事实，不给建议、不做评价。\n"
        "有合适的工具就调工具查；查到结果后用一句话直接回答。\n"
        "找不到对应记录时直接说没有。\n\n"
        "可用工具：\n"
        + tool_decl_text
        + scene_section
    )
