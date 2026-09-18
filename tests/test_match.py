import pytest

from bookman.identify.match import (
    author_surnames,
    authors_agree,
    is_generic_title,
    is_usable_title,
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


def test_author_surnames_ignores_generational_suffixes():
    assert author_surnames("Martin Luther King Jr.") == {"king"}
    assert author_surnames("Martin Luther King, Jr.") == {"king"}
    assert author_surnames("King, Martin Luther, Jr.") == {"king"}
    assert author_surnames("Robert Downey Jr. and Sammy Davis, Jr.") == {"downey", "davis"}
    assert author_surnames("William Strunk Jr. and E. B. White") == {"strunk", "white"}
    assert author_surnames("Strunk, William, Jr.; White, E. B.") == {"strunk", "white"}
    assert author_surnames("Henry VIII") == {"viii"}  # a single token is never a suffix


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


def test_match_basis_same_isbn_with_title_disagreeing_and_no_author_to_vouch_is_none():
    # ADR-19: a contradicting title with nothing to answer it is some
    # other book's record, however the ISBN got shared.
    assert (
        match_basis("Deep Work", "Cal Newport", "The three voices of poetry", None, same_isbn=True)
        is None
    )
    assert (
        match_basis("Deep Work", None, "The three voices of poetry", "T. S. Eliot", same_isbn=True)
        is None
    )


def test_match_basis_same_isbn_with_title_disagreeing_but_author_agreeing_is_isbn():
    # ... unless the author vouches for it (spec row 2).
    assert (
        match_basis(
            "Deep Work", "Cal Newport", "So Good They Can't Ignore You", "Cal Newport",
            same_isbn=True,
        )
        == MatchBasis.ISBN
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


# --- junk titles (FEATURES A12) ---
#
# Two tiers. A *placeholder* names no book at all and is discarded by
# normalize_title. A *generic* title could be real ("The Book"), so it
# survives, but it can't carry a match without an agreeing author.


@pytest.mark.parametrize(
    "placeholder",
    [
        "Untitled",
        "untitled",
        "UNTITLED",
        "Untitled 1",
        "Untitled-1",
        "Untitled Document",
        "Untitled Document 2",
        "Unknown",
        "No Title",
        "Default",
        "Microsoft Word - chapter1.docx",
        "Microsoft Word - Deep Work FINAL.doc",
        "Microsoft PowerPoint - deck.pptx",
        "LibreOffice - notes.odt",
    ],
)
def test_normalize_title_of_a_placeholder_is_empty(placeholder):
    assert normalize_title(placeholder) == ""
    assert not is_usable_title(placeholder)


@pytest.mark.parametrize(
    "generic",
    ["Book", "The Book", "eBook", "Document", "New Document", "Final Draft", "Scanned Document"],
)
def test_a_generic_title_survives_normalization_but_is_flagged(generic):
    normalized = normalize_title(generic)
    assert normalized != ""
    assert is_generic_title(normalized)
    # It is still worth searching for: the author is what identifies it.
    assert is_usable_title(generic)


@pytest.mark.parametrize(
    "real",
    [
        "The Book Thief",
        "The Book of Job",
        "Untitled Poem",
        "Microsoft Word 2019 Step by Step",
        "The New York Trilogy",
        "Document Z",
        "Dune",
        "Version Control with Git",
    ],
)
def test_normalize_title_keeps_a_real_title_containing_a_junk_word(real):
    normalized = normalize_title(real)
    assert normalized != ""
    assert not is_generic_title(normalized)
    assert is_usable_title(real)


def test_titles_agree_is_false_for_two_placeholders():
    assert not titles_agree("Untitled", "Untitled")
    assert not titles_agree("...", "...")


def test_match_basis_two_placeholder_titles_do_not_match():
    # The A12 gap: two unrelated files, each titled "Untitled", used to
    # come back TITLE_ONLY and be filed as one book.
    assert match_basis("Untitled", None, "Untitled", None) is None
    assert match_basis("Untitled", None, "Untitled", "Cal Newport") is None
    assert match_basis("Microsoft Word - a.docx", None, "Microsoft Word - b.docx", None) is None


def test_match_basis_placeholder_title_cannot_carry_an_author_match():
    # Nothing is called "Untitled", so a shared surname corroborates nothing.
    assert match_basis("Untitled", "Cal Newport", "Deep Work", "Cal Newport") is None
    assert match_basis("Untitled", "Alan Watts", "Untitled", "Alan Watts") is None


def test_match_basis_two_generic_titles_do_not_match_without_an_author():
    # The other half of A12: unrelated files a template left titled "Book".
    assert match_basis("Book", None, "Book", None) is None
    assert match_basis("Book", None, "Book", "Cal Newport") is None
    assert match_basis("New Document", None, "New Document", None) is None


def test_match_basis_generic_title_still_matches_when_the_author_agrees():
    # Alan Watts really did write "The Book": a generic title is weak,
    # not worthless, and an agreeing author is enough to redeem it.
    assert (
        match_basis(
            "The Book: On the Taboo Against Knowing Who You Are",
            "Alan Watts",
            "The Book",
            "Watts, Alan",
        )
        == MatchBasis.TITLE_AUTHOR
    )


def test_match_basis_junk_title_does_not_veto_an_isbn():
    # Neither tier is an argument *against* a shared ISBN: a title that
    # says nothing can't contradict, just as a missing title can't.
    assert (
        match_basis("Untitled", "Jane Doe", "Deep Work", "Cal Newport", same_isbn=True)
        == MatchBasis.ISBN
    )
    assert (
        match_basis("Book", "Jane Doe", "Deep Work", "Cal Newport", same_isbn=True)
        == MatchBasis.ISBN
    )
    assert (
        match_basis("Untitled", None, "Deep Work", "Cal Newport", same_isbn=True, isbn_scraped=True)
        == MatchBasis.ISBN
    )
    assert (
        match_basis("Book", None, "Deep Work", "Cal Newport", same_isbn=True, isbn_scraped=True)
        == MatchBasis.ISBN
    )
