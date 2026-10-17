"""Deterministic normalization of Gemini's as-printed transcription."""

import json
from pathlib import Path

import pytest

from app.schemas import DocumentSummary, ExtractionQuality
from app.services.extraction import normalize_date, normalize_extraction, parse_money_to_cents
from extraction_samples import bill_model_output, eob_model_output

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[3] / "fixtures" / "synthetic_case.json").read_text(
        encoding="utf-8"
    )
)
FIXTURE_DOCS = {doc["id"]: doc for doc in FIXTURE["documents"]}


@pytest.mark.parametrize(
    "raw, cents",
    [
        ("$640.00", 64000),
        ("640", 64000),
        ("$1,234.56", 123456),
        ("$1,234,567.8", 123456780),
        ("$0.00", 0),
        ("-$180.00", -18000),
        ("$-180.00", -18000),
        ("($100.00)", -10000),
        ("100.00 CR", -10000),
        ("100.00-", -10000),
        ("+$5", 500),
        ("USD 12.50", 1250),
        ("  $ 7.05 ", 705),
        (None, None),
        ("", None),
        ("N/A", None),
        ("--", None),
        ("$12.345", None),  # sub-cent / ambiguous separator
        ("$1,23.00", None),  # bad grouping
        ("1.234,56", None),  # non-U.S. format
        ("about $50", None),
        ("$640.00 (Claim DEMO-C100)", None),
    ],
)
def test_parse_money_to_cents(raw, cents):
    assert parse_money_to_cents(raw) == cents


@pytest.mark.parametrize(
    "raw, iso",
    [
        ("10/01/2026", "2026-10-01"),
        ("1/2/2026", "2026-01-02"),  # U.S. month/day order
        ("10-01-2026", "2026-10-01"),
        ("10/01/26", "2026-10-01"),
        ("2026-10-01", "2026-10-01"),
        ("2026-10-01T00:00:00Z", "2026-10-01"),
        ("Oct 1, 2026", "2026-10-01"),
        ("October 1st, 2026", "2026-10-01"),
        ("Sept. 9, 2026", "2026-09-09"),
        ("1 Oct 2026", "2026-10-01"),
        ("02/30/2026", None),
        ("13/01/2026", None),
        ("10/01/2026 - 10/03/2026", None),
        ("Smarch 1, 2026", None),
        ("N/A", None),
        (None, None),
    ],
)
def test_normalize_date(raw, iso):
    assert normalize_date(raw) == iso


@pytest.mark.parametrize(
    "factory, kind, doc_id",
    [(bill_model_output, "bill", "doc_bill"), (eob_model_output, "eob", "doc_eob")],
)
def test_synthetic_extraction_reproduces_fixture_exactly(factory, kind, doc_id):
    expected = FIXTURE_DOCS[doc_id]
    summary = normalize_extraction(factory(), kind=kind, filename=expected["filename"], pages=1)
    assert summary.model_dump(mode="json") == expected


def test_payments_and_adjustments_are_magnitudes_but_line_credits_keep_sign():
    out = bill_model_output(
        insurance_paid="($180.00)",
        adjustments="-$100.00",
        line_items=[
            {"description": "Payment reversal", "code": None, "service_date": None,
             "quantity": None, "unit_amount": None, "line_total": "-$25.00",
             "page": 1, "source_text": None},
        ],
    )
    summary = normalize_extraction(out, kind="bill", filename="b.pdf", pages=1)
    assert (summary.insurance_paid_cents, summary.adjustments_cents) == (18000, 10000)
    assert summary.line_items[0].line_total_cents == -2500


def test_unknown_values_stay_null_not_zero():
    out = bill_model_output(total_charges=None, insurance_paid=None, adjustments="N/A")
    summary = normalize_extraction(out, kind="bill", filename="b.pdf", pages=1)
    assert summary.total_charges_cents is None
    assert summary.insurance_paid_cents is None
    assert summary.adjustments_cents is None
    assert summary.extraction_quality == ExtractionQuality.complete


def test_unreadable_amount_is_null_with_warning_and_partial():
    out = bill_model_output(amount_due="six hundred-ish")
    summary = normalize_extraction(out, kind="bill", filename="b.pdf", pages=1)
    assert summary.amount_due_cents is None
    assert summary.extraction_quality == ExtractionQuality.partial
    assert any("amount due" in w for w in summary.extraction_warnings)


def test_missing_headline_amount_is_partial():
    out = eob_model_output(patient_responsibility=None)
    summary = normalize_extraction(out, kind="eob", filename="e.pdf", pages=1)
    assert summary.extraction_quality == ExtractionQuality.partial
    assert any("patient responsibility" in w for w in summary.extraction_warnings)


def test_unreadable_document_date_is_partial():
    out = bill_model_output(service_date="10/01/2026 - 10/03/2026")
    summary = normalize_extraction(out, kind="bill", filename="b.pdf", pages=1)
    assert summary.service_date is None
    assert summary.extraction_quality == ExtractionQuality.partial


def test_document_in_wrong_slot_is_flagged():
    summary = normalize_extraction(eob_model_output(), kind="bill", filename="x.pdf", pages=1)
    assert summary.extraction_quality == ExtractionQuality.partial
    assert any("looks like an insurance EOB" in w for w in summary.extraction_warnings)


def test_non_billing_document_with_nothing_extracted_is_failed():
    out = bill_model_output(
        detected_document_type="other",
        provider_name=None, document_date=None, service_date=None, claim_number=None,
        total_charges=None, amount_due=None, insurance_paid=None, adjustments=None,
        line_items=[],
    )
    summary = normalize_extraction(out, kind="bill", filename="cat.png", pages=1)
    assert summary.extraction_quality == ExtractionQuality.failed
    assert summary.line_items == []
    assert any("does not look like a provider bill" in w for w in summary.extraction_warnings)


def test_illegible_document_is_partial():
    summary = normalize_extraction(
        bill_model_output(is_fully_legible=False), kind="bill", filename="b.pdf", pages=1
    )
    assert summary.extraction_quality == ExtractionQuality.partial


def test_model_warnings_pass_through_without_downgrading():
    out = bill_model_output(
        extraction_warnings=["  Patient address   is redacted. ", "Patient address is redacted."]
        + [f"note {i}" for i in range(20)]
    )
    summary = normalize_extraction(out, kind="bill", filename="b.pdf", pages=1)
    assert summary.extraction_quality == ExtractionQuality.complete
    assert summary.extraction_warnings[0] == "Patient address is redacted."
    assert len(summary.extraction_warnings) == 8


def test_line_items_get_sequential_ids_and_empty_rows_are_dropped():
    blank = {"description": " ", "code": None, "service_date": None, "quantity": None,
             "unit_amount": None, "line_total": None, "page": None, "source_text": None}
    items = bill_model_output().model_dump()["line_items"]
    out = bill_model_output(line_items=[blank, items[0], blank, items[1]])
    summary = normalize_extraction(out, kind="bill", filename="b.pdf", pages=1)
    assert [li.id for li in summary.line_items] == ["li_bill_1", "li_bill_2"]


def test_out_of_range_pages_are_removed_with_warning():
    items = bill_model_output().model_dump()["line_items"]
    items[0]["page"] = 3
    items[1]["page"] = 0
    summary = normalize_extraction(
        bill_model_output(line_items=items), kind="bill", filename="b.pdf", pages=2
    )
    assert [li.page for li in summary.line_items] == [None, None, 1]
    assert summary.extraction_quality == ExtractionQuality.partial


def test_line_without_legible_description_keeps_its_amount():
    item = {"description": None, "code": None, "service_date": None, "quantity": None,
            "unit_amount": None, "line_total": "$45.00", "page": 1, "source_text": None}
    summary = normalize_extraction(
        bill_model_output(line_items=[item]), kind="bill", filename="b.pdf", pages=1
    )
    assert summary.line_items[0].description == "(description not legible)"
    assert summary.line_items[0].line_total_cents == 4500


def test_eob_status_is_lowercased_and_only_kept_for_eobs():
    eob = normalize_extraction(
        eob_model_output(eob_status=" PROCESSED "), kind="eob", filename="e.pdf", pages=1
    )
    bill = normalize_extraction(
        bill_model_output(eob_status="Processed"), kind="bill", filename="b.pdf", pages=1
    )
    assert (eob.eob_status, bill.eob_status) == ("processed", None)


@pytest.mark.parametrize(
    "filename, shown",
    [
        ("C:\\Users\\someone\\Downloads\\bill.pdf", "bill.pdf"),
        ("/tmp/uploads/eob.png", "eob.png"),
        ("", "bill-upload"),
        ("x" * 300 + ".pdf", None),
    ],
)
def test_filename_is_reduced_to_a_short_basename(filename, shown):
    summary = normalize_extraction(bill_model_output(), kind="bill", filename=filename, pages=1)
    if shown is None:
        assert len(summary.filename) <= 120
    else:
        assert summary.filename == shown


def test_output_always_validates_as_document_summary():
    summary = normalize_extraction(bill_model_output(), kind="estimate", filename="g.pdf", pages=1)
    DocumentSummary.model_validate(summary.model_dump())
    assert summary.id == "doc_estimate"
    assert summary.line_items[0].id == "li_estimate_1"
