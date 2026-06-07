import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "GemmaSlide Backend")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    max_slide_count: int = int(os.getenv("MAX_SLIDE_COUNT", "500"))
    temp_root: Path = Path(os.getenv("TEMP_ROOT", "/tmp/gemmaslide"))
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url: str = os.getenv(
        "CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    celery_result_backend: str = os.getenv(
        "CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    job_state_ttl_seconds: int = int(os.getenv("JOB_STATE_TTL_SECONDS", "86400"))
    sse_poll_interval_seconds: float = float(
        os.getenv("SSE_POLL_INTERVAL_SECONDS", "1.0")
    )
    sse_heartbeat_seconds: float = float(os.getenv("SSE_HEARTBEAT_SECONDS", "10.0"))
    llm_endpoint: str | None = os.getenv("LLM_ENDPOINT")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "2000"))
    llm_slide_context_chars: int = int(os.getenv("LLM_SLIDE_CONTEXT_CHARS", "800"))
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    # Live co-present LLM (separate endpoint/model for low-latency suggestions)
    live_llm_endpoint: str = os.getenv("LIVE_LLM_ENDPOINT", "")
    live_llm_api_key: str = os.getenv("LIVE_LLM_API_KEY", "")
    live_llm_model: str = os.getenv("LIVE_LLM_MODEL", "unsloth/gemma-4-E4B-it-GGUF")
    live_llm_max_tokens: int = int(os.getenv("LIVE_LLM_MAX_TOKENS", "384"))
    live_llm_request_timeout: float = float(os.getenv("LIVE_LLM_REQUEST_TIMEOUT", "12.0"))
    # Branch tree generation needs much more output tokens (30-node JSON tree).
    # Defaults to the main (Google) LLM, not the low-latency HF endpoint.
    branch_llm_model: str = os.getenv(
        "BRANCH_LLM_MODEL", os.getenv("LLM_MODEL", "gemma-4-31b-it")
    )
    branch_llm_endpoint: str = os.getenv(
        "BRANCH_LLM_ENDPOINT", os.getenv("LLM_ENDPOINT", "")
    )
    branch_llm_api_key: str = os.getenv(
        "BRANCH_LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")
    )
    branch_llm_max_tokens: int = int(os.getenv("BRANCH_LLM_MAX_TOKENS", "8192"))
    branch_llm_request_timeout: float = float(os.getenv("BRANCH_LLM_REQUEST_TIMEOUT", "90.0"))
    dashscope_api_key: str | None = os.getenv("DASHSCOPE_API_KEY", os.getenv("OPENAI_API_KEY"))
    decorative_min_area_norm: float = float(
        os.getenv("DECORATIVE_MIN_AREA_NORM", "0.002")
    )
    tts_enabled: bool = os.getenv("TTS_ENABLED", "true").lower() in ("1", "true", "yes")
    tts_model: str = os.getenv("TTS_MODEL", "qwen3-tts-flash")
    tts_voice: str = os.getenv("TTS_VOICE", "Cherry")
    tts_max_retries: int = int(os.getenv("TTS_MAX_RETRIES", "5"))
    asr_model: str = os.getenv("ASR_MODEL", "fun-asr-realtime")
    asr_sample_rate: int = int(os.getenv("ASR_SAMPLE_RATE", "16000"))
    asr_format: str = os.getenv("ASR_FORMAT", "pcm")
    asr_semantic_punctuation_enabled: bool = os.getenv(
        "ASR_SEMANTIC_PUNCTUATION_ENABLED", "true"
    ).lower() in ("1", "true", "yes")
    cors_allow_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
            if origin.strip()
        ]
    )


settings = Settings()
