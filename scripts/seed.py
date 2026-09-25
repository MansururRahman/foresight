"""Convenience wrapper: seed the demo workspace.

Preferred (inside Docker Compose):
    docker compose run --rm api python -m app.seed

Natively (Postgres, auth and the api venv available):
    cd services/api && AUTH_URL=http://localhost:8001 uv run python -m app.seed
"""

import os
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    api_dir = Path(__file__).resolve().parents[1] / "services" / "api"
    env = {**os.environ, "AUTH_URL": os.environ.get("AUTH_URL", "http://localhost:8001")}
    sys.exit(subprocess.call(["uv", "run", "python", "-m", "app.seed"], cwd=api_dir, env=env))
