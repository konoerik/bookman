from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject

from bookman.formats.pdf import _ISBN_SCAN_PAGES, BadPdfError, parse_pdf
from bookman.models import ReadIssue

VALID_ISBN13 = "9780306406157"


def _add_text_page(writer: PdfWriter, text: str) -> None:
    from pypdf.generic import DecodedStreamObject

    page = writer.add_blank_page(width=200, height=200)

    content = DecodedStreamObject()
    content.set_data(f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode())
    content_ref = writer._add_object(content)
    page[NameObject("/Contents")] = content_ref

    font = DictionaryObject()
    font[NameObject("/Type")] = NameObject("/Font")
    font[NameObject("/Subtype")] = NameObject("/Type1")
    font[NameObject("/BaseFont")] = NameObject("/Helvetica")
    font_ref = writer._add_object(font)

    font_dict = DictionaryObject()
    font_dict[NameObject("/F1")] = font_ref
    resources = DictionaryObject()
    resources[NameObject("/Font")] = font_dict
    page[NameObject("/Resources")] = resources


def _make_pdf(
    path: Path,
    *,
    title: str | None = "A Title",
    author: str | None = "An Author",
    page_texts: tuple[str, ...] = (),
    num_blank_pages: int = 0,
    password: str | None = None,
    algorithm: str = "RC4-128",
) -> Path:
    writer = PdfWriter()
    for text in page_texts:
        _add_text_page(writer, text)
    for _ in range(num_blank_pages):
        writer.add_blank_page(width=200, height=200)
    if not page_texts and num_blank_pages == 0:
        writer.add_blank_page(width=200, height=200)

    metadata = {}
    if title is not None:
        metadata["/Title"] = title
    if author is not None:
        metadata["/Author"] = author
    if metadata:
        writer.add_metadata(metadata)

    if password is not None:
        writer.encrypt(user_password=password, owner_password="owner", algorithm=algorithm)

    with open(path, "wb") as f:
        writer.write(f)
    return path


def test_parse_pdf_reads_title_and_author_from_info_dict(tmp_path):
    pdf = _make_pdf(tmp_path / "book.pdf", title="Deep Work", author="Cal Newport")
    result = parse_pdf(pdf)
    assert result.title == "Deep Work"
    assert result.author == "Cal Newport"


def test_parse_pdf_finds_isbn_in_first_pages_text(tmp_path):
    pdf = _make_pdf(tmp_path / "book.pdf", page_texts=(f"ISBN {VALID_ISBN13}",))
    result = parse_pdf(pdf)
    assert result.isbns == [VALID_ISBN13]
    assert result.isbns_scraped


def test_parse_pdf_finds_isbn_on_a_copyright_page_after_four_pages_of_front_matter(tmp_path):
    # FEATURES B8: a No Starch PDF runs cover, blank, half-title, blank,
    # title page, and only then the copyright page with the ISBN -- page
    # index 5, which the original five-page window stopped just short of.
    # (Observed on 5 of 18 in a real bundle, orphaning each one's PDF.)
    page_texts = ("cover", "", "half title", "", "title page", f"ISBN {VALID_ISBN13}")
    pdf = _make_pdf(tmp_path / "book.pdf", page_texts=page_texts)
    result = parse_pdf(pdf)
    assert result.isbns == [VALID_ISBN13]


def test_parse_pdf_ignores_isbn_beyond_scan_page_limit(tmp_path):
    page_texts = ("no isbn here",) * _ISBN_SCAN_PAGES + (f"ISBN {VALID_ISBN13}",)
    pdf = _make_pdf(tmp_path / "book.pdf", page_texts=page_texts)
    result = parse_pdf(pdf)
    assert result.isbns == []


def test_parse_pdf_missing_info_dict_returns_none_title_author(tmp_path):
    pdf = _make_pdf(tmp_path / "book.pdf", title=None, author=None)
    result = parse_pdf(pdf)
    assert result.title is None
    assert result.author is None


def test_parse_pdf_no_isbn_in_text_returns_empty_isbns(tmp_path):
    pdf = _make_pdf(tmp_path / "book.pdf", page_texts=("just some prose",))
    result = parse_pdf(pdf)
    assert result.isbns == []


def test_parse_pdf_nonexistent_path_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_pdf(tmp_path / "missing.pdf")


def test_parse_pdf_not_a_pdf_raises_bad_pdf_error(tmp_path):
    not_a_pdf = tmp_path / "book.pdf"
    not_a_pdf.write_bytes(b"this is not a pdf file at all")
    with pytest.raises(BadPdfError, match="check that it opens in a PDF reader"):
        parse_pdf(not_a_pdf)


def test_parse_pdf_with_a_real_password_reports_it_instead_of_failing(tmp_path):
    # Spec PR6 (ADR-29): the file is intact and bought; bookman just
    # cannot see inside it. It is imported on its filename alone.
    pdf = _make_pdf(tmp_path / "book.pdf", title="Deep Work", password="secret")
    result = parse_pdf(pdf)
    assert result.read_issue == ReadIssue.PASSWORD
    assert (result.title, result.author, result.isbns) == (None, None, [])


def test_parse_pdf_reads_an_aes_pdf_with_an_empty_password(tmp_path):
    # FIELD-NOTES FN-12: every InformIT PDF is AES-encrypted with an empty
    # user password. With the crypto extra installed it reads normally.
    pdf = _make_pdf(
        tmp_path / "book.pdf",
        title="Domain-Driven Design Distilled",
        page_texts=(f"ISBN {VALID_ISBN13}",),
        password="",
        algorithm="AES-256",
    )
    result = parse_pdf(pdf)
    assert result.read_issue is None
    assert result.title == "Domain-Driven Design Distilled"
    assert result.isbns == [VALID_ISBN13]


def test_parse_pdf_reports_a_missing_crypto_backend_instead_of_failing(tmp_path, monkeypatch):
    # FN-12 without the extra: pypdf raises DependencyError, which is not
    # a PdfReadError and used to escape as an undocumented exception.
    from pypdf.errors import DependencyError

    from bookman.formats import pdf as pdf_module

    def reader_without_backend(path):
        raise DependencyError("cryptography>=3.1 is required for AES algorithm")

    monkeypatch.setattr(pdf_module, "PdfReader", reader_without_backend)
    result = parse_pdf(_make_pdf(tmp_path / "book.pdf", password="", algorithm="AES-256"))
    assert result.read_issue == ReadIssue.NEEDS_CRYPTO
    assert (result.title, result.author, result.isbns) == (None, None, [])


def test_parse_pdf_reports_a_null_encrypt_entry_instead_of_failing(tmp_path):
    # FIELD-NOTES FN-20 ("A Mind for Numbers"): the trailer's /Encrypt is
    # a null object and pypdf's encryption setup dies with AttributeError.
    pdf = _make_pdf(tmp_path / "book.pdf", title="A Mind for Numbers")
    raw = pdf.read_bytes()
    assert b"trailer\n<<\n" in raw
    pdf.write_bytes(raw.replace(b"trailer\n<<\n", b"trailer\n<<\n/Encrypt null\n", 1))
    result = parse_pdf(pdf)
    assert result.read_issue == ReadIssue.UNSUPPORTED_ENCRYPTION
    assert (result.title, result.author, result.isbns) == (None, None, [])


def test_parse_pdf_reports_a_drm_security_handler_instead_of_failing(tmp_path):
    # A non-Standard security handler (Adobe DRM) makes pypdf raise
    # NotImplementedError -- the same escape as FN-20.
    pdf = _make_pdf(tmp_path / "book.pdf", password="")
    raw = pdf.read_bytes()
    assert b"/Filter /Standard" in raw
    pdf.write_bytes(raw.replace(b"/Filter /Standard", b"/Filter /EBX_HAND"))  # same length
    assert parse_pdf(pdf).read_issue == ReadIssue.UNSUPPORTED_ENCRYPTION


def test_parse_pdf_unencrypted_file_has_no_read_issue(tmp_path):
    assert parse_pdf(_make_pdf(tmp_path / "book.pdf")).read_issue is None


def test_parse_pdf_silences_pypdf_recoverable_warnings(tmp_path, monkeypatch, caplog):
    """pypdf logs a WARNING for every recoverable oddity it meets while
    extracting page text (missing fontTools, odd encodings...). None of
    that is actionable for a caller scanning five pages for an ISBN, so
    it must not leak out of `parse_pdf`, and the logger's level must be
    put back afterwards."""
    import logging

    from bookman.formats import pdf as pdf_module

    pypdf_logger = logging.getLogger("pypdf")
    original_level = pypdf_logger.level

    class NoisyReader:
        is_encrypted = False
        metadata = None
        pages: list = []

        def __init__(self, path):
            logging.getLogger("pypdf._cmap").warning("fontTools is required ...")

    monkeypatch.setattr(pdf_module, "PdfReader", NoisyReader)

    with caplog.at_level(logging.WARNING):
        parse_pdf(_make_pdf(tmp_path / "noisy.pdf"))

    assert not [r for r in caplog.records if r.name.startswith("pypdf")]
    assert pypdf_logger.level == original_level
