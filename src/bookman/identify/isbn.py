"""ISBN-10/ISBN-13 detection, validation, and normalization."""

from __future__ import annotations

import re

_SEPARATORS = re.compile(r"[-\s]")
_CANDIDATE_PATTERN = re.compile(r"(?<![0-9-])[0-9][0-9xX\- ]{8,16}[0-9xX](?![0-9-])")


def _clean(candidate: str) -> str:
    return _SEPARATORS.sub("", candidate).upper()


def _isbn10_checksum_ok(digits: str) -> bool:
    if not re.fullmatch(r"\d{9}[\dX]", digits):
        return False
    total = 0
    for i, ch in enumerate(digits):
        value = 10 if ch == "X" else int(ch)
        total += value * (10 - i)
    return total % 11 == 0


def _isbn13_checksum_ok(digits: str) -> bool:
    if not digits.isdigit():
        return False
    total = sum((1 if i % 2 == 0 else 3) * int(ch) for i, ch in enumerate(digits))
    return total % 10 == 0


def _isbn13_check_digit(twelve_digits: str) -> str:
    total = sum((1 if i % 2 == 0 else 3) * int(ch) for i, ch in enumerate(twelve_digits))
    return str((10 - (total % 10)) % 10)


def is_valid_isbn(candidate: str) -> bool:
    """Check whether a string is a structurally valid ISBN-10 or ISBN-13.

    Strips hyphens and spaces, then requires the correct length and
    checksum for either format. Does not check whether the ISBN
    corresponds to a real published book.

    Args:
        candidate: A possible ISBN, with or without hyphens/spaces.

    Returns:
        True if `candidate` is a well-formed ISBN-10 or ISBN-13.
    """
    cleaned = _clean(candidate)
    if len(cleaned) == 10:
        return _isbn10_checksum_ok(cleaned)
    if len(cleaned) == 13:
        return _isbn13_checksum_ok(cleaned)
    return False


def normalize_isbn(candidate: str) -> str:
    """Convert a valid ISBN-10 to its ISBN-13 equivalent; pass ISBN-13 through.

    Args:
        candidate: A structurally valid ISBN-10 or ISBN-13 (hyphens/spaces
            allowed).

    Returns:
        13-digit ISBN string with no separators.

    Raises:
        ValueError: If `candidate` is not a valid ISBN-10 or ISBN-13.
    """
    cleaned = _clean(candidate)
    if len(cleaned) == 13 and _isbn13_checksum_ok(cleaned):
        return cleaned
    if len(cleaned) == 10 and _isbn10_checksum_ok(cleaned):
        core = "978" + cleaned[:9]
        return core + _isbn13_check_digit(core)
    raise ValueError(f"not a valid ISBN-10 or ISBN-13: {candidate!r}")


def extract_isbns(text: str) -> list[str]:
    """Find and validate ISBN-10/ISBN-13 strings within free text.

    Scans `text` for sequences matching ISBN-10 or ISBN-13 shape (with
    optional hyphens/spaces), verifies each candidate's checksum via
    is_valid_isbn, and normalizes survivors to ISBN-13. Intended for
    PDF first-page text and EPUB dc:identifier values not already
    tagged as an ISBN scheme.

    Args:
        text: Arbitrary text to scan (e.g. a PDF's first-page text, or
            a single dc:identifier value).

    Returns:
        Normalized ISBN-13 strings found in `text`, in order of first
        appearance, with duplicates removed. Empty list if none found.
    """
    found: list[str] = []
    seen: set[str] = set()
    for match in _CANDIDATE_PATTERN.finditer(text):
        cleaned = _clean(match.group())
        if len(cleaned) not in (10, 13) or not is_valid_isbn(cleaned):
            continue
        normalized = normalize_isbn(cleaned)
        if normalized not in seen:
            seen.add(normalized)
            found.append(normalized)
    return found
