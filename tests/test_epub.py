import zipfile
from pathlib import Path

import pytest
from helpers import make_epub

from bookman.formats.epub import BadEpubError, extract_cover, parse_epub

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
    # dc:identifier is the publisher's own assertion, not a text scan.
    assert not result.isbns_scraped


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


# --- extract_cover (ADR-28) -----------------------------------------------

JPEG = b"\xff\xd8\xff\xe0 not really a jpeg"


@pytest.mark.parametrize("declared", ["properties", "meta", "id"])
def test_extract_cover_reads_the_declared_cover_image(tmp_path, declared):
    # The three ways the first real bundle declared a cover: EPUB 3
    # properties="cover-image", EPUB 2 <meta name="cover">, and a
    # manifest item merely called "cover".
    epub = make_epub(tmp_path / "b.epub", cover=JPEG, cover_declared=declared)
    assert extract_cover(epub) == JPEG


def test_extract_cover_returns_none_when_nothing_is_declared(tmp_path):
    epub = make_epub(tmp_path / "b.epub")
    assert extract_cover(epub) is None


def test_extract_cover_returns_none_when_the_declared_member_is_missing(tmp_path):
    epub = make_epub(tmp_path / "b.epub", cover=JPEG)
    with zipfile.ZipFile(epub) as zf:
        members = {n: zf.read(n) for n in zf.namelist() if not n.endswith(".jpg")}
    with zipfile.ZipFile(epub, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    assert extract_cover(epub) is None


def test_extract_cover_never_raises_for_an_unreadable_file(tmp_path):
    bad = tmp_path / "b.epub"
    bad.write_bytes(b"not a zip")
    assert extract_cover(bad) is None


def _make_epub_with_spine(path: Path, documents: list[str], *, identifiers=()) -> Path:
    """An EPUB whose spine is `documents`, in reading order, each an
    XHTML body with the given text (FIELD-NOTES FN-21's shape)."""
    items = "".join(
        f'<item id="d{n}" href="text/d{n}.xhtml" media-type="application/xhtml+xml"/>'
        for n in range(len(documents))
    )
    spine = "".join(f'<itemref idref="d{n}"/>' for n in range(len(documents)))
    ids = "".join(f"<dc:identifier>{i}</dc:identifier>" for i in identifiers)
    opf = (
        '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="2.0">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>T</dc:title>'
        f"{ids}</metadata><manifest>{items}</manifest><spine>{spine}</spine></package>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("OEBPS/content.opf", opf)
        for n, text in enumerate(documents):
            zf.writestr(
                f"OEBPS/text/d{n}.xhtml",
                f'<html xmlns="http://www.w3.org/1999/xhtml"><body><p>{text}</p></body></html>',
            )
    return path


OTHER_ISBN13 = "9781801815727"


def test_parse_epub_scans_front_matter_when_the_metadata_has_no_isbn(tmp_path):
    # FIELD-NOTES FN-21 (Packt): dc:identifier is only a urn:uuid; the
    # ISBN is on the title page. Found there, it counts as scraped.
    epub = _make_epub_with_spine(
        tmp_path / "book.epub",
        ["Cover", f"Title page. ISBN {VALID_ISBN13}", "Contributors", "Preface"],
        identifiers=["urn:uuid:9a4d0a36-4002-459a-a7f2-5b4d879c57b9"],
    )
    result = parse_epub(epub)
    assert result.isbns == [VALID_ISBN13]
    assert result.isbns_scraped


def test_parse_epub_does_not_scan_past_the_front_matter(tmp_path):
    # Chapters cite editions and back matter advertises other books.
    epub = _make_epub_with_spine(
        tmp_path / "book.epub",
        ["Cover", "Title page", "Contributors", "Preface", f"Chapter 1 cites {OTHER_ISBN13}"],
    )
    assert parse_epub(epub).isbns == []


def test_parse_epub_ignores_isbns_in_markup(tmp_path):
    # Packt names images after other books' ISBNs; only text counts.
    epub = _make_epub_with_spine(
        tmp_path / "book.epub", [f'<img src="{OTHER_ISBN13}.png"/>Title page']
    )
    assert parse_epub(epub).isbns == []


def test_parse_epub_does_not_scan_when_the_metadata_declares_an_isbn(tmp_path):
    epub = _make_epub_with_spine(
        tmp_path / "book.epub", [f"Title page. ISBN {OTHER_ISBN13}"], identifiers=[VALID_ISBN13]
    )
    result = parse_epub(epub)
    assert result.isbns == [VALID_ISBN13]
    assert not result.isbns_scraped


def test_parse_epub_without_a_spine_still_parses(tmp_path):
    assert parse_epub(_make_epub(tmp_path / "book.epub")).isbns == []
