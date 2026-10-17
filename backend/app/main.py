"""ClearBill AI FastAPI application.

Run locally (from backend/, single worker; the case store is in-memory):

    uvicorn app.main:app --reload --port 8000 --env-file .env
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.routes import analysis
from app.routes.errors import ApiError, error_response
from app.schemas import ErrorCode, ExtractionError
from app.services.case_store import get_case_store

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"
DEFAULT_FRONTEND_ORIGIN = "http://localhost:3000"


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_case_store()  # load and validate the demo fixture now, failing fast if broken
    yield


def allowed_origins() -> list[str]:
    raw = os.getenv("FRONTEND_ORIGIN") or DEFAULT_FRONTEND_ORIGIN
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
    if DEFAULT_FRONTEND_ORIGIN in origins:
        origins.append("http://127.0.0.1:3000")
    return origins


def create_app() -> FastAPI:
    app = FastAPI(title="ClearBill AI API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    app.include_router(analysis.router, prefix=API_PREFIX)

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return error_response(exc.code, exc.message, exc.http_status, retryable=exc.retryable)

    @app.exception_handler(ExtractionError)
    async def _extraction_error(_: Request, exc: ExtractionError):
        return error_response(exc.code, exc.message, exc.http_status, retryable=exc.retryable)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, _: RequestValidationError):
        if request.url.path.endswith("/letters"):
            return error_response(
                ErrorCode.BAD_SELECTION,
                "Select at least one finding and a letter type to draft a letter.",
                400,
            )
        return error_response(
            ErrorCode.INVALID_UPLOAD,
            "Please upload a provider bill (PDF, PNG, or JPG). The EOB and estimate are optional.",
            400,
        )

    @app.exception_handler(Exception)
    async def _unexpected_error(_: Request, exc: Exception):
        logger.error("Unhandled server error (%s)", type(exc).__name__, exc_info=exc)
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            "Something went wrong on our side. Please try again, or use the sample case.",
            500,
            retryable=True,
        )

    return app


app = create_app()
