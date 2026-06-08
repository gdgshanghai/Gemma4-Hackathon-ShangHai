"""SP Pipeline：剧本解析器（ticket 3.B）。

公共 API：
  Slugline / ParsedLine / ParsedScene   解析结果 dataclass（frozen）
  SPParseError                          解析失败异常（当前路径不主动抛，保留兼容）
  split_scenes_by_slugline / split_for_parse  启发式分场（不调 LLM）
  parse_scene_block                     单场结构化（Gemma 逐行判定 + 代码拼装，普通输出快路径）
  parse_scene_block_fc                  单场结构化的原生 function calling 版（强制调工具，结构由 grammar 保证）
  run_sp_parse                          整本解析（split + 逐场，串行）

设计依据：
  docs/specs/2026-06-03-script-import-sp-pipeline.md §4（注：实现已按 2026-06 实测演进，
  与 spec v1「全 LLM + grammar」不同，详见下）

架构（v5，2026-06 实测拍板）
---------------------------------------
整本剧本远超 n_ctx，且实测 grammar 在 Gemma（~25 万词表）上每 token CPU 开销大、
吞吐降 5.6×。故按「能用代码就别用模型、模型只做必须语义判断、不用 grammar」分工：

1. 分场（split_scenes_by_slugline，纯代码）：正则认场头（slugline / 场号），对整本
   一次扫切成「每段一场」。瞬时、不受上下文窗口限制（绕开整本喂不进的死结）。
   超长单场再按字数兜底切（split_for_parse → _split_into_chunks）。
2. 场头元信息（_parse_slugline，纯代码正则）：scene_code + 内外景/时间/地点。
3. 逐行结构化（parse_scene_block，唯一调 LLM 处）：把单场正文喂 Gemma，它逐行吐
   [说话人, 台词]——对白给说话人、动作/描述/舞台指示给空串（边吐台词边判定，
   比"只标说话人"的 classify 准）。无 response_format/grammar。
4. 解析模型输出（_parse_lines_output，永不抛）：模型输出不合法时退化为冒号启发式
   兜底（_fallback_lines，台词不丢），保证整本不因单场崩。

历史：v1 全靠 LLM + grammar 输出整场 JSON（慢）；中途试过 classify（只标说话人，
4B 易把含人名的描述误判成对白，质量差）；v5 定为上面的"代码切场 + LLM 逐行 + 无 grammar"。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.llm.config import TASK_CONFIG

if TYPE_CHECKING:
    from backend.llm.service import LLMService


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class SPParseError(Exception):
    """LLM 输出解析失败。

    cause 串联原始异常（json.JSONDecodeError / KeyError 等），
    调用方可通过 e.cause 取原始异常细节。
    """

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


# ---------------------------------------------------------------------------
# 数据类型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Slugline:
    """场景头信息（slugline）三要素。

    任意字段为 None 表示 LLM 未能识别该要素（常态合法值，不是错误）。
    """

    int_ext: str | None
    time_of_day: str | None
    location: str | None


@dataclass(frozen=True)
class ParsedLine:
    """单行台词或舞台指示。

    character=None 表示舞台指示行（对齐 schema script_lines.character 可空）。
    """

    character: str | None
    text: str


@dataclass(frozen=True)
class ParsedScene:
    """单场解析结果。

    scene_code：解析器抽到的显式场次号，抽不到为 None（常态合法值）。
    slugline：内外景/时间/地点；任意字段可 None。
    lines：有序行列表；line_no 由入库侧（3.C）分配，解析器不 emit。
    """

    scene_code: str | None
    slugline: Slugline
    lines: list[ParsedLine]


# ---------------------------------------------------------------------------
# 内部常量
# ---------------------------------------------------------------------------

# 默认单块字符上限（触发分块的阈值）
_DEFAULT_CHUNK_SIZE = 1500


# ---------------------------------------------------------------------------
# Prompt 构建
# ---------------------------------------------------------------------------


def _build_system_prompt() -> str:
    """返回 TASK_CONFIG["script_parse"]["system"]（v5 完整输出 prompt，逐行 [说话人,台词]）。"""
    return TASK_CONFIG["script_parse"]["system"]


# ---------------------------------------------------------------------------
# 分块
# ---------------------------------------------------------------------------


def _lines_to_paragraphs(lines: list[str]) -> list[str]:
    """把行列表按空行切成段落块，返回非空段落列表（不含空行本身）。

    连续多个空行视为单个段落分隔。
    """
    paragraphs: list[str] = []
    current: list[str] = []

    for line in lines:
        if line.strip() == "":
            if current:
                paragraphs.append("\n".join(current))
                current = []
        else:
            current.append(line)

    if current:
        paragraphs.append("\n".join(current))

    return paragraphs


def _split_paragraph_by_lines(paragraph: str, chunk_size: int) -> list[str]:
    """单个超大段落按行机械切兜底，不切断单行。"""
    lines = paragraph.splitlines()
    chunks: list[str] = []
    current_lines: list[str] = []
    current_size = 0

    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if current_lines and current_size + line_len > chunk_size:
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_size = line_len
        else:
            current_lines.append(line)
            current_size += line_len

    if current_lines:
        chunks.append("\n".join(current_lines))

    return chunks


def _split_into_chunks(raw_text: str, chunk_size: int) -> list[str]:
    """空行优先切分文本，返回各块列表。

    策略：
    1. 先按空行把文本切成段落块（剧本场间通常有空行，空行切降低跨块孤儿场概率）。
    2. 按 chunk_size 字符数累积段落块成 chunk；段落内不切（保场内完整）。
    3. 若单个段落块本身超过 chunk_size，退化到按行机械切兜底（防超 token）。
    """
    sep = "\n\n"  # 段落分隔符；size 记账与拼接共用同一来源，避免魔数漂移
    lines = raw_text.splitlines()
    paragraphs = _lines_to_paragraphs(lines)

    chunks: list[str] = []
    current_parts: list[str] = []
    current_size = 0

    for para in paragraphs:
        para_size = len(para) + len(sep)

        if para_size > chunk_size:
            # 段落本身超限：先 flush 当前积累，再按行切兜底
            if current_parts:
                chunks.append(sep.join(current_parts))
                current_parts = []
                current_size = 0
            chunks.extend(_split_paragraph_by_lines(para, chunk_size))
        elif current_parts and current_size + para_size > chunk_size:
            # 加入后超限：先 flush，新段落开新块
            chunks.append(sep.join(current_parts))
            current_parts = [para]
            current_size = para_size
        else:
            current_parts.append(para)
            current_size += para_size

    if current_parts:
        chunks.append(sep.join(current_parts))

    return chunks


# ---------------------------------------------------------------------------
# 启发式分场（按场头切分，不调 LLM）
# ---------------------------------------------------------------------------
#
# 为什么用启发式：整本剧本（~2万字）远超 n_ctx=8192，无法一次喂模型「找出所有场」；
# 而场边界由「场头（slugline）」这种结构标记决定，可对整本一次扫、瞬时切开——
# 切完每段=一场（已落进 n_ctx），再逐段交 LLM 做语义结构化（character/text 判定）。
# 即：边界靠模式（这里），语义靠 LLM（_parse_chunk_output）。用户 2026-06-05 拍板。

# 单行最长视为场头的字数（超过多半是叙述/台词，不是场头）
_MAX_HEADER_LEN = 30
# 单场块最长字符；超过则退回按字数切（防单场超 n_ctx）
_MAX_BLOCK_CHARS = 3000

# 显式场次号开头：场3 / 第3场 / 场景3 / SCENE 3 / S3 / 3. / 3A. / 12、
_SCENE_NUM_RE = re.compile(
    r"^\s*(?:"
    r"第?\s*\d+\s*场"
    r"|场\s*\d+"
    r"|场景\s*\d+"
    r"|S(?:CENE)?\s*\.?\s*\d+"
    r"|\d{1,3}[A-Za-z]?\s*[.、．]"
    r")",
    re.IGNORECASE,
)
# 内外景标记（slugline 必含其一）
_INT_EXT_RE = re.compile(r"(内景|外景|内|外|INT|EXT)", re.IGNORECASE)
# 以内外景「场头 token」开头（内 咖啡馆 日）：内景/外景/INT/EXT，或 内/外 后紧跟空白（含全角空格）。
# 收紧——不再裸匹配「内/外」，以免把「外婆…」「内心…」等叙述误判成场头。
_STARTS_INT_EXT_RE = re.compile(r"^\s*(?:内景|外景|INT|EXT|[内外][\s　])", re.IGNORECASE)
# 时间标记（用于「反序 slugline」判定：大漠 日 外）
_TIME_RE = re.compile(r"(日|夜|晨|昏|黎明|清晨|傍晚|凌晨|白天|晚上|早晨|午后|黄昏)")
# 显式场次「标号」（高精度，不含易撞列表的 "N."）：第N场 / 场N / 场景N / SCENE N / SN
_SCENE_LABEL_RE = re.compile(
    r"^\s*(?:第?\s*\d+\s*场|场\s*\d+|场景\s*\d+|S(?:CENE)?\s*\.?\s*\d+)",
    re.IGNORECASE,
)
# 句读：含则多半是叙述/台词（注意不含 ·／-／空格 等 slugline 分隔符）
_PROSE_PUNCT_RE = re.compile(r"[，。！？；,!?;]")


def _is_scene_header(line: str) -> bool:
    """判断一行是否为场头（slugline / 场次号）。

    判定（高精度优先，避免把含「内/外」的叙述/台词误判成场头）：
      1. 显式场次号开头（场3 / SCENE 3 / 3.）→ 是。
      2. 含台词冒号（：/:）→ 不是（那是对白行）。
      3. 过长（>30 字）→ 不是。
      4. 含句读（，。！？；）→ 不是（叙述/台词，杀「窗外，…夜。」「外婆…。」类误判）。
      5. 以内外景 token 开头（内景/外景/INT/EXT/内|外+空白）→ 是（内 咖啡馆 日）。
      6. 含内外景标记 且 含时间标记 → 是（反序 slugline：大漠 日 外）。
    """
    s = line.strip()
    if not s:
        return False
    if _SCENE_NUM_RE.match(s):
        return True
    if "：" in s or ":" in s:
        return False
    if len(s) > _MAX_HEADER_LEN:
        return False
    if _PROSE_PUNCT_RE.search(s):
        return False
    if _STARTS_INT_EXT_RE.match(s):
        return True
    return bool(_INT_EXT_RE.search(s) and _TIME_RE.search(s))


def split_scenes_by_slugline(raw_text: str) -> list[str]:
    """按场头把整本剧本切成「每段一场」的文本块（不调 LLM）。

    分两种剧本：
      - 有显式场号（第1场 / 场1 / SCENE 1）→ **只在场号处切**：连续场、无号 slugline、
        含「内/外/日/夜」的叙述都自动并入当前编号场；首个场号前的前言（人物表/标题）丢弃。
        （避免把叙述、子场误切成独立场——用户 2026-06-06 反馈的 27→33 误切。）
      - 无场号 → 回退 slugline 启发式（_is_scene_header，已收紧排除句读散文）。
    返回非空块列表；空输入返回 []。
    """
    lines = raw_text.splitlines()
    if any(_SCENE_LABEL_RE.match(ln.strip()) for ln in lines):
        return _split_at(lines, lambda ln: bool(_SCENE_LABEL_RE.match(ln.strip())), drop_preamble=True)
    return _split_at(lines, _is_scene_header, drop_preamble=False)


def _split_at(lines: list[str], is_header, *, drop_preamble: bool) -> list[str]:
    """在 is_header 命中处切块。

    drop_preamble=True：首个场头之前的内容（前言）丢弃，不成块；只有见到首个场头后才开始积累。
    drop_preamble=False：保留首个场头前的前言为一块（无场号剧本的旧行为）。
    """
    blocks: list[str] = []
    current: list[str] = []
    started = False
    for line in lines:
        if is_header(line):
            if started or any(x.strip() for x in current):
                blocks.append("\n".join(current))
            current = [line]
            started = True
        elif started or not drop_preamble:
            current.append(line)
        # drop_preamble 且未见场头：前言行直接丢弃
    if started or not drop_preamble:
        blocks.append("\n".join(current))
    return [b for b in blocks if b.strip()]


# ---------------------------------------------------------------------------
# 输出解析
# ---------------------------------------------------------------------------


def _strip_markdown_fence(text: str) -> str:
    """剥除 ```json ... ``` 或 ``` ... ``` 包裹，只剥一层。"""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline == -1:
            return stripped
        content_start = first_newline + 1
        last_fence = stripped.rfind("```")
        if last_fence > content_start:
            return stripped[content_start:last_fence].strip()
    return stripped


# 对白行启发式：行首较短说话人名 + 冒号 + 台词（仅用于"模型输出不可解析"时的兜底）
_DIALOGUE_FULL_RE = re.compile(r"^([^：:。！？.!?，,]{1,18})[：:]\s*(.+)$")


def _fallback_lines(body_lines: list[str]) -> list[ParsedLine]:
    """模型输出不可解析时的兜底：按冒号启发式拆行（有冒号=对白，否则=描述）。

    保证台词原文不丢、且尽量保留说话人；比"全部按描述"体验好。
    """
    out: list[ParsedLine] = []
    for ln in body_lines:
        m = _DIALOGUE_FULL_RE.match(ln)
        if m:
            out.append(ParsedLine(character=m.group(1).strip(), text=m.group(2).strip()))
        else:
            out.append(ParsedLine(character=None, text=ln))
    return out


# 整行只是一个括号语气（全/半角），如 （笑）/（停顿两秒）/（对沈默）
_PAREN_ONLY_RE = re.compile(r"^[（(][^）)]*[）)]$")


def _merge_parentheticals(lines: list[ParsedLine]) -> list[ParsedLine]:
    """把「整行只是括号语气」的行并入下一行台词前缀，避免它单独占一行。

    剧本里独占一行的括号（语气/动作提示）是给下一句台词的，应贴在台词前（用户 2026-06-06 反馈）。
    合并后说话人沿用下一行（台词的说话人）；连续多个括号累积；末尾孤立括号无下一行 → 保留为描述行。
    模型已内联（如「（笑）你好」）的不受影响——非纯括号行，正则不匹配。
    """
    out: list[ParsedLine] = []
    pending = ""
    for ln in lines:
        if _PAREN_ONLY_RE.match(ln.text.strip()):
            pending += ln.text.strip()
            continue
        if pending:
            out.append(ParsedLine(character=ln.character, text=pending + ln.text))
            pending = ""
        else:
            out.append(ln)
    if pending:  # 末尾孤立括号：保留为描述行，不丢
        out.append(ParsedLine(character=None, text=pending))
    return out


# 角色名尾部括号注记：（V.O.）/（O.S.）/（画外音）/（记忆中的自己）等。
_CHAR_PAREN_SUFFIX_RE = re.compile(r"[（(][^（）()]*[）)]\s*$")


def normalize_character(name: str | None) -> str | None:
    """归一角色名：剥掉尾部括号注记（夏雨（V.O.）→ 夏雨；沈默（记忆中的自己）→ 沈默）。

    用户 2026-06-06：角色名不一致但实为同一人/同一声纹 → 直接合并。反复剥连续尾部括号；
    若整名就是括号（如「（旁白）」剥后为空）则保留原名不动。None/描述行原样返回。
    """
    if name is None:
        return None
    cur = name.strip()
    while True:
        stripped = _CHAR_PAREN_SUFFIX_RE.sub("", cur).strip()
        if stripped == cur or not stripped:
            break
        cur = stripped
    return cur or (name.strip() or None)


def _normalize_characters(lines: list[ParsedLine]) -> list[ParsedLine]:
    """对每行 character 做归一（剥尾部括号注记），text 不动。解析落库前的统一收口。"""
    return [
        ParsedLine(character=normalize_character(ln.character), text=ln.text)
        for ln in lines
    ]


def _finalize_lines(lines: list[ParsedLine]) -> list[ParsedLine]:
    """解析输出落库前的统一收尾：括号语气并入下一行 → 角色名归一。

    parse_scene_block / parse_scene_block_fc（含兜底）三条出口共用，避免重复拼接。
    """
    return _normalize_characters(_merge_parentheticals(lines))


def _parse_slugline(header: str) -> tuple[str | None, Slugline]:
    """从场头行抽 scene_code + slugline 三要素（best-effort 正则，仅供展示/去重）。"""
    s = header.strip()
    code: str | None = None
    m = re.match(r"^\s*(?:第|场景|场|S(?:CENE)?)\s*\.?\s*(\d{1,3}[A-Za-z]?)", s, re.IGNORECASE)
    if m:
        code = m.group(1)
    else:
        m2 = re.match(r"^\s*(\d{1,3}[A-Za-z]?)\s*[.、．]", s)
        if m2:
            code = m2.group(1)

    int_ext: str | None = None
    mie = _INT_EXT_RE.search(s)
    if mie:
        tok = mie.group(1)
        int_ext = "内" if tok.upper() == "INT" else "外" if tok.upper() == "EXT" else tok

    mt = _TIME_RE.search(s)
    time_of_day = mt.group(1) if mt else None

    # location：去掉已识别成分后的残余（粗糙，识别不到就 None）
    rest = s
    for tok in filter(None, [code, time_of_day]):
        rest = rest.replace(tok, " ")
    rest = re.sub(r"(第|场景|场|SCENE|INT|EXT|内景|外景|内|外)", " ", rest, flags=re.IGNORECASE)
    rest = re.sub(r"[·.、．\-_:：|]", " ", rest)
    rest = " ".join(rest.split()).strip()
    location = rest or None

    return code, Slugline(int_ext=int_ext, time_of_day=time_of_day, location=location)


def _parse_lines_output(raw_text: str, body_lines: list[str]) -> list[ParsedLine]:
    """解析模型的 [[说话人,台词],...] 完整输出 → list[ParsedLine]。**永不抛**。

    无 grammar，故模型偶发输出不合法时走 _fallback_lines（冒号启发式，台词不丢）。
    台词正文取自模型输出（模型已剥"说话人："前缀），不再二次处理。
    """
    cleaned = _strip_markdown_fence(raw_text) if raw_text else ""
    lb, rb = cleaned.find("["), cleaned.rfind("]")
    arr = None
    if lb != -1 and rb > lb:
        try:
            arr = json.loads(cleaned[lb : rb + 1])
        except (json.JSONDecodeError, ValueError):
            arr = None
    if not isinstance(arr, list) or not arr:
        return _fallback_lines(body_lines)

    parsed: list[ParsedLine] = []
    for item in arr:
        if isinstance(item, list) and item:
            speaker = item[0].strip() if isinstance(item[0], str) else ""
            text = " ".join(str(x) for x in item[1:]).strip() if len(item) > 1 else ""
            if not text:
                continue
            parsed.append(ParsedLine(character=speaker or None, text=text))
        elif isinstance(item, str) and item.strip():  # 模型偶发吐纯字符串 → 当描述
            parsed.append(ParsedLine(character=None, text=item.strip()))
    return parsed or _fallback_lines(body_lines)


def _split_scene_header(block: str) -> tuple[str | None, Slugline, list[str]]:
    """切出场头（scene_code + slugline）与正文行（已 strip、去空行）。

    首行是场头（_is_scene_header）→ 代码抽 scene_code/slugline，正文取其后；
    否则整块都是正文、无场头元信息。parse_scene_block 与 parse_scene_block_fc 共用。
    """
    lines = block.splitlines()
    scene_code: str | None = None
    slugline = Slugline(int_ext=None, time_of_day=None, location=None)
    body_lines = lines
    if lines and _is_scene_header(lines[0]):
        scene_code, slugline = _parse_slugline(lines[0])
        body_lines = lines[1:]
    body = [ln.strip() for ln in body_lines if ln.strip()]
    return scene_code, slugline, body


def _parse_fc_lines(tool_call: dict, body_lines: list[str]) -> list[ParsedLine]:
    """解析 report_parsed_lines tool_call 的 arguments → list[ParsedLine]。**永不抛**。

    forced tool_choice 的 grammar 已保证结构合法，但仍做防御解析 + 兜底（与 v5 一致）：
    arguments 缺失/非法时退化为冒号启发式（_fallback_lines，台词不丢）。
    speaker 空串 → None（描述行）。兼容模型偶发吐 [说话人,台词] 数组而非 {speaker,text}。
    """
    try:
        args = json.loads(tool_call["function"]["arguments"])
        raw_lines = args.get("lines")
    except (KeyError, TypeError, json.JSONDecodeError, ValueError):
        return _fallback_lines(body_lines)
    if not isinstance(raw_lines, list) or not raw_lines:
        return _fallback_lines(body_lines)

    parsed: list[ParsedLine] = []
    for item in raw_lines:
        if isinstance(item, dict):
            speaker, text = item.get("speaker", ""), item.get("text", "")
        elif isinstance(item, list) and item:  # 容忍模型偶发吐数组
            speaker = item[0] if isinstance(item[0], str) else ""
            text = " ".join(str(x) for x in item[1:]) if len(item) > 1 else ""
        else:
            continue
        speaker = speaker.strip() if isinstance(speaker, str) else ""
        text = text.strip() if isinstance(text, str) else ""
        if not text:
            continue
        parsed.append(ParsedLine(character=speaker or None, text=text))
    return parsed or _fallback_lines(body_lines)


# ---------------------------------------------------------------------------
# 核心函数
# ---------------------------------------------------------------------------


def split_for_parse(raw_text: str, *, chunk_size: int = _DEFAULT_CHUNK_SIZE) -> list[str]:
    """把整本切成「逐场」可解析的小块：先按场头分场，超长场再按字数兜底切。

    返回的每块都已落进 n_ctx，适合单独喂一次 LLM。空输入返回 []。
    调用方（端点）可据此逐块解析 + 上报进度 + 增量入库。
    """
    if not raw_text or not raw_text.strip():
        return []
    chunks: list[str] = []
    for block in split_scenes_by_slugline(raw_text):
        if len(block) > _MAX_BLOCK_CHARS:
            chunks.extend(_split_into_chunks(block, chunk_size))
        else:
            chunks.append(block)
    return [c for c in chunks if c.strip()]


async def parse_scene_block(
    block: str,
    llm_service: "LLMService",
    *,
    timeout: float = 120.0,
) -> list[ParsedScene]:
    """完整输出（无 grammar）：Gemma 逐行吐 [说话人,台词]，代码解析拼装。返回 [一个 ParsedScene]。

    流程：场头行 → 代码抽 scene_code+slugline；正文喂模型 → 拿 [[说话人,台词],...]
    （模型边吐台词边判断动作/对白，质量比 classify 好）→ 解析成 ParsedLine。

    **永不抛 SPParseError**：模型输出不合法时走冒号启发式兜底（台词不丢），不影响其余场。
    infer 自身异常（超时等）仍向上抛，由调用方处理。
    """
    scene_code, slugline, body = _split_scene_header(block)
    if not body:
        return [ParsedScene(scene_code=scene_code, slugline=slugline, lines=[])]

    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": "剧本：\n" + "\n".join(body)},
    ]
    raw_output: str = await llm_service.infer(
        messages,
        task_type="script_parse",
        priority=3,
        timeout=timeout,
    )
    parsed_lines = _finalize_lines(_parse_lines_output(raw_output, body))  # 永不抛
    return [ParsedScene(scene_code=scene_code, slugline=slugline, lines=parsed_lines)]


async def parse_scene_block_fc(
    block: str,
    llm_service: "LLMService",
    *,
    timeout: float = 120.0,
) -> list[ParsedScene]:
    """单场解析的**原生 function calling** 版：强制调 report_parsed_lines 工具。

    与 parse_scene_block 同输入同输出（返回 [一个 ParsedScene]），区别仅在 LLM 调用机制：
    走 infer_tool（forced tool_choice），输出结构由 JSON grammar 物理保证，不靠事后 JSON 容错。
    用于单场路径（照片增补 / 更新对话框 / 黑客松原生 FC 展示）——一次一调，grammar 成本可忍；
    整本逐场热循环仍用 parse_scene_block（快路径，无 grammar）。

    **永不抛 SPParseError**：tool_call 缺失（模型没走 FC）或 arguments 非法时，
    退化为冒号启发式兜底（台词不丢）。infer_tool 自身异常（超时等）仍向上抛。
    """
    scene_code, slugline, body = _split_scene_header(block)
    if not body:
        return [ParsedScene(scene_code=scene_code, slugline=slugline, lines=[])]

    messages = [
        {"role": "system", "content": TASK_CONFIG["script_parse_fc"]["system"]},
        {"role": "user", "content": "剧本：\n" + "\n".join(body)},
    ]
    try:
        tool_call: dict = await llm_service.infer_tool(
            messages,
            task_type="script_parse_fc",
            priority=3,
            timeout=timeout,
        )
    except LookupError:  # 模型没走 FC（tool_calls 缺失）→ 兜底，不崩
        fallback = _finalize_lines(_fallback_lines(body))
        return [ParsedScene(scene_code=scene_code, slugline=slugline, lines=fallback)]

    parsed_lines = _finalize_lines(_parse_fc_lines(tool_call, body))  # 永不抛
    return [ParsedScene(scene_code=scene_code, slugline=slugline, lines=parsed_lines)]


async def run_sp_parse(
    raw_text: str,
    llm_service: "LLMService",
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    timeout: float = 120.0,
) -> list[ParsedScene]:
    """执行剧本解析：raw_text → list[ParsedScene]（一次性版，逐块串行）。

    分块策略改为「按场头分场」（split_for_parse）：每块=一场，比旧的按字数切
    更快、不易超时、且避免一场被切两半的孤儿场。需要进度/增量入库的调用方
    （端点）可改用 split_for_parse + parse_scene_block 自行循环。

    Args:
        raw_text: 剧本原始文本（粘贴/文件提取/OCR 文本）。
        llm_service: 注入的 LLMService 实例。
        chunk_size: 超长单场的兜底切分字符上限（默认 1500）。
        timeout: 每块 infer 最大等待（默认 120s）。

    Returns:
        ParsedScene 列表，按输入顺序。空输入返回 []。

    Raises:
        SPParseError: LLM 输出非合法 JSON / 顶层缺 scenes / 场缺 lines / 类型错。
        asyncio.TimeoutError: infer 超时，不吞，让 caller 感知。
    """
    blocks = split_for_parse(raw_text, chunk_size=chunk_size)
    all_scenes: list[ParsedScene] = []
    for block in blocks:
        all_scenes.extend(await parse_scene_block(block, llm_service, timeout=timeout))
    return all_scenes
