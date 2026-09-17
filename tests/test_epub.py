import zipfile
from pathlib import Path

import pytest

from bookman.formats.epub import BadEpubError, parse_epub

CONTAINER_XML = b"""<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

VALID_ISBN13 = "9780306406157"


def _opf_xml(*, title=None, author=None, identifiers=()):
    parts = [
        '<?xml version="1.0"?>',
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0">',
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">',
    ]
    if title is not None:
        parts.append(f"<dc:title>{title}</dc:title>")
    if author is not None:
        parts.append(f"<dc:creator>{author}</dc:creator>")
    for ident in identifiers:
        parts.append(f"<dc:identifier>{ident}</dc:identifier>")
    parts.append("</metadata></package>")
    return "".join(parts).encode("utf-8")


def _make_epub(
    path: Path,
    *,
    title="A Title",
    author="An Author",
    identifiers=(),
    include_container=True,
    include_opf=True,
) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        if include_container:
            zf.writestr("META-INF/container.xml", CONTAINER_XML)
        if include_opf:
            zf.writestr(
                "OEBPS/content.opf",
                _opf_xml(title=title, author=author, identifiers=identifiers),
            )
    return path


def test_parse_epub_reads_title_author_and_isbn(tmp_path):
    epub = _make_epub(
        tmp_path / "book.epub",
        title="Structure and Interpretation",
        author="Harold Abelson",
        identifiers=[f"urn:isbn:{VALID_ISBN13}"],
    )
    result = parse_epub(epub)
    assert result.title == "Structure and Interpretation"
    assert result.author == "Harold Abelson"
    assert result.isbns == [VALID_ISBN13]


def test_parse_epub_missing_identifier_returns_empty_isbns(tmp_path):
    epub = _make_epub(tmp_path / "book.epub", identifiers=())
    result = parse_epub(epub)
    assert result.isbns == []


def test_parse_epub_multiple_identifiers_filters_to_valid_isbns(tmp_path):
    epub = _make_epub(
        tmp_path / "book.epub",
        identifiers=["urn:uuid:550e8400-e29b-41d4-a716-446655440000", f"urn:isbn:{VALID_ISBN13}"],
    )
    result = parse_epub(epub)
    assert result.isbns == [VALID_ISBN13]


def test_parse_epub_missing_title_or_author_returns_none(tmp_path):
    epub = _make_epub(tmp_path / "book.epub", title=None, author=None)
    result = parse_epub(epub)
    assert result.title is None
    assert result.author is None


def test_parse_epub_nonexistent_path_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_epub(tmp_path / "missing.epub")


def test_parse_epub_not_a_zip_raises_bad_epub_error(tmp_path):
    not_a_zip = tmp_path / "book.epub"
    not_a_zip.write_bytes(b"this is not a zip file")
    with pytest.raises(BadEpubError):
        parse_epub(not_a_zip)


def test_parse_epub_missing_container_xml_raises_bad_epub_error(tmp_path):
    epub = _make_epub(tmp_path / "book.epub", include_container=False)
    with pytest.raises(BadEpubError):
        parse_epub(epub)


def test_parse_epub_missing_opf_raises_bad_epub_error(tmp_path):
    epub = _make_epub(tmp_path / "book.epub", include_opf=False)
    with pytest.raises(BadEpubError):
        parse_epub(epub)
