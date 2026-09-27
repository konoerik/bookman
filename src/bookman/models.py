"""Core value objects: a Book and the on-disk formats that back it."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from uuid import uuid4


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


class ReadIssue(str, Enum):
    """Why bookman could not read inside a file it still imported.

    Such a file is really of its format -- intact, and a book the user
    bought -- but its contents are closed to bookman, so it was
    cataloged on its filename alone (spec PR6, ADR-29). Recorded on the
    `BookFormat`, not the `Book`: a book whose other format was readable
    is not the worse for it. `advice` is the sentence to show the user.
    """

    NEEDS_CRYPTO = "needs_crypto"
    """Encrypted with AES, and bookman's optional crypto support is not installed."""

    PASSWORD = "password"
    """Protected by a password, and an empty one does not open it."""

    UNSUPPORTED_ENCRYPTION = "unsupported_encryption"
    """Declares encryption bookman cannot handle: a DRM security handler,
    or an encryption entry too damaged to read."""

    @property
    def advice(self) -> str:
        """What happened and what to do about it, as one sentence for a
        person: the next step is always named."""
        return _READ_ISSUE_ADVICE[self]


_READ_ISSUE_ADVICE = {
    ReadIssue.NEEDS_CRYPTO: (
        "the file is encrypted and bookman's optional crypto support is not installed, "
        "so bookman named the book after the file; install bookman[crypto], then delete "
        "this book's folder and import the file again to read its title, author and ISBN"
    ),
    ReadIssue.PASSWORD: (
        "the file is protected by a password, so bookman named the book after the file; "
        "check its title and author, and correct them by hand if needed"
    ),
    ReadIssue.UNSUPPORTED_ENCRYPTION: (
        "the file uses encryption bookman cannot read (DRM, or a damaged encryption entry), "
        "so bookman named the book after the file; check its title and author, "
        "and correct them by hand if needed"
    ),
}


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
    """A single on-disk file representing one format of a Book.

    Attributes:
        kind: The file's format.
        path: Where the file is, inside the book's folder.
        read_issue: Why bookman could not read inside this file, or None
            if it could. The book was named after the file, so a
            later, readable import of the same file is a different book
            to bookman: the way back is to delete the folder and import
            again, which is what `ReadIssue.advice` says.
    """

    kind: FormatKind
    path: Path
    read_issue: ReadIssue | None = None


@dataclass
class Book:
    """A logical ebook: one title, one or more on-disk formats.

    Attributes:
        id: Stable identity, minted once and stored in metadata.json.
            Unlike `directory` it survives a rename of the book's
            folder, so a frontend can select a book, edit its title,
            and still be talking about the same book afterwards
            (ADR-17). Always set: a Book built in memory gets a fresh
            one, a Book loaded from disk gets the stored one.
        title: Display title.
        author: Author name(s), or None if unknown. The file's own
            spelling when the file had one (ADR-22).
        record_author: What the metadata source's record named as the
            author, kept as provenance beside `author` so a frontend can
            show "Open Library says ..." and offer it as the alternative
            spelling. None when no record was accepted. A difference
            from `author` is not a review signal.
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
        directory: The book's folder in the managed library -- where
            it lives, and its display name. None until the book has
            been persisted; set by every operation that reads or
            writes metadata.json. Not the book's identity since
            ADR-17: use `id` for that, because a title edit renames
            this folder.
    """

    title: str
    author: str | None
    isbn: str | None
    id: str = field(default_factory=lambda: uuid4().hex)
    record_author: str | None = None
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
