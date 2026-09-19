"""The evidence-merge policy of `Library.import_file` (step 5), tested
directly on bare Books -- no files, no network."""

from bookman.identify.resolve import Identification
from bookman.library import _apply_identification
from bookman.models import Book, MatchBasis


def _found(
    basis: MatchBasis | None,
    *,
    title: str | None = "Found Title",
    author: str | None = "Found Author",
    isbn: str | None = "9780306406157",
    cover_url: str | None = "cover.jpg",
    record_author: str | None = "Record Author",
) -> Identification:
    return Identification(
        title=title,
        author=author,
        isbn=isbn,
        cover_url=cover_url,
        basis=basis,
        record_author=record_author,
    )


def _book(**overrides: object) -> Book:
    fields: dict[str, object] = {
        "title": "Book Title",
        "author": "Book Author",
        "isbn": None,
        "identified": MatchBasis.TITLE_AUTHOR,
    }
    fields.update(overrides)
    return Book(**fields)  # type: ignore[arg-type]


def test_new_book_takes_everything_the_file_said():
    book = Book(title="Book Title", author=None, isbn=None)

    cover = _apply_identification(book, _found(MatchBasis.ISBN), None, title="Book Title")

    assert (book.author, book.isbn, book.identified) == (
        "Found Author",
        "9780306406157",
        MatchBasis.ISBN,
    )
    assert book.grouped is None
    assert cover == "cover.jpg"


def test_stronger_identification_replaces_title_author_isbn_and_fetches_cover():
    book = _book(identified=MatchBasis.TITLE_AUTHOR)

    cover = _apply_identification(
        book, _found(MatchBasis.ISBN), MatchBasis.TITLE_AUTHOR, title="Found Title"
    )

    assert book.title == "Found Title"
    assert book.author == "Found Author"
    assert book.isbn == "9780306406157"
    assert book.identified == MatchBasis.ISBN
    assert cover == "cover.jpg"


def test_equal_identification_keeps_the_first_title_but_updates_the_rest():
    book = _book(identified=MatchBasis.TITLE_AUTHOR)

    cover = _apply_identification(
        book, _found(MatchBasis.TITLE_AUTHOR), MatchBasis.TITLE_AUTHOR, title="Found Title"
    )

    assert book.title == "Book Title"
    assert book.author == "Found Author"
    assert book.identified == MatchBasis.TITLE_AUTHOR
    assert cover == "cover.jpg"


def test_weaker_identification_only_fills_empty_fields():
    book = _book(identified=MatchBasis.ISBN, author=None)

    cover = _apply_identification(
        book, _found(MatchBasis.TITLE_ONLY), MatchBasis.TITLE_AUTHOR, title="Found Title"
    )

    assert book.title == "Book Title"
    assert book.author == "Found Author"  # was empty
    assert book.isbn == "9780306406157"  # was empty
    assert book.identified == MatchBasis.ISBN
    assert cover is None


def test_failed_identification_on_existing_book_changes_nothing():
    book = _book(identified=MatchBasis.TITLE_AUTHOR, isbn="9781234567897")

    cover = _apply_identification(
        book, _found(None, cover_url=None), MatchBasis.TITLE_AUTHOR, title="Found Title"
    )

    assert (book.title, book.author, book.isbn) == ("Book Title", "Book Author", "9781234567897")
    assert book.identified == MatchBasis.TITLE_AUTHOR
    assert cover is None


def test_record_author_follows_the_adopted_identification():
    """ADR-22: provenance travels with the record whose fields were
    adopted, and stays put when a weaker or failed lookup is not."""
    book = _book(identified=MatchBasis.TITLE_AUTHOR, record_author="Old Record Author")

    _apply_identification(book, _found(MatchBasis.ISBN), MatchBasis.TITLE_AUTHOR, title="T")
    assert book.record_author == "Record Author"

    _apply_identification(
        book,
        _found(MatchBasis.TITLE_ONLY, record_author="Weaker Record Author"),
        MatchBasis.TITLE_AUTHOR,
        title="T",
    )
    assert book.record_author == "Record Author"

    _apply_identification(
        book, _found(None, record_author=None), MatchBasis.TITLE_AUTHOR, title="T"
    )
    assert book.record_author == "Record Author"


def test_adopted_identification_never_overwrites_present_values_with_missing_ones():
    book = _book(identified=None, isbn="9781234567897")

    _apply_identification(
        book,
        _found(MatchBasis.TITLE_AUTHOR, author=None, isbn=None),
        MatchBasis.TITLE_AUTHOR,
        title="Found Title",
    )

    assert book.author == "Book Author"
    assert book.isbn == "9781234567897"
    assert book.identified == MatchBasis.TITLE_AUTHOR


def test_grouped_records_the_weakest_basis_ever_used():
    book = _book(grouped=MatchBasis.ISBN)
    _apply_identification(book, _found(None), MatchBasis.TITLE_AUTHOR, title="x")
    assert book.grouped == MatchBasis.TITLE_AUTHOR

    book = _book(grouped=MatchBasis.TITLE_ONLY)
    _apply_identification(book, _found(None), MatchBasis.ISBN, title="x")
    assert book.grouped == MatchBasis.TITLE_ONLY


def test_reviewed_book_keeps_its_metadata_and_fetches_no_cover():
    book = _book(reviewed=True, identified=None)

    cover = _apply_identification(
        book, _found(MatchBasis.ISBN), MatchBasis.TITLE_AUTHOR, title="Found Title"
    )

    assert (book.title, book.author, book.isbn) == ("Book Title", "Book Author", None)
    assert book.identified is None
    assert book.reviewed is True
    assert book.grouped == MatchBasis.TITLE_AUTHOR
    assert cover is None


def test_title_only_join_clears_reviewed_but_still_keeps_the_humans_metadata():
    # ADR-9: the flag resurfaces the book for another look; the
    # correction itself is not overwritten by the doubtful join.
    book = _book(reviewed=True, identified=None, author=None)

    cover = _apply_identification(
        book, _found(MatchBasis.ISBN), MatchBasis.TITLE_ONLY, title="Found Title"
    )

    assert book.reviewed is False
    assert book.grouped == MatchBasis.TITLE_ONLY
    assert (book.title, book.author, book.identified) == ("Book Title", None, None)
    assert cover is None
