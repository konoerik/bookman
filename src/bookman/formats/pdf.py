"""PDF metadata extraction (via pypdf, bookman's one runtime dependency)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pypdf import PasswordType, PdfReader
from pypdf.errors import PdfReadError

from bookman.errors import ParseError
from bookman.formats.base import ParsedMetadata
from bookman.identify.isbn import extract_isbns

_ISBN_SCAN_PAGES = 5
_PYPDF_LOGGER = "pypdf"


class BadPdfError(ParseError):
    """Raised when a file is not a readable PDF."""


def parse_pdf(path: Path) -> ParsedMetadata:
    """Extract title, author, and ISBN identifiers from a PDF file.

    Reads the PDF's document info dictionary (/Title, /Author) via
    pypdf, and scans the text of the first `_ISBN_SCAN_PAGES` pages
    (where a copyright/title page ISBN typically appears) for
    ISBN-10/13 identifiers via bookman.identify.isbn.extract_isbns.
    PDFs rarely carry a structured ISBN field, so this is a
    best-effort text scan rather than a lookup of a known metadata key.

    Args:
        path: Path to a .pdf file.

    Returns:
        ParsedMetadata with whatever fields could be found. A missing,
        empty, or unreadable info dict field is returned as None;
        `isbns` is empty (not None) if none are found in the scanned
        pages.

    Raises:
        FileNotFoundError: If path does not exist.
        BadPdfError: If the file cannot be read as a PDF (corrupt,
            encrypted without a usable password, or not a PDF at all).
    """
    try:
        with _quiet_pypdf():
            reader = PdfReader(path)
            if reader.is_encrypted and reader.decrypt("") == PasswordType.NOT_DECRYPTED:
                raise BadPdfError(f"{path}: encrypted, no usable password")
            title = _clean(reader.metadata.title) if reader.metadata else None
            author = _clean(reader.metadata.author) if reader.metadata else None
            page_texts = (page.extract_text() or "" for page in reader.pages[:_ISBN_SCAN_PAGES])
            isbns = extract_isbns("\n".join(page_texts))
    except PdfReadError as exc:
        raise BadPdfError(f"{path}: not a valid PDF file") from exc

    return ParsedMetadata(title=title, author=author, isbns=isbns)


@contextmanager
def _quiet_pypdf() -> Iterator[None]:
    """Raise pypdf's logger to ERROR for the duration of the block.

    pypdf logs a WARNING for every recoverable oddity it handles while
    extracting text (fonts it can't fully decode without fontTools, odd
    encodings...). Real-world PDFs trigger dozens of these, and none are
    actionable for a best-effort ISBN scan of the first few pages, so
    they'd just be noise on the user's terminal. Errors still surface.
    """
    logger = logging.getLogger(_PYPDF_LOGGER)
    previous = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(previous)


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    return text or None
