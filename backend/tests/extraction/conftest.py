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
)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live: calls the real Gemini API (opt-in via RUN_LIVE_GEMINI=1)"
    )


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch, request):
    """Unit tests never see a developer's real key or limits."""
    if request.node.get_closest_marker("live"):
        return
    for name in _CONFIG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
