"""Immutable environment-backed settings for the local V13 runtime."""

from __future__ import annotations

import os
from datetime import time
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPROVED_LM_STUDIO_MODEL = "gemma-4-26b-a4b-it"

_DEFAULTS = {
    "V13_LM_STUDIO_BASE_URL": "http://127.0.0.1:1234/v1",
    "V13_LM_STUDIO_MODEL": APPROVED_LM_STUDIO_MODEL,
    "V13_BACKEND_PORT": "8040",
    "V13_CHILD_PORT": "8041",
    "V13_PARENT_PORT": "8042",
    "V13_DB_PATH": "data/local/studypilot_v13.db",
    "V13_TIMEZONE": "Asia/Shanghai",
    "V13_DEFAULT_SLEEP_TIME": "21:30",
    "V13_MOCK_ENABLED": "false",
    "V13_DEMO_MODE": "false",
}


class Settings(BaseModel):
    """Validated local runtime settings without credential material."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    repository_root: Path
    lm_studio_base_url: str = Field(min_length=1)
    lm_studio_model: str = Field(min_length=1)
    backend_port: int = Field(ge=1, le=65_535)
    child_port: int = Field(ge=1, le=65_535)
    parent_port: int = Field(ge=1, le=65_535)
    database_path: Path
    timezone: str = Field(min_length=1)
    default_sleep_time: time
    mock_enabled: bool
    demo_mode: bool


def load_settings(
    *,
    project_root: str | Path = PROJECT_ROOT,
    environ: Mapping[str, str] | None = None,
    env_file: str | Path | None = None,
) -> Settings:
    """Load settings from defaults, an optional dotenv file, and the environment."""
    root = Path(project_root).expanduser().resolve()
    values = dict(_DEFAULTS)
    dotenv_path = Path(env_file) if env_file is not None else root / ".env"
    if dotenv_path.is_file():
        values.update(
            {
                key: value
                for key, value in dotenv_values(dotenv_path).items()
                if key in _DEFAULTS and value is not None
            }
        )
    source = os.environ if environ is None else environ
    values.update({key: source[key] for key in _DEFAULTS if key in source})

    database_path = Path(values["V13_DB_PATH"]).expanduser()
    if not database_path.is_absolute():
        database_path = root / database_path

    return Settings(
        repository_root=root,
        lm_studio_base_url=values["V13_LM_STUDIO_BASE_URL"],
        lm_studio_model=values["V13_LM_STUDIO_MODEL"],
        backend_port=int(values["V13_BACKEND_PORT"]),
        child_port=int(values["V13_CHILD_PORT"]),
        parent_port=int(values["V13_PARENT_PORT"]),
        database_path=database_path.resolve(),
        timezone=values["V13_TIMEZONE"],
        default_sleep_time=time.fromisoformat(values["V13_DEFAULT_SLEEP_TIME"]),
        mock_enabled=_parse_bool(values["V13_MOCK_ENABLED"]),
        demo_mode=_parse_bool(values["V13_DEMO_MODE"]),
    )


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean setting: {value!r}")
