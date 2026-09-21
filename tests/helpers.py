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
        records: Per-ISBN answers that take precedence over `record`,
            for scripting a file that carries several ISBNs.
        results: What `search` returns for *any* query.
        cover: What `fetch_cover` returns; None makes it raise
            `MetadataSourceError`, like a failed download.
        fail: When True, every lookup and search raises
            `MetadataSourceError` -- the network is down.
        fail_isbns: ISBNs whose lookup alone raises, for a source that
            is up but chokes on one request.
        calls: Every call made, as ("lookup_by_isbn", isbn),
            ("search", title, author) or ("fetch_cover", url) tuples.
    """

    def __init__(
        self,
        *,
        record: Candidate | None = None,
        records: dict[str, Candidate | None] | None = None,
        results: list[Candidate] | None = None,
        cover: bytes | None = None,
        fail: bool = False,
    ) -> None:
        self.record = record
        self.records = dict(records or {})
        self.results = list(results or [])
        self.cover = cover
        self.fail = fail
        self.fail_isbns: set[str] = set()
        self.calls: list[tuple[str, ...]] = []

    def lookup_by_isbn(self, isbn: str) -> Candidate | None:
        self.calls.append(("lookup_by_isbn", isbn))
        if self.fail or isbn in self.fail_isbns:
            raise MetadataSourceError("boom")
        return self.records.get(isbn, self.record)

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


COVER_MEMBER = "images/front.jpg"  # relative to the OPF, as hrefs are


def opf_xml(
    *,
    title: str | None = None,
    author: str | None = None,
    identifiers=(),
    cover_declared: str | None = None,
) -> bytes:
    """An OPF package document. `cover_declared` adds a manifest item for
    `COVER_MEMBER` and points at it the way one generation of EPUBs
    does: "properties" (EPUB 3 `properties="cover-image"`), "meta"
    (EPUB 2 `<meta name="cover">`) or "id" (an item just called
    `cover`, nothing else marking it).
    """
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
    if cover_declared == "meta":
        parts.append('<meta name="cover" content="img1"/>')
    parts.append("</metadata>")
    if cover_declared is not None:
        item_id = "cover" if cover_declared == "id" else "img1"
        props = ' properties="cover-image"' if cover_declared == "properties" else ""
        parts.append(
            "<manifest>"
            '<item id="text" href="text.xhtml" media-type="application/xhtml+xml"/>'
            f'<item id="{item_id}" href="{COVER_MEMBER}" media-type="image/jpeg"{props}/>'
            "</manifest>"
        )
    parts.append("</package>")
    return "".join(parts).encode("utf-8")


def make_epub(
    path: Path,
    *,
    title: str | None = "A Title",
    author: str | None = None,
    identifiers=(),
    cover: bytes | None = None,
    cover_declared: str = "properties",
) -> Path:
    """Write a minimal EPUB. `cover` embeds those bytes as the cover
    image, declared per `cover_declared` (see `opf_xml`)."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr(
            "OEBPS/content.opf",
            opf_xml(
                title=title,
                author=author,
                identifiers=identifiers,
                cover_declared=cover_declared if cover is not None else None,
            ),
        )
        if cover is not None:
            zf.writestr(f"OEBPS/{COVER_MEMBER}", cover)
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
