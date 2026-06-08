import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

ProviderKey = Literal["cloud", "local"]

CONFIG_DIR = Path(os.environ.get("FINSIGHT_CONFIG_DIR", Path(__file__).resolve().parents[1] / ".finsight"))
CONFIG_PATH = CONFIG_DIR / "llm_settings.json"
LOCAL_QWEN_PROVIDER = {
    "enabled": True,
    "providerName": "本地 vLLM / Qwen3.6",
    "baseUrl": os.environ.get("FINSIGHT_LOCAL_LLM_BASE_URL", "http://127.0.0.1:8004/v1"),
    "apiKey": os.environ.get("FINSIGHT_LOCAL_LLM_API_KEY", ""),
    "model": os.environ.get("FINSIGHT_LOCAL_LLM_MODEL", "Qwen3.6-35B-A3B-FP8"),
    "temperature": 0.2,
    "maxTokens": 8192,
    "timeoutSeconds": 180,
    "chatTemplateKwargs": {"enable_thinking": False},
}
LOCAL_GEMMA4_PROVIDER = {
    "enabled": True,
    "providerName": "本地 vLLM / Gemma4",
    "baseUrl": os.environ.get("FINSIGHT_GEMMA4_LLM_BASE_URL", "http://127.0.0.1:8006/v1"),
    "apiKey": os.environ.get("FINSIGHT_GEMMA4_LLM_API_KEY", ""),
    "model": os.environ.get("FINSIGHT_GEMMA4_LLM_MODEL", "Gemma-4-26B-A4B-it-NVFP4"),
    "temperature": 0.2,
    "maxTokens": 8192,
    "timeoutSeconds": 600,
    "chatTemplateKwargs": {"enable_thinking": False},
}
LOCAL_MODEL_PRESETS = {
    "qwen36": deepcopy(LOCAL_QWEN_PROVIDER),
    "gemma4": deepcopy(LOCAL_GEMMA4_PROVIDER),
}
LEGACY_LOCAL_BASE_URLS = {"http://localhost:8000/v1", "http://127.0.0.1:8000/v1"}
LEGACY_LOCAL_MODELS = {"local-model", ""}

DEFAULT_SETTINGS: dict[str, Any] = {
    "activeProvider": "local",
    "providers": {
        "cloud": {
            "enabled": False,
            "providerName": "云端 OpenAI Compatible",
            "baseUrl": "",
            "apiKey": "",
            "model": "",
            "temperature": 0.2,
            "maxTokens": 4096,
            "timeoutSeconds": 60,
        },
        "local": deepcopy(LOCAL_QWEN_PROVIDER),
    },
    "updatedAt": None,
}


class LLMProviderUpdate(BaseModel):
    enabled: bool = True
    providerName: str = Field(default="", max_length=80)
    baseUrl: str = Field(default="", max_length=300)
    apiKey: str | None = Field(default=None, max_length=500)
    clearApiKey: bool = False
    model: str = Field(default="", max_length=120)
    temperature: float = Field(default=0.2, ge=0, le=2)
    maxTokens: int = Field(default=8192, ge=1, le=262144)
    timeoutSeconds: int = Field(default=60, ge=5, le=600)


class LLMSettingsUpdate(BaseModel):
    activeProvider: ProviderKey = "local"
    providers: dict[ProviderKey, LLMProviderUpdate]


class LLMTestRequest(BaseModel):
    provider: ProviderKey
    message: str = Field(default="请只回复 OK", max_length=2000)
    config: LLMProviderUpdate | None = None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _normalize_base_url(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def _endpoint(base_url: str, suffix: str) -> str:
    base = _normalize_base_url(base_url)
    if not base:
        raise ValueError("baseUrl is required")
    return f"{base}/{suffix.lstrip('/')}"


def _sanitize_provider(provider: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(provider)
    cleaned["providerName"] = str(cleaned.get("providerName") or "").strip()
    cleaned["baseUrl"] = _normalize_base_url(str(cleaned.get("baseUrl") or ""))
    cleaned["model"] = str(cleaned.get("model") or "").strip()
    cleaned["apiKey"] = str(cleaned.get("apiKey") or "").strip()
    cleaned["enabled"] = bool(cleaned.get("enabled", True))
    cleaned["temperature"] = float(cleaned.get("temperature", 0.2))
    cleaned["maxTokens"] = int(cleaned.get("maxTokens", 4096))
    cleaned["timeoutSeconds"] = int(cleaned.get("timeoutSeconds", 60))
    chat_template_kwargs = cleaned.get("chatTemplateKwargs")
    cleaned["chatTemplateKwargs"] = chat_template_kwargs if isinstance(chat_template_kwargs, dict) else {}
    return cleaned


def _apply_local_model_preset_extras(provider: dict[str, Any]) -> dict[str, Any]:
    model = str(provider.get("model") or "").strip()
    for preset in LOCAL_MODEL_PRESETS.values():
        if model == preset["model"]:
            provider["chatTemplateKwargs"] = deepcopy(preset.get("chatTemplateKwargs") or {})
            break
    return provider


def _migrate_legacy_local_provider(settings: dict[str, Any]) -> None:
    local = settings["providers"].get("local", {})
    base_url = _normalize_base_url(str(local.get("baseUrl") or ""))
    model = str(local.get("model") or "").strip()
    if base_url in LEGACY_LOCAL_BASE_URLS and model in LEGACY_LOCAL_MODELS:
        api_key = str(local.get("apiKey") or "").strip()
        settings["providers"]["local"] = deepcopy(LOCAL_QWEN_PROVIDER)
        settings["providers"]["local"]["apiKey"] = api_key


def _public_provider(provider: dict[str, Any]) -> dict[str, Any]:
    public = dict(provider)
    public.pop("apiKey", None)
    public["hasApiKey"] = bool(provider.get("apiKey"))
    return public


def _public_local_model_presets() -> dict[str, Any]:
    return {
        key: _public_provider(_sanitize_provider(deepcopy(value)))
        for key, value in LOCAL_MODEL_PRESETS.items()
    }


def load_llm_settings(include_secrets: bool = False) -> dict[str, Any]:
    settings = deepcopy(DEFAULT_SETTINGS)
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                settings = _deep_merge(settings, saved)
        except (OSError, json.JSONDecodeError):
            pass

    for key in ("cloud", "local"):
        settings["providers"][key] = _sanitize_provider(settings["providers"].get(key, {}))
    settings["providers"]["local"] = _apply_local_model_preset_extras(settings["providers"]["local"])

    _migrate_legacy_local_provider(settings)

    if settings.get("activeProvider") not in ("cloud", "local"):
        settings["activeProvider"] = "local"

    if include_secrets:
        return settings

    public = deepcopy(settings)
    public["providers"] = {
        key: _public_provider(value)
        for key, value in settings["providers"].items()
    }
    public["localModelPresets"] = _public_local_model_presets()
    return public


def save_llm_settings(update: LLMSettingsUpdate) -> dict[str, Any]:
    current = load_llm_settings(include_secrets=True)
    next_settings = deepcopy(current)
    next_settings["activeProvider"] = update.activeProvider

    for key, provider_update in update.providers.items():
        incoming = provider_update.model_dump()
        provider = deepcopy(current["providers"].get(key, DEFAULT_SETTINGS["providers"][key]))
        for field in ("enabled", "providerName", "baseUrl", "model", "temperature", "maxTokens", "timeoutSeconds"):
            provider[field] = incoming[field]
        if incoming.get("clearApiKey"):
            provider["apiKey"] = ""
        elif incoming.get("apiKey") is not None and incoming.get("apiKey", "").strip():
            provider["apiKey"] = incoming["apiKey"].strip()
        provider = _sanitize_provider(provider)
        if key == "local":
            provider = _apply_local_model_preset_extras(provider)
        next_settings["providers"][key] = provider

    next_settings["updatedAt"] = datetime.now(timezone.utc).isoformat()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(next_settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return load_llm_settings(include_secrets=False)


def _provider_from_request(request: LLMTestRequest) -> dict[str, Any]:
    saved = load_llm_settings(include_secrets=True)
    provider = deepcopy(saved["providers"][request.provider])
    if request.config is not None:
        incoming = request.config.model_dump()
        for field in ("enabled", "providerName", "baseUrl", "model", "temperature", "maxTokens", "timeoutSeconds"):
            provider[field] = incoming[field]
        if incoming.get("clearApiKey"):
            provider["apiKey"] = ""
        elif incoming.get("apiKey") is not None and incoming.get("apiKey", "").strip():
            provider["apiKey"] = incoming["apiKey"].strip()
    provider = _sanitize_provider(provider)
    if request.provider == "local":
        provider = _apply_local_model_preset_extras(provider)
    return provider


async def test_llm_provider(request: LLMTestRequest) -> dict[str, Any]:
    provider = _provider_from_request(request)
    if not provider["baseUrl"]:
        return {"ok": False, "message": "请先填写 Base URL", "provider": request.provider}
    if not provider["model"]:
        return {"ok": False, "message": "请先填写模型名称", "provider": request.provider}

    headers = {"Content-Type": "application/json"}
    if provider.get("apiKey"):
        headers["Authorization"] = f"Bearer {provider['apiKey']}"

    payload = {
        "model": provider["model"],
        "messages": [
            {"role": "system", "content": "You are a connectivity checker. Reply concisely."},
            {"role": "user", "content": request.message},
        ],
        "temperature": provider["temperature"],
        "max_tokens": min(provider["maxTokens"], 64),
        "stream": False,
        "chat_template_kwargs": provider.get("chatTemplateKwargs") or {},
    }

    started = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=float(provider["timeoutSeconds"])) as client:
            resp = await client.post(
                _endpoint(provider["baseUrl"], "/chat/completions"),
                headers=headers,
                json=payload,
            )
            elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "provider": request.provider,
                    "statusCode": resp.status_code,
                    "latencyMs": elapsed_ms,
                    "message": resp.text[:600],
                }
            data = resp.json()
            content = ""
            choices = data.get("choices") or []
            if choices:
                message = choices[0].get("message") or {}
                content = str(message.get("content") or choices[0].get("text") or "")
            return {
                "ok": True,
                "provider": request.provider,
                "statusCode": resp.status_code,
                "latencyMs": elapsed_ms,
                "model": provider["model"],
                "message": content.strip()[:600] or "连接成功",
            }
    except Exception as exc:  # noqa: BLE001 - surface connectivity errors to the UI
        return {
            "ok": False,
            "provider": request.provider,
            "message": str(exc)[:600],
        }
