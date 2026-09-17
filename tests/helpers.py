"""Shared test scaffolding: a scriptable MetadataSource and builders for
minimal but valid EPUB/PDF files. Imported by name (`from helpers import
...`); pytest puts tests/ on sys.path."""

from __future__ import annotations

import zipfile
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from bookman.identify.source import Candidate, MetadataSourceError

VALID_ISBN13 = "9780306406157"

CONTAINER_XML = b"""<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


class FakeSource:
    """A `MetadataSource` whose answers are plain attributes, so a test
    can script them up front or change them between imports.

    Attributes:
        record: What `lookup_by_isbn` returns for *any* ISBN (None =
            the source has no record).
        results: What `search` returns for *any* query.
        cover: What `fetch_cover` returns; None makes it raise
            `MetadataSourceError`, like a failed download.
        fail: When True, every lookup and search raises
            `MetadataSourceError` -- the network is down.
        calls: Every call made, as ("lookup_by_isbn", isbn),
            ("search", title, author) or ("fetch_cover", url) tuples.
    """

    def __init__(
        self,
        *,
        record: Candidate | None = None,
        results: list[Candidate] | None = None,
        cover: bytes | None = None,
        fail: bool = False,
    ) -> None:
        self.record = record
        self.results = list(results or [])
        self.cover = cover
        self.fail = fail
        self.calls: list[tuple[str, ...]] = []

    def lookup_by_isbn(self, isbn: str) -> Candidate | None:
        self.calls.append(("lookup_by_isbn", isbn))
        if self.fail:
            raise MetadataSourceError("boom")
        return self.record

    def search(self, title: str, author: str | None = None) -> list[Candidate]:
        self.calls.append(("search", title, author or ""))
        if self.fail:
            raise MetadataSourceError("boom")
        return list(self.results)

    def fetch_cover(self, url: str) -> bytes:
        self.calls.append(("fetch_cover", url))
        if self.cover is None:
            raise MetadataSourceError("boom")
        return self.cover

    def called(self, method: str) -> bool:
        return any(call[0] == method for call in self.calls)


def opf_xml(*, title: str | None = None, author: str | None = None, identifiers=()) -> bytes:
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


def make_epub(
    path: Path, *, title: str | None = "A Title", author: str | None = None, identifiers=()
) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr(
            "OEBPS/content.opf",
            opf_xml(title=title, author=author, identifiers=identifiers),
        )
    return path


def make_pdf(
    path: Path, *, title: str | None = "A Title", author: str | None = None, text: str = ""
) -> Path:
    writer = PdfWriter()
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

    metadata = {}
    if title is not None:
        metadata["/Title"] = title
    if author is not None:
        metadata["/Author"] = author
    if metadata:
        writer.add_metadata(metadata)

    with open(path, "wb") as f:
        writer.write(f)
    return path
