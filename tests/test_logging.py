"""Swallowed failures are logged under the "bookman" logger, so a
frontend can show *why* a book came back file-only or was skipped."""

import logging

from helpers import make_epub

from bookman.storage.store import Catalog


def test_failed_lookup_is_logged_as_a_warning_and_import_continues(
    tmp_path, library, source, caplog
):
    source.fail = True

    with caplog.at_level(logging.WARNING, logger="bookman"):
        book = library.import_file(make_epub(tmp_path / "a.epub", title="Deep Work"))

    assert book.identified is None
    [record] = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert record.name == "bookman.identify"
    assert "search 'Deep Work' failed" in record.getMessage()


def test_failed_cover_download_is_logged_as_a_warning(tmp_path, library, source, caplog):
    from bookman.identify.source import Candidate

    source.results = [Candidate(title="Deep Work", author="Cal Newport", cover_url="c.jpg")]
    source.cover = None  # every fetch fails

    with caplog.at_level(logging.WARNING, logger="bookman"):
        book = library.import_file(
            make_epub(tmp_path / "a.epub", title="Deep Work", author="Cal Newport")
        )

    assert book.cover_path is None
    assert any("cover download" in r.getMessage() for r in caplog.records)


def test_skipped_corrupt_metadata_is_logged_with_its_folder(tmp_path, caplog):
    root = tmp_path / "Library"
    (root / "Broken").mkdir(parents=True)
    (root / "Broken" / "metadata.json").write_text("{")
    (root / "Not A Book").mkdir()

    with caplog.at_level(logging.WARNING, logger="bookman"):
        assert Catalog(root).all() == []

    messages = [r.getMessage() for r in caplog.records]
    assert any("Broken" in m for m in messages)
    assert not any("Not A Book" in m for m in messages)  # not a book folder: silent


def test_package_installs_a_null_handler_so_importing_is_silent():
    logger = logging.getLogger("bookman")
    assert any(isinstance(h, logging.NullHandler) for h in logger.handlers)
