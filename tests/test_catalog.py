import json

import pytest

from bookman.errors import CatalogError
from bookman.models import Book, BookFormat, FormatKind, MatchBasis
from bookman.storage.catalog import load_metadata, save_metadata


def _make_book_dir(tmp_path, **overrides):
    directory = tmp_path / "A Title"
    directory.mkdir()
    (directory / "book.epub").write_bytes(b"epub bytes")
    (directory / "book.pdf").write_bytes(b"pdf bytes")
    (directory / "cover.png").write_bytes(b"png bytes")

    book = Book(
        title="A Title",
        author="An Author",
        isbn="9780306406157",
        formats=[
            BookFormat(kind=FormatKind.EPUB, path=directory / "book.epub"),
            BookFormat(kind=FormatKind.PDF, path=directory / "book.pdf"),
        ],
        cover_path=directory / "cover.png",
        identified=MatchBasis.ISBN,
        grouped=MatchBasis.TITLE_AUTHOR,
        reviewed=True,
    )
    for key, value in overrides.items():
        setattr(book, key, value)
    return directory, book


def test_save_then_load_metadata_roundtrips_book(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)
    loaded = load_metadata(directory)

    assert loaded.title == book.title
    assert loaded.author == book.author
    assert loaded.isbn == book.isbn
    assert loaded.identified == book.identified
    assert loaded.grouped == book.grouped
    assert loaded.reviewed is True
    assert loaded.cover_path == book.cover_path
    assert {(f.kind, f.path) for f in loaded.formats} == {(f.kind, f.path) for f in book.formats}
    assert not (directory / "metadata.json.tmp").exists()


def test_save_and_load_set_the_books_directory(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    assert book.directory is None  # not persisted yet

    save_metadata(book, directory)
    assert book.directory == directory

    assert load_metadata(directory).directory == directory


def test_save_metadata_refuses_to_rehome_a_book(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)
    elsewhere = tmp_path / "Elsewhere"
    elsewhere.mkdir()

    with pytest.raises(ValueError):
        save_metadata(book, elsewhere)
    assert not (elsewhere / "metadata.json").exists()


def test_save_metadata_rejects_format_path_outside_directory(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    outside = tmp_path / "elsewhere.epub"
    outside.write_bytes(b"epub bytes")
    book.formats.append(BookFormat(kind=FormatKind.EPUB, path=outside))

    with pytest.raises(ValueError):
        save_metadata(book, directory)


def test_save_metadata_overwrites_existing_file(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    (directory / "metadata.json").write_text('{"stale": true}')

    save_metadata(book, directory)
    loaded = load_metadata(directory)
    assert loaded.title == book.title


def test_load_metadata_missing_file_raises_file_not_found(tmp_path):
    directory = tmp_path / "Empty"
    directory.mkdir()
    with pytest.raises(FileNotFoundError):
        load_metadata(directory)


def test_load_metadata_invalid_json_raises_value_error(tmp_path):
    directory = tmp_path / "Broken"
    directory.mkdir()
    (directory / "metadata.json").write_text("{not json")
    with pytest.raises(ValueError):
        load_metadata(directory)


def test_load_metadata_missing_required_field_raises_value_error(tmp_path):
    directory = tmp_path / "Incomplete"
    directory.mkdir()
    (directory / "metadata.json").write_text('{"title": "X"}')
    with pytest.raises(ValueError):
        load_metadata(directory)


def test_load_metadata_unknown_format_kind_raises_value_error(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)
    data = (directory / "metadata.json").read_text().replace('"epub"', '"azw3"')
    (directory / "metadata.json").write_text(data)

    with pytest.raises(ValueError):
        load_metadata(directory)


def test_load_metadata_resolves_paths_against_given_directory(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)

    moved = tmp_path / "Moved Title"
    directory.rename(moved)

    loaded = load_metadata(moved)
    assert loaded.cover_path == moved / "cover.png"
    assert {f.path for f in loaded.formats} == {moved / "book.epub", moved / "book.pdf"}


def test_load_metadata_rejects_format_filename_escaping_directory(tmp_path):
    directory = tmp_path / "A Title"
    directory.mkdir()
    data = {
        "title": "A Title",
        "author": None,
        "isbn": None,
        "confidence": "needs_review",
        "formats": [{"kind": "epub", "filename": "../../etc/evil.epub"}],
        "cover": None,
    }
    (directory / "metadata.json").write_text(json.dumps(data))

    with pytest.raises(ValueError):
        load_metadata(directory)


def test_load_metadata_rejects_cover_filename_escaping_directory(tmp_path):
    directory = tmp_path / "A Title"
    directory.mkdir()
    data = {
        "title": "A Title",
        "author": None,
        "isbn": None,
        "confidence": "needs_review",
        "formats": [],
        "cover": "../sibling/cover.png",
    }
    (directory / "metadata.json").write_text(json.dumps(data))

    with pytest.raises(ValueError):
        load_metadata(directory)


def _v1_metadata(confidence):
    return {
        "title": "Old Book",
        "author": "Old Author",
        "isbn": "9780306406157",
        "confidence": confidence,
        "formats": [{"kind": "epub", "filename": "book.epub"}],
        "cover": None,
    }


def test_save_then_load_metadata_roundtrips_none_fields(tmp_path):
    directory, book = _make_book_dir(tmp_path, identified=None, grouped=None, reviewed=False)
    save_metadata(book, directory)
    loaded = load_metadata(directory)

    assert loaded.identified is None
    assert loaded.grouped is None
    assert loaded.reviewed is False
    assert loaded.needs_review is True


def test_save_metadata_writes_schema_version_4_without_confidence(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)
    data = json.loads((directory / "metadata.json").read_text())

    assert data["version"] == 4
    assert data["id"] == book.id
    assert "confidence" not in data
    assert data["identified"] == "isbn"
    assert data["grouped"] == "title_author"
    assert data["reviewed"] is True


def test_load_metadata_migrates_version_1_verified(tmp_path):
    directory = tmp_path / "Old Book"
    directory.mkdir()
    (directory / "metadata.json").write_text(json.dumps(_v1_metadata("verified")))

    loaded = load_metadata(directory)

    assert loaded.identified == MatchBasis.ISBN
    assert loaded.grouped is None
    assert loaded.reviewed is False
    assert loaded.needs_review is False


def test_load_metadata_migrates_version_1_needs_review(tmp_path):
    directory = tmp_path / "Old Book"
    directory.mkdir()
    (directory / "metadata.json").write_text(json.dumps(_v1_metadata("needs_review")))

    loaded = load_metadata(directory)

    assert loaded.identified is None
    assert loaded.grouped is None
    assert loaded.needs_review is True


def test_load_metadata_upgrades_version_1_file_on_next_save(tmp_path):
    directory = tmp_path / "Old Book"
    directory.mkdir()
    (directory / "book.epub").write_bytes(b"epub bytes")
    (directory / "metadata.json").write_text(json.dumps(_v1_metadata("verified")))

    save_metadata(load_metadata(directory), directory)
    data = json.loads((directory / "metadata.json").read_text())

    assert data["version"] == 4
    assert data["identified"] == "isbn"
    assert data["id"]


def test_load_metadata_rejects_unknown_version_1_confidence(tmp_path):
    directory = tmp_path / "Old Book"
    directory.mkdir()
    (directory / "metadata.json").write_text(json.dumps(_v1_metadata("maybe")))

    with pytest.raises(ValueError):
        load_metadata(directory)


def test_load_metadata_rejects_unknown_match_basis(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)
    data = (directory / "metadata.json").read_text().replace('"title_author"', '"vibes"')
    (directory / "metadata.json").write_text(data)

    with pytest.raises(ValueError):
        load_metadata(directory)


def test_load_metadata_rejects_unsupported_schema_version(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)
    data = (directory / "metadata.json").read_text().replace('"version": 4', '"version": 99')
    (directory / "metadata.json").write_text(data)

    with pytest.raises(ValueError):
        load_metadata(directory)


def test_load_metadata_rejects_non_boolean_reviewed(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)
    data = (
        (directory / "metadata.json").read_text().replace('"reviewed": true', '"reviewed": "yes"')
    )
    (directory / "metadata.json").write_text(data)

    with pytest.raises(ValueError):
        load_metadata(directory)


# --- I5: stable book identity (ADR-17) ----------------------------------


def test_id_round_trips_through_save_and_load(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)

    assert load_metadata(directory).id == book.id


def test_id_survives_a_folder_rename(tmp_path):
    """The point of I5: a title edit renames the folder (K2), and the
    book must still be the same book afterwards."""
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)

    renamed = tmp_path / "A Corrected Title"
    directory.rename(renamed)

    assert load_metadata(renamed).id == book.id


def test_two_books_get_different_ids(tmp_path):
    first = Book(title="T", author=None, isbn=None)
    second = Book(title="T", author=None, isbn=None)

    assert first.id != second.id


def test_pre_v3_file_gets_a_stable_id_across_repeated_loads(tmp_path):
    """An un-upgraded book is read more than once before it is ever
    saved; a freshly minted id each time would be no identity at all."""
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)
    data = json.loads((directory / "metadata.json").read_text())
    del data["id"]
    data["version"] = 2
    (directory / "metadata.json").write_text(json.dumps(data))

    assert load_metadata(directory).id == load_metadata(directory).id


def test_record_author_round_trips(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    book.record_author = "Martin Luther King Jr., J.D. Jackson"
    save_metadata(book, directory)

    assert load_metadata(directory).record_author == "Martin Luther King Jr., J.D. Jackson"


def test_v3_file_without_record_author_loads_as_none(tmp_path):
    """A version-3 file predates `record_author` (ADR-22); it reads as
    unknown provenance and is upgraded on its next save."""
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)
    data = json.loads((directory / "metadata.json").read_text())
    del data["record_author"]
    data["version"] = 3
    (directory / "metadata.json").write_text(json.dumps(data))

    loaded = load_metadata(directory)
    assert loaded.record_author is None
    assert loaded.author == book.author

    save_metadata(loaded, directory)
    assert json.loads((directory / "metadata.json").read_text())["version"] == 4


def test_pre_v3_derived_id_becomes_a_stored_id_on_save(tmp_path):
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)
    data = json.loads((directory / "metadata.json").read_text())
    del data["id"]
    data["version"] = 2
    (directory / "metadata.json").write_text(json.dumps(data))

    derived = load_metadata(directory)
    save_metadata(derived, directory)
    renamed = tmp_path / "Moved After Upgrade"
    directory.rename(renamed)

    assert json.loads((renamed / "metadata.json").read_text())["id"] == derived.id
    assert load_metadata(renamed).id == derived.id


def test_version_1_file_gets_an_id(tmp_path):
    directory = tmp_path / "Old Book"
    directory.mkdir()
    (directory / "book.epub").write_bytes(b"epub bytes")
    (directory / "metadata.json").write_text(json.dumps(_v1_metadata("verified")))

    assert load_metadata(directory).id


@pytest.mark.parametrize("bad", [42, "", "   ", [], {}])
def test_load_metadata_rejects_a_malformed_id(tmp_path, bad):
    directory, book = _make_book_dir(tmp_path)
    save_metadata(book, directory)
    data = json.loads((directory / "metadata.json").read_text())
    data["id"] = bad
    (directory / "metadata.json").write_text(json.dumps(data))

    with pytest.raises(CatalogError):
        load_metadata(directory)
