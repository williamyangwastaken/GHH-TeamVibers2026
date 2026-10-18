import asyncio

import httpx

from app.schemas import ErrorCode
from app.services.groq_api import (
    MAX_AUTOMATIC_RETRY_AFTER_SECONDS,
    _ExtractedEOBHeader,
    _extract_eob_summary,
    _is_daily_token_limit,
    _map_api_error,
    _retry_after_seconds,
)


def test_groq_retry_after_seconds_is_read_from_rate_limit_response():
    response = httpx.Response(429, headers={"retry-after": "3.5"})
    assert _retry_after_seconds(response) == 3.5
    assert _retry_after_seconds(httpx.Response(429)) is None


def test_long_groq_reset_is_not_retried_inside_request():
    response = httpx.Response(429, headers={"retry-after": str(MAX_AUTOMATIC_RETRY_AFTER_SECONDS + 1)})
    assert _retry_after_seconds(response) > MAX_AUTOMATIC_RETRY_AFTER_SECONDS


def test_groq_rate_limit_message_explains_eob_comparison_cannot_run_yet():
    error = _map_api_error(httpx.Response(429, json={"error": {"message": "Rate limit reached"}}))
    assert error.code == ErrorCode.MODEL_UNAVAILABLE
    assert error.http_status == 429
    assert "bill and EOB were not compared" in error.message
    assert "Usage and Limits" in error.message


def test_groq_daily_token_limit_is_reported_with_reset_hint():
    response = httpx.Response(
        429,
        json={"error": {"message": "Limit on tokens per day (TPD). Try again in 3m32.112s."}},
    )
    assert _is_daily_token_limit(response)
    error = _map_api_error(response)
    assert "daily token limit" in error.message
    assert "try again in about 4 minutes" in error.message.lower()
    assert "this document could not be analyzed" in error.message.lower()
    assert "EOB was uploaded" not in error.message


def test_eob_comparison_extracts_only_claim_fields_in_one_call(monkeypatch):
    calls = []

    async def fake_generate_json(**kwargs):
        calls.append(kwargs)
        return _ExtractedEOBHeader(
            detected_document_type="eob",
            is_fully_legible=True,
            provider_name="Sample Clinic",
            insurer_name="Sample Plan",
            document_date="2026-10-07",
            service_date="2026-10-01",
            claim_number="CLM-123",
            total_charges="$800.00",
            patient_responsibility="$300.00",
            insurance_paid="$400.00",
            adjustments="$100.00",
            eob_status="Finalized",
            extraction_warnings=[],
        )

    monkeypatch.setattr("app.services.groq_api.generate_json", fake_generate_json)
    result = asyncio.run(_extract_eob_summary(document_text="claim summary", images=[]))

    assert len(calls) == 1
    assert calls[0]["max_completion_tokens"] == 384
    assert result.claim_number == "CLM-123"
    assert result.patient_responsibility == "$300.00"
    assert result.insurance_paid == "$400.00"
    assert result.line_items == []
    assert any("service lines were not separately analyzed" in note for note in result.extraction_warnings)
