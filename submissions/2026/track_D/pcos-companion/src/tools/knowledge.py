"""
指南来源的 PCOS 知识检索（RAG）—— 保证医学内容准确、可溯源。

MVP 用轻量 TF-IDF over 一个由*公开权威指南*整理的本地知识库
（中华医学会 PCOS 诊治指南、WHO 事实清单、Lancet 2026 共识等，见
 data/knowledge_base/pcos_guidelines.jsonl 中的 `source` 字段）。
正式版可平滑替换为向量检索；接口保持不变。
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from src.tools.registry import register

_KB_PATH = Path(__file__).resolve().parents[2] / "data" / "knowledge_base" / "pcos_guidelines.jsonl"
_DOCS: list[dict[str, Any]] = []
_DF: Counter = Counter()


def _tokenize(text: str) -> list[str]:
    # 简单中英混合分词：英文按词，中文按 bigram
    text = text.lower()
    en = re.findall(r"[a-z0-9]+", text)
    zh = re.findall(r"[\u4e00-\u9fff]", text)
    bigrams = ["".join(p) for p in zip(zh, zh[1:])]
    return en + zh + bigrams


def _load() -> None:
    if _DOCS or not _KB_PATH.exists():
        return
    for line in _KB_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        doc = json.loads(line)
        doc["_tokens"] = _tokenize(doc["question"] + " " + doc["answer"])
        _DOCS.append(doc)
        for t in set(doc["_tokens"]):
            _DF[t] += 1


def _score(query_tokens: list[str], doc: dict[str, Any]) -> float:
    n = len(_DOCS) or 1
    tf = Counter(doc["_tokens"])
    s = 0.0
    for t in query_tokens:
        if t in tf:
            idf = math.log((n + 1) / (_DF[t] + 1)) + 1
            s += (tf[t] / len(doc["_tokens"])) * idf
    return s


def lookup_pcos_knowledge(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    _load()
    query = args.get("query", "")
    q_tokens = _tokenize(query)
    ranked = sorted(_DOCS, key=lambda d: _score(q_tokens, d), reverse=True)
    top = ranked[:2] if ranked else []
    if not top or _score(q_tokens, top[0]) == 0:
        return {
            "tool": "lookup_pcos_knowledge",
            "found": False,
            "message": "知识库里没有足够把握的答案，建议把这个问题留给医生。",
        }
    return {
        "tool": "lookup_pcos_knowledge",
        "found": True,
        "snippets": [
            {"answer": d["answer"], "source": d["source"]} for d in top
        ],
        "note": "请用通俗语言转述，并提醒『具体情况因人而异，建议就医』。",
    }


register("lookup_pcos_knowledge", lookup_pcos_knowledge)
