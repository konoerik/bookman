"""Catalog: every persisted book under one library root, behind one object.

Owns the two on-disk pieces of storage together -- the per-folder
metadata.json sidecars (storage.catalog, the source of truth) and the
sqlite search index (storage.index, a disposable cache) -- so that every
write keeps them consistent and no caller has to remember to reindex.
`Library` is the only intended user; a frontend goes through `Library`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from bookman.errors import CatalogError
from bookman.models import Book
from bookman.storage import index
from bookman.storage.catalog import load_metadata, save_metadata

_INDEX_FILENAME = ".bookman-index.sqlite3"
_log = logging.getLogger("bookman.storage")


class Catalog:
    """The set of cataloged books directly under a library root."""

    def __init__(self, root: Path) -> None:
        """Bind to a library root. Nothing is read or written until an
        operation needs it; the index is (re)built lazily on first use
        if it is missing or from an older layout.

        Args:
            root: The managed library's top-level directory, whose
                immediate subdirectories are book folders. Must exist.
        """
        self.root = root
        self._index_path = root / _INDEX_FILENAME

    def all(self) -> list[Book]:
        """Load every cataloged book, in folder-name order.

        A folder with no metadata.json, or one that fails to parse, is
        skipped rather than aborting the whole read.

        Returns:
            Every Book under `root`, each carrying its `directory`.

        Raises:
            FileNotFoundError: If `root` does not exist.
        """
        if not self.root.exists():
            raise FileNotFoundError(self.root)
        books = []
        for directory in sorted(p for p in self.root.iterdir() if p.is_dir()):
            try:
                books.append(load_metadata(directory))
            except FileNotFoundError:
                continue  # not a book folder
            except CatalogError as exc:
                _log.warning("skipping %s: %s", directory, exc)
        return books

    def get(self, directory: Path) -> Book:
        """Load one book by its folder.

        Args:
            directory: The book's folder under `root`.

        Returns:
            The Book as last saved there.

        Raises:
            FileNotFoundError: If the folder has no metadata.json.
            CatalogError: If its metadata.json is unreadable.
        """
        return load_metadata(directory)

    def put(self, book: Book, directory: Path | None = None) -> None:
        """Persist a book: write its metadata.json and update its index row.

        Args:
            book: The book to save. Its formats and cover must lie in
                its folder (see storage.catalog.save_metadata).
            directory: Where a not-yet-persisted book (one whose
                `directory` is None) should live. Ignored for a book
                that already has a `directory`, which is never re-homed.

        Raises:
            CatalogError: If neither `book.directory` nor `directory` is
                given, or if `directory` disagrees with `book.directory`.
            OSError: If the folder does not exist or the write fails.
        """
        target = book.directory or directory
        if target is None:
            raise CatalogError("a new book needs a directory to be saved into")
        save_metadata(book, target)
        self._ensure_index()
        index.upsert(self._index_path, target.name, book)

    def relocate(self, old_name: str, book: Book) -> None:
        """Record that `book`'s folder has been renamed on disk.

        Writes the book into its *current* folder and moves its search
        index row there, dropping the row for `old_name`. The new row
        is written before the old one is dropped, so an interruption
        leaves a stale row rather than no row -- and a stale row is
        already tolerated (`search` logs and skips a name it cannot
        load), whereas a missing one would hide the book until the
        index was rebuilt.

        The directory rename itself is the caller's business; `Catalog`
        owns metadata.json and the index, not the library's layout
        (ADR-12).

        Args:
            old_name: The folder name the book used to have.
            book: The book, with `directory` already pointing at its
                new folder.

        Raises:
            CatalogError: If `book.directory` is None.
            OSError: If the write fails.
        """
        if book.directory is None:
            raise CatalogError("a relocated book must carry its new directory")
        self.put(book)
        if book.directory.name != old_name:
            index.delete(self._index_path, old_name)

    def search(self, query: str) -> list[Book]:
        """Find books whose title or author contains `query`, case-folded.

        Args:
            query: Substring to look for.

        Returns:
            Matching Books, loaded fresh from their metadata.json (so
            results always reflect current on-disk state, never a stale
            index row), in folder-name order. A matched folder whose
            metadata.json is missing or unreadable is omitted.
        """
        self._ensure_index()
        books = []
        for name in index.search(self._index_path, query):
            try:
                books.append(load_metadata(self.root / name))
            except (FileNotFoundError, CatalogError) as exc:
                _log.warning("skipping indexed %s: %s", name, exc)
        return books

    def rebuild_index(self) -> None:
        """Rebuild the search index from every metadata.json under `root`.
        Never needed in normal use (every `put` keeps the index current);
        for repair after files were edited or moved by hand.

        Raises:
            OSError: If `root` does not exist or the index cannot be written.
        """
        index.rebuild_index(self.root, self._index_path)

    def _ensure_index(self) -> None:
        if not index.is_current(self._index_path):
            self.rebuild_index()
