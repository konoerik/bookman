import pytest

from bookman.identify.isbn import extract_isbns, is_valid_isbn, normalize_isbn

VALID_ISBN10 = "0306406152"
VALID_ISBN10_HYPHENATED = "0-306-40615-2"
VALID_ISBN13 = "9780306406157"
VALID_ISBN13_HYPHENATED = "978-0-306-40615-7"
INVALID_CHECKSUM_ISBN10 = "0306406153"


def test_is_valid_isbn_accepts_valid_isbn10():
    assert is_valid_isbn(VALID_ISBN10) is True


def test_is_valid_isbn_accepts_valid_isbn13():
    assert is_valid_isbn(VALID_ISBN13) is True


def test_is_valid_isbn_rejects_bad_checksum():
    assert is_valid_isbn(INVALID_CHECKSUM_ISBN10) is False


def test_is_valid_isbn_rejects_wrong_length():
    assert is_valid_isbn("12345") is False


def test_is_valid_isbn_ignores_hyphens_and_spaces():
    assert is_valid_isbn(VALID_ISBN10_HYPHENATED) is True
    assert is_valid_isbn("978 0 306 40615 7") is True


def test_normalize_isbn_converts_isbn10_to_isbn13():
    assert normalize_isbn(VALID_ISBN10) == VALID_ISBN13
    assert normalize_isbn(VALID_ISBN10_HYPHENATED) == VALID_ISBN13


def test_normalize_isbn_passes_through_isbn13():
    assert normalize_isbn(VALID_ISBN13) == VALID_ISBN13
    assert normalize_isbn(VALID_ISBN13_HYPHENATED) == VALID_ISBN13


def test_normalize_isbn_raises_on_invalid_input():
    with pytest.raises(ValueError):
        normalize_isbn(INVALID_CHECKSUM_ISBN10)
    with pytest.raises(ValueError):
        normalize_isbn("not an isbn")


def test_extract_isbns_finds_isbn13_in_prose():
    text = f"This edition's ISBN is {VALID_ISBN13}, printed in 2020."
    assert extract_isbns(text) == [VALID_ISBN13]


def test_extract_isbns_finds_hyphenated_isbn10():
    text = f"ISBN: {VALID_ISBN10_HYPHENATED}"
    assert extract_isbns(text) == [VALID_ISBN13]


def test_extract_isbns_deduplicates_and_normalizes():
    text = f"ISBN-10: {VALID_ISBN10_HYPHENATED} ISBN-13: {VALID_ISBN13}"
    assert extract_isbns(text) == [VALID_ISBN13]


def test_extract_isbns_returns_empty_for_no_match():
    assert extract_isbns("no identifiers in this string at all") == []
