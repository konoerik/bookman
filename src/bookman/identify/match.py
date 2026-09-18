"""Decide whether two descriptions of a book (title/author pairs, possibly
with an ISBN) refer to the same book. Used in two places: to accept or
reject an Open Library candidate for a file (identify/resolve.py), and to
decide whether a file belongs in an existing library folder (library.py).
Stdlib only.

This module is the MATCH rule of `docs/IDENTIFICATION.md` (steps MATCH-0..3)
-- the one place both questions are decided, so they cannot drift apart
(spec PR2). Each function names the step it implements.
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
# Generational suffixes: part of the name, never the surname (FEATURES D9).
_NAME_SUFFIXES = frozenset({"jr", "jnr", "sr", "snr", "ii", "iii", "iv"})
# Junk titles come in two strengths (docs/FEATURES.md A12).
#
# Placeholder words name no book at all: nothing is ever really called
# "Untitled" or "No Title", so such a title is discarded outright by
# `normalize_title` and compares as if the file had no title.
_PLACEHOLDER_TITLE_WORDS = frozenset("untitled unknown none no title default".split())
# Generic words *could* be a real title -- Alan Watts really did write
# "The Book" -- but say almost nothing on their own. A title built only
# from these survives normalization and can still be corroborated by an
# agreeing author; what it cannot do is carry a match by itself.
_GENERIC_TITLE_WORDS = frozenset(
    "book ebook document doc file text draft copy final new scan scanned version pdf epub".split()
)
_JUNK_TITLE_WORDS = _PLACEHOLDER_TITLE_WORDS | _GENERIC_TITLE_WORDS
# What a converter writes into /Title when the document never had one:
# the source filename, prefixed by the application ("Microsoft Word -
# chapter1.docx"). Matched against the raw title, since normalization
# would strip everything after the " - " and leave only the app name.
_CONVERTER_TITLE = re.compile(
    r"^(?:microsoft\s+\w+|adobe\s+acrobat\w*|libreoffice|openoffice|pages|scrivener)\s+-\s"
)


def normalize_title(title: str) -> str:
    """Reduce a title to the form used for comparison.

    Spec: MATCH-0.

    NFKC-normalizes and casefolds, drops any subtitle (everything after
    the first `:`, `;`, ` - `, or an em/en dash), drops trailing
    parenthesized/bracketed groups (edition notes), strips a leading
    English article, removes punctuation, and collapses whitespace.

    A title that names no book -- a placeholder ("Untitled", "Untitled
    Document 2", "No Title") or a converter's filename stamp ("Microsoft
    Word - chapter1.docx") -- normalizes to the empty string, because it
    is no better evidence than having no title at all. Without this, two
    unrelated files both titled "Untitled" compare as the same book
    (docs/FEATURES.md A12). A merely *generic* title ("Book", "Final
    Draft") survives here and is weakened later instead, in `match_basis`
    -- see `is_generic_title`.

    Args:
        title: A raw title as parsed from a file or returned by a lookup.

    Returns:
        The normalized title, or the empty string if nothing survives
        (the title was only punctuation) or nothing was ever there (a
        placeholder title).
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
    normalized = _WHITESPACE.sub(" ", text).strip()
    return "" if _is_junk_title(title, normalized) else normalized


def _is_junk_title(raw: str, normalized: str) -> bool:
    """Whether a title names nothing at all: a converter's filename
    stamp, or a normalized form built only from junk words and numbers,
    at least one of which is an outright placeholder. "Untitled
    Document" qualifies; "New Document" is merely generic, and "Untitled
    Poem" is a real title that happens to start with a junk word."""
    if _CONVERTER_TITLE.match(unicodedata.normalize("NFKC", raw).casefold().strip()):
        return True
    words = _meaningful_words(normalized)
    return (
        bool(normalized)
        and all(word in _JUNK_TITLE_WORDS for word in words)
        and any(word in _PLACEHOLDER_TITLE_WORDS for word in words)
    )


def is_generic_title(normalized_title: str) -> bool:
    """Whether a *normalized* title is built only from generic words
    ("book", "final draft", "new document 2").

    Spec: MATCH-3's "does the title actually distinguish this book?"
    guard. Also consulted by MATCH-1, where a generic title is too weak
    to contradict a shared ISBN.

    Such a title is too weak to establish a match on its own -- two
    unrelated files called "Book" are not one book -- but it is not
    nothing: an agreeing author can still corroborate it, which is what
    keeps a real title like Alan Watts' "The Book" identifiable.
    """
    words = _meaningful_words(normalized_title)
    return bool(normalized_title) and all(word in _GENERIC_TITLE_WORDS for word in words)


def _meaningful_words(normalized_title: str) -> list[str]:
    """The words of a normalized title, ignoring bare numbers (so
    "untitled 2" reads the same as "untitled")."""
    return [w for w in normalized_title.split() if not _NUMBER_TOKEN.match(w)]


def is_usable_title(title: str) -> bool:
    """Whether a title is worth searching on, i.e. whether anything
    survives `normalize_title`. A generic title counts: searching it
    together with an author is how such a book gets identified.

    Spec: IDENT-4.
    """
    return bool(normalize_title(title))


def author_surnames(author: str) -> set[str]:
    """Extract a comparable surname from each author in an author string.

    Spec: MATCH-2's name rules.

    Splits multiple authors on `;`, `&`, or ` and `. A comma is
    ambiguous: "Newport, Cal" is one person written Last, First, while
    "Jennifer Bassett, Lewis Carroll" is two people. It's read as
    Last, First only when it's the sole comma and one side is a single
    name token (or only initials); otherwise the commas separate
    people. Each name is NFKD-normalized with combining marks removed
    (so accents don't matter) and casefolded; the surname is the last
    token that isn't a generational suffix ("Jr.", "III"). Single-letter
    or dotted initials are ignored, as are placeholders that name
    nobody ("Anonymous", "Unknown", ...).

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
    """A name's comparable tokens: initials dropped, and a trailing
    generational suffix dropped when a name remains in front of it
    ("King Jr" -> ["king"], but "VIII" alone stays)."""
    tokens = [t for t in _NON_WORD.sub(" ", name).split() if len(t) > 1]
    while len(tokens) > 1 and tokens[-1] in _NAME_SUFFIXES:
        tokens.pop()
    return tokens


def _split_on_commas(text: str) -> list[str]:
    """Return the individual names in a comma-bearing author string,
    with a "Last, First" pair reordered to "First Last"."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    # "King, Martin Luther, Jr.": a suffix set off by its own comma is
    # not a person, so it must not count as one when the commas are read.
    parts = [p for p in parts if _NON_WORD.sub("", p).strip() not in _NAME_SUFFIXES]
    if len(parts) == 2 and (len(_name_tokens(parts[0])) < 2 or len(_name_tokens(parts[1])) < 2):
        return [f"{parts[1]} {parts[0]}"]
    return parts


def authors_agree(a: str | None, b: str | None) -> bool | None:
    """Whether two author strings name at least one person in common.

    Spec: MATCH-2's author evidence -- True agrees, False is the rule's
    strongest veto, None means neither side offered evidence.

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

    Spec: MATCH-2's title test. The strict, fuzz-free comparison MATCH-3
    requires is done in `match_basis` directly, not here.

    The fuzz never bridges a difference in numbers: "... Volume 1" and
    "... Volume 2" (or "Part II"/"Part III") are different books however
    long the shared prefix, so the number tokens of both normalized
    forms must match exactly before the ratio is consulted.

    A title that normalizes away to nothing -- only punctuation, or a
    placeholder like "Untitled" -- agrees with nothing, not even another
    empty one.

    Args:
        a: A raw title.
        b: A raw title.

    Returns:
        True if the normalized titles are identical or nearly so.
    """
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return False
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

    Spec: MATCH-1, MATCH-2, MATCH-3 (MATCH-0 runs first, via
    `normalize_title`). This is the single rule both identification and
    grouping call, so the two can never drift apart (spec PR2).

    Rules, in order:
    - `same_isbn`: ISBN, unless the titles are both present and
      disagree and the author does not vouch for the number (disagrees,
      or is missing on either side) -- the guard against a false
      ISBN, mis-keyed or scraped, landing on some other book's record.
      An agreeing author rescues a title mismatch, since a shared ISBN
      is a strong prior.
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

    A title is "present" only if it survives `normalize_title`, so a
    placeholder ("Untitled") counts as no title at all: it can neither
    carry a match nor veto an ISBN. A merely generic title ("Book",
    "Final Draft" -- see `is_generic_title`) is weaker still than it
    looks: it says too little to match on its own or to contradict an
    ISBN, so it can only reach TITLE_AUTHOR, where an agreeing author
    does the real work.

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
    norm_file = normalize_title(file_title) if file_title else ""
    norm_cand = normalize_title(cand_title) if cand_title else ""
    have_titles = bool(norm_file) and bool(norm_cand)
    generic = is_generic_title(norm_file) or is_generic_title(norm_cand)
    title_ok = have_titles and titles_agree(file_title or "", cand_title or "")
    author_ok = authors_agree(file_author, cand_author)

    if same_isbn:
        # A generic title carries no argument against an ISBN, so it
        # doesn't get to veto one. A real title that disagrees does,
        # unless the author vouches for the number (ADR-19) -- and for a
        # scraped ISBN not even then (ADR-14).
        if have_titles and not generic and not title_ok and (isbn_scraped or author_ok is not True):
            return None
        return MatchBasis.ISBN

    if not have_titles:
        return None
    if author_ok is True:
        return MatchBasis.TITLE_AUTHOR if title_ok else None
    if author_ok is False:
        return None
    # No author evidence: require the strict form of title equality,
    # and a title that actually distinguishes this book from another.
    if norm_file == norm_cand and not generic:
        return MatchBasis.TITLE_ONLY
    return None


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))
