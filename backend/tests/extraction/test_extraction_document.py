"""extract_document end to end with Gemini mocked at the adapter boundary."""

import asyncio

import pytest

from app.schemas import DocumentSummary, ErrorCode, ExtractionError, ExtractionQuality
from app.services import extraction, gemini_api, prompts
from extraction_samples import (
    SYNTHETIC_BILL_LINES,
    bill_model_output,
    make_blank_pdf,
    make_png,
    make_text_pdf,
)


@pytest.fixture
def gemini(monkeypatch):
    """Replace the Gemini call; records its keyword arguments."""
    calls = []
    state = {"result": bill_model_output()}

    async def fake_generate_extraction(**kwargs):
        calls.append(kwargs)
        result = state["result"]
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(gemini_api, "generate_extraction", fake_generate_extraction)
    state["calls"] = calls
    return state


def extract(content, content_type="application/pdf", filename="sample-bill.pdf", kind="bill"):
    return asyncio.run(extraction.extract_document(content, content_type, filename, kind))


def test_returns_validated_summary_for_synthetic_bill(gemini):
    pdf = make_text_pdf(SYNTHETIC_BILL_LINES)
    summary = extract(pdf)

    assert isinstance(summary, DocumentSummary)
    assert summary.extraction_quality == ExtractionQuality.complete
    assert (summary.amount_due_cents, summary.total_charges_cents) == (64000, 92000)
    assert [li.line_total_cents for li in summary.line_items] == [52000, 20000, 20000]

    (call,) = gemini["calls"]
    assert call["content"] == pdf
    assert call["mime_type"] == "application/pdf"
    assert call["system_instruction"] == prompts.EXTRACTION_SYSTEM_INSTRUCTION
    assert "PROVIDER BILL" in call["prompt"]


def test_page_count_from_pdf_reaches_prompt_and_summary(gemini):
    summary = extract(make_blank_pdf(4))
    assert summary.pages == 4
    assert "between 1 and 4" in gemini["calls"][0]["prompt"]


def test_image_is_sent_with_detected_mime_type(gemini):
    summary = extract(make_png(), content_type="image/jpeg", filename="bill.jpg")
    assert gemini["calls"][0]["mime_type"] == "image/png"
    assert summary.pages == 1


def test_accepts_kind_as_plain_string_or_enum(gemini):
    from app.schemas import DocumentKind

    assert extract(make_blank_pdf(1), kind=DocumentKind.eob).id == "doc_eob"
    assert extract(make_blank_pdf(1), kind="estimate").kind == DocumentKind.estimate


@pytest.mark.parametrize(
    "content, content_type, code",
    [
        (b"", "application/pdf", ErrorCode.INVALID_UPLOAD),
        (b"hello", "text/plain", ErrorCode.INVALID_UPLOAD),
        (make_blank_pdf(7), "application/pdf", ErrorCode.FILE_TOO_LARGE),
        (make_blank_pdf(1, password="pw"), "application/pdf", ErrorCode.DOCUMENT_UNREADABLE),
    ],
)
def test_invalid_uploads_are_rejected_before_any_gemini_call(gemini, content, content_type, code):
    with pytest.raises(ExtractionError) as info:
        extract(content, content_type)
    assert info.value.code == code
    assert gemini["calls"] == []


def test_gemini_errors_propagate_unchanged(gemini):
    gemini["result"] = ExtractionError(
        ErrorCode.GEMINI_UNAVAILABLE, "busy", http_status=429, retryable=True
    )
    with pytest.raises(ExtractionError) as info:
        extract(make_blank_pdf(1))
    assert (info.value.code, info.value.http_status) == (ErrorCode.GEMINI_UNAVAILABLE, 429)


def test_unexpected_exceptions_become_internal_error(gemini):
    gemini["result"] = RuntimeError("SDK exploded with patient data in message")
    with pytest.raises(ExtractionError) as info:
        extract(make_blank_pdf(1))
    err = info.value
    assert (err.code, err.http_status) == (ErrorCode.INTERNAL_ERROR, 500)
    assert "patient" not in err.message


def test_no_key_configured_gives_503_not_fake_success():
    # Real adapter, no GEMINI_API_KEY: must fail honestly, never fabricate a result.
    with pytest.raises(ExtractionError) as info:
        extract(make_text_pdf(SYNTHETIC_BILL_LINES))
    assert (info.value.code, info.value.http_status) == (ErrorCode.GEMINI_UNAVAILABLE, 503)
