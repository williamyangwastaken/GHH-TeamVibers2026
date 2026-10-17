"""GET /health, GET /demo, POST /analyze."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends

from app.schemas import AnalysisResponse, HealthResponse
from app.services import gemini_api
from app.services.case_store import DEMO_CASE_ID, CaseStore, get_case_store

router = APIRouter()


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    # demo_mode: the UI should steer users to the sample case, either because
    # DEMO_MODE is set or because live Gemini analysis is not configured.
    demo_mode = _env_flag("DEMO_MODE") or not gemini_api.is_configured()
    return HealthResponse(status="ok", demo_mode=demo_mode)


@router.get("/demo", response_model=AnalysisResponse)
def demo(store: CaseStore = Depends(get_case_store)) -> AnalysisResponse:
    """The frozen synthetic case. Never calls Gemini."""
    analysis = store.get(DEMO_CASE_ID)
    assert analysis is not None, "demo case is pinned at startup"
    return analysis
