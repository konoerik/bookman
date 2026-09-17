"""EPUB metadata extraction (stdlib zipfile + XML, no external dependency)."""

from __future__ import annotations

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


class BadEpubError(ParseError):
    """Raised when a file is not a readable, well-formed EPUB."""


def parse_epub(path: Path) -> ParsedMetadata:
    """Extract title, author, and ISBN identifiers from an EPUB file.

    Reads META-INF/container.xml to locate the OPF package document,
    then reads dc:title, dc:creator, and dc:identifier from its
    <metadata> block. Candidate identifiers are validated as ISBNs via
    bookman.identify.isbn; non-ISBN identifier schemes (e.g. a bare
    UUID or DOI) are dropped rather than returned.

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
    except zipfile.BadZipFile as exc:
        raise BadEpubError(f"{path}: not a valid EPUB (zip) file") from exc

    metadata_el = _find_metadata_element(opf_xml, path)
    title = _first_text(metadata_el, "dc:title")
    author = _first_text(metadata_el, "dc:creator")
    identifiers = "\n".join(
        el.text for el in metadata_el.findall("dc:identifier", _OPF_NS) if el.text
    )
    isbns = extract_isbns(identifiers) if identifiers else []

    return ParsedMetadata(title=title, author=author, isbns=isbns)


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
