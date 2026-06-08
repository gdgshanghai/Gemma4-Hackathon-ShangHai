from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).resolve().parents[3]  # eatornot/
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    # LLM config — Gemini 官方 API (OpenAI 兼容)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemma-4-31b-it"

    # Legacy CF AIG (保留兼容)
    CF_AIG_TOKEN: str = ""
    CF_AIG_BASE_URL: str = "https://gateway.ai.cloudflare.com/v1/xxx/default/compat"
    GEMMA_MODEL: str = "google-ai-studio/gemma-4-31b-it"

    # McDonald's MCP config
    MCD_MCP_TOKEN: str = ""
    MCD_MCP_URL: str = "https://mcp.mcd.cn"
    USE_MOCK_MCP: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./eatornot.db"

    # App
    APP_NAME: str = "EatOrNot"
    DEBUG: bool = True

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5178,http://localhost:8000,http://localhost:*"

    model_config = {"env_file": str(ENV_FILE), "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
