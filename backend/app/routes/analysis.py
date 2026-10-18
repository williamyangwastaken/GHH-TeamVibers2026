"""GET /health, GET /demo, POST /analyze."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, Depends, File, UploadFile

from app.schemas import AnalysisResponse, DocumentKind, DocumentSummary, ExtractionError, HealthResponse
from app.services import audit, extraction, groq_api, price_benchmark
from app.services.case_store import DEMO_CASE_ID, CaseStore, get_case_store

router = APIRouter()

_UPLOAD_LABELS = {
    DocumentKind.bill: "Provider bill",
    DocumentKind.eob: "EOB",
    DocumentKind.estimate: "Good Faith Estimate",
}


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    # demo_mode: the UI should steer users to the sample case, either because
    # DEMO_MODE is set or because live Groq analysis is not configured.
    demo_mode = _env_flag("DEMO_MODE") or not groq_api.is_configured()
    return HealthResponse(status="ok", demo_mode=demo_mode)


@router.get("/demo", response_model=AnalysisResponse)
def demo(store: CaseStore = Depends(get_case_store)) -> AnalysisResponse:
    """The frozen synthetic case. Never calls an external model."""
    analysis = store.get(DEMO_CASE_ID)
    assert analysis is not None, "demo case is pinned at startup"
    return analysis


@contextmanager
def _labelled(kind: DocumentKind) -> Iterator[None]:
    """Prefix extraction errors with which upload failed, e.g. "EOB: ..."."""
    try:
        yield
    except ExtractionError as exc:
        raise ExtractionError(
            exc.code,
            f"{_UPLOAD_LABELS[kind]}: {exc.message}",
            http_status=exc.http_status,
            retryable=exc.retryable,
        ) from exc


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    bill: UploadFile = File(...),
    eob: UploadFile | None = File(None),
    estimate: UploadFile | None = File(None),
    store: CaseStore = Depends(get_case_store),
) -> AnalysisResponse:
    """Groq extraction of each upload, then the deterministic audit.

    Every file is validated before any model call is made, so one bad optional
    upload never costs a model request. Uploaded bytes are not stored.
    """
    read_limit = extraction.max_file_size_bytes() + 1  # one extra byte detects oversize
    uploads: list[tuple[DocumentKind, str, str, bytes]] = []
    for kind, upload in ((DocumentKind.bill, bill), (DocumentKind.eob, eob), (DocumentKind.estimate, estimate)):
        if upload is None:
            continue
        content = await upload.read(read_limit)
        if kind != DocumentKind.bill and not content and not upload.filename:
            continue  # an empty optional form field
        with _labelled(kind):
            extraction.validate_upload(content, upload.content_type)
        uploads.append((kind, upload.filename or "", upload.content_type or "", content))

    async def extract(kind: DocumentKind, filename: str, content_type: str, content: bytes) -> DocumentSummary:
        with _labelled(kind):
            return await extraction.extract_document(content, content_type, filename, kind)

    # Serialize provider calls. Concurrent bill + EOB vision/extraction requests
    # can burst through Groq's per-minute token/request limits on small plans.
    extracted_by_kind: dict[DocumentKind, DocumentSummary] = {}
    optional_failures: list[str] = []
    # When both optional documents are present, prioritize the GFE comparison
    # before the EOB. An EOB rate-limit failure must not prevent this requested check.
    extraction_order = {DocumentKind.bill: 0, DocumentKind.estimate: 1, DocumentKind.eob: 2}
    for upload in sorted(uploads, key=lambda item: extraction_order[item[0]]):
        try:
            doc = await extract(*upload)
            extracted_by_kind[doc.kind] = doc
        except ExtractionError as exc:
            kind = upload[0]
            if kind == DocumentKind.bill:
                raise
            # An optional EOB/GFE failure must not discard usable bill/GFE
            # results. The audit will report which comparison is unavailable.
            optional_failures.append(exc.message)

    # Keep API document ordering aligned with the user's bill, EOB, estimate fields.
    documents = [extracted_by_kind[kind] for kind, _, _, _ in uploads if kind in extracted_by_kind]
    by_kind = {doc.kind: doc for doc in documents}
    audit_result = audit.run_audit(
        by_kind[DocumentKind.bill], by_kind.get(DocumentKind.eob), by_kind.get(DocumentKind.estimate)
    )
    audit_result.limitations.extend(optional_failures)
    bill_doc = by_kind[DocumentKind.bill]
    codes = list(dict.fromkeys(
        item.code.upper() for item in bill_doc.line_items
        if item.code and item.quantity == 1 and item.line_total_cents and item.line_total_cents > 0
    ))[:10]
    # CMS receives procedure codes only; the uploaded document and its identifiers
    # remain local to this service. If CMS is unavailable, arithmetic/EOB checks continue.
    if codes:
        results = await asyncio.gather(*(asyncio.to_thread(price_benchmark.national_average_charge, code) for code in codes))
        averages = {code: result for code, result in zip(codes, results) if result is not None}
        audit_result.findings.extend(audit.price_benchmark_findings(bill_doc, averages))
        if len(averages) < len(codes):
            audit_result.limitations.append(
                "A U.S. price reference was unavailable for some coded services. Available references use CMS Original Medicare Part B submitted charges, not all-payer prices."
            )
    else:
        audit_result.limitations.append(
            "No single-unit HCPCS/CPT line codes were available for a CMS national price comparison."
        )
    analysis = AnalysisResponse(
        case_id=store.new_case_id(),
        is_demo=False,
        documents=documents,
        findings=audit_result.findings,
        limitations=audit_result.limitations,
        safety_disclaimer=audit.SAFETY_DISCLAIMER,
    )
    store.put(analysis)
    return analysis
