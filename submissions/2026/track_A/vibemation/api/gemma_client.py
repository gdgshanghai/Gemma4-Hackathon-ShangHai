"""Gemma 4 API 客户端 — 支持 OpenRouter / NVIDIA / 自定义"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# 从 .env 文件加载（仅当未设置环境变量时）
_dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_dotenv_path)

OPENROUTER_KEYS_RAW = os.environ.get("OPENROUTER_KEYS")
if not OPENROUTER_KEYS_RAW:
    raise RuntimeError(
        "缺少 OPENROUTER_KEYS。请在 .env 文件中设置或以环境变量传入。\n"
        f"参考: {Path(__file__).resolve().parent.parent / '.env.example'}"
    )
OPENROUTER_KEYS = [k.strip() for k in OPENROUTER_KEYS_RAW.split(",") if k.strip()]

NVIDIA_KEY = os.environ.get("NVIDIA_KEY")
if not NVIDIA_KEY:
    raise RuntimeError(
        "缺少 NVIDIA_KEY。请在 .env 文件中设置或以环境变量传入。\n"
        f"参考: {Path(__file__).resolve().parent.parent / '.env.example'}"
    )

OPENROUTER_CLIENTS = [
    OpenAI(base_url="https://openrouter.ai/api/v1", api_key=k)
    for k in OPENROUTER_KEYS
]

NVIDIA_CLIENT = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_KEY,
)

_openrouter_idx = 0


def get_client(provider: str = "openrouter_26b") -> tuple[OpenAI, str]:
    global _openrouter_idx

    # 自定义 provider: custom_{name}_{timestamp}
    if provider.startswith("custom_"):
        custom_list = json.loads(os.environ.get("CUSTOM_PROVIDERS", "[]"))
        for c in custom_list:
            if c.get("id") == provider:
                key = c.get("apiKey", "")
                base = c.get("baseUrl", "http://localhost:8000/v1")
                return OpenAI(base_url=base, api_key=key), c.get("model", "")
        # 也支持从 localStorage 传来的查询参数（前端 → 后端）
        return OpenAI(base_url="http://localhost:8000/v1", api_key=""), ""

    if provider == "openrouter_26b":
        _openrouter_idx = (_openrouter_idx + 1) % len(OPENROUTER_CLIENTS)
        return OPENROUTER_CLIENTS[_openrouter_idx], "google/gemma-4-26b-a4b-it"
    elif provider == "openrouter_31b":
        _openrouter_idx = (_openrouter_idx + 1) % len(OPENROUTER_CLIENTS)
        return OPENROUTER_CLIENTS[_openrouter_idx], "google/gemma-4-31b-it"
    elif provider == "nvidia_31b":
        return NVIDIA_CLIENT, "google/gemma-4-31b-it"
    return OPENROUTER_CLIENTS[0], "google/gemma-4-26b-a4b-it"


def chat(messages, model="google/gemma-4-26b-a4b-it", temperature=0.0,
         max_tokens=4096, client=None):
    if client is None:
        client, model = get_client("openrouter_26b")
    resp = client.chat.completions.create(
        model=model, messages=messages,
        temperature=temperature, max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


def chat_with_tools(messages, tools, model="google/gemma-4-26b-it",
                    temperature=0.0, client=None):
    if client is None:
        client, model = get_client("openrouter_26b")
    resp = client.chat.completions.create(
        model=model, messages=messages, tools=tools, temperature=temperature,
    )
    msg = resp.choices[0].message
    return msg.content, (msg.tool_calls or [])


def check_health():
    try:
        OPENROUTER_CLIENTS[0].models.list()
        return True
    except Exception:
        return False


def check_all_providers():
    """检查所有 provider key 的连通性"""
    results = {}
    for i, c in enumerate(OPENROUTER_CLIENTS):
        try:
            c.models.list()
            results[f"openrouter_key_{i}"] = True
        except Exception:
            results[f"openrouter_key_{i}"] = False
    return results
