"""PDF metadata extraction (via pypdf, bookman's one runtime dependency)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pypdf import PasswordType, PdfReader
from pypdf.errors import DependencyError, PdfReadError

from bookman.errors import ParseError
from bookman.formats.base import ParsedMetadata
from bookman.identify.isbn import extract_isbns
from bookman.models import ReadIssue

# Where the copyright page can sit. A real bundle put the ISBN as far
# back as page index 7 (O'Reilly) and at index 5 on every No Starch
# title -- cover, blank, half-title, blank, title page, copyright -- so
# the first five pages missed nearly all of them (FEATURES B8).
_ISBN_SCAN_PAGES = 10
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

    An encrypted PDF that bookman cannot open is not an error (spec
    PR6, ADR-29): it is a real PDF, and a bought book, so it comes back
    with no title, author or ISBNs and a `read_issue` saying why --
    AES without the optional crypto backend, a real password, or
    encryption pypdf cannot handle (a DRM security handler, a damaged
    `/Encrypt` entry). An AES PDF with an empty password reads normally
    once `bookman[crypto]` is installed.

    Args:
        path: Path to a .pdf file.

    Returns:
        ParsedMetadata with whatever fields could be found. A missing,
        empty, or unreadable info dict field is returned as None;
        `isbns` is empty (not None) if none are found in the scanned
        pages, and `isbns_scraped` is always True since they come
        from page text.

    Raises:
        FileNotFoundError: If path does not exist.
        BadPdfError: If the file is not a PDF at all (damaged, or
            something else with a .pdf name).
    """
    try:
        with _quiet_pypdf():
            try:
                reader = PdfReader(path)
            except DependencyError:
                return _unreadable(ReadIssue.NEEDS_CRYPTO)
            except PdfReadError:
                raise
            except Exception:
                # pypdf's encryption setup runs inside the constructor and
                # dies on shapes it does not handle -- NotImplementedError
                # for a DRM handler, AttributeError for a null /Encrypt
                # (FN-20). Only a file that declares encryption gets that
                # benefit of the doubt; any other crash is a real bug.
                if _declares_encryption(path):
                    return _unreadable(ReadIssue.UNSUPPORTED_ENCRYPTION)
                raise
            if reader.is_encrypted and reader.decrypt("") == PasswordType.NOT_DECRYPTED:
                return _unreadable(ReadIssue.PASSWORD)
            title = _clean(reader.metadata.title) if reader.metadata else None
            author = _clean(reader.metadata.author) if reader.metadata else None
            page_texts = (page.extract_text() or "" for page in reader.pages[:_ISBN_SCAN_PAGES])
            isbns = extract_isbns("\n".join(page_texts))
    except PdfReadError as exc:
        raise BadPdfError(
            f"{path}: not a valid PDF file (damaged, or not a PDF); "
            "check that it opens in a PDF reader"
        ) from exc

    return ParsedMetadata(title=title, author=author, isbns=isbns, isbns_scraped=True)


def _unreadable(issue: ReadIssue) -> ParsedMetadata:
    """An intact PDF whose contents bookman cannot read: nothing but the reason."""
    return ParsedMetadata(title=None, author=None, isbns=[], isbns_scraped=True, read_issue=issue)


def _declares_encryption(path: Path) -> bool:
    """Whether the file names an `/Encrypt` entry anywhere -- the trailer
    key every encrypted PDF carries. A byte search, because the parse that
    would find it properly is what just failed."""
    return b"/Encrypt" in path.read_bytes()


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
