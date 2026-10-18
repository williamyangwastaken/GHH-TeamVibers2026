"""Canonical Pydantic v2 models for ClearBill AI.

Public API models mirror ``components.schemas`` in ``api_contract.yaml`` exactly
(field names, required/nullable, enums). The contract is frozen: change the YAML
first, then this file. ``backend/tests/extraction/test_extraction_schemas.py``
checks the two stay in sync.

Conventions shared by every model:
  * Money is integer USD cents; ``None`` means unknown, never zero.
  * Dates are ``YYYY-MM-DD`` strings or ``None``.
  * Page numbers are 1-based or ``None``.
  * ``insurance_paid_cents`` and ``adjustments_cents`` on a DocumentSummary are
    non-negative magnitudes (a printed "-$100.00" adjustment becomes 10000).
    Line-item amounts keep their printed sign (credits are negative).

The ``Extracted*`` models at the bottom are internal: they are the structured
output schema sent to the model and are never returned to the browser.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DocumentKind(StrEnum):
    bill = "bill"
    eob = "eob"
    estimate = "estimate"


class ExtractionQuality(StrEnum):
    complete = "complete"
    partial = "partial"
    failed = "failed"


class FindingStatus(StrEnum):
    verified_inconsistency = "verified_inconsistency"
    needs_review = "needs_review"
    insufficient_information = "insufficient_information"


class FindingSeverity(StrEnum):
    info = "info"
    low = "low"
    medium = "medium"


class FindingCategory(StrEnum):
    arithmetic = "arithmetic"
    insurance_comparison = "insurance_comparison"
    possible_duplicate = "possible_duplicate"
    estimate_comparison = "estimate_comparison"
    price_benchmark = "price_benchmark"
    missing_context = "missing_context"


class LetterIntent(StrEnum):
    clarification = "clarification"
    dispute = "dispute"


class ErrorCode(StrEnum):
    INVALID_UPLOAD = "INVALID_UPLOAD"
    DOCUMENT_UNREADABLE = "DOCUMENT_UNREADABLE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_AUTH_FAILED = "MODEL_AUTH_FAILED"
    # Legacy Gemini adapter error; live extraction uses MODEL_UNAVAILABLE.
    GEMINI_UNAVAILABLE = "GEMINI_UNAVAILABLE"
    CASE_NOT_FOUND = "CASE_NOT_FOUND"
    BAD_SELECTION = "BAD_SELECTION"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Public API models (api_contract.yaml)
# ---------------------------------------------------------------------------


class ContractModel(BaseModel):
    """Base for contract models: unknown fields are rejected, not silently kept."""

    model_config = ConfigDict(extra="forbid")


class HealthResponse(ContractModel):
    status: Literal["ok"]
    demo_mode: bool


class LineItem(ContractModel):
    id: str
    description: str
    code: str | None = None
    service_date: str | None = Field(default=None, description="YYYY-MM-DD or null")
    quantity: int | None = None
    unit_amount_cents: int | None = None
    line_total_cents: int | None = None
    page: int | None = Field(default=None, ge=1)
    source_text: str | None = Field(
        default=None,
        description="Model excerpt of the source line; not automatically verified verbatim.",
    )


class DocumentSummary(ContractModel):
    id: str
    kind: DocumentKind
    filename: str
    pages: int = Field(ge=1)
    extraction_quality: ExtractionQuality
    provider_name: str | None = None
    insurer_name: str | None = None
    document_date: str | None = None
    service_date: str | None = None
    claim_number: str | None = None
    total_charges_cents: int | None = None
    amount_due_cents: int | None = Field(
        default=None, description="Current provider statement balance."
    )
    patient_responsibility_cents: int | None = Field(
        default=None, description="Typically from an EOB."
    )
    insurance_paid_cents: int | None = Field(
        default=None, description="Non-negative magnitude."
    )
    adjustments_cents: int | None = Field(
        default=None, description="Non-negative magnitude."
    )
    expected_total_cents: int | None = Field(
        default=None, description="Good Faith Estimate total."
    )
    eob_status: str | None = None
    line_items: list[LineItem]
    extraction_warnings: list[str]


class EvidenceRef(ContractModel):
    document_id: str
    page: int | None = Field(default=None, ge=1)
    line_item_id: str | None = None
    field: str
    amount_cents: int | None = None
    source_text: str | None = None
    verification_note: str | None = None


class Finding(ContractModel):
    id: str
    rule_id: str
    category: FindingCategory
    status: FindingStatus
    severity: FindingSeverity
    title: str
    explanation: str
    alternative_explanations: list[str]
    next_step: str
    difference_cents: int | None = Field(
        default=None, description="Never present as proven savings."
    )
    evidence: list[EvidenceRef]
    missing_information: list[str]


class AnalysisResponse(ContractModel):
    case_id: str
    is_demo: bool
    documents: list[DocumentSummary]
    findings: list[Finding]
    limitations: list[str]
    safety_disclaimer: str


class LetterRequest(ContractModel):
    case_id: str
    finding_ids: list[str] = Field(min_length=1)
    intent: LetterIntent


class LetterResponse(ContractModel):
    subject: str
    body: str
    safety_note: str
    is_fallback: bool


class ErrorDetail(ContractModel):
    code: ErrorCode
    message: str
    retryable: bool


class ErrorResponse(ContractModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ExtractionError(Exception):
    """A user-safe extraction failure that maps directly onto an ErrorResponse.

    ``message`` is shown to the browser, so it never contains document content,
    filenames, prompts, model output, or stack traces.

    Route usage::

        except ExtractionError as exc:
            return JSONResponse(exc.to_response().model_dump(mode="json"),
                                status_code=exc.http_status)
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        http_status: int,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable

    def to_response(self) -> ErrorResponse:
        return ErrorResponse(
            error=ErrorDetail(code=self.code, message=self.message, retryable=self.retryable)
        )

    def __repr__(self) -> str:
        return f"ExtractionError({self.code}, http_status={self.http_status})"


# ---------------------------------------------------------------------------
# Internal model structured-output models
# ---------------------------------------------------------------------------
# These define the model output shape and support honest extraction:
#   * no ``extra="forbid"`` (the API rejects ``additionalProperties``);
#   * every field is required but nullable, so the model must emit each key and
#     use null for anything not printed, rather than omitting or guessing;
#   * money and dates are copied *as printed* and normalized in Python, so the
#     model never does unit conversion or arithmetic.


class ExtractedDocumentType(StrEnum):
    bill = "bill"
    eob = "eob"
    estimate = "estimate"
    other = "other"


class ExtractedLineItem(BaseModel):
    description: str | None = Field(
        description="Service or charge description exactly as printed."
    )
    code: str | None = Field(
        description="Procedure/revenue code printed on this line (e.g. CPT, HCPCS). Null if none is printed."
    )
    service_date: str | None = Field(description="Service date for this line, exactly as printed.")
    quantity: int | None = Field(description="Units/quantity if printed, else null.")
    unit_amount: str | None = Field(
        description="Per-unit price exactly as printed, including $, commas, minus sign or parentheses."
    )
    line_total: str | None = Field(
        description="Line total exactly as printed, including $, commas, minus sign or parentheses."
    )
    page: int | None = Field(description="1-based page this line appears on, or null if unsure.")
    source_text: str | None = Field(
        description="Short verbatim excerpt (max ~150 characters) of the printed line, or null."
    )


class ExtractedDocument(BaseModel):
    detected_document_type: ExtractedDocumentType = Field(
        description="What this document actually appears to be, regardless of how it was uploaded."
    )
    is_fully_legible: bool = Field(
        description="False if any part is cut off, blurry, handwritten, or otherwise hard to read."
    )
    provider_name: str | None = Field(description="Healthcare provider/facility name as printed.")
    insurer_name: str | None = Field(description="Insurance company/plan name as printed.")
    document_date: str | None = Field(
        description="Statement, EOB processed, or estimate issue date, exactly as printed."
    )
    service_date: str | None = Field(
        description="Date of service exactly as printed. Copy the full text if it is a range."
    )
    claim_number: str | None = Field(
        description=(
            "Insurer/provider claim identifier exactly as printed. Do not use a patient member ID, "
            "group number, provider account number, authorization number, or generic reference number. "
            "If the document has several ambiguous identifiers, return null."
        )
    )
    total_charges: str | None = Field(description="Total billed charges exactly as printed.")
    amount_due: str | None = Field(
        description="Current balance / amount due now from the patient, exactly as printed."
    )
    patient_responsibility: str | None = Field(
        description="Amount explicitly labeled patient responsibility, exactly as printed."
    )
    insurance_paid: str | None = Field(
        description="Total paid by insurance/plan, exactly as printed."
    )
    adjustments: str | None = Field(
        description="Total contractual adjustments/discounts, exactly as printed."
    )
    expected_total: str | None = Field(
        description="Good Faith Estimate total expected cost, exactly as printed."
    )
    eob_status: str | None = Field(
        description="Claim status only if explicitly printed (e.g. Processed, Finalized, Pending, Denied)."
    )
    line_items: list[ExtractedLineItem] = Field(
        description="Every individual charge/service line in printed order. Empty if none."
    )
    extraction_warnings: list[str] = Field(
        description="Short plain-English notes about anything unclear, ambiguous, or unreadable."
    )
