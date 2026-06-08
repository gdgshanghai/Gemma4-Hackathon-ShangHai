"""Gemma 4 4B Multimodal client wrapper.

Loads google/gemma-4-4b-it-multimodal once at startup and exposes two
high-level calls used by the API layer:

    extract_palette(image_bytes)      -> 4 hex colors + Chinese aesthetic names
    inscribe_with_tools(palette, ...) -> title + line of poem, via native
                                         function calling against the
                                         district-archive + save tools

Falls back to a deterministic stub when GEMMA_STUB=1 so reviewers without
GPU access can still run the demo end-to-end.
"""
from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass
from typing import Any


GEMMA_MODEL_ID = os.environ.get("GEMMA_MODEL_ID", "google/gemma-4-4b-it-multimodal")
GEMMA_STUB = os.environ.get("GEMMA_STUB", "0") == "1"
GEMMA_DEVICE = os.environ.get("GEMMA_DEVICE", "auto")


@dataclass
class GemmaResponse:
    text: str
    tool_calls: list[dict[str, Any]]
    raw: dict[str, Any]


class GemmaClient:
    def __init__(self) -> None:
        self._processor = None
        self._model = None
        if not GEMMA_STUB:
            self._load()

    def _load(self) -> None:
        from transformers import AutoProcessor, Gemma4ForConditionalGeneration
        import torch

        self._processor = AutoProcessor.from_pretrained(GEMMA_MODEL_ID)
        self._model = Gemma4ForConditionalGeneration.from_pretrained(
            GEMMA_MODEL_ID,
            torch_dtype=torch.bfloat16,
            device_map=GEMMA_DEVICE,
        )
        self._model.eval()

    def extract_palette(self, image_bytes: bytes) -> list[dict[str, str]]:
        """Multimodal call: feed the image, ask for 4 dominant colors with
        Chinese aesthetic names suitable for a heritage color archive.
        """
        if GEMMA_STUB:
            return _stub_palette(image_bytes)

        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        prompt = (
            "你是一位中文色彩档案员,正在为城市更新前的街景做色彩存档。"
            "看这张照片,选出 4 种最有代表性的颜色。"
            "只回 JSON 数组,每项含 hex(大写,#RRGGBB)与 zh(2-4 字汉语雅名,"
            "禁用'红/蓝/灰'等大类词,优先用'砖红/暮褐/苔青/茧白'这种文学化命名)。"
        )
        msgs = [{
            "role": "user",
            "content": [
                {"type": "image", "image": img},
                {"type": "text", "text": prompt},
            ],
        }]
        out = self._chat(msgs, max_new_tokens=256)
        return _parse_palette_json(out.text)

    def inscribe_with_tools(
        self,
        palette: list[dict[str, str]],
        place: str,
        geo: str,
        tool_handler,
    ) -> dict[str, Any]:
        """Native function calling: ask Gemma to draft a title + a line of
        poem for the specimen, calling tools to look up the district archive
        and save the specimen along the way.
        """
        if GEMMA_STUB:
            return _stub_inscribe(palette, place, geo, tool_handler)

        tools = _archive_tools_schema()
        sys_prompt = (
            "你是中文城市色彩存档的题字员。给定一张色彩标本的调色板和位置,"
            "先调用 lookup_district_archive 查街区是否在历史保护名录,"
            "再写一个 6-12 字的中文题名和一句不超过 18 字的散文式短句,"
            "最后调用 save_specimen 把结果存档。"
        )
        user_msg = json.dumps({"palette": palette, "place": place, "geo": geo}, ensure_ascii=False)
        msgs = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg},
        ]

        for _ in range(4):
            out = self._chat(msgs, tools=tools, max_new_tokens=512)
            if not out.tool_calls:
                return _parse_inscribe_text(out.text)
            for call in out.tool_calls:
                result = tool_handler(call["name"], call["arguments"])
                msgs.append({"role": "assistant", "content": "", "tool_calls": [call]})
                msgs.append({"role": "tool", "name": call["name"], "content": json.dumps(result, ensure_ascii=False)})
        raise RuntimeError("inscribe loop exceeded tool-call budget")

    def _chat(self, msgs: list[dict], *, tools=None, max_new_tokens=256) -> GemmaResponse:
        import torch
        kwargs = {"add_generation_prompt": True, "return_tensors": "pt", "tokenize": True}
        if tools:
            kwargs["tools"] = tools
        inputs = self._processor.apply_chat_template(msgs, **kwargs).to(self._model.device)
        with torch.inference_mode():
            ids = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )
        text = self._processor.batch_decode(
            ids[:, inputs["input_ids"].shape[-1]:],
            skip_special_tokens=False,
        )[0]
        tool_calls = _parse_tool_calls(text)
        return GemmaResponse(text=text, tool_calls=tool_calls, raw={})


def _archive_tools_schema() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "lookup_district_archive",
                "description": "查询街区是否在城市历史保护名录中,以及现存色彩档案数量",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "place": {"type": "string", "description": "街道地址,如 '巨鹿路 821 号'"},
                        "geo":   {"type": "string", "description": "经纬度文本"},
                    },
                    "required": ["place"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "save_specimen",
                "description": "把题字完成的色彩标本写入存档库,返回 specimen_no",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title":   {"type": "string"},
                        "line":    {"type": "string", "description": "散文式短句"},
                        "palette": {"type": "array",  "items": {"type": "object"}},
                        "place":   {"type": "string"},
                        "in_archive": {"type": "boolean"},
                    },
                    "required": ["title", "line", "palette", "place"],
                },
            },
        },
    ]


def _parse_tool_calls(text: str) -> list[dict[str, Any]]:
    """Gemma 4 emits tool calls as <tool_call>{...}</tool_call> blocks per
    its native chat template. Extract them; ignore malformed entries.
    """
    import re
    calls = []
    for m in re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.DOTALL):
        try:
            obj = json.loads(m.group(1))
            calls.append({"name": obj["name"], "arguments": obj.get("arguments", {})})
        except (json.JSONDecodeError, KeyError):
            continue
    return calls


def _parse_palette_json(text: str) -> list[dict[str, str]]:
    import re
    m = re.search(r"\[\s*\{.*?\}\s*\]", text, re.DOTALL)
    if not m:
        raise ValueError(f"palette JSON not found in model output: {text[:200]}")
    items = json.loads(m.group(0))
    return [{"hex": it["hex"].upper(), "zh": it["zh"]} for it in items[:4]]


def _parse_inscribe_text(text: str) -> dict[str, Any]:
    import re
    title = re.search(r"题名[::]\s*(.+)", text)
    line = re.search(r"短句[::]\s*(.+)", text)
    return {
        "title": (title.group(1).strip() if title else "无题"),
        "line":  (line.group(1).strip()  if line  else ""),
    }


def _stub_palette(image_bytes: bytes) -> list[dict[str, str]]:
    """Deterministic offline stub keyed off image byte length, so reviewers
    without GPUs see the full UX flow with stable pseudo-AI output.
    """
    presets = [
        [{"hex": "#A14328", "zh": "砖红"}, {"hex": "#8A8378", "zh": "尘灰"},
         {"hex": "#D7C2A0", "zh": "土黄"}, {"hex": "#3B2C20", "zh": "深褐"}],
        [{"hex": "#6F5A8C", "zh": "紫藤"}, {"hex": "#C7B8D6", "zh": "霭紫"},
         {"hex": "#3E3450", "zh": "夜紫"}, {"hex": "#E5D6E5", "zh": "残樱"}],
        [{"hex": "#8B97A0", "zh": "雾青"}, {"hex": "#C4CBCE", "zh": "霜灰"},
         {"hex": "#4D585F", "zh": "远山"}, {"hex": "#DCDBD3", "zh": "茧白"}],
    ]
    return presets[len(image_bytes) % len(presets)]


def _stub_inscribe(palette, place, geo, tool_handler) -> dict[str, Any]:
    archive = tool_handler("lookup_district_archive", {"place": place, "geo": geo})
    saved = tool_handler("save_specimen", {
        "title": f"{place.split(' ')[0]}·{palette[0]['zh']}与{palette[3]['zh']}",
        "line":  "光从砖缝里抖落,像旧年寄的信。",
        "palette": palette,
        "place": place,
        "in_archive": archive.get("listed", False),
    })
    return {"title": saved["title"], "line": saved["line"], "specimen_no": saved["specimen_no"], "in_archive": archive.get("listed", False)}


_client: GemmaClient | None = None


def get_client() -> GemmaClient:
    global _client
    if _client is None:
        _client = GemmaClient()
    return _client
