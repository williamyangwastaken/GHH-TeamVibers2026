"""Upload validation: size, type-by-signature, PDF pages, encryption, corruption."""

import pytest

from app.schemas import ErrorCode, ExtractionError
from app.services.extraction import validate_upload
from extraction_samples import JPEG_BYTES, make_blank_pdf, make_png, make_text_pdf

MB = 1024 * 1024


def rejected(content, content_type="application/pdf") -> ExtractionError:
    with pytest.raises(ExtractionError) as info:
        validate_upload(content, content_type)
    return info.value


@pytest.mark.parametrize("pages", [1, 6])
def test_pdf_within_page_limit_is_accepted(pages):
    upload = validate_upload(make_blank_pdf(pages), "application/pdf")
    assert (upload.mime_type, upload.pages) == ("application/pdf", pages)


def test_text_pdf_is_accepted():
    assert validate_upload(make_text_pdf(["Hello"]), "application/pdf").pages == 1


def test_png_and_jpeg_count_as_one_page():
    png = validate_upload(make_png(), "image/png")
    jpg = validate_upload(JPEG_BYTES, "image/jpeg")
    assert (png.mime_type, png.pages) == ("image/png", 1)
    assert (jpg.mime_type, jpg.pages) == ("image/jpeg", 1)


def test_pdf_over_page_limit_is_413():
    err = rejected(make_blank_pdf(7))
    assert (err.code, err.http_status) == (ErrorCode.FILE_TOO_LARGE, 413)
    assert "6 pages" in err.message


def test_page_limit_is_configurable(monkeypatch):
    monkeypatch.setenv("MAX_PDF_PAGES", "2")
    assert rejected(make_blank_pdf(3)).code == ErrorCode.FILE_TOO_LARGE


def test_file_over_10mb_is_413():
    err = rejected(b"%PDF-1.7\n" + b"0" * (10 * MB))
    assert (err.code, err.http_status, err.retryable) == (ErrorCode.FILE_TOO_LARGE, 413, False)


def test_file_exactly_at_size_limit_is_accepted(monkeypatch):
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "1")
    png = make_png()
    exact = png + b"\0" * (MB - len(png))
    assert validate_upload(exact, "image/png").pages == 1
    assert rejected(exact + b"\0", "image/png").code == ErrorCode.FILE_TOO_LARGE


def test_empty_file_is_400():
    err = rejected(b"")
    assert (err.code, err.http_status) == (ErrorCode.INVALID_UPLOAD, 400)


@pytest.mark.parametrize(
    "content, content_type",
    [
        (b"just some text", "text/plain"),
        (b"GIF89a\x01\x00\x01\x00", "image/gif"),
        (b"MZ\x90\x00 pretend exe", "application/pdf"),  # declared type lies
        (b"<html></html>", "application/octet-stream"),
        (make_text_pdf(["x"]), "text/plain"),  # disallowed declared type
    ],
)
def test_unsupported_types_are_415(content, content_type):
    err = rejected(content, content_type)
    assert (err.code, err.http_status) == (ErrorCode.INVALID_UPLOAD, 415)


@pytest.mark.parametrize("content_type", [None, "", "application/octet-stream", "Application/PDF; charset=binary"])
def test_signature_wins_over_generic_or_decorated_declared_types(content_type):
    assert validate_upload(make_blank_pdf(1), content_type).mime_type == "application/pdf"


def test_misdeclared_supported_type_uses_detected_type():
    # A PNG renamed to .jpg: accepted, and Gemini is told the true type.
    assert validate_upload(make_png(), "image/jpeg").mime_type == "image/png"


@pytest.mark.parametrize("password", ["secret", ""])
def test_encrypted_pdf_is_422(password):
    err = rejected(make_blank_pdf(1, password=password))
    assert (err.code, err.http_status) == (ErrorCode.DOCUMENT_UNREADABLE, 422)
    assert "password" in err.message.lower()


@pytest.mark.parametrize(
    "content",
    [b"%PDF-1.7\nnot really a pdf", make_blank_pdf(2)[:200], b"%PDF-"],
    ids=["garbage", "truncated", "header-only"],
)
def test_corrupt_pdf_is_422(content):
    err = rejected(content)
    assert (err.code, err.http_status) == (ErrorCode.DOCUMENT_UNREADABLE, 422)


@pytest.mark.parametrize(
    "content",
    [b"\x89PNG\r\n\x1a\n" + b"\0" * 4, make_png()[:16], make_png(width=0)],
    ids=["no-ihdr", "truncated", "zero-width"],
)
def test_corrupt_png_is_422(content):
    err = rejected(content, "image/png")
    assert (err.code, err.http_status) == (ErrorCode.DOCUMENT_UNREADABLE, 422)


def test_error_messages_never_echo_file_contents():
    secret = b"%PDF-1.7\nPATIENT SSN 123-45-6789"
    assert "123-45-6789" not in rejected(secret).message
