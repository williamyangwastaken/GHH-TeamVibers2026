"""POST /analyze end to end, with Gemini mocked at the extraction boundary."""

import pytest

from app.schemas import ErrorCode, ExtractedDocument, ExtractionError
from app.services import extraction, gemini_api
from audit_cases import blank_pdf, demo_documents

PDF = "application/pdf"


@pytest.fixture
def fake_extract(monkeypatch):
    """extract_document returns the demo fixture's document for each kind."""
    bill, eob = demo_documents()
    by_kind = {"bill": bill, "eob": eob}
    calls = []

    async def fake(content, content_type, filename, kind):
        calls.append(str(kind))
        return by_kind[str(kind)].model_copy(update={"filename": filename})

    monkeypatch.setattr(extraction, "extract_document", fake)
    return calls


def files(**uploads):
    return {name: (f"{name}.pdf", content, ctype) for name, (content, ctype) in uploads.items()}


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message", "retryable"}
    assert body["error"]["code"] == code
    return body["error"]


def test_bill_and_eob_produce_findings_and_a_stored_case(client, fake_extract):
    response = client.post("/api/v1/analyze", files=files(bill=(blank_pdf(), PDF), eob=(blank_pdf(), PDF)))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["is_demo"] is False
    assert data["case_id"].startswith("case-")
    assert [d["filename"] for d in data["documents"]] == ["bill.pdf", "eob.pdf"]
    assert [f["id"] for f in data["findings"]] == ["f-eob-1", "f-dup-1"]
    assert "Do not upload real medical records" in data["safety_disclaimer"]
    assert sorted(fake_extract) == ["bill", "eob"]

    letter = client.post(
        "/api/v1/letters",
        json={"case_id": data["case_id"], "finding_ids": ["f-eob-1"], "intent": "clarification"},
    )
    assert letter.status_code == 200
    assert "$640.00" in letter.json()["body"]


def test_bill_only_reports_missing_insurance_comparison(client, fake_extract):
    data = client.post("/api/v1/analyze", files=files(bill=(blank_pdf(), PDF))).json()
    assert [f["rule_id"] for f in data["findings"]] == [
        "R3_POSSIBLE_DUPLICATE_LINE_ITEM",
        "R5_MISSING_INFORMATION",
    ]
    assert fake_extract == ["bill"]


def test_empty_optional_field_is_ignored(client, fake_extract):
    response = client.post(
        "/api/v1/analyze",
        files={"bill": ("bill.pdf", blank_pdf(), PDF), "eob": ("", b"", "application/octet-stream")},
    )
    assert response.status_code == 200, response.text
    assert fake_extract == ["bill"]


def test_missing_bill_is_400(client, fake_extract):
    error = assert_error(client.post("/api/v1/analyze", files=files(eob=(blank_pdf(), PDF))), 400, "INVALID_UPLOAD")
    assert "bill" in error["message"]
    assert fake_extract == []


def test_bad_optional_file_is_rejected_before_any_extraction(client, fake_extract):
    response = client.post(
        "/api/v1/analyze", files=files(bill=(blank_pdf(), PDF), eob=(b"hello", "text/plain"))
    )
    error = assert_error(response, 415, "INVALID_UPLOAD")
    assert error["message"].startswith("EOB: ")
    assert fake_extract == []


def test_oversized_bill_is_413(client, fake_extract, monkeypatch):
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "1")
    big = b"%PDF-1.7\n" + b"0" * (1024 * 1024)
    error = assert_error(client.post("/api/v1/analyze", files=files(bill=(big, PDF))), 413, "FILE_TOO_LARGE")
    assert error["message"].startswith("Provider bill: ")


def test_too_many_pages_is_413(client, fake_extract):
    assert_error(client.post("/api/v1/analyze", files=files(bill=(blank_pdf(7), PDF))), 413, "FILE_TOO_LARGE")


def test_without_gemini_upload_fails_honestly(client):
    # Real extraction path, no key: an honest 503, never a fabricated analysis.
    error = assert_error(client.post("/api/v1/analyze", files=files(bill=(blank_pdf(), PDF))), 503, "GEMINI_UNAVAILABLE")
    assert "sample case" in error["message"]


def test_bill_error_is_reported_first(client, monkeypatch):
    async def fail(content, content_type, filename, kind):
        raise ExtractionError(ErrorCode.EXTRACTION_FAILED, f"{kind} failed", http_status=502, retryable=True)

    monkeypatch.setattr(extraction, "extract_document", fail)
    response = client.post("/api/v1/analyze", files=files(bill=(blank_pdf(), PDF), eob=(blank_pdf(), PDF)))
    error = assert_error(response, 502, "EXTRACTION_FAILED")
    assert error == {"code": "EXTRACTION_FAILED", "message": "Provider bill: bill failed", "retryable": True}


def test_unexpected_errors_are_500_without_internals(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app

    async def explode(*args):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(extraction, "extract_document", explode)
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        response = client.post("/api/v1/analyze", files=files(bill=(blank_pdf(), PDF)))
    error = assert_error(response, 500, "INTERNAL_ERROR")
    assert "secret" not in response.text and error["retryable"] is True


def test_full_pipeline_with_model_output_mocked(client, monkeypatch):
    """Real validation + normalization + audit; only the Gemini call is faked."""
    printed = {
        "detected_document_type": "bill", "is_fully_legible": True,
        "provider_name": "Sample Valley Clinic", "insurer_name": None,
        "document_date": "10/08/2026", "service_date": "10/01/2026", "claim_number": "DEMO-C300",
        "total_charges": "$300.00", "amount_due": "$300.00", "patient_responsibility": None,
        "insurance_paid": None, "adjustments": None, "expected_total": None, "eob_status": None,
        "line_items": [
            {"description": "Office visit", "code": "99213", "service_date": "10/01/2026", "quantity": 1,
             "unit_amount": "$250.00", "line_total": "$250.00", "page": 1, "source_text": None},
        ],
        "extraction_warnings": [],
    }

    async def fake_generate_extraction(**kwargs):
        return ExtractedDocument.model_validate(printed)

    monkeypatch.setattr(gemini_api, "generate_extraction", fake_generate_extraction)
    data = client.post("/api/v1/analyze", files=files(bill=(blank_pdf(), PDF))).json()
    (math,) = [f for f in data["findings"] if f["rule_id"] == "R1_BILL_TOTAL_ARITHMETIC"]
    assert (math["status"], math["difference_cents"]) == ("verified_inconsistency", 5000)
    assert data["documents"][0]["amount_due_cents"] == 30000
