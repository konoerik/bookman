"""Core value objects: a Book and the on-disk formats that back it."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class FormatKind(str, Enum):
    """Ebook file formats bookman can catalog."""

    EPUB = "epub"
    PDF = "pdf"
    MOBI = "mobi"


class MatchBasis(str, Enum):
    """The evidence on which two descriptions of a book were judged to be
    the same book -- used both for "this file is this Open Library record"
    (`Book.identified`) and "this file belongs in this folder"
    (`Book.grouped`). Listed strongest first.
    """

    ISBN = "isbn"
    """Identical normalized ISBN-13 (with title/author not both contradicting it)."""

    TITLE_AUTHOR = "title_author"
    """Normalized titles agree and the authors share a surname."""

    TITLE_ONLY = "title_only"
    """Normalized titles are identical, but an author was missing on one
    side so nothing corroborated it."""


_BASIS_STRENGTH = {
    MatchBasis.ISBN: 3,
    MatchBasis.TITLE_AUTHOR: 2,
    MatchBasis.TITLE_ONLY: 1,
}


def weaker_basis(a: MatchBasis | None, b: MatchBasis | None) -> MatchBasis | None:
    """Return the weaker of two match bases; None (no evidence either way)
    is ignored, so `weaker_basis(None, x)` is `x`.
    """
    if a is None:
        return b
    if b is None:
        return a
    return a if _BASIS_STRENGTH[a] <= _BASIS_STRENGTH[b] else b


def stronger_basis(a: MatchBasis | None, b: MatchBasis | None) -> MatchBasis | None:
    """Return the stronger of two match bases; None loses to anything."""
    if a is None:
        return b
    if b is None:
        return a
    return a if _BASIS_STRENGTH[a] >= _BASIS_STRENGTH[b] else b


@dataclass(frozen=True)
class BookFormat:
    """A single on-disk file representing one format of a Book."""

    kind: FormatKind
    path: Path


@dataclass
class Book:
    """A logical ebook: one title, one or more on-disk formats.

    Attributes:
        title: Display title.
        author: Author name(s), or None if unknown.
        isbn: An ISBN-13 found in one of the book's files, or None.
        formats: The format files on disk for this book.
        cover_path: The cover image on disk, if one was fetched.
        identified: How the Open Library record that supplied this
            book's metadata was matched to the file, or None if no
            online record agreed with the file and the metadata is
            only what the file itself said.
        grouped: The weakest evidence that ever joined a second format
            file into this book's folder, or None if nothing has been
            grouped yet (single format so far).
        reviewed: A human has confirmed or corrected this book. Imports
            add formats to a reviewed book but never overwrite its
            title/author/isbn/cover/identified. A TITLE_ONLY grouping
            into a reviewed book clears the flag, since the book's
            contents changed in a way that deserves another look.
        directory: The book's folder in the managed library -- its
            identity (ADR-11). None until the book has been persisted;
            set by every operation that reads or writes metadata.json.
    """

    title: str
    author: str | None
    isbn: str | None
    formats: list[BookFormat] = field(default_factory=list)
    cover_path: Path | None = None
    identified: MatchBasis | None = None
    grouped: MatchBasis | None = None
    reviewed: bool = False
    directory: Path | None = None

    @property
    def needs_review(self) -> bool:
        """Whether a human should look at this book.

        False once `reviewed` is set. Otherwise True when the metadata
        was never corroborated online (`identified` is None) or only
        weakly (TITLE_ONLY), or when formats were grouped on
        title-only evidence.
        """
        if self.reviewed:
            return False
        return (
            self.identified is None
            or self.identified == MatchBasis.TITLE_ONLY
            or self.grouped == MatchBasis.TITLE_ONLY
        )
