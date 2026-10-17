"""Gemini adapter: request shape, retries, and error mapping (no network)."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai import types

from app.schemas import ErrorCode, ExtractedDocument, ExtractionError
from app.services import gemini_api
from extraction_samples import bill_model_output


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    async def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return await outcome()
        return outcome


@pytest.fixture
def fake(monkeypatch):
    """Configure a key/model and route the SDK client to scripted outcomes."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    monkeypatch.setattr(gemini_api, "RETRY_BASE_DELAY_SECONDS", 0)
    models = FakeModels([])
    monkeypatch.setattr(gemini_api, "get_client", lambda: SimpleNamespace(aio=SimpleNamespace(models=models)))
    return models


def run(**overrides):
    kwargs = {
        "content": b"%PDF-1.4 fake",
        "mime_type": "application/pdf",
        "system_instruction": "SYSTEM",
        "prompt": "PROMPT",
    }
    kwargs.update(overrides)
    return asyncio.run(gemini_api.generate_extraction(**kwargs))


def run_error(**overrides) -> ExtractionError:
    with pytest.raises(ExtractionError) as info:
        run(**overrides)
    return info.value


def ok(parsed=None, text=None):
    return SimpleNamespace(parsed=parsed, text=text, candidates=[])


def api_error(cls, code, status, message="error"):
    return cls(code, {"error": {"code": code, "status": status, "message": message}})


def test_sends_bytes_with_structured_output_config(fake):
    expected = bill_model_output()
    fake.outcomes = [ok(parsed=expected)]
    assert run(content=b"PDFBYTES", mime_type="application/pdf") is expected

    (call,) = fake.calls
    assert call["model"] == "test-model"
    part, prompt = call["contents"]
    assert isinstance(part, types.Part)
    assert (part.inline_data.data, part.inline_data.mime_type) == (b"PDFBYTES", "application/pdf")
    assert prompt == "PROMPT"
    config = call["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is ExtractedDocument
    assert config.system_instruction == "SYSTEM"
    assert config.temperature == 0


def test_falls_back_to_validating_response_text(fake):
    fake.outcomes = [ok(text=bill_model_output().model_dump_json())]
    assert run() == bill_model_output()


def test_real_sdk_response_object_is_parsed(fake):
    response = types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(
            role="model", parts=[types.Part(text=bill_model_output().model_dump_json())]
        ))]
    )
    fake.outcomes = [response]
    assert run().amount_due == "$640.00"


@pytest.mark.parametrize("text", [None, "", "not json", '{"provider_name": "only one field"}'])
def test_unusable_model_output_is_502_extraction_failed(fake, text):
    fake.outcomes = [ok(text=text)]
    err = run_error()
    assert (err.code, err.http_status, err.retryable) == (ErrorCode.EXTRACTION_FAILED, 502, True)
    assert len(fake.calls) == 1


def test_missing_configuration_is_503_without_calling(monkeypatch, fake):
    monkeypatch.delenv("GEMINI_API_KEY")
    err = run_error()
    assert (err.code, err.http_status, err.retryable) == (ErrorCode.GEMINI_UNAVAILABLE, 503, False)
    assert fake.calls == []


def test_transient_errors_are_retried_then_succeed(fake):
    fake.outcomes = [
        api_error(genai_errors.ClientError, 429, "RESOURCE_EXHAUSTED"),
        api_error(genai_errors.ServerError, 503, "UNAVAILABLE"),
        ok(parsed=bill_model_output()),
    ]
    assert run().claim_number == "DEMO-C100"
    assert len(fake.calls) == 3


def test_persistent_rate_limit_is_429_after_two_retries(fake):
    fake.outcomes = [api_error(genai_errors.ClientError, 429, "RESOURCE_EXHAUSTED")] * 5
    err = run_error()
    assert (err.code, err.http_status, err.retryable) == (ErrorCode.GEMINI_UNAVAILABLE, 429, True)
    assert len(fake.calls) == 3


def test_persistent_server_error_is_503(fake):
    fake.outcomes = [api_error(genai_errors.ServerError, 500, "INTERNAL")] * 5
    err = run_error()
    assert (err.code, err.http_status, err.retryable) == (ErrorCode.GEMINI_UNAVAILABLE, 503, True)
    assert len(fake.calls) == 3


@pytest.mark.parametrize(
    "exc",
    [TimeoutError(), httpx.ConnectError("boom"), httpx.ReadTimeout("slow")],
    ids=["timeout", "connect", "read-timeout"],
)
def test_network_failures_are_retried_then_503(fake, exc):
    fake.outcomes = [exc] * 5
    err = run_error()
    assert (err.code, err.http_status, err.retryable) == (ErrorCode.GEMINI_UNAVAILABLE, 503, True)
    assert len(fake.calls) == 3


def test_slow_call_hits_hard_timeout(monkeypatch, fake):
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "0.01")

    async def hang():
        await asyncio.sleep(5)

    fake.outcomes = [hang] * 3
    assert run_error().code == ErrorCode.GEMINI_UNAVAILABLE
    assert len(fake.calls) == 3


def test_bad_request_is_not_retried(fake):
    fake.outcomes = [api_error(genai_errors.ClientError, 400, "INVALID_ARGUMENT", "Unable to process input")]
    err = run_error()
    assert (err.code, err.http_status, err.retryable) == (ErrorCode.EXTRACTION_FAILED, 502, False)
    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    "code, status, message",
    [
        (400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key."),
        (403, "PERMISSION_DENIED", "denied"),
        (404, "NOT_FOUND", "models/test-model is not found"),
    ],
)
def test_configuration_errors_are_503_not_retryable(fake, code, status, message):
    fake.outcomes = [api_error(genai_errors.ClientError, code, status, message)]
    err = run_error()
    assert (err.code, err.http_status, err.retryable) == (ErrorCode.GEMINI_UNAVAILABLE, 503, False)
    assert "API key" not in err.message
    assert len(fake.calls) == 1


def test_extracted_document_schema_converts_for_gemini_developer_api():
    """The SDK accepts ExtractedDocument as response_schema (no network)."""
    transformers = pytest.importorskip("google.genai._transformers")
    from google import genai

    client = genai.Client(api_key="offline-check")
    schema = transformers.t_schema(client._api_client, ExtractedDocument)
    props = schema.properties
    assert set(props) == set(ExtractedDocument.model_fields)
    assert props["amount_due"].nullable is True
    assert props["detected_document_type"].enum == ["bill", "eob", "estimate", "other"]
    assert props["line_items"].items.properties["line_total"].nullable is True
