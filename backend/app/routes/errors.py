"""Contract-shaped API errors: {"error": {"code", "message", "retryable"}}."""

from __future__ import annotations

from fastapi.responses import JSONResponse

from app.schemas import ErrorCode, ErrorDetail, ErrorResponse


class ApiError(Exception):
    """Raise from a route to return an ErrorResponse. ``message`` is shown to users."""

    def __init__(
        self, code: ErrorCode, message: str, *, http_status: int, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable


def error_response(
    code: ErrorCode, message: str, http_status: int, *, retryable: bool = False
) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, retryable=retryable))
    return JSONResponse(body.model_dump(mode="json"), status_code=http_status)
