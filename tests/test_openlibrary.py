import json
import urllib.error

import pytest

from bookman.identify.openlibrary import (
    OpenLibraryError,
    OpenLibrarySource,
    fetch_cover,
    lookup_by_isbn,
    search,
)
from bookman.identify.source import MetadataSourceError

ISBN = "9780306406157"
BIBKEY = f"ISBN:{ISBN}"


class _FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return self._data


def _patch_urlopen(monkeypatch, *, returns: bytes | None = None, raises: Exception | None = None):
    """Stub urlopen; returns a list that records every URL requested."""
    urls = []

    def fake_urlopen(url, timeout=None):
        urls.append(url)
        if raises is not None:
            raise raises
        return _FakeResponse(returns)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return urls


def test_lookup_by_isbn_returns_metadata_for_known_isbn(monkeypatch):
    payload = {
        BIBKEY: {
            "title": "Godel, Escher, Bach",
            "authors": [{"name": "Douglas Hofstadter"}],
            "cover": {"small": "s.jpg", "medium": "m.jpg", "large": "l.jpg"},
        }
    }
    _patch_urlopen(monkeypatch, returns=json.dumps(payload).encode())

    result = lookup_by_isbn(ISBN)

    assert result.title == "Godel, Escher, Bach"
    assert result.author == "Douglas Hofstadter"
    assert result.cover_url == "l.jpg"


def test_lookup_by_isbn_returns_none_for_unknown_isbn(monkeypatch):
    _patch_urlopen(monkeypatch, returns=json.dumps({}).encode())

    assert lookup_by_isbn(ISBN) is None


def test_lookup_by_isbn_raises_open_library_error_on_http_failure(monkeypatch):
    _patch_urlopen(monkeypatch, raises=urllib.error.URLError("boom"))

    with pytest.raises(OpenLibraryError):
        lookup_by_isbn(ISBN)


def test_lookup_by_isbn_raises_open_library_error_on_malformed_response(monkeypatch):
    _patch_urlopen(monkeypatch, returns=b"not valid json")

    with pytest.raises(OpenLibraryError):
        lookup_by_isbn(ISBN)


def test_fetch_cover_returns_image_bytes(monkeypatch):
    image_bytes = b"\xff\xd8\xff fake jpeg bytes"
    _patch_urlopen(monkeypatch, returns=image_bytes)

    assert fetch_cover("https://covers.openlibrary.org/b/isbn/x-L.jpg") == image_bytes


def test_fetch_cover_raises_open_library_error_on_http_failure(monkeypatch):
    _patch_urlopen(monkeypatch, raises=urllib.error.URLError("boom"))

    with pytest.raises(OpenLibraryError):
        fetch_cover("https://covers.openlibrary.org/b/isbn/x-L.jpg")


def test_search_returns_results_with_cover_url_from_cover_i(monkeypatch):
    payload = {
        "numFound": 2,
        "docs": [
            {
                "title": "Alice's Adventures in Wonderland",
                "author_name": ["Lewis Carroll"],
                "cover_i": 10527843,
            },
            {
                "title": "Alice / Through the Looking Glass",
                "author_name": ["Lewis Carroll", "John Tenniel"],
            },
        ],
    }
    urls = _patch_urlopen(monkeypatch, returns=json.dumps(payload).encode())

    results = search("Alice's Adventures in Wonderland", "Lewis Carroll")

    assert [r.title for r in results] == [
        "Alice's Adventures in Wonderland",
        "Alice / Through the Looking Glass",
    ]
    assert results[0].author == "Lewis Carroll"
    assert results[0].cover_url == "https://covers.openlibrary.org/b/id/10527843-L.jpg"
    assert results[1].author == "Lewis Carroll, John Tenniel"
    assert results[1].cover_url is None
    assert urls[0].startswith("https://openlibrary.org/search.json?")
    assert "title=Alice%27s+Adventures+in+Wonderland" in urls[0]
    assert "author=Lewis+Carroll" in urls[0]
    assert "limit=5" in urls[0]


def test_search_returns_empty_list_when_no_docs(monkeypatch):
    _patch_urlopen(monkeypatch, returns=json.dumps({"numFound": 0, "docs": []}).encode())

    assert search("Nothing Like This Exists") == []


def test_search_omits_author_param_when_none(monkeypatch):
    urls = _patch_urlopen(monkeypatch, returns=json.dumps({"docs": []}).encode())

    search("Lazarillo de Tormes", None, limit=3)

    assert "author=" not in urls[0]
    assert "limit=3" in urls[0]


def test_search_raises_open_library_error_on_http_failure(monkeypatch):
    _patch_urlopen(monkeypatch, raises=urllib.error.URLError("boom"))

    with pytest.raises(OpenLibraryError):
        search("Anything")


def test_search_raises_open_library_error_on_malformed_response(monkeypatch):
    _patch_urlopen(monkeypatch, returns=b"[not, an, object")

    with pytest.raises(OpenLibraryError):
        search("Anything")


def test_search_raises_open_library_error_on_wrong_shape(monkeypatch):
    _patch_urlopen(monkeypatch, returns=json.dumps({"docs": [42]}).encode())

    with pytest.raises(OpenLibraryError):
        search("Anything")


def test_open_library_error_is_a_metadata_source_error():
    assert issubclass(OpenLibraryError, MetadataSourceError)


def test_open_library_source_delegates_to_the_module_functions(monkeypatch):
    urls = _patch_urlopen(monkeypatch, returns=json.dumps({"docs": []}).encode())

    assert OpenLibrarySource().search("Deep Work", "Cal Newport") == []
    assert "search.json" in urls[0]
