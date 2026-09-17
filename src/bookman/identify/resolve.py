"""Turn a file's own parsed metadata into the best-supported description
of the book: a metadata-source record that agrees with the file, or the
file's metadata alone if nothing online does.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from bookman.formats.base import ParsedMetadata
from bookman.identify.match import is_usable_title, match_basis
from bookman.identify.source import Candidate, MetadataSource, MetadataSourceError
from bookman.models import MatchBasis, stronger_basis

T = TypeVar("T")
_log = logging.getLogger("bookman.identify")


@dataclass
class Identification:
    """What `identify` settled on for one file.

    Attributes:
        title: Resolved title (the file's own, falling back to an
            accepted record's), or None if neither had one.
        author: Resolved author (an accepted record's when the match
            corroborated it, else the file's).
        isbn: The file's ISBN-13, or None if the file had none or its
            ISBN was rejected as not describing this file.
        cover_url: Cover to download for the accepted record, if any.
        basis: How the accepted record was matched to the file, or
            None if no record was accepted and title/author are the
            file's own.
    """

    title: str | None
    author: str | None
    isbn: str | None
    cover_url: str | None
    basis: MatchBasis | None


def identify(parsed: ParsedMetadata, source: MetadataSource) -> Identification:
    """Find a record in `source` that agrees with a file's parsed metadata.

    1. If the file carries an ISBN, look it up. The record is accepted
       only if `match_basis(..., same_isbn=True)` agrees -- i.e. the
       record's title and author don't *both* contradict the file's,
       or, for an ISBN scraped from page text, the titles agree. If
       it's rejected, the ISBN is dropped from the result too, so a
       false-positive ISBN can't later seed an ISBN-based grouping.
    2. Otherwise, if the file has a usable title -- a placeholder like
       "Untitled" is not one -- search by title (and author,
       if known) and accept the best candidate `match_basis` agrees
       with: the strongest basis wins, and among equals the first (in
       the source's relevance order) that has a cover, since a cover
       is half the point of looking the book up. A file with no author
       can only be matched TITLE_ONLY, on an identical normalized title.
    3. If neither step accepted a record, or the lookup failed, return
       the file's own metadata with `basis=None`.

    An accepted record supplies the cover, and the author when the
    match corroborated it (ISBN or TITLE_AUTHOR). On a TITLE_ONLY match
    the record's author is uncorroborated, so it only fills in a file
    that had none. The title stays the file's own: acceptance already
    established that the two agree, and the publisher's spelling in
    the file is usually cleaner than Open Library's crowd-sourced one.
    The record's title is used only when the file has none.

    Args:
        parsed: Metadata extracted from the file by a format parser.
        source: Where to look the book up.

    Returns:
        An Identification. Never raises for a failed or empty lookup.
    """
    isbn: str | None = None
    if parsed.isbns:
        file_isbn = parsed.isbns[0]
        record = _safe(lambda: source.lookup_by_isbn(file_isbn), f"ISBN lookup {file_isbn}")
        if record is None:
            isbn = file_isbn
        else:
            basis = match_basis(
                parsed.title,
                parsed.author,
                record.title,
                record.author,
                same_isbn=True,
                isbn_scraped=parsed.isbns_scraped,
            )
            if basis is not None:
                _log.debug("accepted ISBN %s record %r (%s)", file_isbn, record.title, basis.value)
                return _accepted(parsed, record, file_isbn, basis)
            # The record contradicts the file: this ISBN isn't this book's.
            _log.info(
                "rejected ISBN %s: record %r by %r contradicts file %r by %r",
                file_isbn, record.title, record.author, parsed.title, parsed.author,
            )

    file_title = parsed.title
    if file_title and is_usable_title(file_title):
        candidates = _safe(
            lambda: source.search(file_title, parsed.author), f"search {file_title!r}"
        ) or []
        best: tuple[Candidate, MatchBasis] | None = None
        for record in candidates:
            basis = match_basis(parsed.title, parsed.author, record.title, record.author)
            if basis is None:
                continue
            if best is None or _outranks(record, basis, best):
                best = (record, basis)
        if best is not None:
            record, basis = best
            _log.debug("accepted search hit %r (%s) for %r", record.title, basis.value, file_title)
            return _accepted(parsed, best[0], isbn, best[1])
        _log.info("no agreeing record among %d candidates for %r", len(candidates), file_title)

    return Identification(
        title=parsed.title, author=parsed.author, isbn=isbn, cover_url=None, basis=None
    )


def _outranks(record: Candidate, basis: MatchBasis, best: tuple[Candidate, MatchBasis]) -> bool:
    """Whether (record, basis) should replace the current best candidate:
    a strictly stronger basis, or the same basis with a cover where the
    current best has none."""
    best_record, best_basis = best
    if basis != best_basis:
        return stronger_basis(basis, best_basis) == basis
    return best_record.cover_url is None and record.cover_url is not None


def _accepted(
    parsed: ParsedMetadata, record: Candidate, isbn: str | None, basis: MatchBasis
) -> Identification:
    if basis == MatchBasis.TITLE_ONLY:
        author = parsed.author or record.author
    else:
        author = record.author or parsed.author
    return Identification(
        title=parsed.title or record.title,
        author=author,
        isbn=isbn,
        cover_url=record.cover_url,
        basis=basis,
    )


def _safe(call: Callable[[], T], what: str) -> T | None:
    """Run a lookup, treating a failed request the same as no record
    (logged as a warning, since the outcome is now file-only)."""
    try:
        return call()
    except MetadataSourceError as exc:
        _log.warning("%s failed, continuing without it: %s", what, exc)
        return None
