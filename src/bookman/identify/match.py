"""Decide whether two descriptions of a book (title/author pairs, possibly
with an ISBN) refer to the same book. Used in two places: to accept or
reject an Open Library candidate for a file (identify/resolve.py), and to
decide whether a file belongs in an existing library folder (library.py).
Stdlib only.
"""

from __future__ import annotations

import difflib
import re
import unicodedata

from bookman.models import MatchBasis

_FUZZY_TITLE_THRESHOLD = 0.9
_SUBTITLE_SEPARATORS = re.compile(r"\s*(?::|;|\s-\s|\s–\s|\s—\s|—)\s*")
_TRAILING_BRACKETS = re.compile(r"\s*[(\[][^()\[\]]*[)\]]\s*$")
_LEADING_ARTICLE = re.compile(r"^(?:the|a|an)\s+")
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")
_AUTHOR_SEPARATORS = re.compile(r"\s*(?:;|&|\band\b)\s*")
# A whole token that is a number: digits, or a roman numeral 1-39 (enough
# for volume/part markers; the bound keeps words like "mix" or "civil" out).
_NUMBER_TOKEN = re.compile(r"^(?:\d+|(?=[ivx])x{0,3}(?:ix|iv|v?i{0,3}))$")
# "Authors" that name nobody and so can't corroborate anything.
_NON_AUTHORS = frozenset({"anonymous", "anon", "unknown", "various", "unknown author"})


def normalize_title(title: str) -> str:
    """Reduce a title to the form used for comparison.

    NFKC-normalizes and casefolds, drops any subtitle (everything after
    the first `:`, `;`, ` - `, or an em/en dash), drops trailing
    parenthesized/bracketed groups (edition notes), strips a leading
    English article, removes punctuation, and collapses whitespace.

    Args:
        title: A raw title as parsed from a file or returned by a lookup.

    Returns:
        The normalized title. May be empty if nothing survives (e.g. the
        title was only punctuation).
    """
    text = unicodedata.normalize("NFKC", title).casefold().strip()
    text = _SUBTITLE_SEPARATORS.split(text, maxsplit=1)[0]
    while True:
        stripped = _TRAILING_BRACKETS.sub("", text)
        if stripped == text:
            break
        text = stripped
    text = _LEADING_ARTICLE.sub("", text)
    text = _NON_WORD.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def author_surnames(author: str) -> set[str]:
    """Extract a comparable surname from each author in an author string.

    Splits multiple authors on `;`, `&`, or ` and `. A comma is
    ambiguous: "Newport, Cal" is one person written Last, First, while
    "Jennifer Bassett, Lewis Carroll" is two people. It's read as
    Last, First only when it's the sole comma and one side is a single
    name token (or only initials); otherwise the commas separate
    people. Each name is NFKD-normalized with combining marks removed
    (so accents don't matter) and casefolded; the surname is the last
    token. Single-letter or dotted initials are ignored, as are
    placeholders that name nobody ("Anonymous", "Unknown", ...).

    Args:
        author: A raw author string, possibly naming several people.

    Returns:
        The set of normalized surnames. Empty if none could be found.
    """
    surnames: set[str] = set()
    for part in _AUTHOR_SEPARATORS.split(author):
        for name in _split_on_commas(_strip_accents(part).casefold().strip()):
            if name in _NON_AUTHORS:
                continue
            tokens = _name_tokens(name)
            if tokens:
                surnames.add(tokens[-1])
    return surnames


def _name_tokens(name: str) -> list[str]:
    return [t for t in _NON_WORD.sub(" ", name).split() if len(t) > 1]


def _split_on_commas(text: str) -> list[str]:
    """Return the individual names in a comma-bearing author string,
    with a "Last, First" pair reordered to "First Last"."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) == 2 and (len(_name_tokens(parts[0])) < 2 or len(_name_tokens(parts[1])) < 2):
        return [f"{parts[1]} {parts[0]}"]
    return parts


def authors_agree(a: str | None, b: str | None) -> bool | None:
    """Whether two author strings name at least one person in common.

    Args:
        a: An author string, or None if unknown.
        b: An author string, or None if unknown.

    Returns:
        None if either side is missing (no evidence either way), else
        True if the two share a surname (see `author_surnames`).
    """
    if not a or not b:
        return None
    surnames_a = author_surnames(a)
    surnames_b = author_surnames(b)
    if not surnames_a or not surnames_b:
        return None
    return bool(surnames_a & surnames_b)


def titles_agree(a: str, b: str) -> bool:
    """Whether two titles are the same after normalization, allowing a
    small amount of fuzz (difflib ratio >= 0.9 on the normalized forms).

    The fuzz never bridges a difference in numbers: "... Volume 1" and
    "... Volume 2" (or "Part II"/"Part III") are different books however
    long the shared prefix, so the number tokens of both normalized
    forms must match exactly before the ratio is consulted.

    Args:
        a: A raw title.
        b: A raw title.

    Returns:
        True if the normalized titles are identical or nearly so.
    """
    na, nb = normalize_title(a), normalize_title(b)
    if na == nb:
        return True
    if _number_tokens(na) != _number_tokens(nb):
        return False
    return difflib.SequenceMatcher(None, na, nb).ratio() >= _FUZZY_TITLE_THRESHOLD


def _number_tokens(normalized_title: str) -> list[str]:
    return [t for t in normalized_title.split() if _NUMBER_TOKEN.match(t)]


def match_basis(
    file_title: str | None,
    file_author: str | None,
    cand_title: str | None,
    cand_author: str | None,
    *,
    same_isbn: bool = False,
    isbn_scraped: bool = False,
) -> MatchBasis | None:
    """Judge whether a file's own metadata and a candidate description
    (an Open Library record, or an existing library book) are the same book.

    Rules, in order:
    - `same_isbn`: ISBN, unless title and author are both present on
      both sides and *both* disagree -- the guard against a
      false-positive ISBN (a checksum-passing number scraped from a
      PDF) overwriting good data. Either agreeing is enough, since a
      shared ISBN is a strong prior.
    - ... except when `isbn_scraped`: an ISBN pulled from page text
      may be a *cited* book's ("Also by this author ..."), and a
      shared author is exactly what such a citation shares. So a
      scraped ISBN needs the titles to agree whenever both are
      present; the author alone can't vouch for it.
    - Authors agree (share a surname) and titles agree (fuzzily):
      TITLE_AUTHOR.
    - Authors disagree: None, regardless of title.
    - An author is missing on either side and the normalized titles
      are *identical* (no fuzz): TITLE_ONLY.
    - Otherwise None.

    Args:
        file_title: Title from the file, or None.
        file_author: Author from the file, or None.
        cand_title: Title of the candidate, or None.
        cand_author: Author of the candidate, or None.
        same_isbn: True if both sides carry the same normalized ISBN.
        isbn_scraped: True if the file's ISBN was scanned from its text
            rather than read from a metadata field (see
            `ParsedMetadata.isbns_scraped`). Only meaningful with
            `same_isbn`.

    Returns:
        The basis on which they match, or None if they don't.
    """
    have_titles = bool(file_title) and bool(cand_title)
    title_ok = have_titles and titles_agree(file_title or "", cand_title or "")
    author_ok = authors_agree(file_author, cand_author)

    if same_isbn:
        if have_titles and not title_ok and (isbn_scraped or author_ok is False):
            return None
        return MatchBasis.ISBN

    if not have_titles:
        return None
    if author_ok is True:
        return MatchBasis.TITLE_AUTHOR if title_ok else None
    if author_ok is False:
        return None
    # No author evidence: require the strict form of title equality.
    normalized = normalize_title(file_title or "")
    if normalized and normalized == normalize_title(cand_title or ""):
        return MatchBasis.TITLE_ONLY
    return None


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))
