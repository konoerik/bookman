"""Read/write a Book's metadata.json sidecar — the library's source of truth.

Each managed book folder holds a metadata.json alongside its format files
and cover. It is the durable record; any search index (see storage/index.py)
is a disposable cache rebuilt from these files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from bookman.errors import CatalogError
from bookman.models import Book, BookFormat, FormatKind, MatchBasis

_METADATA_FILENAME = "metadata.json"
_SCHEMA_VERSION = 4
# Versions whose fields this module understands directly. Version 1 is
# handled separately, by migration.
_MODERN_VERSIONS = (2, 3, _SCHEMA_VERSION)

# Namespace for deriving an id for a pre-version-3 book that has none
# stored. Deterministic, so repeated reads of an un-upgraded file agree
# on the same id instead of minting a new one each time (ADR-17).
_LEGACY_ID_NAMESPACE = uuid5(NAMESPACE_URL, "https://bookman.local/metadata-id")

# Version-1 files had a single `confidence` field; map it onto the split
# model. "verified" could only have come from an exact-ISBN lookup.
_V1_CONFIDENCE_TO_IDENTIFIED = {
    "verified": MatchBasis.ISBN,
    "needs_review": None,
}


def save_metadata(book: Book, directory: Path) -> None:
    """Write a Book's metadata to <directory>/metadata.json (schema version 4).

    Serializes id, title, author, record_author, isbn, identified,
    grouped, reviewed, and
    each format's kind and filename (relative to `directory`, not the
    absolute path stored on `BookFormat.path`), plus the cover filename
    if `book.cover_path` is set. Overwrites any existing metadata.json
    in `directory`, upgrading an older-version file in place. On
    success `book.directory` is set to `directory`.

    Args:
        book: The book to serialize. Every `book.formats[*].path` and
            `book.cover_path`, if set, must be located directly inside
            `directory` (as they would be after a prior scan of that
            directory). If `book.directory` is already set it must be
            `directory`: a book is never silently re-homed. `book.id`
            is written as-is, so a book that moves folders keeps its
            identity (ADR-17).
        directory: The book's folder in the managed library.

    Raises:
        CatalogError: If any format path or the cover path is not inside
            `directory`, or `book.directory` names a different folder.
        OSError: If `directory` does not exist or metadata.json cannot
            be written.
    """
    if book.directory is not None and book.directory.resolve() != directory.resolve():
        raise CatalogError(f"book lives in {book.directory}, not {directory}")
    data = {
        "version": _SCHEMA_VERSION,
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "record_author": book.record_author,
        "isbn": book.isbn,
        "identified": book.identified.value if book.identified else None,
        "grouped": book.grouped.value if book.grouped else None,
        "reviewed": book.reviewed,
        "formats": [
            {"kind": fmt.kind.value, "filename": _relative_filename(fmt.path, directory)}
            for fmt in book.formats
        ],
        "cover": _relative_filename(book.cover_path, directory) if book.cover_path else None,
    }
    target = directory / _METADATA_FILENAME
    tmp = directory / f"{_METADATA_FILENAME}.tmp"
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, target)
    book.directory = directory


def load_metadata(directory: Path) -> Book:
    """Read a Book back from <directory>/metadata.json.

    Reconstructs `BookFormat.path` and `Book.cover_path` (if present)
    as `directory / <stored filename>` — paths are always resolved
    against the directory actually passed in, not any path recorded at
    save time, so a relocated library folder still loads correctly.
    `Book.directory` is set to `directory` for the same reason: where a
    book lives is never stored inside the file. What *is* stored is
    `Book.id`, the book's identity since ADR-17 — the folder name is a
    display name that a title edit will change.

    A version-1 file (no `version` key; a single `confidence` field)
    is migrated on read: "verified" becomes `identified=ISBN`,
    "needs_review" becomes `identified=None`; `grouped` is None and
    `reviewed` False either way.

    A pre-version-3 file carries no `id`. Rather than mint a fresh one
    per read -- which would make the identity unstable, defeating its
    purpose -- one is *derived* from the folder name, so every read of
    an un-upgraded book agrees. It becomes a stored id the next time
    the book is saved, and from then on survives a rename (ADR-17).

    The file on disk is upgraded the next time it is saved.

    Args:
        directory: The book's folder in the managed library.

    Returns:
        The Book as it was last saved.

    Raises:
        FileNotFoundError: If `directory/metadata.json` does not exist.
        CatalogError: If metadata.json exists but is not valid JSON, is
            missing a required field, has an unrecognized
            FormatKind/MatchBasis/confidence value, schema version or
            id, or names a format/cover filename that would resolve
            outside `directory` (e.g. via a path separator or `..`).
    """
    path = directory / _METADATA_FILENAME
    if not path.exists():
        raise FileNotFoundError(path)

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise CatalogError(f"{path}: invalid JSON") from exc

    try:
        formats = [
            BookFormat(
                kind=FormatKind(fmt["kind"]),
                path=_resolve_filename(fmt["filename"], directory, path),
            )
            for fmt in data["formats"]
        ]
        cover = data.get("cover")
        identified, grouped, reviewed = _read_match_fields(data)
        return Book(
            id=_read_id(data, directory),
            title=data["title"],
            author=data["author"],
            # Added in version 4; absent from older files.
            record_author=data.get("record_author"),
            isbn=data["isbn"],
            formats=formats,
            cover_path=_resolve_filename(cover, directory, path) if cover else None,
            identified=identified,
            grouped=grouped,
            reviewed=reviewed,
            directory=directory,
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise CatalogError(f"{path}: {exc}") from exc


_MatchFields = tuple["MatchBasis | None", "MatchBasis | None", bool]


def _read_match_fields(data: dict[str, object]) -> _MatchFields:
    version = data.get("version", 1)
    if version == 1:
        confidence = data["confidence"]
        if confidence not in _V1_CONFIDENCE_TO_IDENTIFIED:
            raise ValueError(f"unrecognized confidence {confidence!r}")
        return _V1_CONFIDENCE_TO_IDENTIFIED[str(confidence)], None, False
    if version not in _MODERN_VERSIONS:
        raise ValueError(f"unsupported metadata schema version {version!r}")
    identified = data["identified"]
    grouped = data["grouped"]
    reviewed = data["reviewed"]
    if not isinstance(reviewed, bool):
        raise ValueError(f"reviewed must be a boolean, got {reviewed!r}")
    return (
        MatchBasis(identified) if identified is not None else None,
        MatchBasis(grouped) if grouped is not None else None,
        reviewed,
    )


def _read_id(data: dict[str, object], directory: Path) -> str:
    """The book's stored id, or one derived from its folder name for a
    file written before schema version 3."""
    stored = data.get("id")
    if stored is None:
        return uuid5(_LEGACY_ID_NAMESPACE, directory.name).hex
    if not isinstance(stored, str) or not stored.strip():
        raise ValueError(f"id must be a non-empty string, got {stored!r}")
    return stored


def _relative_filename(path: Path, directory: Path) -> str:
    if path.parent.resolve() != directory.resolve():
        raise CatalogError(f"{path} is not inside {directory}")
    return path.name


def _resolve_filename(filename: str, directory: Path, context_path: Path) -> Path:
    candidate = directory / filename
    if candidate.resolve().parent != directory.resolve():
        raise CatalogError(f"{context_path}: filename {filename!r} escapes {directory}")
    return candidate
