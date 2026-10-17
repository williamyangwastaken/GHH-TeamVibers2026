"""Ephemeral in-memory store of analyses, so /letters can reuse server-held findings.

Prototype limitations (by design, see CONTRACT.md / handoff section 8):
  * single process only: run uvicorn with one worker;
  * cases expire after CASE_TTL_MINUTES (default 60) and vanish on restart;
  * only normalized analysis JSON is kept, never uploaded file bytes.
The synthetic demo case is pinned and never expires.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

from app.schemas import AnalysisResponse

DEMO_CASE_ID = "demo-mismatch"
DEMO_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "synthetic_case.json"
DEFAULT_TTL_MINUTES = 60
DEFAULT_MAX_CASES = 200


def load_demo_case(path: Path = DEMO_FIXTURE_PATH) -> AnalysisResponse:
    """Load and validate the frozen synthetic fixture. Raises if it is missing or invalid."""
    return AnalysisResponse.model_validate_json(path.read_text(encoding="utf-8"))


class CaseStore:
    def __init__(
        self,
        *,
        ttl_seconds: float = DEFAULT_TTL_MINUTES * 60,
        max_cases: int = DEFAULT_MAX_CASES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_cases = max_cases
        self._clock = clock
        self._lock = threading.Lock()
        self._cases: OrderedDict[str, tuple[float, AnalysisResponse]] = OrderedDict()
        self._pinned: dict[str, AnalysisResponse] = {}

    @staticmethod
    def new_case_id() -> str:
        """Unguessable id: a case id is the only thing guarding its findings."""
        return f"case-{secrets.token_urlsafe(12)}"

    def put(self, analysis: AnalysisResponse, *, pinned: bool = False) -> None:
        with self._lock:
            if pinned:
                self._pinned[analysis.case_id] = analysis
                return
            now = self._clock()
            self._purge_expired(now)
            self._cases.pop(analysis.case_id, None)
            self._cases[analysis.case_id] = (now + self._ttl, analysis)
            while len(self._cases) > self._max_cases:
                self._cases.popitem(last=False)  # evict the oldest

    def get(self, case_id: str) -> AnalysisResponse | None:
        with self._lock:
            if case_id in self._pinned:
                return self._pinned[case_id]
            entry = self._cases.get(case_id)
            if entry is None:
                return None
            expires_at, analysis = entry
            if self._clock() >= expires_at:
                del self._cases[case_id]
                return None
            return analysis

    def __len__(self) -> int:
        with self._lock:
            self._purge_expired(self._clock())
            return len(self._cases) + len(self._pinned)

    def _purge_expired(self, now: float) -> None:
        expired = [cid for cid, (expires_at, _) in self._cases.items() if now >= expires_at]
        for cid in expired:
            del self._cases[cid]


_store: CaseStore | None = None
_store_lock = threading.Lock()


def _ttl_seconds_from_env() -> float:
    try:
        minutes = float(os.getenv("CASE_TTL_MINUTES") or DEFAULT_TTL_MINUTES)
    except ValueError:
        minutes = DEFAULT_TTL_MINUTES
    return (minutes if minutes > 0 else DEFAULT_TTL_MINUTES) * 60


def get_case_store() -> CaseStore:
    """Process-wide store with the demo case preloaded (also a FastAPI dependency)."""
    global _store
    with _store_lock:
        if _store is None:
            store = CaseStore(ttl_seconds=_ttl_seconds_from_env())
            store.put(load_demo_case(), pinned=True)
            _store = store
        return _store
