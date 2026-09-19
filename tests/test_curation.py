"""K1-K3: the human half of ADR-4 -- mark reviewed, edit, re-identify.

The review flag has always been honored on import; these are the
operations that let a frontend act on it (ADR-18).
"""

import pytest
from helpers import VALID_ISBN13
from helpers import make_epub as _make_epub
from helpers import make_pdf as _make_pdf

from bookman.errors import CatalogError
from bookman.identify.source import Candidate
from bookman.models import Book, FormatKind, MatchBasis


@pytest.fixture
def book(tmp_path, library, source):
    source.record = None
    return library.import_file(
        _make_epub(tmp_path / "a.epub", title="Dune", author="Frank Herbert")
    )


# --- K1: mark reviewed --------------------------------------------------


def test_mark_reviewed_clears_the_review_queue(library, book):
    assert book.needs_review

    library.mark_reviewed(book)

    assert book.reviewed
    assert not book.needs_review
    assert library.scan()[0].reviewed


def test_mark_reviewed_can_be_undone(library, book):
    library.mark_reviewed(book)
    library.mark_reviewed(book, False)

    assert not library.scan()[0].reviewed
    assert library.scan()[0].needs_review


def test_curation_rejects_a_book_that_was_never_saved(library):
    unsaved = Book(title="Nowhere", author=None, isbn=None)

    with pytest.raises(CatalogError):
        library.mark_reviewed(unsaved)
    with pytest.raises(CatalogError):
        library.edit(unsaved, title="X")
    with pytest.raises(CatalogError):
        library.reidentify(unsaved)


# --- K2: edit -----------------------------------------------------------


def test_edit_updates_only_the_fields_passed(library, book):
    library.edit(book, author="Herbert, Frank")

    saved = library.scan()[0]
    assert saved.author == "Herbert, Frank"
    assert saved.title == "Dune"
    assert saved.isbn is None


def test_edit_marks_the_book_reviewed(library, book):
    """Otherwise the edit is not durable -- see the import test below."""
    library.edit(book, author="Frank Herbert")

    assert library.scan()[0].reviewed


def test_edit_survives_a_later_import_of_another_format(tmp_path, library, source, book):
    """The reason an edit sets `reviewed`: the book below is unidentified,
    so the incoming PDF's ISBN match is strictly stronger and would
    otherwise overwrite the human's author (that overwrite is the
    behavior `test_library::upgrades_identification_on_follow_up_format`
    pins). The ISBN is what lets the two group despite disagreeing
    authors, which is the case worth protecting."""
    library.edit(book, isbn=VALID_ISBN13, author="The Real Author")
    assert book.identified is None

    source.record = Candidate(title="Dune", author="Someone Else", cover_url=None)
    library.import_file(
        _make_pdf(tmp_path / "b.pdf", title="Dune", text=f"ISBN {VALID_ISBN13}")
    )

    saved = library.scan()[0]
    assert saved.author == "The Real Author"
    assert saved.grouped == MatchBasis.ISBN
    assert {fmt.kind for fmt in saved.formats} == {FormatKind.EPUB, FormatKind.PDF}


def test_edit_can_clear_an_author_but_not_the_title(library, book):
    library.edit(book, author=None)
    assert library.scan()[0].author is None

    for bad in ["", "   "]:
        with pytest.raises(CatalogError):
            library.edit(book, title=bad)


def test_edit_normalizes_an_isbn_and_rejects_an_invalid_one(library, book):
    library.edit(book, isbn="0-306-40615-2")
    assert library.scan()[0].isbn == VALID_ISBN13

    with pytest.raises(CatalogError):
        library.edit(book, isbn="97803064061599")

    library.edit(book, isbn=None)
    assert library.scan()[0].isbn is None


def test_edit_renames_the_folder_and_its_format_files(library, book):
    old_directory = book.directory

    library.edit(book, title="Dune: Book One")

    assert not old_directory.exists()
    assert book.directory.name == "Dune - Book One"
    assert [fmt.path.name for fmt in book.formats] == ["Dune - Book One.epub"]
    assert all(fmt.path.exists() for fmt in book.formats)
    assert sorted(p.name for p in book.directory.iterdir()) == [
        "Dune - Book One.epub",
        "metadata.json",
    ]


def test_edit_keeps_the_book_findable_after_a_rename(library, book):
    library.edit(book, title="Dune Messiah")

    assert [b.title for b in library.search("messiah")] == ["Dune Messiah"]
    assert library.search("dune") != []
    assert [b.title for b in library.scan()] == ["Dune Messiah"]


def test_edit_preserves_the_books_id_across_a_rename(library, book):
    original = book.id

    library.edit(book, title="Dune Messiah")

    assert book.id == original
    assert library.scan()[0].id == original


def test_edit_moves_the_cover_with_the_book(tmp_path, library, source):
    source.results = [Candidate(title="Sapiens", author="Yuval Noah Harari", cover_url="u")]
    source.cover = b"png bytes"
    saved = library.import_file(
        _make_epub(tmp_path / "s.epub", title="Sapiens", author="Yuval Noah Harari")
    )
    assert saved.cover_path is not None

    library.edit(saved, title="Sapiens: A Brief History")

    assert saved.cover_path.exists()
    assert saved.cover_path.parent == saved.directory
    assert library.scan()[0].cover_path.read_bytes() == b"png bytes"


def test_edit_does_not_move_a_book_whose_folder_name_is_unchanged(library, book):
    directory = book.directory

    library.edit(book, title="Dune:")

    assert book.directory == directory
    assert library.scan()[0].title == "Dune:"


def test_edit_deduplicates_a_folder_name_taken_by_another_book(tmp_path, library, source):
    source.record = None
    library.import_file(_make_epub(tmp_path / "a.epub", title="Dune"))
    other = library.import_file(_make_epub(tmp_path / "b.epub", title="Emma"))

    library.edit(other, title="Dune")

    assert other.directory.name == "Dune (2)"
    assert sorted(b.directory.name for b in library.scan()) == ["Dune", "Dune (2)"]


# --- K3: re-identify ----------------------------------------------------


def test_reidentify_applies_a_new_match_to_an_unreviewed_book(library, book, source):
    assert book.identified is None

    source.results = [Candidate(title="Dune", author="Frank Herbert", cover_url=None)]
    library.reidentify(book)

    assert book.identified == MatchBasis.TITLE_AUTHOR
    assert library.scan()[0].identified == MatchBasis.TITLE_AUTHOR


def test_reidentify_leaves_a_reviewed_books_fields_alone(library, book, source):
    library.edit(book, author="The Real Author")

    source.results = [Candidate(title="Dune", author="Someone Else", cover_url=None)]
    library.reidentify(book)

    assert book.author == "The Real Author"
    assert library.scan()[0].author == "The Real Author"


def test_reidentify_records_the_sources_author_even_on_a_reviewed_book(library, book, source):
    """`record_author` is the source's statement, not the human's field
    (ADR-22), so a reviewed book still learns what the source says."""
    library.edit(book, author="Frank Herbert")

    source.results = [Candidate(title="Dune", author="Herbert, Frank", cover_url=None)]
    library.reidentify(book)

    assert book.author == "Frank Herbert"
    assert book.record_author == "Herbert, Frank"
    assert library.scan()[0].record_author == "Herbert, Frank"


def test_reidentify_fetches_a_missing_cover_for_a_reviewed_book(library, book, source):
    """The E12 route: a human fixes the title, then asks for the cover."""
    library.edit(book, title="Dune")
    assert book.cover_path is None

    source.results = [Candidate(title="Dune", author="Frank Herbert", cover_url="u")]
    source.cover = b"png bytes"
    library.reidentify(book)

    assert book.cover_path is not None
    assert book.cover_path.read_bytes() == b"png bytes"
    assert library.scan()[0].author == "Frank Herbert"


def test_reidentify_survives_a_failed_lookup(library, book, source):
    source.fail = True

    library.reidentify(book)

    assert book.title == "Dune"
    assert book.identified is None


def test_reidentify_never_renames_the_folder(library, book, source):
    directory = book.directory
    source.results = [Candidate(title="DUNE (Special Edition)", author=None, cover_url=None)]

    library.reidentify(book)

    assert book.title == "Dune"
    assert book.directory == directory
