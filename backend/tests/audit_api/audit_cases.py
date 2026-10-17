"""Synthetic DocumentSummary builders for audit/API tests. No real patient data."""

from __future__ import annotations

import io

from pypdf import PdfWriter

from app.schemas import DocumentSummary, LineItem
from app.services.case_store import load_demo_case


def line(item_id, description, total, *, code=None, date="2026-10-01", qty=1, page=1, unit=None):
    return LineItem(
        id=item_id,
        description=description,
        code=code,
        service_date=date,
        quantity=qty,
        unit_amount_cents=total if unit is None else unit,
        line_total_cents=total,
        page=page,
        source_text=None,
    )


def clean_bill(**overrides) -> DocumentSummary:
    """Internally consistent bill whose amount due matches clean_eob()."""
    data = dict(
        id="doc_bill",
        kind="bill",
        filename="bill.pdf",
        pages=1,
        extraction_quality="complete",
        provider_name="Sample Valley Clinic",
        document_date="2026-10-08",
        service_date="2026-10-01",
        claim_number="DEMO-C200",
        total_charges_cents=72000,
        amount_due_cents=39000,
        insurance_paid_cents=33000,
        line_items=[
            line("li_bill_1", "Outpatient Visit - Level 4", 52000, code="99214"),
            line("li_bill_2", "Venipuncture", 20000, code="36415"),
        ],
        extraction_warnings=[],
    )
    data.update(overrides)
    return DocumentSummary.model_validate(data)


def clean_eob(**overrides) -> DocumentSummary:
    data = dict(
        id="doc_eob",
        kind="eob",
        filename="eob.pdf",
        pages=1,
        extraction_quality="complete",
        provider_name="Sample Valley Clinic",
        insurer_name="Fictional Mutual Health",
        document_date="2026-10-07",
        service_date="2026-10-01",
        claim_number="DEMO-C200",
        total_charges_cents=72000,
        patient_responsibility_cents=39000,
        insurance_paid_cents=33000,
        eob_status="finalized",
        line_items=[
            line("li_eob_1", "Office Visit", 52000, code="99214"),
            line("li_eob_2", "Venipuncture", 20000, code="36415"),
        ],
        extraction_warnings=[],
    )
    data.update(overrides)
    return DocumentSummary.model_validate(data)


def estimate_doc(**overrides) -> DocumentSummary:
    data = dict(
        id="doc_estimate", kind="estimate", filename="gfe.pdf", pages=1,
        extraction_quality="complete", expected_total_cents=50000,
        line_items=[], extraction_warnings=[],
    )
    data.update(overrides)
    return DocumentSummary.model_validate(data)


def demo_documents() -> tuple[DocumentSummary, DocumentSummary]:
    bill, eob = load_demo_case().documents
    return bill, eob


def blank_pdf(pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
