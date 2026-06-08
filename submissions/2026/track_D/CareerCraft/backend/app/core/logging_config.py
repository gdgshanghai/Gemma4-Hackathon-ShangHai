"""Centralized logging configuration.

A single ``dictConfig`` describes every logger we care about — root, uvicorn's
own loggers (which don't propagate), the dedicated ``careercraft.llm`` audit
channel, and noisy third-parties. Passing the same dict to
``uvicorn.run(log_config=...)`` lets uvicorn adopt our configuration instead of
us hot-patching its loggers post-hoc.

File-based logging (general app log + LLM audit dump) is disabled when
``settings.environment == "production"``; in that mode ``careercraft.llm`` is
attached to a ``NullHandler`` so no prompts/responses ever hit disk.
"""

from __future__ import annotations

import logging.config
import os
from typing import Any

from app.core.config import settings


def _file_logging_enabled() -> bool:
  return settings.environment.lower() != "production"


def build_log_config() -> dict[str, Any]:
  """Build a complete ``logging.config.dictConfig`` payload.

  Safe to call multiple times; ``dictConfig`` rebuilds handlers idempotently.
  Also suitable for ``uvicorn.run(log_config=...)``.
  """
  use_files = _file_logging_enabled()
  log_dir = os.path.abspath(settings.log_dir)
  if use_files:
    os.makedirs(os.path.join(log_dir, "llm"), exist_ok=True)

  formatters = {
      "default": {
          "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
      },
      "raw": {"format": "%(message)s"},
  }

  handlers: dict[str, dict[str, Any]] = {
      "console": {
          "class": "logging.StreamHandler",
          "formatter": "default",
      },
  }
  if use_files:
    # ``RotatingFileHandler`` rotates by size (no midnight rename race that
    # plagues ``TimedRotatingFileHandler`` on Windows under uvicorn --reload),
    # while still capping local disk usage in development.
    handlers["app_file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": os.path.join(log_dir, "app.log"),
        "maxBytes": 10 * 1024 * 1024,
        "backupCount": 5,
        "encoding": "utf-8",
        "formatter": "default",
    }
    handlers["llm_file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": os.path.join(log_dir, "llm", "llm.log"),
        "maxBytes": 20 * 1024 * 1024,
        "backupCount": 10,
        "encoding": "utf-8",
        "formatter": "raw",
    }
  else:
    handlers["llm_null"] = {"class": "logging.NullHandler"}

  app_handlers = ["console"] + (["app_file"] if use_files else [])
  llm_handlers = ["llm_file"] if use_files else ["llm_null"]

  return {
      "version": 1,
      "disable_existing_loggers": False,
      "formatters": formatters,
      "handlers": handlers,
      "loggers": {
          # uvicorn loggers don't propagate to root, so wire them explicitly.
          "uvicorn": {"handlers": app_handlers, "level": "INFO", "propagate": False},
          "uvicorn.error": {"handlers": app_handlers, "level": "INFO", "propagate": False},
          "uvicorn.access": {"handlers": app_handlers, "level": "INFO", "propagate": False},
          # Dedicated audit channel for LLM round-trips.
          "careercraft.llm": {
              "handlers": llm_handlers,
              "level": "INFO",
              "propagate": False,
          },
          # --reload's file watcher is extremely chatty at INFO.
          "watchfiles": {"level": "WARNING"},
          "watchfiles.main": {"level": "WARNING"},
      },
      "root": {"handlers": app_handlers, "level": "INFO"},
  }


def setup_logging() -> None:
  """Apply the logging configuration. Idempotent."""
  logging.config.dictConfig(build_log_config())
