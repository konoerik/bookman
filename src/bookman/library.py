"""Library: the orchestration layer tying parsing, identification, and
storage into an end-to-end import flow. This is bookman's main entry point
for a consumer (e.g. the companion TUI) once implemented.
"""

from __future__ import annotations

import filecmp
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from bookman.errors import CatalogError, FormatConflictError, MetadataSourceError
from bookman.formats import is_supported, parser_for
from bookman.formats.base import ParsedMetadata
from bookman.identify.isbn import is_valid_isbn, normalize_isbn
from bookman.identify.match import match_basis
from bookman.identify.openlibrary import OpenLibrarySource
from bookman.identify.resolve import Identification, identify
from bookman.identify.source import MetadataSource
from bookman.models import (
    Book,
    BookFormat,
    FormatKind,
    MatchBasis,
    stronger_basis,
    weaker_basis,
)
from bookman.storage.catalog import save_metadata
from bookman.storage.store import Catalog

# A colon is the usual title/subtitle separator, so it becomes " -"
# rather than vanishing ("Deep Work: Rules" -> "Deep Work - Rules", not
# "Deep Work Rules"). The rest are dropped outright.
_DIRNAME_COLON = re.compile(r"\s*:")
_UNSAFE_DIRNAME_CHARS = re.compile(r'[\\/*?"<>|]')
_MAX_DIRNAME_LENGTH = 150
_log = logging.getLogger("bookman.library")


class _Unset:
    """Sentinel for an argument that was not passed, as distinct from an
    argument explicitly passed as None (which *clears* a field)."""

    def __repr__(self) -> str:
        return "<unset>"


_UNSET = _Unset()


@dataclass
class ImportBatchResult:
    """The outcome of importing every supported file in a directory.

    Attributes:
        imported: (source path, Book) for each file that imported, in
            processing order. A book fed by several files appears once
            per file, each time reflecting its state after that file.
        failed: (source path, exception) for each file that raised.
        skipped: Non-hidden files with no registered format parser
            (e.g. a bundle's .mobi). Not an error, but the user should
            hear that they weren't imported.
        conflicts: Files refused because the book they belong to already
            holds a different file of the same kind (spec GROUP-4,
            ADR-21). Not a failure: nothing is wrong with the file, and
            nothing was changed. Each carries what a frontend needs to
            ask the user what they meant -- see `FormatConflictError`.
    """

    imported: list[tuple[Path, Book]] = field(default_factory=list)
    failed: list[tuple[Path, Exception]] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    conflicts: list[FormatConflictError] = field(default_factory=list)


class Library:
    """A managed ebook library rooted at a single flat directory of book folders.

    **One writer at a time.** A library root assumes a single process
    writes to it: one TUI, or one CLI command, not both at once and not
    two TUIs. Reads (`scan`, `search`) are safe alongside a writer --
    each metadata.json is written atomically and the search index is
    replaced in one step -- but two concurrent *imports* into the same
    root can interleave: both may resolve the same file to the same
    book and race on its folder, and the second `metadata.json` write
    wins. Nothing detects or prevents this; there is no lock file
    (FEATURES M6). Any `Library` instances *within* one process share
    the same assumption -- the class holds no lock either.
    """

    def __init__(self, root: Path, *, source: MetadataSource | None = None) -> None:
        """Open (or initialize) a managed library at `root`.

        Args:
            root: The library's top-level directory. Created (including
                any missing parents) if it doesn't already exist.
            source: Where imports look books up. Defaults to Open
                Library; pass `NullSource()` for offline, file-only
                imports, or any other `MetadataSource`.
        """
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._catalog = Catalog(root)
        self._source: MetadataSource = source if source is not None else OpenLibrarySource()

    def import_file(self, path: Path) -> Book:
        """Identify, place, and catalog a single ebook file into the library.

        Pipeline:
        1. Parse `path` with the parser registered for its suffix
           (bookman.formats: .epub -> parse_epub, .pdf -> parse_pdf).
        2. Identify it (identify.resolve.identify): look up the file's
           ISBN, or search the metadata source by the file's title/author,
           per `docs/IDENTIFICATION.md` steps IDENT-1..6,
           and accept a record only if it agrees with what the file
           says about itself (identify.match.match_basis). An
           accepted record supplies a cover URL and fills a missing
           title or author, while a title or author the file has
           stays the file's own (the two agree, and the file's
           spelling is the publisher's; ADR-10, ADR-22) -- the record's
           author is kept as `record_author`; a rejected ISBN is
           discarded. Otherwise the file's own title/author stand,
           with `identified=None`.
        3. Decide which book folder this file belongs to
           (`_find_book`; spec GROUP-1..3):
           a. An existing book with the same ISBN: that folder
              (basis ISBN).
           b. Otherwise an existing book whose title and author agree
              with the resolved ones (basis TITLE_AUTHOR), or -- when
              an author is missing on either side -- whose normalized
              title is identical (basis TITLE_ONLY). Authors that
              disagree never group, whatever the titles.
           c. Otherwise, this is a new book: create a folder named
              after the resolved title (filesystem-sanitized: a colon
              becomes " -", other unsafe characters are dropped; with
              a numeric suffix appended if that name is already taken
              by an unrelated folder).
        4. Copy (not move -- the source file is left in place)
           `path` into that folder as `<folder name><suffix>`, so every
           format of a book shares its folder's name. A book holds one
           file per kind (spec GROUP-4, ADR-21): if the folder already
           has a *different* file of this kind the import is refused
           with `FormatConflictError` before anything is touched; the
           same bytes again is a re-import and simply replaces the
           file (also removing a pre-0.3 `book<suffix>` name).
        5. Record the evidence on the Book (spec GROUP-4):
           - New book (3c): `identified` is step 2's basis (or None),
             `grouped` stays None.
           - Existing book (3a/3b): `grouped` becomes the weaker of
             its previous value and this join's basis -- it records
             the weakest link ever used, so a title-only join is
             remembered even after later ISBN joins.
           - Existing book, not `reviewed`: if step 2 identified the
             file at least as strongly as the book was identified
             before, the resolved author/cover and `identified`
             replace the book's; the title is replaced only on
             *strictly* stronger evidence, so equally-identified
             formats don't take turns respelling it. A failed or
             weaker lookup on a follow-up format changes nothing
             (identification never downgrades).
           - Existing book, `reviewed`: title/author/isbn/cover/
             `identified` are left exactly as the human set them. A
             TITLE_ONLY join clears `reviewed`, since the book's
             contents changed in a doubtful way.
        6. Write/overwrite metadata.json for the resulting folder and
           update its row in the search index (storage.store.Catalog.put).

        Args:
            path: Path to the ebook file to import.

        Returns:
            The Book as cataloged after this import, reflecting every
            format currently in its folder -- not just the one just
            added.

        Raises:
            FileNotFoundError: If path does not exist.
            UnsupportedFormatError: If path's suffix has no registered
                parser (e.g. .mobi -- not supported until a later
                slice; see ROADMAP).
            FormatConflictError: If the book this file belongs to
                already holds a different file of the same format kind.
                Nothing has been changed when this is raised.
            BadEpubError: Propagated unchanged if path is a .epub that
                formats.epub.parse_epub cannot read (a `ParseError`).
            BadPdfError: Propagated unchanged if path is a .pdf that
                formats.pdf.parse_pdf cannot read (a `ParseError`).
            OSError: If copying the file, or writing metadata.json or
                cover.png, fails (e.g. disk full, permissions).
        """
        if not path.exists():
            raise FileNotFoundError(path)
        kind, parser = parser_for(path)

        parsed = parser(path)
        found = identify(parsed, self._source)
        title = found.title or path.stem

        match = self._find_book(title, found.author, found.isbn)
        if match is None:
            directory = self._new_directory(title)
            book, join = Book(title=title, author=found.author, isbn=found.isbn), None
        else:
            book, join = match
            assert book.directory is not None  # every loaded Book carries it (ADR-11)
            directory = book.directory
            _refuse_conflicting_format(book, path, kind, join, found, title=title)

        _place_format(book, directory, path, kind)
        cover_url = _apply_identification(book, found, join, title=title)
        if cover_url:
            self._save_cover(book, directory, cover_url)

        self._persist(book, directory)
        return book

    def import_directory(self, directory: Path, *, recursive: bool = False) -> ImportBatchResult:
        """Import every file with a registered format parser under `directory`.

        Calls `import_file` once per matching file (in sorted path
        order, for deterministic output). A single file's failure --
        an unsupported format slipping through, a corrupt EPUB/PDF, or
        an OSError writing its destination -- is caught and recorded
        rather than aborting the batch, so one bad file in a bundle
        doesn't block the rest (mirrors `scan`'s skip-and-continue
        treatment of a bad metadata.json).

        Args:
            directory: Directory to import from. Only files directly
                inside it are considered unless `recursive` is set.
            recursive: If True, also import matching files in
                subdirectories. Defaults to False (top level only).

        Returns:
            An ImportBatchResult (see its attributes). Files whose
            suffix has no parser land in `skipped` rather than being
            attempted; hidden files (a leading dot, e.g. .DS_Store) are
            ignored entirely. A file refused for colliding with a book's
            existing file of the same kind lands in `conflicts`, not
            `failed`.

        Raises:
            FileNotFoundError: If `directory` does not exist.
            NotADirectoryError: If `directory` exists but isn't a
                directory.
        """
        if not directory.exists():
            raise FileNotFoundError(directory)
        if not directory.is_dir():
            raise NotADirectoryError(directory)

        candidates = directory.rglob("*") if recursive else directory.iterdir()
        files = sorted(
            path for path in candidates if path.is_file() and not path.name.startswith(".")
        )

        result = ImportBatchResult()
        for path in files:
            if not is_supported(path):
                result.skipped.append(path)
                continue
            try:
                result.imported.append((path, self.import_file(path)))
            except FormatConflictError as conflict:
                result.conflicts.append(conflict)
            except Exception as exc:
                # One bad file must not abort the batch.
                result.failed.append((path, exc))
        return result

    def scan(self) -> list[Book]:
        """Load every cataloged book directly under `root`.

        Equivalent to calling storage.catalog.load_metadata on every
        immediate subdirectory of `root` that has a metadata.json,
        skipping ones that don't.

        A folder with a metadata.json that fails to parse (invalid
        JSON, missing field, unrecognized enum value) is skipped the
        same as one with no metadata.json at all, rather than aborting
        the whole scan.

        The search index is refreshed from what was read, so a
        metadata.json edited by hand (the way to fix a book without a
        frontend, ADR-24) is found by `search` after the next scan
        without any repair step. metadata.json stays the source of
        truth; the index only ever restates it (ADR-12).

        Returns:
            Every cataloged Book in the library, in folder-name order,
            each carrying its `directory`.

        Raises:
            FileNotFoundError: If `root` itself does not exist.
        """
        books = self._catalog.all()
        self._catalog.reindex(books)
        return books

    def search(self, query: str) -> list[Book]:
        """Search cataloged books by title/author substring.

        Uses the sqlite search index (storage.index), building it
        first if it is missing or from an older layout, so a fresh or
        relocated Library can be searched without an explicit rebuild.

        Args:
            query: Substring to match against title or author
                (case-insensitive).

        Returns:
            Matching Books, loaded fresh from their metadata.json (so
            results always reflect current on-disk state, never a
            stale index row), in folder-name order. A matched directory
            whose metadata.json is missing or fails to parse is
            silently omitted rather than raising.
        """
        return self._catalog.search(query)

    def mark_reviewed(self, book: Book, reviewed: bool = True) -> Book:
        """Record that a human has (or has not) checked this book.

        A reviewed book is excluded from the review queue
        (`Book.needs_review`) and its title/author/isbn/cover survive
        any later import (ADR-4, ADR-9). Clearing the flag puts it back
        in the queue without changing anything else.

        Args:
            book: A persisted book, as returned by `scan`, `search` or
                `import_file`.
            reviewed: True to mark it checked, False to un-mark it.

        Returns:
            The same Book, updated and saved.

        Raises:
            CatalogError: If `book` has never been persisted.
            OSError: If the write fails.
        """
        directory = _persisted_directory(book)
        book.reviewed = reviewed
        self._persist(book, directory)
        _log.info("marked %r reviewed=%s", book.title, reviewed)
        return book

    def edit(
        self,
        book: Book,
        *,
        title: str | _Unset = _UNSET,
        author: str | None | _Unset = _UNSET,
        isbn: str | None | _Unset = _UNSET,
    ) -> Book:
        """Correct a book's metadata by hand.

        Omit an argument to leave that field alone; pass None to
        `author` or `isbn` to clear it (a PDF whose `/Author` is
        "Adobe InDesign" is worth erasing, not keeping). `title` cannot
        be cleared -- every book has one.

        Editing **sets `reviewed`**. This is not a convenience: an
        un-reviewed edit would be silently overwritten the next time a
        format of the same book is imported and identified more
        strongly, so an edit that did not set the flag would not be
        durable (ADR-18). Call `mark_reviewed(book, False)` afterwards
        to put it back in the queue.

        Changing the title renames the book's folder and every format
        file inside it, since both are named after the title (ADR-1,
        ADR-10). If the new name is taken by an unrelated book, a
        numeric suffix is appended, exactly as on import.

        Args:
            book: A persisted book, as returned by `scan`, `search` or
                `import_file`. Mutated in place.
            title: A new title. Must contain something.
            author: A new author string, or None to clear it.
            isbn: A new ISBN-10 or ISBN-13 in any punctuation, stored
                normalized to ISBN-13, or None to clear it.

        Returns:
            The same Book, updated and saved, with `directory`,
            `formats` and `cover_path` repointed if it moved.

        Raises:
            CatalogError: If `book` has never been persisted, `title`
                is empty or blank, or `isbn` is not a valid ISBN.
            OSError: If the rename or the write fails.
        """
        directory = _persisted_directory(book)

        if not isinstance(isbn, _Unset) and isbn is not None:
            if not is_valid_isbn(isbn):
                raise CatalogError(f"not a valid ISBN: {isbn!r}")
            isbn = normalize_isbn(isbn)
        if not isinstance(title, _Unset) and not title.strip():
            raise CatalogError("a book's title cannot be blank")

        if not isinstance(author, _Unset):
            book.author = author
        if not isinstance(isbn, _Unset):
            book.isbn = isbn
        book.reviewed = True

        renamed = not isinstance(title, _Unset) and title != book.title
        if not isinstance(title, _Unset):
            book.title = title
        if not renamed:
            self._persist(book, directory)
            return book

        if _folder_already_named(directory.name, _sanitize_dirname(book.title)):
            self._persist(book, directory)
            return book

        old_name = directory.name
        self._rename_folder(book, directory)
        self._catalog.relocate(old_name, book)
        _log.info("renamed %r -> %r", old_name, book.directory.name if book.directory else None)
        return book

    def reidentify(self, book: Book) -> Book:
        """Look this book up again and apply what comes back.

        For a book whose lookup failed, that never matched, or whose
        title a human has since corrected -- the usual route to a cover
        the original import could not find.

        A **reviewed** book is not overwritten: the lookup still runs,
        but only a cover it lacks and fields left empty are filled in,
        never the title, author or ISBN a human set. An unreviewed book
        adopts the result outright, exactly as an import would.

        The title is never changed: the book's own title is what is
        searched on, and the file's title wins over the source's
        (ADR-10). A rename is therefore never needed here.

        Args:
            book: A persisted book, as returned by `scan`, `search` or
                `import_file`. Mutated in place.

        Returns:
            The same Book, updated and saved. Unchanged if nothing
            agreed, or if the lookup failed (never raises for that).

        Raises:
            CatalogError: If `book` has never been persisted.
            OSError: If the write fails.
        """
        directory = _persisted_directory(book)
        found = identify(
            ParsedMetadata(
                title=book.title,
                author=book.author,
                isbns=[book.isbn] if book.isbn else [],
            ),
            self._source,
        )

        if book.reviewed:
            # A human's fields stand; fill only what is missing.
            book.author = book.author or found.author
            book.isbn = book.isbn or found.isbn
            adopt_cover = found.cover_url is not None and book.cover_path is None
        else:
            book.author = found.author or book.author
            book.isbn = found.isbn or book.isbn
            book.identified = found.basis
            adopt_cover = found.cover_url is not None
        # Provenance, not a human's field: reviewed or not, the book
        # records what the source says now.
        book.record_author = found.record_author or book.record_author

        if adopt_cover and found.cover_url:
            self._save_cover(book, directory, found.cover_url)
        self._persist(book, directory)
        _log.info("re-identified %r as %s", book.title, found.basis)
        return book

    def _rename_folder(self, book: Book, directory: Path) -> None:
        """Move `book` into a folder named after its (new) title, taking
        its format files and cover with it.

        Ordered so the dangerous window is as small as it can be: the
        files inside are renamed first, then metadata.json is rewritten
        (atomically) to match, and only then is the folder itself
        renamed -- which is a single atomic operation, and the stored
        filenames are relative so they stay correct across it. An
        interruption after the metadata write therefore leaves a book
        that loads perfectly under a stale folder name; only a failure
        midway through the inner renames leaves a folder needing
        repair, and that stretch is nothing but `Path.rename` calls.
        """
        target = self._new_directory(book.title)
        target.rmdir()  # claimed the name; `rename` needs it free

        new_stem = target.name
        book.formats = [
            BookFormat(kind=fmt.kind, path=_rename_in_place(fmt.path, new_stem))
            for fmt in book.formats
        ]
        # The cover is always "cover.png", not named after the folder,
        # so it needs no rename -- only repointing once the folder moves.
        save_metadata(book, directory)

        directory.rename(target)
        book.directory = target
        book.formats = [
            BookFormat(kind=fmt.kind, path=target / fmt.path.name) for fmt in book.formats
        ]
        if book.cover_path is not None:
            book.cover_path = target / book.cover_path.name

    def _find_book(
        self, title: str, author: str | None, isbn: str | None
    ) -> tuple[Book, MatchBasis] | None:
        """Find the existing book a file described by (title, author,
        isbn) belongs to, and the basis for that judgment.

        Spec: GROUP-1 (the ISBN join) then GROUP-2 (strongest MATCH
        across every existing book). Returning None is GROUP-3: this is
        a new book.

        An exact ISBN match wins outright -- subject to the same guard
        `identify` applies to a lookup hit: a shared ISBN whose title
        *and* author both contradict the file is a scraped false
        positive, not a match. Otherwise the strongest `match_basis`
        across all books wins, so a TITLE_AUTHOR match is preferred
        over a TITLE_ONLY one. None if no book matches.
        """
        existing = self._catalog.all()

        # GROUP-1: a shared ISBN is not sufficient on its own -- run the
        # same MATCH rule identification runs, or one false-positive ISBN
        # in two unrelated files merges them.
        if isbn:
            for book in existing:
                if book.isbn == isbn and match_basis(
                    title, author, book.title, book.author, same_isbn=True
                ):
                    return book, MatchBasis.ISBN

        # GROUP-2: TITLE_AUTHOR beats TITLE_ONLY; ties resolve by sorted
        # folder order (the catalog's), so imports are repeatable.
        title_only: Book | None = None
        for book in existing:
            basis = match_basis(title, author, book.title, book.author)
            if basis == MatchBasis.TITLE_AUTHOR:
                return book, basis
            if basis == MatchBasis.TITLE_ONLY and title_only is None:
                title_only = book
        if title_only is not None:
            return title_only, MatchBasis.TITLE_ONLY

        return None

    def _new_directory(self, title: str) -> Path:
        """Atomically claim a new, not-yet-existing book folder.

        Uses mkdir(exist_ok=False) with a retry-on-collision loop
        rather than check-then-create, so two concurrent imports for
        two different books that sanitize to the same folder name
        can't both succeed against the same directory.
        """
        base = _sanitize_dirname(title)
        counter = 1
        while True:
            name = base if counter == 1 else f"{base} ({counter})"
            candidate = self.root / name
            try:
                candidate.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                counter += 1
                continue
            return candidate

    def _persist(self, book: Book, directory: Path) -> None:
        """Write `book`'s metadata.json into `directory` and update its
        search-index row so `search` sees the change."""
        self._catalog.put(book, directory)

    def _save_cover(self, book: Book, directory: Path, url: str) -> None:
        """Download `url` to <directory>/cover.png and point `book` at it.
        A failed download leaves any existing cover in place.
        """
        try:
            cover_bytes = self._source.fetch_cover(url)
        except MetadataSourceError as exc:
            _log.warning(
                "IDENT-6 cover download for %r failed, continuing without it: %s",
                book.title,
                exc,
            )
            return
        cover_path = directory / "cover.png"
        cover_path.write_bytes(cover_bytes)
        book.cover_path = cover_path


_DEDUP_SUFFIX = re.compile(r" \(\d+\)$")


def _folder_already_named(folder_name: str, base: str) -> bool:
    """Whether a folder called `folder_name` is already the right home for
    a book whose title sanitizes to `base`.

    True for an exact match, and for the deduplicated variants
    `_new_directory` mints ("Dune (2)"), so re-titling "Dune:" to "Dune"
    leaves the book where it is instead of shuffling it to "Dune (3)".
    """
    return folder_name == base or _DEDUP_SUFFIX.sub("", folder_name) == base


def _persisted_directory(book: Book) -> Path:
    """The folder a curation operation will act on, or an error naming
    why it cannot: an in-memory Book has nothing to edit."""
    if book.directory is None:
        raise CatalogError("this book has not been saved to a library yet")
    return book.directory


def _rename_in_place(path: Path, new_stem: str) -> Path:
    """Rename one file to `<new_stem><its suffix>` beside itself."""
    target = path.with_name(f"{new_stem}{path.suffix}")
    if target != path:
        path.rename(target)
    return target


def _refuse_conflicting_format(
    book: Book,
    source: Path,
    kind: FormatKind,
    join: MatchBasis,
    found: Identification,
    *,
    title: str,
) -> None:
    """Raise `FormatConflictError` if `book` already holds a file of
    `kind` that is not byte-for-byte `source`.

    Spec: GROUP-4, first rule (ADR-21). A book holds one file per kind;
    the same bytes again is F13's idempotent re-import and passes,
    anything else is refused before the folder or catalog is touched.
    The existing file is compared directly -- no stored hash is needed
    to tell a re-import from a different file. A recorded file that has
    gone missing from disk is not a conflict: there is nothing to lose.
    """
    for fmt in book.formats:
        if fmt.kind != kind or not fmt.path.exists():
            continue
        if filecmp.cmp(source, fmt.path, shallow=False):
            return
        raise FormatConflictError(
            source,
            book,
            fmt.path,
            join,
            title=title,
            author=found.author,
            isbn=found.isbn,
        )


def _place_format(book: Book, directory: Path, source: Path, kind: FormatKind) -> None:
    """Copy `source` into `directory` as `<folder name><suffix>` and make
    it `book`'s file for `kind`.

    Any previous file of the same kind under a different name (a
    pre-0.3 `book<suffix>`) is deleted, and its entry replaced, so a
    book never lists two files of one kind. The source is left in place.
    """
    dest = directory / f"{directory.name}{source.suffix.lower()}"
    shutil.copyfile(source, dest)
    for fmt in book.formats:
        if fmt.kind == kind and fmt.path != dest:
            fmt.path.unlink(missing_ok=True)
    book.formats = [fmt for fmt in book.formats if fmt.kind != kind]
    book.formats.append(BookFormat(kind=kind, path=dest))


def _apply_identification(
    book: Book, found: Identification, join: MatchBasis | None, *, title: str
) -> str | None:
    """Fold what `identify` found for one file into the book it joins.

    Spec: GROUP-4 (and GROUP-3's `identified` for a new book).

    This is the evidence policy of `Library.import_file`, step 5, kept
    pure so it can be tested on bare `Book`s and reused by any
    operation that re-identifies a book:

    - `join` is None for a new book: the book takes the file's
      title/author/isbn and `identified` outright.
    - Otherwise `grouped` becomes the weaker of its previous value and
      `join` (the weakest link ever used is what's remembered), and a
      TITLE_ONLY join clears `reviewed`.
    - A book that was `reviewed` going in keeps its title/author/isbn/
      `identified` untouched, even when this join just cleared the
      flag: a human's corrections outrank anything an import finds,
      and clearing the flag only asks for another look.
    - If the file was identified at least as strongly as the book
      already was, the file's author/isbn, `record_author` and
      `identified` replace the book's (missing values never overwrite
      present ones). The title is replaced only on *strictly* stronger
      evidence, so equally identified formats don't take turns
      respelling it.
    - A weaker or failed identification changes nothing except filling
      an empty author/isbn.

    Args:
        book: The book being imported into; mutated in place.
        found: What `identify` settled on for the file.
        join: The basis on which the file joined an existing book, or
            None if the book was created for it.
        title: The resolved title for the file (`found.title`, or the
            filename stem if the file had none).

    Returns:
        The cover URL to download for this book, or None if the found
        record has no cover or its identification wasn't adopted.
    """
    was_reviewed = book.reviewed
    if join is not None:
        book.grouped = weaker_basis(book.grouped, join)
        if book.reviewed and join == MatchBasis.TITLE_ONLY:
            book.reviewed = False

    if was_reviewed:
        return None

    adopted = join is None or (
        found.basis is not None and stronger_basis(found.basis, book.identified) == found.basis
    )
    if not adopted:
        book.author = book.author or found.author
        book.isbn = book.isbn or found.isbn
        return None

    if join is None or found.basis != book.identified:
        book.title = title
    book.author = found.author or book.author
    book.record_author = found.record_author or book.record_author
    book.isbn = found.isbn or book.isbn
    book.identified = found.basis
    return found.cover_url


def _sanitize_dirname(title: str) -> str:
    cleaned = _DIRNAME_COLON.sub(" -", title)
    cleaned = _UNSAFE_DIRNAME_CHARS.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")
    cleaned = cleaned[:_MAX_DIRNAME_LENGTH].rstrip(" .-")
    return cleaned or "Untitled"
