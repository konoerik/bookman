"""The metadata-source seam: what `identify` needs from an online (or
offline) catalog, independent of which one. Open Library is the first
implementation (identify/openlibrary.py); a second source, a cache, or
a test double plugs in by satisfying `MetadataSource`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bookman.errors import MetadataSourceError


@dataclass
class Candidate:
    """One record a source holds that might describe a file's book.

    Nothing here judges whether it *does* -- that is
    `identify.match.match_basis`'s job.

    Attributes:
        title: The record's title, or None if the source omits it.
        author: The record's author name(s), joined by ", " when the
            source lists several, or None.
        cover_url: Where to download a cover image for this record,
            or None if the source has none.
    """

    title: str | None
    author: str | None
    cover_url: str | None


class MetadataSource(Protocol):
    """A catalog `identify` can ask about a book.

    Implementations must never raise anything but
    `MetadataSourceError` for a failed request; a *missing* record is
    not a failure (return None or an empty list).
    """

    def lookup_by_isbn(self, isbn: str) -> Candidate | None:
        """The record for a normalized ISBN-13, or None if the source
        has none.

        Raises:
            MetadataSourceError: If the request fails.
        """
        ...

    def search(self, title: str, author: str | None = None) -> list[Candidate]:
        """Candidate records for a title (and author, if known), best
        first by the source's own relevance. Empty if nothing matched.

        Raises:
            MetadataSourceError: If the request fails.
        """
        ...

    def fetch_cover(self, url: str) -> bytes:
        """The image bytes behind a `Candidate.cover_url`.

        Raises:
            MetadataSourceError: If the request fails.
        """
        ...


class NullSource:
    """A source that knows nothing: every import is file-only. Use for
    offline runs or when no online lookup is wanted."""

    def lookup_by_isbn(self, isbn: str) -> Candidate | None:
        return None

    def search(self, title: str, author: str | None = None) -> list[Candidate]:
        return []

    def fetch_cover(self, url: str) -> bytes:
        raise MetadataSourceError("NullSource has no covers")


__all__ = ["Candidate", "MetadataSource", "MetadataSourceError", "NullSource"]
