"""Document extraction: upload validation -> Groq structured output -> DocumentSummary.

Public API (frozen in CONTRACT.md):

    await extract_document(content, content_type, filename, kind) -> DocumentSummary

Also exported so routes can reject every bad upload before making any model
calls:

    validate_upload(content, content_type) -> ValidatedUpload

Every failure raises ``ExtractionError`` (code, user-safe message, HTTP status,
retryable). Groq only transcribes printed text; dollars -> cents, date
normalization, and quality grading happen deterministically here.

Upload limits come from MAX_FILE_SIZE_MB (default 10, MiB) and MAX_PDF_PAGES
(default 6).
"""

from __future__ import annotations

import io
import logging
import os
import re
import struct
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from pypdf import PdfReader

from app.schemas import (
    DocumentKind,
    DocumentSummary,
    ErrorCode,
    ExtractedDocument,
    ExtractedDocumentType,
    ExtractionError,
    ExtractionQuality,
    LineItem,
)
from app.services import groq_api, prompts

logger = logging.getLogger(__name__)

__all__ = [
    "ErrorCode",
    "ExtractionError",
    "ValidatedUpload",
    "extract_document",
    "normalize_date",
    "normalize_extraction",
    "parse_money_to_cents",
    "validate_upload",
]

DEFAULT_MAX_FILE_SIZE_MB = 10
DEFAULT_MAX_PDF_PAGES = 6

PDF_MIME = "application/pdf"
PNG_MIME = "image/png"
JPEG_MIME = "image/jpeg"

_DECLARED_TYPES = {
    "application/pdf": PDF_MIME,
    "application/x-pdf": PDF_MIME,
    "image/png": PNG_MIME,
    "image/jpeg": JPEG_MIME,
    "image/jpg": JPEG_MIME,
    "image/pjpeg": JPEG_MIME,
}
# Browsers and HTTP clients sometimes omit or genericize the type; the file
# signature is authoritative either way.
_GENERIC_DECLARED_TYPES = {"", "application/octet-stream", "binary/octet-stream"}

_KIND_LABELS = {
    "bill": "a provider bill",
    "eob": "an insurance EOB",
    "estimate": "a Good Faith Estimate",
}

# The headline amount each kind of document exists to report.
_KEY_AMOUNT = {
    DocumentKind.bill: ("amount_due", "current balance or amount due"),
    DocumentKind.eob: ("patient_responsibility", "patient responsibility amount"),
    DocumentKind.estimate: ("expected_total", "estimated total cost"),
}

_MAX_MODEL_WARNINGS = 8


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def extract_document(
    content: bytes,
    content_type: str,
    filename: str,
    kind: DocumentKind,
) -> DocumentSummary:
    """
    Validates file signature/size/pages, calls Groq structured output,
    normalizes currency to integer cents and dates to YYYY-MM-DD (or None),
    and returns a validated DocumentSummary. Raises ExtractionError (with ErrorCode) on failure.

    A readable file from which nothing useful could be extracted is returned
    with ``extraction_quality="failed"`` rather than raised, so the audit can
    still report it as missing context.
    """
    upload = validate_upload(content, content_type)
    try:
        kind = DocumentKind(kind)
        extracted = await groq_api.generate_extraction(
            content=content,
            mime_type=upload.mime_type,
            system_instruction=prompts.EXTRACTION_SYSTEM_INSTRUCTION,
            prompt=prompts.build_extraction_prompt(kind, upload.pages),
            kind=kind,
        )
        return normalize_extraction(extracted, kind=kind, filename=filename, pages=upload.pages)
    except ExtractionError:
        raise
    except Exception as exc:
        logger.exception("Unexpected extraction failure")
        raise ExtractionError(
            ErrorCode.INTERNAL_ERROR,
            "Something went wrong while analyzing this document. "
            "Please try again, or use the sample case.",
            http_status=500,
            retryable=True,
        ) from exc


# ---------------------------------------------------------------------------
# Upload validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidatedUpload:
    mime_type: str  # detected from the file signature, not the declared type
    pages: int


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name) or default)
    except ValueError:
        return default
    return value if value > 0 else default


def max_file_size_bytes() -> int:
    return _int_env("MAX_FILE_SIZE_MB", DEFAULT_MAX_FILE_SIZE_MB) * 1024 * 1024


def max_pdf_pages() -> int:
    return _int_env("MAX_PDF_PAGES", DEFAULT_MAX_PDF_PAGES)


def _unsupported_type() -> ExtractionError:
    return ExtractionError(
        ErrorCode.INVALID_UPLOAD,
        "Unsupported file type. Please upload a PDF, PNG, or JPG.",
        http_status=415,
    )


def _unreadable(message: str) -> ExtractionError:
    return ExtractionError(ErrorCode.DOCUMENT_UNREADABLE, message, http_status=422)


def validate_upload(content: bytes, content_type: str | None) -> ValidatedUpload:
    """Check size, type (by signature), and PDF page count. No network calls."""
    if not content:
        raise ExtractionError(
            ErrorCode.INVALID_UPLOAD, "The uploaded file is empty.", http_status=400
        )

    limit = max_file_size_bytes()
    if len(content) > limit:
        raise ExtractionError(
            ErrorCode.FILE_TOO_LARGE,
            f"Each file must be {limit // (1024 * 1024)} MB or smaller.",
            http_status=413,
        )

    declared = (content_type or "").split(";", 1)[0].strip().lower()
    if declared not in _DECLARED_TYPES and declared not in _GENERIC_DECLARED_TYPES:
        raise _unsupported_type()

    mime_type = _sniff_mime_type(content)
    if mime_type is None:
        raise _unsupported_type()

    if mime_type == PDF_MIME:
        return ValidatedUpload(mime_type, _count_pdf_pages(content))
    if mime_type == PNG_MIME:
        _check_png(content)
    return ValidatedUpload(mime_type, 1)


def _sniff_mime_type(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG_MIME
    if content.startswith(b"\xff\xd8\xff"):
        return JPEG_MIME
    # The PDF spec allows the header anywhere in the first 1024 bytes.
    if b"%PDF-" in content[:1024]:
        return PDF_MIME
    return None


def _count_pdf_pages(content: bytes) -> int:
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        encrypted = reader.is_encrypted
        pages = 0 if encrypted else len(reader.pages)
    except Exception as exc:  # pypdf raises many types for malformed files
        logger.info("PDF could not be parsed (%s)", type(exc).__name__)
        raise _unreadable("This PDF appears to be damaged and could not be read.") from None

    if encrypted:
        raise _unreadable(
            "This PDF is password-protected or encrypted. Please upload an unprotected copy."
        )
    if pages < 1:
        raise _unreadable("This PDF has no pages.")
    limit = max_pdf_pages()
    if pages > limit:
        raise ExtractionError(
            ErrorCode.FILE_TOO_LARGE,
            f"PDFs can have at most {limit} pages; this one has {pages}.",
            http_status=413,
        )
    return pages


def _check_png(content: bytes) -> None:
    # Signature (8) + IHDR length (4) + "IHDR" (4) + width (4) + height (4).
    if len(content) < 24 or content[12:16] != b"IHDR":
        raise _unreadable("This image appears to be damaged and could not be read.")
    width, height = struct.unpack(">II", content[16:24])
    if width == 0 or height == 0:
        raise _unreadable("This image appears to be damaged and could not be read.")


# ---------------------------------------------------------------------------
# Normalization (pure, deterministic)
# ---------------------------------------------------------------------------

_NULL_TOKENS = {"N/A", "NA", "NONE", "NULL", "-", "--", "—", "–", "UNKNOWN"}
_MONEY_BODY = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?")

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_ISO_DATE = re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[T ].*)?")
_US_DATE = re.compile(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})")
_MONTH_FIRST = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})")
_DAY_FIRST = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})")


def _clean_text(raw: str | None, max_len: int | None = None) -> str | None:
    """Collapse whitespace; map empty and placeholder values ("N/A", "--") to None."""
    if raw is None:
        return None
    text = " ".join(str(raw).split())
    if not text or text.upper() in _NULL_TOKENS:
        return None
    if max_len is not None and len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def parse_money_to_cents(raw: str | None) -> int | None:
    """Parse a printed USD amount into integer cents.

    Handles "$1,234.56", "-$50.00", "$-50.00", "($50.00)", "50.00 CR", "50.00-",
    and "USD 12". Returns None for blank/placeholder values and for anything
    ambiguous (bad digit grouping, sub-cent precision, stray text).
    """
    text = _clean_text(raw)
    if text is None:
        return None

    s = text.upper().replace(" ", "")
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    if s.endswith("CR"):
        negative, s = True, s[:-2]
    for prefix in ("USD", "US$"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    if s.endswith("USD"):
        s = s[:-3]
    s = s.replace("$", "")
    if s.startswith("-"):
        negative, s = True, s[1:]
    elif s.startswith("+"):
        s = s[1:]
    elif s.endswith("-"):
        negative, s = True, s[:-1]

    if not _MONEY_BODY.fullmatch(s):
        return None
    try:
        cents = Decimal(s.replace(",", "")) * 100
    except InvalidOperation:
        return None
    return -int(cents) if negative else int(cents)


def normalize_date(raw: str | None) -> str | None:
    """Normalize a printed date to YYYY-MM-DD, or None if it is not one clear date.

    Numeric dates are read as U.S. month/day order (this product targets U.S.
    medical bills); two-digit years are taken as 20YY. Ranges return None.
    """
    text = _clean_text(raw)
    if text is None:
        return None
    s = text.rstrip(".")

    if m := _ISO_DATE.fullmatch(s):
        year, month, day = int(m[1]), int(m[2]), int(m[3])
    elif m := _US_DATE.fullmatch(s):
        month, day = int(m[1]), int(m[2])
        year = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
    elif (m := _MONTH_FIRST.fullmatch(s)) and m[1].lower() in _MONTHS:
        month, day, year = _MONTHS[m[1].lower()], int(m[2]), int(m[3])
    elif (m := _DAY_FIRST.fullmatch(s)) and m[2].lower() in _MONTHS:
        day, month, year = int(m[1]), _MONTHS[m[2].lower()], int(m[3])
    else:
        return None

    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _display_filename(filename: str | None, kind: DocumentKind) -> str:
    base = re.split(r"[\\/]", filename or "")[-1]
    return _clean_text(base, 120) or f"{kind}-upload"


def normalize_extraction(
    extracted: ExtractedDocument,
    *,
    kind: DocumentKind,
    filename: str,
    pages: int,
) -> DocumentSummary:
    """Turn Groq's as-printed transcription into a validated DocumentSummary.

    Grading: ``failed`` if no amounts or line items were found; ``partial`` if
    anything needed a warning from us (unreadable values, missing headline
    amount, wrong document type, legibility); otherwise ``complete``. Free-text
    model warnings are passed through but do not change the grade by themselves.
    """
    kind = DocumentKind(kind)
    warnings: list[str] = []

    def money(raw: str | None, label: str, *, magnitude: bool = False) -> int | None:
        cents = parse_money_to_cents(raw)
        if cents is None and _clean_text(raw) is not None:
            warnings.append(
                f"The {label} could not be read as a dollar amount; verify it against the document."
            )
        if cents is not None and magnitude:
            cents = abs(cents)
        return cents

    def day(raw: str | None, label: str) -> str | None:
        iso = normalize_date(raw)
        if iso is None and _clean_text(raw) is not None:
            warnings.append(
                f"The {label} could not be read as a single calendar date; verify it against the document."
            )
        return iso

    detected = extracted.detected_document_type
    if detected == ExtractedDocumentType.other:
        warnings.append(
            f"This file does not look like {_KIND_LABELS[kind]}. Extracted values may be incomplete."
        )
    elif detected.value != kind.value:
        warnings.append(
            f"This file looks like {_KIND_LABELS[detected.value]} but was uploaded as "
            f"{_KIND_LABELS[kind]}. Check that each file is in the right slot."
        )
    if not extracted.is_fully_legible:
        warnings.append(
            "Parts of this document were hard to read; verify extracted values against the original."
        )

    amounts = {
        "total_charges": money(extracted.total_charges, "total charges"),
        "amount_due": money(extracted.amount_due, "amount due"),
        "patient_responsibility": money(
            extracted.patient_responsibility, "patient responsibility"
        ),
        "insurance_paid": money(extracted.insurance_paid, "insurance paid", magnitude=True),
        "adjustments": money(extracted.adjustments, "adjustments", magnitude=True),
        "expected_total": money(extracted.expected_total, "estimated total"),
    }
    document_date = day(extracted.document_date, "document date")
    service_date = day(extracted.service_date, "service date")

    key_field, key_label = _KEY_AMOUNT[kind]
    if _clean_text(getattr(extracted, key_field)) is None:
        warnings.append(f"No {key_label} was found on this document.")

    line_items: list[LineItem] = []
    unreadable_line_amounts = 0
    unreadable_line_dates = 0
    dropped_pages = False
    for raw_item in extracted.line_items:
        unit = parse_money_to_cents(raw_item.unit_amount)
        total = parse_money_to_cents(raw_item.line_total)
        description = _clean_text(raw_item.description, 300)
        if description is None and unit is None and total is None:
            continue  # empty row
        for raw_amount, parsed in ((raw_item.unit_amount, unit), (raw_item.line_total, total)):
            if parsed is None and _clean_text(raw_amount) is not None:
                unreadable_line_amounts += 1
        line_date = normalize_date(raw_item.service_date)
        if line_date is None and _clean_text(raw_item.service_date) is not None:
            unreadable_line_dates += 1
        page = raw_item.page
        if page is not None and not 1 <= page <= pages:
            page, dropped_pages = None, True
        line_items.append(
            LineItem(
                id=f"li_{kind}_{len(line_items) + 1}",
                description=description or "(description not legible)",
                code=_clean_text(raw_item.code, 20),
                service_date=line_date,
                quantity=raw_item.quantity,
                unit_amount_cents=unit,
                line_total_cents=total,
                page=page,
                source_text=_clean_text(raw_item.source_text, 300),
            )
        )
    if unreadable_line_amounts:
        warnings.append(
            f"{unreadable_line_amounts} line-item amount(s) could not be read; verify them against the document."
        )
    if unreadable_line_dates:
        warnings.append(
            f"{unreadable_line_dates} line-item date(s) could not be read as a single calendar date."
        )
    if dropped_pages:
        warnings.append("Some page references did not match this document and were removed.")

    has_amounts = any(v is not None for v in amounts.values()) or any(
        li.line_total_cents is not None or li.unit_amount_cents is not None for li in line_items
    )
    if not has_amounts and not line_items:
        quality = ExtractionQuality.failed
        warnings.append("No billing amounts or line items could be extracted from this document.")
    elif warnings:
        quality = ExtractionQuality.partial
    else:
        quality = ExtractionQuality.complete

    model_warnings: list[str] = []
    for raw_warning in extracted.extraction_warnings:
        note = _clean_text(raw_warning, 200)
        if note and note not in model_warnings and note not in warnings:
            model_warnings.append(note)
    warnings.extend(model_warnings[:_MAX_MODEL_WARNINGS])

    return DocumentSummary(
        id=f"doc_{kind}",
        kind=kind,
        filename=_display_filename(filename, kind),
        pages=pages,
        extraction_quality=quality,
        provider_name=_clean_text(extracted.provider_name, 200),
        insurer_name=_clean_text(extracted.insurer_name, 200),
        document_date=document_date,
        service_date=service_date,
        claim_number=_clean_text(extracted.claim_number, 64),
        total_charges_cents=amounts["total_charges"],
        amount_due_cents=amounts["amount_due"],
        patient_responsibility_cents=amounts["patient_responsibility"],
        insurance_paid_cents=amounts["insurance_paid"],
        adjustments_cents=amounts["adjustments"],
        expected_total_cents=amounts["expected_total"],
        eob_status=(
            (_clean_text(extracted.eob_status, 40) or "").lower() or None
            if kind == DocumentKind.eob
            else None
        ),
        line_items=line_items,
        extraction_warnings=warnings,
    )
