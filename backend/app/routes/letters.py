"""POST /letters: draft a letter from findings held server-side for a case."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routes.errors import ApiError
from app.schemas import ErrorCode, LetterRequest, LetterResponse
from app.services import letters
from app.services.case_store import CaseStore, get_case_store

router = APIRouter()


@router.post("/letters", response_model=LetterResponse)
async def create_letter(
    request: LetterRequest, store: CaseStore = Depends(get_case_store)
) -> LetterResponse:
    analysis = store.get(request.case_id)
    if analysis is None:
        raise ApiError(
            ErrorCode.CASE_NOT_FOUND,
            "This analysis has expired or does not exist. Please run the analysis again or open the sample case.",
            http_status=404,
        )
    try:
        return await letters.draft_letter(analysis, request.finding_ids, request.intent)
    except letters.LetterSelectionError as exc:
        raise ApiError(ErrorCode.BAD_SELECTION, str(exc), http_status=400) from exc
