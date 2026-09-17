"""Open Library metadata/cover lookup (stdlib urllib, no HTTP dependency).

The module functions are the client; `OpenLibrarySource` wraps them to
satisfy `identify.source.MetadataSource`, and is the default source a
`Library` uses.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from bookman.identify.source import Candidate, MetadataSourceError

_BOOKS_API_URL = "https://openlibrary.org/api/books"
_SEARCH_API_URL = "https://openlibrary.org/search.json"
_COVER_BY_ID_URL = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
_SEARCH_FIELDS = "title,author_name,cover_i"
_TIMEOUT_SECONDS = 10.0


class OpenLibraryError(MetadataSourceError):
    """Raised when an Open Library request fails or returns unusable data."""


class OpenLibrarySource:
    """Open Library as a `MetadataSource`: `lookup_by_isbn`, `search`,
    and `fetch_cover` delegate to this module's functions unchanged."""

    def lookup_by_isbn(self, isbn: str) -> Candidate | None:
        return lookup_by_isbn(isbn)

    def search(self, title: str, author: str | None = None) -> list[Candidate]:
        return search(title, author)

    def fetch_cover(self, url: str) -> bytes:
        return fetch_cover(url)


def lookup_by_isbn(isbn: str) -> Candidate | None:
    """Query Open Library's Books API for metadata by ISBN.

    Calls the Books API (bibkeys=ISBN:<isbn>, jscmd=data) which returns
    title, resolved author name(s), and cover image URLs in a single
    request. `isbn` is expected to already be a normalized, validated
    ISBN-13 (see bookman.identify.isbn.normalize_isbn) -- this function
    does not validate it further before querying.

    Args:
        isbn: A normalized ISBN-13 (digits only, no separators).

    Returns:
        A Candidate, or None if Open Library has no record for `isbn`
        (not treated as an error). Individual fields on the result may
        still be None if Open Library's record omits them.

    Raises:
        OpenLibraryError: If the request fails (network error, non-2xx
            response) or the response body isn't the expected JSON shape.
    """
    bibkey = f"ISBN:{isbn}"
    query = urllib.parse.urlencode({"bibkeys": bibkey, "jscmd": "data", "format": "json"})
    raw = _fetch_bytes(f"{_BOOKS_API_URL}?{query}")

    try:
        payload = json.loads(raw)
        entry = payload.get(bibkey)
        if entry is None:
            return None
        return Candidate(
            title=entry.get("title"),
            author=_join_authors(entry.get("authors")),
            cover_url=_best_cover_url(entry.get("cover")),
        )
    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
        raise OpenLibraryError(f"unexpected response shape for {bibkey}") from exc


def search(title: str, author: str | None = None, *, limit: int = 5) -> list[Candidate]:
    """Query Open Library's Search API for candidate records by title
    (and author, if known).

    Calls /search.json with `title=` and, when given, `author=`,
    asking only for the title, author names, and cover id of each
    document. Results come back in Open Library's own relevance order;
    nothing here judges whether any of them is actually the book --
    that's `bookman.identify.match.match_basis`'s job.

    Args:
        title: The title to search for, as parsed from the file.
        author: The author to narrow by, or None to search by title only.
        limit: Maximum number of candidates to return.

    Returns:
        Up to `limit` Candidates, possibly empty if nothing
        matched (not treated as an error). A result's `cover_url`
        points at the large cover for the document's `cover_i`, or is
        None if the document has no cover.

    Raises:
        OpenLibraryError: If the request fails (network error, non-2xx
            response) or the response body isn't the expected JSON shape.
    """
    params = {"title": title, "limit": str(limit), "fields": _SEARCH_FIELDS}
    if author:
        params["author"] = author
    raw = _fetch_bytes(f"{_SEARCH_API_URL}?{urllib.parse.urlencode(params)}")

    try:
        payload = json.loads(raw)
        docs = payload.get("docs") or []
        return [
            Candidate(
                title=doc.get("title"),
                author=_join_names(doc.get("author_name")),
                cover_url=_cover_url_for_id(doc.get("cover_i")),
            )
            for doc in docs
        ]
    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
        raise OpenLibraryError("unexpected response shape from search") from exc


def fetch_cover(url: str) -> bytes:
    """Download cover image bytes from a URL returned by lookup_by_isbn.

    Args:
        url: A `cover_url` value from a Candidate.

    Returns:
        Raw image bytes as returned by the server (format depends on
        `url`, typically JPEG).

    Raises:
        OpenLibraryError: If the request fails (network error, non-2xx
            response).
    """
    return _fetch_bytes(url)


def _fetch_bytes(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT_SECONDS) as response:
            data: bytes = response.read()
            return data
    except (urllib.error.URLError, OSError) as exc:
        raise OpenLibraryError(f"request to {url} failed: {exc}") from exc


def _join_authors(authors: object) -> str | None:
    if not isinstance(authors, list):
        return None
    names = []
    for entry in authors:
        if isinstance(entry, dict):
            name = entry.get("name")
            if name:
                names.append(name)
    return ", ".join(names) if names else None


def _join_names(names: object) -> str | None:
    if not isinstance(names, list):
        return None
    cleaned = [name for name in names if isinstance(name, str) and name]
    return ", ".join(cleaned) if cleaned else None


def _cover_url_for_id(cover_id: object) -> str | None:
    if isinstance(cover_id, int) and cover_id > 0:
        return _COVER_BY_ID_URL.format(cover_id=cover_id)
    return None


def _best_cover_url(cover: object) -> str | None:
    if not isinstance(cover, dict):
        return None
    for size in ("large", "medium", "small"):
        value = cover.get(size)
        if value:
            return str(value)
    return None
