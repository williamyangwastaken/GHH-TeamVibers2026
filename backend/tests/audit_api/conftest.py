import sys
from pathlib import Path

import pytest

# Make ``import app`` work whether pytest runs from backend/ or the repo root.
BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_CONFIG_ENV_VARS = (
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "GEMINI_TIMEOUT_SECONDS",
    "MAX_FILE_SIZE_MB",
    "MAX_PDF_PAGES",
    "DEMO_MODE",
    "FRONTEND_ORIGIN",
    "CASE_TTL_MINUTES",
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """Tests never see a developer's real key, limits, or origins."""
    for name in _CONFIG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
