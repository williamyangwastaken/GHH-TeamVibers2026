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


# --- multi-key pool, failover, round-robin -------------------------------------

import itertools
import time

import pytest

from app.services import groq_api


@pytest.fixture
def clean_keys(monkeypatch):
    for name in list(__import__("os").environ):
        if name.startswith("GROQ_API_KEY"):
            monkeypatch.delenv(name)
    monkeypatch.setattr(groq_api, "_key_cursor", itertools.count())
    return monkeypatch


def test_key_pool_loads_all_formats_deduplicated(clean_keys):
    clean_keys.setenv("GROQ_API_KEY", "gsk_aaa111")
    clean_keys.setenv("GROQ_API_KEY_1", "gsk_aaa111")  # duplicate of the primary
    clean_keys.setenv("GROQ_API_KEY_2", "gsk_bbb222")
    clean_keys.setenv("GROQ_API_KEYS", " gsk_ccc333, ,gsk_bbb222,")
    assert groq_api._api_keys() == ["gsk_aaa111", "gsk_bbb222", "gsk_ccc333"]
    assert groq_api._mask_key("gsk_aaa111") == "gsk_...111"


def test_blank_keys_are_not_configured(clean_keys):
    clean_keys.setenv("GROQ_API_KEY", "  ")
    clean_keys.setenv("GROQ_API_KEY_2", "")
    assert groq_api._api_keys() == []
    assert not groq_api.is_configured()


class _FakeClient:
    """Stands in for httpx.AsyncClient; records the bearer key of each request."""

    calls: list[str] = []
    plan: dict[str, int] = {}

    def __init__(self, **_):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def post(self, url, headers, json):
        key = headers["Authorization"].removeprefix("Bearer ")
        type(self).calls.append(key)
        status = type(self).plan.get(key, 200)
        if status == 200:
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
        return httpx.Response(status, headers={"retry-after": "55"}, json={"error": {"message": "rate limited"}})


@pytest.fixture
def fake_http(clean_keys):
    _FakeClient.calls = []
    _FakeClient.plan = {}
    clean_keys.setattr(groq_api.httpx, "AsyncClient", _FakeClient)
    clean_keys.setenv("GROQ_API_KEY", "gsk_key1")
    clean_keys.setenv("GROQ_API_KEY_2", "gsk_key2")
    return _FakeClient


def _chat():
    return asyncio.run(groq_api._chat(system_instruction="s", user_text="u"))


def test_429_switches_to_key_two_with_zero_delay(fake_http):
    fake_http.plan = {"gsk_key1": 429}  # cursor starts at key 1
    started = time.monotonic()
    assert _chat() == "ok"
    assert fake_http.calls == ["gsk_key1", "gsk_key2"]
    assert time.monotonic() - started < 1.0  # retry-after: 55 was NOT honoured


def test_all_keys_rate_limited_raises_without_sleeping(fake_http):
    fake_http.plan = {"gsk_key1": 429, "gsk_key2": 503}
    started = time.monotonic()
    with pytest.raises(groq_api.ExtractionError):
        _chat()
    assert sorted(fake_http.calls) == ["gsk_key1", "gsk_key2"]
    assert time.monotonic() - started < 1.0


def test_round_robin_spreads_initial_calls_across_keys(fake_http):
    for _ in range(4):
        _chat()
    assert fake_http.calls == ["gsk_key1", "gsk_key2", "gsk_key1", "gsk_key2"]
