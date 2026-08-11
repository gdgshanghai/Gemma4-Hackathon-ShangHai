"""Project-identifying entry points used by the Windows launcher."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: studypilot_service.py {migrate|api}")
    if sys.argv[1] == "migrate":
        from backend.config import load_settings
        from backend.storage.database import run_migrations

        settings = load_settings()
        run_migrations(settings.database_path)
        print(f"Database migrations complete: {settings.database_path}")
        return 0
    if sys.argv[1] == "api":
        from backend.api.run import run_api

        run_api()
        return 0
    raise SystemExit(f"unknown service action: {sys.argv[1]}")


if __name__ == "__main__":
    raise SystemExit(main())
