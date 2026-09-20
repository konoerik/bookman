"""Turn a file's own parsed metadata into the best-supported description
of the book: a metadata-source record that agrees with the file, or the
file's metadata alone if nothing online does.

This module is the Identify stage of `docs/IDENTIFICATION.md` (steps
IDENT-1..6). Log lines name the step that produced them, so one book's
path through the pipeline can be read off without stepping through code.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TypeVar

from bookman.formats.base import ParsedMetadata
from bookman.identify.match import is_usable_author, is_usable_title, match_basis
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
        author: Resolved author (the file's own, falling back to an
            accepted record's), or None if neither had one. A file
            author that was only a stand-in ("Unknown") counts as none.
        isbn: The file's ISBN-13, or None if the file had none or its
            ISBN was rejected as not describing this file.
        cover_url: Cover to download for the accepted record, if any.
        basis: How the accepted record was matched to the file, or
            None if no record was accepted and title/author are the
            file's own.
        record_author: What the accepted record said the author is,
            kept as provenance so a frontend can offer it beside the
            file's own spelling (ADR-22). None if no record was
            accepted or it named no author.
    """

    title: str | None
    author: str | None
    isbn: str | None
    cover_url: str | None
    basis: MatchBasis | None
    record_author: str | None = None


def identify(parsed: ParsedMetadata, source: MetadataSource) -> Identification:
    """Find a record in `source` that agrees with a file's parsed metadata.

    Spec: IDENT-1..6.

    1. If the file carries ISBNs, look each up in turn until one is
       accepted. A record is accepted only if
       `match_basis(..., same_isbn=True)` agrees -- i.e. the record's
       title and author don't *both* contradict the file's, or, for an
       ISBN scraped from page text, the titles agree. A rejected ISBN
       is dropped from the result, so a false-positive ISBN can't later
       seed an ISBN-based grouping; an ISBN the source doesn't know is
       kept (the first such one, if several) as the file's own claim.
    2. Otherwise, if the file has a usable title -- a placeholder like
       "Untitled" is not one -- search by title (and author,
       if known) and accept the best candidate `match_basis` agrees
       with: the strongest basis wins, and among equals the first (in
       the source's relevance order) that has a cover, since a cover
       is half the point of looking the book up. A file with no author
       can only be matched TITLE_ONLY, on an identical normalized title.
    3. If neither step accepted a record, or the lookup failed, return
       the file's own metadata with `basis=None`.

    An accepted record supplies the cover. The title and author stay
    the file's own: acceptance already established that the two agree,
    the publisher's spelling in the file is usually cleaner than Open
    Library's crowd-sourced one, and the record's author list is the
    work's -- every edition's contributors, narrators included -- while
    the file names who wrote this one (ADR-22). The record's title and
    author are used only when the file has none; the record's author is
    also kept as `record_author` for a frontend to offer. A file author
    that is only a stand-in ("Unknown", "N/A") counts as none.

    Args:
        parsed: Metadata extracted from the file by a format parser.
        source: Where to look the book up.

    Returns:
        An Identification. Never raises for a failed or empty lookup
        (spec PR1: identification is advisory, never blocking).
    """
    if parsed.author is not None and not is_usable_author(parsed.author):
        # IDENT-6's stand-in rule, applied up front so every path below
        # -- match, accept, or file-only -- sees the file as authorless.
        _log.debug("IDENT-6 ignoring stand-in author %r", parsed.author)
        parsed = replace(parsed, author=None)

    isbn: str | None = None
    # IDENT-1: try each ISBN in turn until one is accepted. A file can
    # legitimately carry the print and ebook ISBNs, or a cited list; the
    # first is not privileged.
    for file_isbn in parsed.isbns:
        # IDENT-2: a failed lookup and an unknown ISBN are both "no record".
        record = _safe(
            functools.partial(source.lookup_by_isbn, file_isbn),
            f"IDENT-2 ISBN lookup {file_isbn}",
        )
        if record is None:
            # IDENT-2: keep the ISBN -- it is the file's own claim, and the
            # source not knowing it proves nothing. The first such claim
            # stands; the parser already ordered them best first.
            _log.debug("IDENT-2 no record for ISBN %s", file_isbn)
            if isbn is None:
                isbn = file_isbn
            continue
        # IDENT-3: cross-check the record against the file.
        basis = match_basis(
            parsed.title,
            parsed.author,
            record.title,
            record.author,
            same_isbn=True,
            isbn_scraped=parsed.isbns_scraped,
        )
        if basis is not None:
            _log.debug(
                "IDENT-3 accepted ISBN %s record %r (%s)",
                file_isbn,
                record.title,
                basis.value,
            )
            return _accepted(parsed, record, file_isbn, basis)
        # IDENT-3: the record contradicts the file, so this ISBN isn't
        # this book's. It is dropped -- never kept as `isbn` -- so a false
        # positive cannot seed an ISBN-based join later (GROUP-1).
        _log.info(
            "IDENT-3 rejected ISBN %s: record %r by %r contradicts file %r by %r",
            file_isbn,
            record.title,
            record.author,
            parsed.title,
            parsed.author,
        )

    # IDENT-4: a placeholder title is not worth searching on.
    file_title = parsed.title
    if file_title and is_usable_title(file_title):
        # IDENT-5: candidates are proposals; each must pass MATCH on its own.
        candidates = (
            _safe(
                lambda: source.search(file_title, parsed.author), f"IDENT-5 search {file_title!r}"
            )
            or []
        )
        best: tuple[Candidate, MatchBasis] | None = None
        for record in candidates:
            basis = match_basis(parsed.title, parsed.author, record.title, record.author)
            if basis is None:
                continue
            if best is None or _outranks(record, basis, best):
                best = (record, basis)
        if best is not None:
            record, basis = best
            _log.debug(
                "IDENT-5 accepted search hit %r (%s) for %r",
                record.title,
                basis.value,
                file_title,
            )
            return _accepted(parsed, best[0], isbn, best[1])
        _log.info(
            "IDENT-5 no agreeing record among %d candidates for %r",
            len(candidates),
            file_title,
        )

    return Identification(
        title=parsed.title, author=parsed.author, isbn=isbn, cover_url=None, basis=None
    )


def _outranks(record: Candidate, basis: MatchBasis, best: tuple[Candidate, MatchBasis]) -> bool:
    """Whether (record, basis) should replace the current best candidate:
    a strictly stronger basis, or the same basis with a cover where the
    current best has none.

    Spec: IDENT-5's ranking. Relevance order does not decide; a stronger
    basis beats a weaker one that has a cover.
    """
    best_record, best_basis = best
    if basis != best_basis:
        return stronger_basis(basis, best_basis) == basis
    return best_record.cover_url is None and record.cover_url is not None


def _accepted(
    parsed: ParsedMetadata, record: Candidate, isbn: str | None, basis: MatchBasis
) -> Identification:
    """Apply an accepted record to the file's metadata.

    Spec: IDENT-6. The title (ADR-10) and author (ADR-22) stay the
    file's own; the record's fill a blank, and its author is kept as
    provenance either way.
    """
    return Identification(
        title=parsed.title or record.title,
        author=parsed.author or record.author,
        isbn=isbn,
        cover_url=record.cover_url,
        basis=basis,
        record_author=record.author,
    )


def _safe(call: Callable[[], T], what: str) -> T | None:
    """Run a lookup, treating a failed request the same as no record
    (logged as a warning, since the outcome is now file-only).

    Spec: IDENT-2's failure rule -- a lookup failure must never raise out
    of an import or degrade what is already known.
    """
    try:
        return call()
    except MetadataSourceError as exc:
        _log.warning("%s failed, continuing without it: %s", what, exc)
        return None
