import pytest

from bookman.identify.match import (
    author_surnames,
    authors_agree,
    match_basis,
    normalize_title,
    titles_agree,
)
from bookman.models import MatchBasis

# --- normalize_title ---


def test_normalize_title_strips_subtitle_after_colon():
    assert normalize_title("Deep Work: Rules for Focused Success") == "deep work"


def test_normalize_title_strips_subtitle_after_semicolon():
    assert (
        normalize_title("A Christmas Carol in Prose; Being a Ghost Story of Christmas")
        == "christmas carol in prose"
    )


def test_normalize_title_strips_subtitle_after_spaced_dash():
    assert normalize_title("Dune - The Deluxe Edition") == "dune"
    assert normalize_title("Dune — Deluxe") == "dune"


def test_normalize_title_keeps_hyphenated_words():
    assert normalize_title("Self-Reliance") == "self reliance"


def test_normalize_title_strips_edition_parenthetical():
    assert normalize_title("Fluent Python (2nd Edition)") == "fluent python"
    assert normalize_title("Fluent Python [Early Release] (2nd Edition)") == "fluent python"


def test_normalize_title_strips_leading_article_and_punctuation():
    assert normalize_title("The Hobbit!") == "hobbit"
    assert normalize_title("An Unquiet Mind") == "unquiet mind"
    assert normalize_title("Alice's Adventures in Wonderland") == "alice s adventures in wonderland"


def test_normalize_title_folds_unicode_case():
    assert normalize_title("Λουκής Λάρας") == normalize_title("λουκής λάρας")
    assert normalize_title("ÉTÉ") == normalize_title("été")


def test_normalize_title_of_only_punctuation_is_empty():
    assert normalize_title("...") == ""


# --- author_surnames / authors_agree ---


def test_author_surnames_handles_last_first_order():
    assert author_surnames("Carroll, Lewis") == {"carroll"}
    assert author_surnames("Lewis Carroll") == {"carroll"}


def test_author_surnames_ignores_initials():
    assert author_surnames("J. K. Rowling") == {"rowling"}
    assert author_surnames("Rowling, J. K.") == {"rowling"}


def test_author_surnames_handles_multiple_authors():
    assert author_surnames("Neil Gaiman & Terry Pratchett") == {"gaiman", "pratchett"}
    assert author_surnames("Neil Gaiman and Terry Pratchett") == {"gaiman", "pratchett"}
    assert author_surnames("Gaiman, Neil; Pratchett, Terry") == {"gaiman", "pratchett"}


def test_author_surnames_reads_comma_list_of_full_names_as_several_people():
    assert author_surnames("Jennifer Bassett, Lewis Carroll") == {"bassett", "carroll"}
    assert author_surnames("A. R. S. Bel, Ferdinand Du Chevalier, Anonymous") == {
        "bel",
        "chevalier",
    }


def test_author_surnames_reads_last_first_with_compound_surname():
    assert author_surnames("García Márquez, Gabriel") == {"marquez"}


def test_author_surnames_strips_accents():
    assert author_surnames("Gabriel García Márquez") == {"marquez"}
    assert author_surnames("Gabriel Garcia Marquez") == {"marquez"}


def test_author_surnames_ignores_placeholders():
    assert author_surnames("Anonymous") == set()
    assert author_surnames("Unknown") == set()


def test_authors_agree_returns_none_when_either_missing():
    assert authors_agree(None, "Lewis Carroll") is None
    assert authors_agree("Lewis Carroll", None) is None
    assert authors_agree("", "Lewis Carroll") is None
    assert authors_agree("Anonymous", "Anonymous") is None


def test_authors_agree_on_shared_surname():
    assert authors_agree("Carroll, Lewis", "Lewis Carroll") is True
    assert authors_agree("Neil Gaiman & Terry Pratchett", "Terry Pratchett") is True
    assert authors_agree("Lewis Carroll", "Charles Dickens") is False


# --- titles_agree ---


def test_titles_agree_on_normalized_equality():
    assert titles_agree("Deep Work", "Deep Work: Rules for Focused Success")


def test_titles_agree_allows_small_fuzz_on_normalized_forms():
    assert titles_agree("The Pragmatic Programmer", "Pragmatic Programmer, The")


@pytest.mark.parametrize(
    ("a", "b"),
    [
        # Long titles: the fuzz alone would swallow the one-digit difference.
        ("The Lord of the Rings Volume 1", "The Lord of the Rings Volume 2"),
        ("Introduction to Algorithms", "Introduction to Algorithms 2"),
        ("The Art of Computer Programming Volume 1", "The Art of Computer Programming"),
        # Roman numerals are volume markers too.
        ("Decline and Fall of the Roman Empire II", "Decline and Fall of the Roman Empire III"),
    ],
)
def test_titles_agree_treats_differing_volume_numbers_as_different_books(a, b):
    assert not titles_agree(a, b)


def test_titles_agree_keeps_fuzz_when_numbers_match():
    assert titles_agree("The Lord of the Rings Volume 1", "Lord of the Rings, Volume 1")
    assert titles_agree("Fahrenheit 451", "Fahrenheit 451 (50th Anniversary Edition)")


# --- match_basis: the Backlog's concrete failure cases ---


def test_match_basis_book_of_job_vs_joel_is_none():
    assert match_basis("The Book of Job", "Job", "The Book of Joel", "Joel") is None
    # Even with no authors at all: fuzzy is never enough on its own.
    assert match_basis("The Book of Job", None, "The Book of Joel", None) is None


def test_match_basis_deep_work_with_subtitle_is_title_author():
    assert (
        match_basis(
            "Deep Work", "Cal Newport", "Deep Work: Rules for Focused Success", "Newport, Cal"
        )
        == MatchBasis.TITLE_AUTHOR
    )


def test_match_basis_same_title_different_authors_is_none():
    assert match_basis("Dune", "Frank Herbert", "Dune", "Kevin J. Anderson") is None


def test_match_basis_shared_surname_counts_as_agreement():
    # Known limitation of surname matching, pinned so a change is deliberate.
    assert match_basis("Dune", "Frank Herbert", "Dune", "Brian Herbert") == MatchBasis.TITLE_AUTHOR


def test_match_basis_missing_author_identical_title_is_title_only():
    assert match_basis("Deep Work", None, "Deep Work", "Cal Newport") == MatchBasis.TITLE_ONLY
    assert (
        match_basis("Deep Work: Rules", "Cal Newport", "deep work", None) == MatchBasis.TITLE_ONLY
    )


def test_match_basis_missing_author_fuzzy_title_is_none():
    assert match_basis("The Pragmatic Programmer", None, "Pragmatic Programmer, The", None) is None


def test_match_basis_missing_title_is_none():
    assert match_basis(None, "Cal Newport", "Deep Work", "Cal Newport") is None
    assert match_basis("Deep Work", "Cal Newport", None, "Cal Newport") is None


def test_match_basis_same_isbn_with_agreeing_title_is_isbn():
    assert (
        match_basis("Deep Work", "Someone Else", "Deep Work", "Cal Newport", same_isbn=True)
        == MatchBasis.ISBN
    )


def test_match_basis_same_isbn_with_agreeing_author_is_isbn():
    assert (
        match_basis("Garbled OCR Title", "Cal Newport", "Deep Work", "Cal Newport", same_isbn=True)
        == MatchBasis.ISBN
    )


def test_match_basis_same_isbn_with_missing_fields_is_isbn():
    # Nothing to cross-check against: the ISBN stands.
    assert match_basis(None, None, "Deep Work", "Cal Newport", same_isbn=True) == MatchBasis.ISBN
    assert (
        match_basis("Deep Work", None, "Deep Work", "Cal Newport", same_isbn=True)
        == MatchBasis.ISBN
    )


def test_match_basis_same_isbn_with_title_and_author_both_disagreeing_is_none():
    assert (
        match_basis("My Tax Return 2019", "Jane Doe", "Deep Work", "Cal Newport", same_isbn=True)
        is None
    )


def test_match_basis_scraped_isbn_with_only_author_agreeing_is_none():
    # "Also by Cal Newport: So Good They Can't Ignore You, ISBN ..." in
    # Deep Work's front matter: same author, different book.
    assert (
        match_basis(
            "Deep Work",
            "Cal Newport",
            "So Good They Can't Ignore You",
            "Cal Newport",
            same_isbn=True,
            isbn_scraped=True,
        )
        is None
    )


def test_match_basis_scraped_isbn_with_agreeing_title_is_isbn():
    # A publisher-as-author PDF (A13): the title corroborates the ISBN.
    assert (
        match_basis(
            "Deep Work",
            "Manning Publications",
            "Deep Work",
            "Cal Newport",
            same_isbn=True,
            isbn_scraped=True,
        )
        == MatchBasis.ISBN
    )


def test_match_basis_scraped_isbn_without_file_title_is_isbn():
    # No title to cross-check (a PDF with an empty info dict): the ISBN stands.
    assert (
        match_basis(None, None, "Deep Work", "Cal Newport", same_isbn=True, isbn_scraped=True)
        == MatchBasis.ISBN
    )
