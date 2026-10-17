"""Live Gemini smoke tests on synthetic PDFs. Opt-in; skipped by default.

    RUN_LIVE_GEMINI=1 GEMINI_API_KEY=... GEMINI_MODEL=... python -m pytest tests/extraction -m live -v
"""

import asyncio
import os

import pytest

from app.schemas import ExtractionQuality
from app.services.extraction import extract_document
from extraction_samples import (
    PROMPT_INJECTION_LINE,
    SYNTHETIC_BILL_LINES,
    SYNTHETIC_EOB_LINES,
    make_text_pdf,
)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not (
            os.getenv("RUN_LIVE_GEMINI") == "1"
            and os.getenv("GEMINI_API_KEY")
            and os.getenv("GEMINI_MODEL")
        ),
        reason="set RUN_LIVE_GEMINI=1, GEMINI_API_KEY and GEMINI_MODEL to call Gemini",
    ),
]


def extract(lines, kind):
    pdf = make_text_pdf(lines)
    return asyncio.run(extract_document(pdf, "application/pdf", f"sample-{kind}.pdf", kind))


def test_live_bill_extraction_matches_printed_values():
    summary = extract(SYNTHETIC_BILL_LINES, "bill")
    assert summary.extraction_quality != ExtractionQuality.failed
    assert summary.amount_due_cents == 64000
    assert summary.total_charges_cents == 92000
    assert summary.claim_number == "DEMO-C100"
    assert summary.service_date == "2026-10-01"
    assert len(summary.line_items) == 3  # duplicate lab draw must not be merged


def test_live_eob_extraction_matches_printed_values():
    summary = extract(SYNTHETIC_EOB_LINES, "eob")
    assert summary.patient_responsibility_cents == 39000
    assert summary.insurance_paid_cents == 33000
    assert summary.eob_status == "finalized"


def test_live_prompt_injection_in_document_is_ignored():
    summary = extract(SYNTHETIC_BILL_LINES + ["", PROMPT_INJECTION_LINE], "bill")
    assert summary.amount_due_cents == 64000
