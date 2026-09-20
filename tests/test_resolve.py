import pytest
from helpers import FakeSource

from bookman.formats import ParsedMetadata
from bookman.identify.resolve import identify
from bookman.identify.source import Candidate
from bookman.models import MatchBasis

ISBN = "9780306406157"
DEEP_WORK = Candidate(title="Deep Work", author="Cal Newport", cover_url="dw.jpg")


@pytest.fixture
def source():
    return FakeSource()


def _parsed(
    title="Deep Work: Rules for Focused Success",
    author="Newport, Cal",
    isbns=(),
    isbns_scraped=False,
):
    return ParsedMetadata(
        title=title, author=author, isbns=list(isbns), isbns_scraped=isbns_scraped
    )


def test_identify_accepts_isbn_hit_that_agrees_on_title(source):
    source.record = DEEP_WORK

    found = identify(_parsed(author=None, isbns=[ISBN]), source)

    assert found.basis == MatchBasis.ISBN
    assert not source.called("search")  # an accepted ISBN hit ends the lookup
    assert found.title == "Deep Work: Rules for Focused Success"  # the file's, not the record's
    assert found.author == "Cal Newport"
    assert found.isbn == ISBN
    assert found.cover_url == "dw.jpg"


def test_identify_uses_record_title_only_when_file_has_none(source):
    source.record = DEEP_WORK

    found = identify(ParsedMetadata(title=None, author="Cal Newport", isbns=[ISBN]), source)

    assert found.basis == MatchBasis.ISBN
    assert found.title == "Deep Work"


def test_identify_rejects_isbn_hit_disagreeing_on_title_and_author_and_drops_isbn(source):
    other = Candidate(title="Guide to Tax Law", author="Jane Doe", cover_url="tax.jpg")
    source.record = other

    found = identify(_parsed(isbns=[ISBN]), source)

    assert found.basis is None
    assert found.title == "Deep Work: Rules for Focused Success"
    assert found.author == "Newport, Cal"
    assert found.isbn is None
    assert found.cover_url is None


def test_identify_rejects_scraped_isbn_of_another_book_by_the_same_author(source):
    # The ISBN scraped from Deep Work's "Also by Cal Newport" page belongs
    # to a different Newport book; the shared author must not vouch for it.
    other = Candidate(
        title="So Good They Can't Ignore You", author="Cal Newport", cover_url="sg.jpg"
    )
    source.record = other
    source.results = [DEEP_WORK]

    found = identify(_parsed(isbns=[ISBN], isbns_scraped=True), source)

    assert found.basis == MatchBasis.TITLE_AUTHOR
    assert found.cover_url == "dw.jpg"
    assert found.isbn is None


def test_identify_accepts_asserted_isbn_when_only_the_author_agrees(source):
    # An EPUB's dc:identifier is publisher-asserted: a record whose title
    # differs (the volume's own title, an edition) but shares the author
    # is still this book.
    volume = Candidate(
        title="The Fellowship of the Ring", author="J.R.R. Tolkien", cover_url="f.jpg"
    )
    source.record = volume

    found = identify(
        _parsed(title="The Lord of the Rings Volume 1", author="Tolkien", isbns=[ISBN]), source
    )

    assert found.basis == MatchBasis.ISBN
    assert found.isbn == ISBN


def test_identify_keeps_isbn_when_open_library_has_no_record(source):

    found = identify(_parsed(isbns=[ISBN]), source)

    assert found.basis is None
    assert found.isbn == ISBN


PRINT_ISBN = "9781455586691"
EBOOK_ISBN = "9781455586677"
EMMA = Candidate(title="Emma", author="Jane Austen", cover_url="emma.jpg")


def test_identify_tries_the_next_isbn_when_the_first_is_unknown(source):
    source.records = {EBOOK_ISBN: DEEP_WORK}

    found = identify(_parsed(isbns=[PRINT_ISBN, EBOOK_ISBN]), source)

    assert found.basis == MatchBasis.ISBN
    assert found.isbn == EBOOK_ISBN
    assert found.cover_url == "dw.jpg"
    assert not source.called("search")


def test_identify_tries_the_next_isbn_when_the_first_is_rejected(source):
    source.records = {PRINT_ISBN: EMMA, EBOOK_ISBN: DEEP_WORK}

    found = identify(_parsed(isbns=[PRINT_ISBN, EBOOK_ISBN]), source)

    assert found.basis == MatchBasis.ISBN
    assert found.isbn == EBOOK_ISBN


def test_identify_stops_at_the_first_accepted_isbn(source):
    source.records = {PRINT_ISBN: DEEP_WORK, EBOOK_ISBN: DEEP_WORK}

    found = identify(_parsed(isbns=[PRINT_ISBN, EBOOK_ISBN]), source)

    assert found.isbn == PRINT_ISBN
    assert source.calls == [("lookup_by_isbn", PRINT_ISBN)]


def test_identify_keeps_the_first_unknown_isbn_when_none_is_accepted(source):
    found = identify(_parsed(isbns=[PRINT_ISBN, EBOOK_ISBN]), source)

    assert found.basis is None
    assert found.isbn == PRINT_ISBN
    assert [c[1] for c in source.calls if c[0] == "lookup_by_isbn"] == [PRINT_ISBN, EBOOK_ISBN]


def test_identify_drops_a_rejected_isbn_but_keeps_an_unknown_one(source):
    source.records = {PRINT_ISBN: EMMA}

    found = identify(_parsed(isbns=[PRINT_ISBN, EBOOK_ISBN]), source)

    assert found.basis is None
    assert found.isbn == EBOOK_ISBN


def test_identify_keeps_no_isbn_when_every_one_is_rejected(source):
    source.records = {PRINT_ISBN: EMMA, EBOOK_ISBN: EMMA}

    found = identify(_parsed(isbns=[PRINT_ISBN, EBOOK_ISBN]), source)

    assert found.basis is None
    assert found.isbn is None


def test_identify_moves_on_to_the_next_isbn_when_a_lookup_fails(source):
    source.fail_isbns = {PRINT_ISBN}
    source.records = {EBOOK_ISBN: DEEP_WORK}

    found = identify(_parsed(isbns=[PRINT_ISBN, EBOOK_ISBN]), source)

    assert found.basis == MatchBasis.ISBN
    assert found.isbn == EBOOK_ISBN


def test_identify_falls_back_to_search_after_unknown_isbn(source):
    source.results = [DEEP_WORK]

    found = identify(_parsed(isbns=[ISBN]), source)

    assert found.basis == MatchBasis.TITLE_AUTHOR
    assert found.isbn == ISBN


def test_identify_searches_by_title_and_author_without_isbn(source):
    source.results = [DEEP_WORK]

    found = identify(_parsed(), source)

    assert source.calls == [("search", "Deep Work: Rules for Focused Success", "Newport, Cal")]
    assert found.basis == MatchBasis.TITLE_AUTHOR
    assert found.title == "Deep Work: Rules for Focused Success"
    assert found.author == "Newport, Cal"
    assert found.record_author == "Cal Newport"
    assert found.isbn is None
    assert found.cover_url == "dw.jpg"


def test_identify_search_without_file_author_requires_identical_title(source):
    source.results = [DEEP_WORK]

    close_but_not_identical = identify(_parsed(title="Deep Works", author=None), source)
    identical_after_normalization = identify(_parsed(title="Deep Work: Rules", author=None), source)

    assert close_but_not_identical.basis is None
    assert identical_after_normalization.basis == MatchBasis.TITLE_ONLY
    assert identical_after_normalization.author == "Cal Newport"


def test_identify_skips_non_agreeing_search_docs_and_takes_first_agreeing(source):
    docs = [
        Candidate(title="Deep Work", author="Someone Else", cover_url="wrong.jpg"),
        Candidate(title="Deep Work Summary", author="Cal Newport", cover_url="also.jpg"),
        DEEP_WORK,
        Candidate(title="Deep Work", author="Cal Newport", cover_url="later.jpg"),
    ]
    source.results = docs

    found = identify(_parsed(), source)

    assert found.basis == MatchBasis.TITLE_AUTHOR
    assert found.cover_url == "dw.jpg"


def test_identify_prefers_agreeing_doc_with_a_cover(source):
    docs = [
        Candidate(title="Deep Work", author="Cal Newport", cover_url=None),
        DEEP_WORK,
    ]
    source.results = docs

    found = identify(_parsed(), source)

    assert found.cover_url == "dw.jpg"


def test_identify_prefers_stronger_basis_over_cover(source):
    docs = [
        Candidate(title="Deep Work", author=None, cover_url="weak.jpg"),
        Candidate(title="Deep Work", author="Cal Newport", cover_url=None),
    ]
    source.results = docs

    found = identify(_parsed(title="Deep Work"), source)

    assert found.basis == MatchBasis.TITLE_AUTHOR
    assert found.cover_url is None


MLK_WORK = Candidate(
    title="Strength to Love",
    author="Martin Luther King Jr., J.D. Jackson",  # the audiobook's narrator
    cover_url="stl.jpg",
)


def test_identify_keeps_the_files_author_over_the_records_on_a_corroborated_match(source):
    """FEATURES D13 / ADR-22: a work-level author list carries every
    edition's contributors. The file names who wrote this one."""
    source.results = [MLK_WORK]

    found = identify(_parsed(title="Strength to Love", author="Martin Luther King Jr."), source)

    assert found.basis == MatchBasis.TITLE_AUTHOR
    assert found.author == "Martin Luther King Jr."
    assert found.record_author == "Martin Luther King Jr., J.D. Jackson"


def test_identify_keeps_the_files_author_on_an_isbn_match_too(source):
    source.records[ISBN] = MLK_WORK

    found = identify(
        _parsed(title="Strength to Love", author="King, Martin Luther, Jr.", isbns=[ISBN]), source
    )

    assert found.basis == MatchBasis.ISBN
    assert found.author == "King, Martin Luther, Jr."
    assert found.record_author == "Martin Luther King Jr., J.D. Jackson"


@pytest.mark.parametrize("stand_in", ["Unknown", "unknown author", "N/A", "  "])
def test_identify_treats_a_stand_in_author_as_none(source, stand_in):
    """FEATURES D14: "Unknown" is a blank, so the record fills it."""
    source.results = [DEEP_WORK]

    found = identify(_parsed(title="Deep Work", author=stand_in), source)

    assert found.basis == MatchBasis.TITLE_ONLY
    assert found.author == "Cal Newport"


def test_identify_drops_a_stand_in_author_even_when_nothing_matches(source):
    found = identify(_parsed(title="Deep Work", author="Unknown"), source)

    assert found.basis is None
    assert found.author is None
    assert found.record_author is None


def test_identify_title_only_match_keeps_the_files_author(source):
    junk = Candidate(title="Lazarillo de Tormes", author="A. Bel, F. Chevalier", cover_url=None)
    source.results = [junk]

    found = identify(_parsed(title="Lazarillo de Tormes", author="Anonymous"), source)

    assert found.basis == MatchBasis.TITLE_ONLY
    assert found.author == "Anonymous"


def test_identify_fills_missing_record_fields_from_the_file(source):
    partial = Candidate(title="Deep Work", author=None, cover_url=None)
    source.results = [partial]

    found = identify(_parsed(title="Deep Work", author=None), source)

    assert found.basis == MatchBasis.TITLE_ONLY
    assert found.title == "Deep Work"
    assert found.author is None


def test_identify_returns_file_metadata_when_nothing_agrees(source):

    found = identify(_parsed(), source)

    assert found.basis is None
    assert found.title == "Deep Work: Rules for Focused Success"
    assert found.author == "Newport, Cal"


def test_identify_returns_file_metadata_on_network_error(source):
    source.fail = True

    found = identify(_parsed(isbns=[ISBN]), source)

    assert found.basis is None
    assert found.isbn == ISBN
    assert found.title == "Deep Work: Rules for Focused Success"


def test_identify_does_nothing_without_title_or_isbn(source):
    found = identify(ParsedMetadata(title=None, author="Cal Newport"), source)

    assert source.calls == []
    assert found.basis is None
    assert found.title is None
    assert found.author == "Cal Newport"


def test_identify_does_not_search_on_a_placeholder_title(source):
    # FEATURES A12: "Untitled" would only return whatever Open Library
    # happens to rank first, and match_basis would reject all of it.
    source.results = [DEEP_WORK]

    found = identify(_parsed(title="Untitled", author=None), source)

    assert not source.called("search")
    assert found.basis is None
    assert found.title == "Untitled"  # left alone for the user to correct


def test_identify_still_searches_a_real_title_containing_a_placeholder_word(source):
    source.results = [Candidate(title="The Book Thief", author="Markus Zusak", cover_url="bt.jpg")]

    found = identify(_parsed(title="The Book Thief", author="Markus Zusak"), source)

    assert source.called("search")
    assert found.basis == MatchBasis.TITLE_AUTHOR


def test_identify_searches_a_generic_title_and_lets_the_author_settle_it(source):
    # A generic title is still searched -- with the author alongside it,
    # that is how Alan Watts' "The Book" gets its cover.
    source.results = [Candidate(title="The Book", author="Watts, Alan", cover_url="tb.jpg")]

    found = identify(_parsed(title="The Book", author="Alan Watts"), source)

    assert source.called("search")
    assert found.basis == MatchBasis.TITLE_AUTHOR
    assert found.cover_url == "tb.jpg"
