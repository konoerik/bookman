"""The exception hierarchy a frontend can rely on."""

import pytest

import bookman
from bookman import (
    BadEpubError,
    BadPdfError,
    BookmanError,
    CatalogError,
    ConfigError,
    LibraryNotConfiguredError,
    MetadataSourceError,
    OpenLibraryError,
    ParseError,
    UnsupportedFormatError,
)


@pytest.mark.parametrize(
    ("error", "parents"),
    [
        (ParseError, (BookmanError, ValueError)),
        (BadEpubError, (ParseError,)),
        (BadPdfError, (ParseError,)),
        (UnsupportedFormatError, (BookmanError, ValueError)),
        (MetadataSourceError, (BookmanError,)),
        (OpenLibraryError, (MetadataSourceError,)),
        (CatalogError, (BookmanError, ValueError)),
        (ConfigError, (BookmanError, ValueError)),
        (LibraryNotConfiguredError, (BookmanError,)),
    ],
)
def test_every_bookman_error_has_its_documented_parents(error, parents):
    for parent in parents:
        assert issubclass(error, parent)
    assert issubclass(error, BookmanError)


def test_every_exported_error_is_a_bookman_error():
    exported = [
        getattr(bookman, name)
        for name in bookman.__all__
        if isinstance(getattr(bookman, name), type)
        and issubclass(getattr(bookman, name), BaseException)
    ]
    assert exported, "no error types exported?"
    assert all(issubclass(e, BookmanError) for e in exported)


def test_corrupt_metadata_raises_catalog_error(tmp_path):
    from bookman.storage.catalog import load_metadata

    (tmp_path / "metadata.json").write_text("{")
    with pytest.raises(CatalogError):
        load_metadata(tmp_path)


def test_bad_config_file_raises_config_error(tmp_path, monkeypatch):
    from bookman import config

    path = tmp_path / "config.json"
    path.write_text("nope")
    monkeypatch.setenv(config.ENV_CONFIG, str(path))
    with pytest.raises(ConfigError):
        config.load_config()
