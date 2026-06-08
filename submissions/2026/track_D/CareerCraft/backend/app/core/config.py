"""Global settings configuration for CareerCraft backend."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  """Application global configuration parameters."""

  app_name: str = "CareerCraft Backend MVP"
  # Runtime environment: "development" | "test" | "production".
  # File logging (including LLM request/response dump) is enabled only when
  # this is NOT "production".
  environment: str = "development"
  log_dir: str = "./logs"
  sqlite_url: str = "sqlite:///./careercraft_mvp.db"
  database_url: str | None = None
  chroma_persist_dir: str = "./chroma_data"

  # Origins allowed by the CORS middleware. Tighten in production.
  cors_origins: list[str] = ["http://localhost:5173"]
  # Override the resolved docs directory; empty string means auto-detect
  # relative to the repository root.
  docs_dir: str = ""

  # Unified LLM configuration.
  llm_provider: str = "gemini"
  llm_api_key: str | None = None
  llm_model: str | None = None
  llm_base_url: str | None = None
  # 单次 LLM HTTP 请求的最大等待时间（秒）。SDK internal retry 已禁用，
  # 所有重试由 call_llm_json 的应用层逻辑统一控制。
  llm_timeout: int = 300
  # When True, ``call_llm_json`` retries once on transient network errors
  # (timeout / connection reset) with a short backoff before surfacing the
  # error to the caller.
  llm_retry_on_timeout: bool = True
  # When True, ``call_llm_json`` retries once on schema-violation responses
  # (model returned valid JSON but wrong shape) with the prior error appended
  # to the prompt as a counter-example.
  llm_retry_on_schema_violation: bool = True
  # Tri-state for OpenAI-compatible adapter strict JSON Schema mode.
  # None = auto-detect by base_url (DashScope / api.openai.com / deepseek /
  # moonshot enable strict mode; ollama / others use json_object).
  # True / False forces the choice regardless of endpoint.
  llm_use_json_schema_response_format: bool | None = None

  mock_agent_output: bool = True

  # Public URL prefix used to build artifact download links from stored
  # filenames. The path component must match the StaticFiles mount in
  # ``app.main`` (``/mock_data``). Override per environment when deployed
  # behind a reverse proxy.
  mock_data_public_base: str = "http://localhost:8000/mock_data"
  # When True, the evaluation orchestrator injects a truncated excerpt of the
  # mission artifact into the LLM prompt so feedback can reference the actual
  # data the user worked on. Disable to bound tokens / latency.
  eval_use_artifact_context: bool = True

  # Identity strategy selector.
  # - anonymous: only accept X-Player-Id header (legacy strict path)
  # - hybrid: accept Authorization(Bearer) first, fall back to X-Player-Id
  #   (compatibility-first default during account-auth migration)
  # - jwt: only accept Authorization(Bearer); currently fails fast at startup
  #   because JWT signature/claims validation is not yet implemented.
  auth_mode: Literal["anonymous", "hybrid", "jwt"] = "hybrid"
  # TODO(auth-upgrade): Configure when JWT mode is implemented.
  jwt_secret: str | None = None
  jwt_algorithm: str = "HS256"

  model_config = SettingsConfigDict(
      env_file=".env",
      env_file_encoding="utf-8",
      extra="ignore",
  )


settings = Settings()

