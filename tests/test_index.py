import sqlite3

import pytest

from bookman.models import Book, BookFormat, FormatKind, MatchBasis
from bookman.storage.catalog import save_metadata
from bookman.storage.index import delete, is_current, rebuild_index, search, upsert


def _add_book(library_root, title, author, isbn="9780306406157"):
    directory = library_root / title
    directory.mkdir()
    (directory / "book.epub").write_bytes(b"epub bytes")
    book = Book(
        title=title,
        author=author,
        isbn=isbn,
        formats=[BookFormat(kind=FormatKind.EPUB, path=directory / "book.epub")],
        identified=MatchBasis.ISBN,
    )
    save_metadata(book, directory)
    return book


def _row_count(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    finally:
        conn.close()


def test_rebuild_index_finds_books_with_metadata_json(tmp_path):
    library_root = tmp_path / "Library"
    library_root.mkdir()
    _add_book(library_root, "Deep Work", "Cal Newport")
    _add_book(library_root, "Sapiens", "Yuval Noah Harari")
    db_path = tmp_path / "index.sqlite3"

    rebuild_index(library_root, db_path)

    assert _row_count(db_path) == 2


def test_rebuild_index_skips_subdirectories_without_metadata_json(tmp_path):
    library_root = tmp_path / "Library"
    library_root.mkdir()
    _add_book(library_root, "Deep Work", "Cal Newport")
    (library_root / "Not A Book").mkdir()
    db_path = tmp_path / "index.sqlite3"

    rebuild_index(library_root, db_path)

    assert _row_count(db_path) == 1


def test_rebuild_index_overwrites_existing_database_file(tmp_path):
    library_root = tmp_path / "Library"
    library_root.mkdir()
    _add_book(library_root, "Deep Work", "Cal Newport")
    db_path = tmp_path / "index.sqlite3"
    rebuild_index(library_root, db_path)

    _add_book(library_root, "Sapiens", "Yuval Noah Harari")
    rebuild_index(library_root, db_path)

    assert _row_count(db_path) == 2


def test_search_matches_title_case_insensitively(tmp_path):
    library_root = tmp_path / "Library"
    library_root.mkdir()
    _add_book(library_root, "Deep Work", "Cal Newport")
    db_path = tmp_path / "index.sqlite3"
    rebuild_index(library_root, db_path)

    assert search(db_path, "deep work") == ["Deep Work"]


def test_search_matches_author_substring(tmp_path):
    library_root = tmp_path / "Library"
    library_root.mkdir()
    _add_book(library_root, "Sapiens", "Yuval Noah Harari")
    db_path = tmp_path / "index.sqlite3"
    rebuild_index(library_root, db_path)

    assert search(db_path, "harari") == ["Sapiens"]


def test_search_matches_non_ascii_title_case_insensitively(tmp_path):
    library_root = tmp_path / "Library"
    library_root.mkdir()
    _add_book(library_root, "Λουκής Λάρας", "Demetrios Vikelas")
    db_path = tmp_path / "index.sqlite3"
    rebuild_index(library_root, db_path)

    assert search(db_path, "λάρας") == ["Λουκής Λάρας"]


def test_search_returns_empty_for_no_match(tmp_path):
    library_root = tmp_path / "Library"
    library_root.mkdir()
    _add_book(library_root, "Deep Work", "Cal Newport")
    db_path = tmp_path / "index.sqlite3"
    rebuild_index(library_root, db_path)

    assert search(db_path, "nonexistent") == []


def test_search_raises_file_not_found_for_missing_db(tmp_path):
    with pytest.raises(FileNotFoundError):
        search(tmp_path / "missing.sqlite3", "anything")


def test_upsert_adds_a_row_and_replaces_it_on_the_same_name(tmp_path):
    library_root = tmp_path / "Library"
    library_root.mkdir()
    db_path = tmp_path / "index.sqlite3"
    rebuild_index(library_root, db_path)
    book = _add_book(library_root, "Deep Work", "Cal Newport")

    upsert(db_path, "Deep Work", book)
    book.author = "C. Newport"
    upsert(db_path, "Deep Work", book)

    assert _row_count(db_path) == 1
    assert search(db_path, "c. newport") == ["Deep Work"]
    assert search(db_path, "cal newport") == []


def test_delete_drops_the_row_and_tolerates_a_missing_one(tmp_path):
    library_root = tmp_path / "Library"
    library_root.mkdir()
    _add_book(library_root, "Deep Work", "Cal Newport")
    db_path = tmp_path / "index.sqlite3"
    rebuild_index(library_root, db_path)

    delete(db_path, "Deep Work")
    delete(db_path, "Never Indexed")

    assert _row_count(db_path) == 0


def test_upsert_and_delete_raise_file_not_found_for_missing_db(tmp_path):
    book = Book(title="T", author=None, isbn=None)
    with pytest.raises(FileNotFoundError):
        upsert(tmp_path / "missing.sqlite3", "T", book)
    with pytest.raises(FileNotFoundError):
        delete(tmp_path / "missing.sqlite3", "T")


def test_is_current_only_for_an_index_with_the_current_schema_stamp(tmp_path):
    library_root = tmp_path / "Library"
    library_root.mkdir()
    db_path = tmp_path / "index.sqlite3"
    assert not is_current(db_path)  # missing

    rebuild_index(library_root, db_path)
    assert is_current(db_path)

    # An index written by the pre-R3 layout carried no version stamp.
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    conn.close()
    assert not is_current(db_path)

    db_path.write_bytes(b"not a database")
    assert not is_current(db_path)
