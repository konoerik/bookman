"""EPUB metadata extraction (stdlib zipfile + XML, no external dependency)."""

from __future__ import annotations

import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from bookman.errors import ParseError
from bookman.formats.base import ParsedMetadata
from bookman.identify.isbn import extract_isbns

_CONTAINER_PATH = "META-INF/container.xml"
_CONTAINER_NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
_OPF_NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}


# How much of the reading order is front matter worth scanning for an ISBN
# when the metadata declares none (ADR-33). Packt puts the ebook ISBN on
# the title page (spine document 1) and in the preface (3); chapters cite
# other editions and back matter advertises other books.
_ISBN_SCAN_DOCUMENTS = 4
_MARKUP = re.compile(r"<[^>]*>")


class BadEpubError(ParseError):
    """Raised when a file is not a readable, well-formed EPUB."""


def parse_epub(path: Path) -> ParsedMetadata:
    """Extract title, author, and ISBN identifiers from an EPUB file.

    Reads META-INF/container.xml to locate the OPF package document,
    then reads dc:title, dc:creator, and dc:identifier from its
    <metadata> block. Candidate identifiers are validated as ISBNs via
    bookman.identify.isbn; non-ISBN identifier schemes (e.g. a bare
    UUID or DOI) are dropped rather than returned.

    When no identifier is a valid ISBN, the text of the first
    `_ISBN_SCAN_DOCUMENTS` documents of the spine -- the title page,
    copyright page and preface -- is scanned instead, and anything found
    is flagged `isbns_scraped` like a PDF's (ADR-33): page text may cite
    another book.

    Args:
        path: Path to a .epub file.

    Returns:
        ParsedMetadata with whatever fields could be found. A missing
        title or author is returned as None rather than raising;
        `isbns` is empty (not None) when no valid ISBN is present.

    Raises:
        FileNotFoundError: If path does not exist.
        BadEpubError: If the file is not a valid zip, or container.xml
            or the OPF package document is missing or unparseable.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            container_xml = _read_member(archive, _CONTAINER_PATH, path)
            opf_path = _find_opf_path(container_xml, path)
            opf_xml = _read_member(archive, opf_path, path)
            metadata_el = _find_metadata_element(opf_xml, path)
            identifiers = "\n".join(
                el.text for el in metadata_el.findall("dc:identifier", _OPF_NS) if el.text
            )
            isbns = extract_isbns(identifiers) if identifiers else []
            scraped = not isbns
            if scraped:
                isbns = extract_isbns(_front_matter_text(archive, opf_path, opf_xml))
    except zipfile.BadZipFile as exc:
        raise BadEpubError(f"{path}: not a valid EPUB (zip) file") from exc

    title = _first_text(metadata_el, "dc:title")
    author = _first_text(metadata_el, "dc:creator")
    return ParsedMetadata(title=title, author=author, isbns=isbns, isbns_scraped=scraped)


def _front_matter_text(archive: zipfile.ZipFile, opf_path: str, opf_xml: bytes) -> str:
    """The text, markup stripped, of the first `_ISBN_SCAN_DOCUMENTS`
    spine documents. Empty when there is no spine or a document is
    missing -- this is a best-effort scan, not a validity check."""
    root = ET.fromstring(opf_xml)
    manifest = root.find("opf:manifest", _OPF_NS)
    spine = root.find("opf:spine", _OPF_NS)
    if manifest is None or spine is None:
        return ""
    hrefs = {item.get("id"): item.get("href") for item in manifest.findall("opf:item", _OPF_NS)}
    base = posixpath.dirname(opf_path)
    texts = []
    for itemref in spine.findall("opf:itemref", _OPF_NS)[:_ISBN_SCAN_DOCUMENTS]:
        href = hrefs.get(itemref.get("idref"))
        if not href:
            continue
        try:
            document = archive.read(posixpath.normpath(posixpath.join(base, href)))
        except KeyError:
            continue
        texts.append(_MARKUP.sub(" ", document.decode("utf-8", errors="replace")))
    return "\n".join(texts)


def extract_cover(path: Path) -> bytes | None:
    """Return the bytes of the cover image an EPUB declares, if any.

    Looks in the OPF package document, in order of authority: the
    EPUB 3 manifest item with `properties="cover-image"`; the EPUB 2
    `<meta name="cover" content="…">` pointing at a manifest item; a
    manifest image item whose id is `cover` or `cover-image`. The
    first that names a member actually in the archive wins. The
    image is returned as stored -- JPEG or PNG, undeclared -- since
    there is no image library to convert it with.

    Spec: IDENT-6 (ADR-28). Best-effort by design: a cover is never
    worth failing an import over, so nothing here raises.

    Args:
        path: Path to a .epub file.

    Returns:
        The image bytes, or None if the file declares no cover, the
        declared member is missing, or the file is not a readable EPUB.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            opf_path = _find_opf_path(_read_member(archive, _CONTAINER_PATH, path), path)
            root = ET.fromstring(_read_member(archive, opf_path, path))
            for href in _cover_hrefs(root):
                member = posixpath.normpath(posixpath.join(posixpath.dirname(opf_path), href))
                try:
                    return archive.read(member)
                except KeyError:
                    continue
    except (OSError, zipfile.BadZipFile, BadEpubError, ET.ParseError):
        return None
    return None


def _cover_hrefs(root: ET.Element) -> list[str]:
    """Candidate cover hrefs from an OPF root, most authoritative first."""
    manifest = root.find("opf:manifest", _OPF_NS)
    if manifest is None:
        return []
    items = {item.attrib.get("id", ""): item for item in manifest.findall("opf:item", _OPF_NS)}
    images = {
        item_id: item
        for item_id, item in items.items()
        if item.attrib.get("media-type", "").startswith("image/") and "href" in item.attrib
    }
    ordered: list[ET.Element] = []
    ordered += [
        i for i in images.values() if "cover-image" in i.attrib.get("properties", "").split()
    ]
    metadata = root.find("opf:metadata", _OPF_NS)
    if metadata is not None:
        for meta in metadata.findall("opf:meta", _OPF_NS):
            if meta.attrib.get("name") == "cover" and meta.attrib.get("content") in images:
                ordered.append(images[meta.attrib["content"]])
    ordered += [i for item_id, i in images.items() if item_id.lower() in ("cover", "cover-image")]
    hrefs: list[str] = []
    for item in ordered:
        if item.attrib["href"] not in hrefs:
            hrefs.append(item.attrib["href"])
    return hrefs


def _read_member(archive: zipfile.ZipFile, member: str, path: Path) -> bytes:
    try:
        return archive.read(member)
    except KeyError as exc:
        raise BadEpubError(f"{path}: missing {member!r}") from exc


def _find_opf_path(container_xml: bytes, path: Path) -> str:
    try:
        root = ET.fromstring(container_xml)
    except ET.ParseError as exc:
        raise BadEpubError(f"{path}: container.xml is not valid XML") from exc
    rootfile = root.find(".//c:rootfile", _CONTAINER_NS)
    if rootfile is None or "full-path" not in rootfile.attrib:
        raise BadEpubError(f"{path}: container.xml has no rootfile full-path")
    return rootfile.attrib["full-path"]


def _find_metadata_element(opf_xml: bytes, path: Path) -> ET.Element:
    try:
        root = ET.fromstring(opf_xml)
    except ET.ParseError as exc:
        raise BadEpubError(f"{path}: OPF package document is not valid XML") from exc
    metadata_el = root.find("opf:metadata", _OPF_NS)
    if metadata_el is None:
        raise BadEpubError(f"{path}: OPF package document has no <metadata>")
    return metadata_el


def _first_text(metadata_el: ET.Element, tag: str) -> str | None:
    el = metadata_el.find(tag, _OPF_NS)
    if el is None or not el.text:
        return None
    text = el.text.strip()
    return text or None
