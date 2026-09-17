from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject

from bookman.formats.pdf import _ISBN_SCAN_PAGES, BadPdfError, parse_pdf

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
        writer.encrypt(user_password=password, owner_password=password)

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
    with pytest.raises(BadPdfError):
        parse_pdf(not_a_pdf)


def test_parse_pdf_encrypted_without_password_raises_bad_pdf_error(tmp_path):
    pdf = _make_pdf(tmp_path / "book.pdf", password="secret")
    with pytest.raises(BadPdfError):
        parse_pdf(pdf)


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
