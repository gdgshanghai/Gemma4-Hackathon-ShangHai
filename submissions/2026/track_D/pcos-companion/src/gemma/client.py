"""
Gemma 4 推理客户端 —— 统一封装端侧 / 云端两档部署。

两档后端（Ollama / vLLM）均暴露 OpenAI 兼容的 /v1/chat/completions 端点，
因此用同一套调用代码即可，差异仅在配置（端点、model 名、是否多模态）。
这让「端侧默认、云端按需」的分级调度对上层完全透明。
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from src.config import CONFIG, ModelTier, GemmaModelSpec


class GemmaClient:
    """对 Gemma 4 OpenAI 兼容端点的薄封装，原生支持 tools（函数调用）。"""

    def __init__(self, tier: ModelTier = ModelTier.EDGE) -> None:
        self.tier = tier
        self.spec: GemmaModelSpec = CONFIG.model_for(tier)
        self._http = httpx.Client(timeout=CONFIG.request_timeout_s)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
    ) -> dict[str, Any]:
        """
        发起一次对话补全。

        关键点：tools 通过 OpenAI 兼容的 `tools` 字段下发，由 Gemma 4 的
        *原生函数调用* 能力解析并在 `message.tool_calls` 中结构化返回——
        不是把工具说明塞进 prompt 里做字符串匹配的「伪函数调用」。
        """
        payload: dict[str, Any] = {
            "model": self.spec.served_model,
            "messages": messages,
            "temperature": CONFIG.temperature,
            "top_p": CONFIG.top_p,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        resp = self._http.post(
            f"{self.spec.endpoint}/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def extract_tool_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
        """从响应里取出结构化的 tool_calls；没有则返回空列表。"""
        try:
            message = response["choices"][0]["message"]
        except (KeyError, IndexError):
            return []
        calls = message.get("tool_calls") or []
        normalized = []
        for call in calls:
            fn = call.get("function", {})
            args = fn.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            normalized.append({
                "id": call.get("id", ""),
                "name": fn.get("name", ""),
                "arguments": args,
            })
        return normalized

    @staticmethod
    def extract_text(response: dict[str, Any]) -> str:
        try:
            return response["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError):
            return ""

    def close(self) -> None:
        self._http.close()
