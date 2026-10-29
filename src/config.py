from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

APP_TITLE = "PatchPilot AI"
APP_DESCRIPTION = "A safe debugging and repair workflow for Python defects."

NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")
NEBIUS_BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.nebius.com/v1")
NEBIUS_MODEL = os.getenv("NEBIUS_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")
USE_MOCK_PROVIDER = os.getenv("USE_MOCK_PROVIDER", "true").lower() in {"1", "true", "yes", "on"}
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "2"))
