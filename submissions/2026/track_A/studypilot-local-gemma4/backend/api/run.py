"""Loopback-only production entry point for the local API."""

from __future__ import annotations

import uvicorn

from backend.api.app import create_app
from backend.config import Settings, load_settings


def run_api(settings: Settings | None = None) -> None:
    runtime_settings = settings or load_settings()
    uvicorn.run(
        create_app(runtime_settings),
        host="127.0.0.1",
        port=runtime_settings.backend_port,
        reload=False,
    )


if __name__ == "__main__":
    run_api()
