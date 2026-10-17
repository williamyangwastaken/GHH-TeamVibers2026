"""Async adapter over the official ``google-genai`` SDK for structured extraction.

Everything provider-specific lives here: client setup, request config, bounded
retries, and translating SDK failures into user-safe ``ExtractionError``s.

Configuration (read at call time, server-side only):
  GEMINI_API_KEY          required for live extraction
  GEMINI_MODEL            required; a model verified for PDF/image input + JSON schema output
  GEMINI_TIMEOUT_SECONDS  optional per-attempt timeout (default 90)

Privacy: nothing here logs document bytes, prompts, model output, or the key.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from app.schemas import ErrorCode, ExtractedDocument, ExtractionError

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_BASE_DELAY_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 90.0
_TRANSIENT_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})

_client: genai.Client | None = None
_client_api_key: str | None = None


def _api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip()


def _model_name() -> str:
    return os.getenv("GEMINI_MODEL", "").strip()


def is_configured() -> bool:
    """True when a key and model are set, i.e. live Gemini calls can be attempted."""
    return bool(_api_key() and _model_name())


def get_client() -> genai.Client:
    """Shared SDK client, rebuilt only if the configured key changes."""
    global _client, _client_api_key
    api_key = _api_key()
    if _client is None or _client_api_key != api_key:
        _client = genai.Client(api_key=api_key)
        _client_api_key = api_key
    return _client


def _timeout_seconds() -> float:
    try:
        value = float(os.getenv("GEMINI_TIMEOUT_SECONDS") or DEFAULT_TIMEOUT_SECONDS)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_TIMEOUT_SECONDS


def _unavailable(*, retryable: bool) -> ExtractionError:
    return ExtractionError(
        ErrorCode.GEMINI_UNAVAILABLE,
        "Live document analysis is temporarily unavailable. "
        "Please try again later, or use the sample case.",
        http_status=503,
        retryable=retryable,
    )


async def _backoff(attempt: int) -> None:
    await asyncio.sleep(RETRY_BASE_DELAY_SECONDS * (2**attempt))


async def generate_extraction(
    *,
    content: bytes,
    mime_type: str,
    system_instruction: str,
    prompt: str,
) -> ExtractedDocument:
    """Send one document to Gemini and return its schema-validated extraction.

    Retries transient failures (timeouts, 429, 5xx) at most ``MAX_RETRIES`` times.
    Raises ``ExtractionError`` for every failure it can classify.
    """
    if not is_configured():
        logger.warning("Gemini extraction requested but GEMINI_API_KEY or GEMINI_MODEL is unset")
        raise _unavailable(retryable=False)

    client = get_client()
    model = _model_name()
    contents = [types.Part.from_bytes(data=content, mime_type=mime_type), prompt]
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=ExtractedDocument,
        temperature=0,
    )
    timeout = _timeout_seconds()

    for attempt in range(MAX_RETRIES + 1):
        can_retry = attempt < MAX_RETRIES
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(model=model, contents=contents, config=config),
                timeout=timeout,
            )
        except genai_errors.APIError as exc:
            if exc.code in _TRANSIENT_STATUS_CODES and can_retry:
                logger.info("Gemini returned HTTP %s; retrying (attempt %d)", exc.code, attempt + 1)
                await _backoff(attempt)
                continue
            raise _map_api_error(exc) from exc
        except (TimeoutError, httpx.TransportError) as exc:
            if can_retry:
                logger.info("Gemini call failed (%s); retrying (attempt %d)", type(exc).__name__, attempt + 1)
                await _backoff(attempt)
                continue
            logger.warning("Gemini call failed after retries (%s)", type(exc).__name__)
            raise _unavailable(retryable=True) from exc
        return parse_response(response)

    raise AssertionError("unreachable")  # pragma: no cover


def _map_api_error(exc: genai_errors.APIError) -> ExtractionError:
    code = exc.code or 0
    logger.warning("Gemini API error: HTTP %s %s", code, exc.status)

    if code == 429:
        return ExtractionError(
            ErrorCode.GEMINI_UNAVAILABLE,
            "The document analysis service is busy right now (rate limit reached). "
            "Please wait a minute and try again, or use the sample case.",
            http_status=429,
            retryable=True,
        )
    # Bad/missing key, no model access, or unknown model: a server config problem.
    if code in (401, 403, 404) or _is_api_key_error(exc):
        return _unavailable(retryable=False)
    if code >= 500 or code in _TRANSIENT_STATUS_CODES:
        return _unavailable(retryable=True)
    # Any other 4xx: the model rejected this particular request/document.
    return ExtractionError(
        ErrorCode.EXTRACTION_FAILED,
        "This document could not be analyzed. Make sure it is a clear PDF, PNG, "
        "or JPG of a bill, EOB, or estimate.",
        http_status=502,
        retryable=False,
    )


def _is_api_key_error(exc: genai_errors.APIError) -> bool:
    # The Gemini API reports an invalid key as HTTP 400 INVALID_ARGUMENT.
    text = f"{exc.message or ''} {exc.details or ''}".lower()
    return "api key" in text or "api_key" in text


def parse_response(response: Any) -> ExtractedDocument:
    """Return the structured extraction, or raise EXTRACTION_FAILED if it is unusable."""
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, ExtractedDocument):
        return parsed

    try:
        text = response.text
    except Exception:  # noqa: BLE001 - SDK accessor; treat any failure as "no text"
        text = None
    if text:
        try:
            return ExtractedDocument.model_validate_json(text)
        except ValidationError:
            pass

    logger.warning(
        "Gemini returned no valid structured output (finish_reason=%s)", _finish_reason(response)
    )
    raise ExtractionError(
        ErrorCode.EXTRACTION_FAILED,
        "The AI model returned an incomplete result for this document. "
        "Please try again, or use the sample case.",
        http_status=502,
        retryable=True,
    )


def _finish_reason(response: Any) -> str | None:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None
    reason = getattr(candidates[0], "finish_reason", None)
    return str(reason) if reason is not None else None
