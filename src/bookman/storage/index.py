"""Disposable sqlite3 search cache, rebuilt from metadata.json sidecars.

storage.catalog's metadata.json files are the source of truth. This index
exists purely so a TUI (or anything else) can filter/search quickly without
re-reading every metadata.json on each keystroke. Deleting the database
file and calling rebuild_index again always reproduces it faithfully.

Rows are keyed by the book folder's *name* (relative to the library
root), never an absolute path, so a relocated library keeps a valid
index. `PRAGMA user_version` stamps the schema; an index written by an
older layout is detected by `is_current` and rebuilt by its owner
(storage.store.Catalog) rather than read.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from bookman.errors import CatalogError
from bookman.models import Book
from bookman.storage.catalog import load_metadata

_log = logging.getLogger("bookman.storage")
_SCHEMA_VERSION = 2
_CREATE_TABLE = """
CREATE TABLE books (
    name TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    isbn TEXT,
    needs_review INTEGER NOT NULL
)
"""
_UPSERT = (
    "INSERT OR REPLACE INTO books (name, title, author, isbn, needs_review) "
    "VALUES (?, ?, ?, ?, ?)"
)


def rebuild_index(library_root: Path, db_path: Path) -> None:
    """Rebuild the search index from every metadata.json under library_root.

    Scans each immediate subdirectory of `library_root` for a
    metadata.json (via storage.catalog.load_metadata), and writes one
    row per book into a fresh sqlite3 database at `db_path`, replacing
    any existing database file. Subdirectories without a metadata.json,
    or with one that fails to parse, are skipped rather than raising.

    Args:
        library_root: The managed library's top-level directory, whose
            immediate subdirectories are book folders.
        db_path: Where to write the sqlite3 database file.

    Raises:
        OSError: If library_root does not exist, or db_path cannot be
            written.
    """
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_CREATE_TABLE)
        conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        for directory in sorted(p for p in library_root.iterdir() if p.is_dir()):
            try:
                book = load_metadata(directory)
            except FileNotFoundError:
                continue  # not a book folder
            except CatalogError as exc:
                _log.warning("not indexing %s: %s", directory, exc)
                continue
            conn.execute(_UPSERT, _row(directory.name, book))
        conn.commit()
    finally:
        conn.close()


def is_current(db_path: Path) -> bool:
    """Whether `db_path` is an index this module can read: it exists and
    carries the current schema stamp. False for a missing file or one
    written by an older layout (which must be rebuilt, not read).

    Args:
        db_path: Path to a sqlite3 database file.
    """
    if not db_path.exists():
        return False
    conn = sqlite3.connect(db_path)
    try:
        version: int = conn.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.DatabaseError:
        return False
    finally:
        conn.close()
    return version == _SCHEMA_VERSION


def upsert(db_path: Path, name: str, book: Book) -> None:
    """Insert or replace the row for one book folder.

    Args:
        db_path: Path to a sqlite3 database previously built by
            rebuild_index.
        name: The book folder's name, relative to the library root.
        book: The book as just saved to that folder.

    Raises:
        FileNotFoundError: If db_path does not exist.
    """
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_UPSERT, _row(name, book))
        conn.commit()
    finally:
        conn.close()


def delete(db_path: Path, name: str) -> None:
    """Drop the row for one book folder, if present.

    Args:
        db_path: Path to a sqlite3 database previously built by
            rebuild_index.
        name: The book folder's name, relative to the library root.

    Raises:
        FileNotFoundError: If db_path does not exist.
    """
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM books WHERE name = ?", (name,))
        conn.commit()
    finally:
        conn.close()


def search(db_path: Path, query: str) -> list[str]:
    """Search the index for books whose title or author matches query.

    Case-insensitive substring match against the indexed title and
    author columns. Case-folding is done via a registered Python
    function (str.casefold), not SQL's `COLLATE NOCASE` -- NOCASE only
    folds ASCII A-Z/a-z, so it silently fails to match e.g. Greek
    "Λ"/"λ" or accented "É"/"é". Does not read metadata.json itself --
    callers join the returned names back onto the library root and
    load the full Book via storage.catalog.load_metadata.

    Args:
        db_path: Path to a sqlite3 database previously built by
            rebuild_index.
        query: Substring to search for in title or author.

    Returns:
        Matching book folder names (relative to the library root), in
        folder-name order. Empty list if nothing matches or the index
        is empty.

    Raises:
        FileNotFoundError: If db_path does not exist.
    """
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.create_function("casefold", 1, lambda s: (s or "").casefold())
        like = f"%{query.casefold()}%"
        rows = conn.execute(
            "SELECT name FROM books "
            "WHERE casefold(title) LIKE ? OR casefold(author) LIKE ? "
            "ORDER BY name",
            (like, like),
        ).fetchall()
    finally:
        conn.close()
    return [str(row[0]) for row in rows]


def _row(name: str, book: Book) -> tuple[str, str, str | None, str | None, int]:
    return (name, book.title, book.author, book.isbn, int(book.needs_review))
