"""The parser contract and the suffix registry every format plugs into.

Kept apart from `bookman.formats.__init__` so parser modules can import
the contract without a circular import; `__init__` registers the
built-in parsers and re-exports everything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from bookman.errors import UnsupportedFormatError
from bookman.models import FormatKind


@dataclass
class ParsedMetadata:
    """Metadata extracted directly from a single ebook file."""

    title: str | None
    author: str | None
    isbns: list[str] = field(default_factory=list)


class FormatParser(Protocol):
    """What a format parser is: a callable from a file path to its
    metadata. `parse_epub` and `parse_pdf` satisfy it as plain
    functions; a class with `__call__` would too.

    A parser raises a `ParseError` subclass when the file is not what
    its suffix claims, and never returns None -- missing fields are
    None on the ParsedMetadata.
    """

    def __call__(self, path: Path) -> ParsedMetadata: ...


_REGISTRY: dict[str, tuple[FormatKind, FormatParser]] = {}


def register(suffix: str, kind: FormatKind, parser: FormatParser) -> None:
    """Make files with `suffix` importable as `kind` via `parser`.

    Args:
        suffix: File extension including the dot, any case (".epub").
        kind: The FormatKind such files are cataloged as.
        parser: The function that reads their metadata.
    """
    _REGISTRY[suffix.lower()] = (kind, parser)


def supported_suffixes() -> tuple[str, ...]:
    """The file extensions (lower-case, with the dot) that have a
    registered parser, sorted. What `Library.import_directory` will
    import; anything else it reports as skipped.
    """
    return tuple(sorted(_REGISTRY))


def is_supported(path: Path) -> bool:
    """Whether `path`'s suffix has a registered parser (case-insensitive)."""
    return path.suffix.lower() in _REGISTRY


def parser_for(path: Path) -> tuple[FormatKind, FormatParser]:
    """The kind and parser registered for `path`'s suffix.

    Raises:
        UnsupportedFormatError: If no parser is registered for it.
    """
    try:
        return _REGISTRY[path.suffix.lower()]
    except KeyError as exc:
        raise UnsupportedFormatError(f"no parser registered for {path.suffix!r}") from exc
