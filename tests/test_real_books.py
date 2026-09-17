"""Integration tests against real, small public-domain EPUBs (Project
Gutenberg) checked into tests/fixtures/books/. Unlike the synthetic
fixtures the other test modules build, these exercise bookman against
real-world EPUB structure and real non-ASCII (Greek, Spanish) text --
frozen locally, so they're as reproducible as any synthetic fixture.

None of these books carry an ISBN and title search would run for each;
`NullSource` keeps them offline and exercises the file-only path."""

from pathlib import Path

from bookman import Library, NullSource

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "books"


def test_import_directory_imports_every_real_fixture_cleanly(tmp_path):
    library = Library(tmp_path / "Library", source=NullSource())

    result = library.import_directory(FIXTURES_DIR)

    assert result.failed == []
    assert len(result.imported) == 4


def test_real_fixtures_have_no_isbn_and_need_review(tmp_path):
    library = Library(tmp_path / "Library", source=NullSource())
    library.import_directory(FIXTURES_DIR)

    for book in library.scan():
        assert book.isbn is None
        assert book.identified is None
        assert book.needs_review


def test_real_fixture_titles_and_authors_are_parsed_correctly(tmp_path):
    library = Library(tmp_path / "Library", source=NullSource())
    library.import_directory(FIXTURES_DIR)

    by_title = {book.title: book.author for book in library.scan()}

    assert by_title["Alice's Adventures in Wonderland"] == "Lewis Carroll"
    assert by_title["A Christmas Carol in Prose; Being a Ghost Story of Christmas"] == (
        "Charles Dickens"
    )
    assert by_title["Λουκής Λάρας"] == "Demetrios Vikelas"
    assert by_title["Vida De Lazarillo De Tormes Y De Sus Fortunas Y Adversidades"] == "Anonymous"


def test_search_matches_greek_title_case_insensitively(tmp_path):
    library = Library(tmp_path / "Library", source=NullSource())
    library.import_directory(FIXTURES_DIR)

    results = library.search("λάρας")

    assert {book.title for book in results} == {"Λουκής Λάρας"}


def test_search_matches_spanish_title_substring(tmp_path):
    library = Library(tmp_path / "Library", source=NullSource())
    library.import_directory(FIXTURES_DIR)

    results = library.search("lazarillo")

    assert {book.title for book in results} == {
        "Vida De Lazarillo De Tormes Y De Sus Fortunas Y Adversidades"
    }
