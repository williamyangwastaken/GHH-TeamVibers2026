"""Document extraction entry point (BE-A -> BE-B handoff).

INITIAL STUB: the signature and error type are final; the body is replaced by
live Gemini extraction in the next commit. It performs no validation and does
not read the file.
"""

from __future__ import annotations

from app.schemas import (
    DocumentKind,
    DocumentSummary,
    ErrorCode,
    ExtractionError,
    ExtractionQuality,
)

__all__ = ["ErrorCode", "ExtractionError", "extract_document"]


async def extract_document(
    content: bytes,
    content_type: str,
    filename: str,
    kind: DocumentKind,
) -> DocumentSummary:
    """
    Validates file signature/size/pages, calls Gemini multimodal structured output,
    normalizes currency to integer cents and dates to YYYY-MM-DD (or None),
    and returns a validated DocumentSummary. Raises ExtractionError (with ErrorCode) on failure.
    """
    kind = DocumentKind(kind)
    return DocumentSummary(
        id=f"doc_{kind}",
        kind=kind,
        filename=filename,
        pages=1,
        extraction_quality=ExtractionQuality.failed,
        line_items=[],
        extraction_warnings=["Extraction is not implemented yet (stub)."],
    )
