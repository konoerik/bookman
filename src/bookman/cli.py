"""Command-line entry point: exposes Library's actions directly, without a
separate frontend. Thin by design -- every command is a straight call into
`bookman.library.Library`; no logic here that a future TUI would need to
duplicate.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import NoReturn

from bookman.config import (
    ENV_LIBRARY,
    Config,
    config_path,
    load_config,
    resolve_library,
    save_config,
)
from bookman.errors import (
    CatalogError,
    FormatConflictError,
    LibraryNotConfiguredError,
    UnsupportedFormatError,
)
from bookman.formats import is_supported, supported_suffixes
from bookman.library import _UNSET, ImportBatchResult, Library, _Unset
from bookman.models import Book, MatchBasis

_SUPPORTED = ", ".join(supported_suffixes())
_RULE_WIDTH = 60
_LIBRARY_HELP = f"library root directory (default: ${ENV_LIBRARY}, then the saved config)"
_BOOK_HELP = "the book's title as `list` shows it, its folder name, or its id"

_DESCRIPTION = """\
bookman - a local ebook library manager.

Point it at a folder of EPUB/PDF files and it identifies each book,
fetches metadata, and files it under a title-named folder in your library.
"""

_EPILOG = f"""\
getting started:
  bookman init ~/Books
      create the library there and remember it; every later command
      uses it unless you pass --library or set ${ENV_LIBRARY}

examples:
  bookman import ~/Downloads/humble-bundle
      import every supported file in that folder

  bookman import book.epub
      import one file

  bookman list --needs-review
      show only books whose match should be checked by hand

  bookman search "newport"
      find books whose title or author contains "newport"

  bookman review "Deep Work"
      mark that book checked, taking it off the review list

  bookman edit "Deep Work" --author "Cal Newport" --no-isbn
      fix the author and drop a wrong ISBN (this marks it reviewed)

  bookman reidentify "Deep Work"
      look the book up again, e.g. for a cover after fixing its title

  bookman config
      show which library is in use and where that setting is stored

run `bookman <command> --help` for the options of one command.
"""


class _Parser(argparse.ArgumentParser):
    """ArgumentParser that shows the full help (not just the usage line)
    when arguments are wrong, so a user who forgot a flag or a positional
    sees what was expected without a second `--help` round trip.
    """

    def error(self, message: str) -> NoReturn:
        self.print_help(sys.stderr)
        self.exit(2, f"\n{self.prog}: error: {message}\n")


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and run the requested bookman command.

    Args:
        argv: Argument list to parse, excluding the program name.
            Defaults to `sys.argv[1:]` (argparse's normal behavior)
            when None.

    Returns:
        Process exit code: 0 on full success. `import` returns 1 if
        any file in the batch failed or was refused as a conflict
        (partial success still imports and reports the rest). `list`, `search`, `review`, `edit` and
        `reidentify` return 1 if the library root doesn't exist; the
        last three also return 1 if no book has the given name or id,
        and `edit` returns 1 for a blank title or an invalid ISBN.
        Any command that needs a library
        returns 1 if none is configured (see `config.resolve_library`)
        or the config file is malformed. Invoking with no command
        prints the help and returns 0. Bad arguments exit 2 via
        argparse. Ctrl-C returns 130. Per-file/command errors are
        printed to stderr, not raised.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "init":
        return _cmd_init(args.directory)
    if args.command == "config":
        return _cmd_config(args.library)

    try:
        root = resolve_library(args.library)
    except LibraryNotConfiguredError as exc:
        _error(str(exc))
        return 1
    except ValueError as exc:
        _error(f"bad config file: {exc}")
        return 1
    if root.exists() and not root.is_dir():
        _error(f"library path is not a directory: {root}")
        return 1

    try:
        if args.command == "import":
            return _cmd_import(root, args.path, recursive=args.recursive)
        if args.command == "list":
            return _cmd_list(root, needs_review_only=args.needs_review)
        if args.command == "search":
            return _cmd_search(root, args.query)
        if args.command == "review":
            return _cmd_review(root, args.book, reviewed=not args.undo)
        if args.command == "edit":
            return _cmd_edit(
                root,
                args.book,
                title=args.title,
                author=_field_change(args.author, clear=args.no_author),
                isbn=_field_change(args.isbn, clear=args.no_isbn),
            )
        if args.command == "reidentify":
            return _cmd_reidentify(root, args.book)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
    raise AssertionError(f"unhandled command: {args.command!r}")


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser with `--library` and the
    init/import/list/search/review/edit/reidentify/config subcommands.

    `--library/-l` (default: None, meaning "resolve via config") is
    accepted both before and after the subcommand, so
    `bookman -l ~/books list` and `bookman list -l ~/books` both work.

    A subparser parses into its own fresh namespace and then copies
    every one of its attributes -- including untouched defaults --
    back onto the top-level namespace, which would silently clobber a
    `--library` given before the subcommand with the subparser's own
    default. `sub_common` avoids that by defaulting to
    `argparse.SUPPRESS`, so `library` is only in that copy-back set
    when the user actually passed `--library` after the subcommand.
    """
    top_common = _Parser(add_help=False)
    top_common.add_argument(
        "--library",
        "-l",
        type=Path,
        default=None,
        metavar="DIR",
        help=_LIBRARY_HELP,
    )

    sub_common = _Parser(add_help=False)
    sub_common.add_argument(
        "--library",
        "-l",
        type=Path,
        default=argparse.SUPPRESS,
        metavar="DIR",
        help=_LIBRARY_HELP,
    )

    parser = _Parser(
        prog="bookman",
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[top_common],
    )
    parser.add_argument("--version", action="version", version=f"bookman {_version()}")
    subparsers = parser.add_subparsers(dest="command", title="commands", metavar="<command>")

    init_parser = subparsers.add_parser(
        "init",
        help="create a library and make it the default for every other command",
        description=(
            "Create the library directory (if needed) and save it as the default, "
            f"in {config_path()}. Run again with a different directory to switch."
        ),
    )
    init_parser.add_argument("directory", type=Path, help="where the library should live")

    import_parser = subparsers.add_parser(
        "import",
        parents=[sub_common],
        help="import a file, or every supported file in a directory",
        description=(
            "Import one ebook file, or every supported file in a directory, "
            f"into the library. Supported formats: {_SUPPORTED}. "
            "The library directory is created if it doesn't exist yet."
        ),
    )
    import_parser.add_argument("path", type=Path, help="ebook file or directory to import")
    import_parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="when PATH is a directory, also import files in its subdirectories",
    )

    list_parser = subparsers.add_parser(
        "list",
        parents=[sub_common],
        help="list cataloged books",
        description="List every book in the library, sorted by title.",
    )
    list_parser.add_argument(
        "--needs-review",
        action="store_true",
        dest="needs_review",
        help="only list books whose identification should be checked by hand",
    )

    search_parser = subparsers.add_parser(
        "search",
        parents=[sub_common],
        help="search cataloged books by title or author",
        description="Find books whose title or author contains QUERY (case-insensitive).",
    )
    search_parser.add_argument("query", help="text to look for in titles and authors")

    review_parser = subparsers.add_parser(
        "review",
        parents=[sub_common],
        help="mark a book as checked by hand, or un-mark it with --undo",
        description=(
            "Record that you have checked BOOK's title, author and ISBN. A reviewed "
            "book leaves the `list --needs-review` queue and keeps its fields through "
            "any later import. --undo puts it back in the queue."
        ),
    )
    review_parser.add_argument("book", help=_BOOK_HELP)
    review_parser.add_argument(
        "--undo",
        action="store_true",
        help="un-mark the book, putting it back in the review queue",
    )

    edit_parser = subparsers.add_parser(
        "edit",
        parents=[sub_common],
        help="correct a book's title, author or ISBN by hand",
        description=(
            "Change BOOK's title, author and/or ISBN. Fields you don't name are left "
            "alone. Editing marks the book reviewed, so the correction survives later "
            "imports; `review --undo` puts it back in the queue. A new title renames "
            "the book's folder and files."
        ),
    )
    edit_parser.add_argument("book", help=_BOOK_HELP)
    edit_parser.add_argument(
        "--title", "-t", metavar="TITLE", help="new title (renames the folder)"
    )
    author_group = edit_parser.add_mutually_exclusive_group()
    author_group.add_argument("--author", "-a", metavar="AUTHOR", help="new author")
    author_group.add_argument("--no-author", action="store_true", help="clear the author")
    isbn_group = edit_parser.add_mutually_exclusive_group()
    isbn_group.add_argument(
        "--isbn", "-i", metavar="ISBN", help="new ISBN-10 or ISBN-13 (stored as ISBN-13)"
    )
    isbn_group.add_argument("--no-isbn", action="store_true", help="clear the ISBN")

    reidentify_parser = subparsers.add_parser(
        "reidentify",
        parents=[sub_common],
        help="look a book up online again",
        description=(
            "Look BOOK up again and apply what comes back -- the way to get a cover, "
            "author or ISBN after fixing a title by hand, or when the original import "
            "found nothing. A reviewed book keeps every field you set and gains only "
            "what it lacked. The title is never changed."
        ),
    )
    reidentify_parser.add_argument("book", help=_BOOK_HELP)

    subparsers.add_parser(
        "config",
        parents=[sub_common],
        help="show which library is in use and where that setting comes from",
        description="Show the library every command will use, and the config file location.",
    )

    return parser


def _cmd_init(directory: Path) -> int:
    """Run `init`: create the library directory and save it as the
    configured default.

    Args:
        directory: Where the library should live, as given on the
            command line. Created (with parents) if missing.

    Returns:
        0 on success, 1 if `directory` exists but is a file.
    """
    if directory.exists() and not directory.is_dir():
        _error(f"not a directory: {directory}")
        return 1
    Library(directory)
    save_config(Config(library=directory))
    _header("Library set up")
    print(f"Library: {directory.resolve()}")
    print(f"Config:  {config_path()}")
    print("every bookman command now uses this library; run `bookman import <dir>` to fill it")
    return 0


def _cmd_config(explicit: Path | None) -> int:
    """Run `config`: print the config file location, what it says, and
    which library the current invocation would actually use (after the
    `--library` flag and `$BOOKMAN_LIBRARY` are taken into account).

    Args:
        explicit: The `--library` value, if one was passed.

    Returns:
        0 always -- an unconfigured or malformed setup is reported,
        not treated as a failure, since the point is to see the state.
    """
    path = config_path()
    _header("bookman configuration")
    print(f"Config file:      {path}" + ("" if path.exists() else " (not created yet)"))
    try:
        saved = load_config(path)
    except ValueError as exc:
        print(f"Saved library:    (unreadable: {exc})")
    else:
        print(f"Saved library:    {saved.library if saved else '(none)'}")
    env = os.environ.get(ENV_LIBRARY)
    print(f"${ENV_LIBRARY}: {env or '(not set)'}")
    if explicit is not None:
        print(f"--library:        {explicit}")
    _rule()
    try:
        print(f"Active library:   {resolve_library(explicit).resolve()}")
    except (LibraryNotConfiguredError, ValueError):
        print("Active library:   (none) - run `bookman init <dir>`")
    return 0


def _cmd_import(root: Path, path: Path, *, recursive: bool) -> int:
    """Run `import`: dispatches to `Library.import_file` for a file or
    `Library.import_directory` for a directory, and prints a one-line
    summary per file (`imported: <title>` or `failed: <path>: <error>`)
    under a header naming the source and destination.

    Args:
        root: Library root, as resolved from `--library`.
        path: File or directory to import, as given on the command line.
        recursive: Forwarded to `import_directory` when `path` is a
            directory; ignored for a single file.

    Returns:
        0 if every file imported cleanly, 1 if any failed or was
        refused as a same-kind conflict (including a single file's
        own failure or refusal) or `path` doesn't exist.
    """
    if not path.exists():
        _error(f"no such file or directory: {path}")
        return 1
    if path.is_file() and not is_supported(path):
        _error(f"unsupported format {path.suffix!r}: {path} (supported: {_SUPPORTED})")
        return 1

    library = Library(root)
    _header(f"Importing: {path}", f"Into:      {root.resolve()}")

    if path.is_dir():
        result = library.import_directory(path, recursive=recursive)
        for source, book in result.imported:
            print(f"imported: {book.title} ({_describe_import(source, book)})")
        for skipped_path in result.skipped:
            print(f"skipped: {skipped_path} (unsupported format {skipped_path.suffix})")
        sys.stdout.flush()
        for conflict in result.conflicts:
            print(_format_conflict(conflict), file=sys.stderr)
        for failed_path, exc in result.failed:
            print(f"failed: {failed_path}: {_describe(exc, failed_path)}", file=sys.stderr)
        sys.stderr.flush()
        if not any((result.imported, result.failed, result.skipped, result.conflicts)):
            hint = "" if recursive else "; try --recursive"
            print(f"no {_SUPPORTED} files found in {path}{hint}")
        _rule()
        print(_format_batch_result(result))
        return 1 if result.failed or result.conflicts else 0

    try:
        book = library.import_file(path)
    except FormatConflictError as conflict:
        print(_format_conflict(conflict), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"failed: {path}: {_describe(exc, path)}", file=sys.stderr)
        return 1
    print(f"imported: {book.title}")
    return 0


def _cmd_list(root: Path, *, needs_review_only: bool) -> int:
    """Run `list`: prints every cataloged book (or, with
    `needs_review_only`, only those whose `Book.needs_review` is set),
    one line each via `_format_book`, under a header naming the library.

    Args:
        root: Library root, as resolved from `--library`.
        needs_review_only: If True, filter `Library.scan()`'s result
            to `needs_review` books before printing.

    Returns:
        0 on success, 1 if the library root doesn't exist.
    """
    if not _require_library(root):
        return 1
    books = Library(root).scan()

    if needs_review_only:
        books = [book for book in books if book.needs_review]

    what = "books needing review" if needs_review_only else "books"
    _header(f"Library: {root.resolve()}", f"{len(books)} {what}")
    if not books:
        print("no books found")
        if not needs_review_only:
            print("(add some with `bookman import <file-or-directory>`)")
        return 0

    for book in sorted(books, key=lambda b: b.title.lower()):
        print(_format_book(book))
    return 0


def _cmd_search(root: Path, query: str) -> int:
    """Run `search`: prints every book matching `query` (title/author
    substring), one line each via `_format_book`, under a header
    naming the query.

    Args:
        root: Library root, as resolved from `--library`.
        query: Passed straight through to `Library.search`.

    Returns:
        0 on success (an empty result set is not an error), 1 if the
        library root doesn't exist.
    """
    if not _require_library(root):
        return 1
    books = Library(root).search(query)

    _header(f"Library: {root.resolve()}", f"{len(books)} matches for {query!r}")
    if not books:
        print("no matches")
        return 0

    for book in books:
        print(_format_book(book))
    return 0


def _cmd_review(root: Path, ref: str, *, reviewed: bool) -> int:
    """Run `review`: `Library.mark_reviewed` on the book `ref` names,
    then print its new state via `_format_book`.

    Args:
        root: Library root, as resolved from `--library`.
        ref: The book's folder name or id, as given on the command line.
        reviewed: False when `--undo` was passed.

    Returns:
        0 on success, 1 if the library root doesn't exist or no book
        matches `ref`.
    """
    if not _require_library(root):
        return 1
    library = Library(root)
    book = _find_book(library, ref)
    if book is None:
        return 1
    library.mark_reviewed(book, reviewed)
    print(f"{'reviewed' if reviewed else 'unreviewed'}: {_format_book(book)}")
    return 0


def _cmd_edit(
    root: Path,
    ref: str,
    *,
    title: str | None,
    author: str | None | _Unset,
    isbn: str | None | _Unset,
) -> int:
    """Run `edit`: `Library.edit` on the book `ref` names, then print
    its new state via `_format_book`, plus the new folder if the title
    change moved it.

    Args:
        root: Library root, as resolved from `--library`.
        ref: The book's folder name or id, as given on the command line.
        title: `--title`, or None to leave the title alone.
        author: `--author`'s value, None for `--no-author`, or `_UNSET`
            when neither was passed. Forwarded as-is to `Library.edit`.
        isbn: Likewise for `--isbn` / `--no-isbn`.

    Returns:
        0 on success; 1 if the library root doesn't exist, no book
        matches `ref`, or `Library.edit` rejects the input (blank
        title, invalid ISBN). Exit 2 via argparse if no field was
        given at all -- the command would otherwise only set `reviewed`,
        which is `review`'s job.
    """
    if title is None and isinstance(author, _Unset) and isinstance(isbn, _Unset):
        _error("nothing to change: pass --title, --author/--no-author or --isbn/--no-isbn")
        return 2
    if not _require_library(root):
        return 1
    library = Library(root)
    book = _find_book(library, ref)
    if book is None:
        return 1
    before = book.directory
    try:
        library.edit(book, title=_UNSET if title is None else title, author=author, isbn=isbn)
    except CatalogError as exc:
        _error(str(exc))
        return 1
    print(f"edited: {_format_book(book)}")
    if book.directory != before and book.directory is not None:
        print(f"moved to: {book.directory.name}")
    return 0


def _cmd_reidentify(root: Path, ref: str) -> int:
    """Run `reidentify`: `Library.reidentify` on the book `ref` names,
    then print its new state via `_format_book` and whether a cover
    is now present.

    Args:
        root: Library root, as resolved from `--library`.
        ref: The book's folder name or id, as given on the command line.

    Returns:
        0 on success (a lookup that finds nothing is not an error --
        the book is simply unchanged), 1 if the library root doesn't
        exist or no book matches `ref`.
    """
    if not _require_library(root):
        return 1
    library = Library(root)
    book = _find_book(library, ref)
    if book is None:
        return 1
    library.reidentify(book)
    cover = "cover" if book.cover_path else "no cover"
    print(f"re-identified: {_format_book(book)} [{cover}]")
    return 0


def _find_book(library: Library, ref: str) -> Book | None:
    """The cataloged book `ref` names, or None after reporting why not.

    Tried in order: the folder name (what's on disk), then `Book.id`
    (for scripts), then the exact title (what `list` prints -- it
    differs from the folder when the title held a colon or another
    character folders can't). A title shared by several books is
    reported as ambiguous, naming their folders, since those are
    unique. Folder name and id come first so a book can always be
    named unambiguously even when its title is shared.
    """
    books = library.scan()
    for book in books:
        if book.directory is not None and book.directory.name == ref:
            return book
    for book in books:
        if book.id == ref:
            return book
    by_title = [book for book in books if book.title == ref]
    if len(by_title) == 1:
        return by_title[0]
    if by_title:
        _error(f"{len(by_title)} books are titled {ref!r}; name one by its folder:")
        for book in by_title:
            print(f"  {book.directory.name if book.directory else '?'}", file=sys.stderr)
        return None
    _error(f"no book named {ref!r}")
    print("(run `bookman list` to see the names; `bookman search` to find one)", file=sys.stderr)
    return None


def _field_change(value: str | None, *, clear: bool) -> str | None | _Unset:
    """Turn an `edit` field's pair of flags into what `Library.edit`
    expects: the new value, None to clear it, or `_UNSET` if neither
    flag was given. argparse's mutually-exclusive group guarantees
    `value` and `clear` aren't both set.
    """
    if clear:
        return None
    if value is not None:
        return value
    return _UNSET


def _require_library(root: Path) -> bool:
    """Report and return False if `root` doesn't exist. `list`/`search`
    call this before constructing a `Library`, which would otherwise
    create the directory (and an index file) as a side effect -- so a
    typo'd `--library` path looks like an empty library instead of a
    mistake.
    """
    if root.is_dir():
        return True
    _error(f"library not found: {root}")
    print("(create it with `bookman init <dir>`)", file=sys.stderr)
    return False


def _header(*lines: str) -> None:
    for line in lines:
        print(line)
    _rule()


def _rule() -> None:
    print("-" * _RULE_WIDTH, flush=True)


def _error(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)


def _describe_import(source: Path, book: Book) -> str:
    """Say which format a file contributed and, if the book already had
    others, that it was grouped with them -- so the second file of a
    two-format book prints as "(pdf, grouped with epub)" rather than as
    an apparent duplicate import of the same title.
    """
    kind = source.suffix.lower().lstrip(".")
    others = [fmt.kind.value for fmt in book.formats if fmt.kind.value != kind]
    if not others:
        return kind
    return f"{kind}, grouped with {', '.join(others)}"


def _describe(exc: BaseException, path: Path) -> str:
    """Turn an import failure into a message that says what went wrong.
    `str(FileNotFoundError(path))` is just the path, and parser errors
    already start with the path, so both would otherwise print as
    `failed: <path>: <path>...`.
    """
    if isinstance(exc, FileNotFoundError):
        return "no such file or directory"
    if isinstance(exc, UnsupportedFormatError):
        return f"unsupported format (supported: {_SUPPORTED})"
    message = str(exc) or type(exc).__name__
    return message.removeprefix(f"{path}: ")


def _version() -> str:
    try:
        return version("bookman")
    except PackageNotFoundError:
        return "unknown"


def _format_book(book: Book) -> str:
    """Render one Book as a single output line: title, author, the formats
    it has on disk (e.g. "epub, pdf"), and -- for a book that needs
    review -- a marker saying why, so it stands out when scanning `list`
    output and the reader knows what to check.
    """
    author = book.author or "unknown author"
    formats = ", ".join(fmt.kind.value for fmt in book.formats)
    reason = _review_reason(book)
    marker = f" [NEEDS REVIEW: {reason}]" if reason else ""
    return f"{book.title} - {author} ({formats}){marker}"


def _review_reason(book: Book) -> str | None:
    """The single most important reason `book.needs_review` is set, or
    None if it isn't. Uncorroborated metadata is reported before a weak
    grouping, since a wrong identity makes the grouping moot.
    """
    if not book.needs_review:
        return None
    if book.identified is None:
        return "no online match"
    if book.identified == MatchBasis.TITLE_ONLY:
        return "matched by title only"
    return "grouped by title only"


def _format_batch_result(result: ImportBatchResult) -> str:
    """Render an ImportBatchResult's summary line, e.g. "3 imported, 1
    failed" -- printed after `_cmd_import`'s per-file lines for a directory
    import. Skipped and refused counts are appended only when there are
    any, so the common clean case stays short.
    """
    summary = f"{len(result.imported)} imported, {len(result.failed)} failed"
    if result.skipped:
        summary += f", {len(result.skipped)} skipped"
    if result.conflicts:
        summary += f", {len(result.conflicts)} not imported (already have that format)"
    return summary


def _format_conflict(conflict: FormatConflictError) -> str:
    """Render a refused same-kind import (ADR-21) as two lines: what was
    refused and why, then what to do about it. The join basis is spelled
    out because it is the real information -- an ISBN join means "same
    book, which file do you want?", a title-only join means "was this
    even the same book?" -- and the hint names the one resolution that
    exists today, deleting the file in the folder and importing again.
    """
    kind = conflict.existing.suffix.lstrip(".")
    reason = {
        MatchBasis.ISBN: "same ISBN",
        MatchBasis.TITLE_AUTHOR: "same title and author",
        MatchBasis.TITLE_ONLY: "same title only -- check it is really the same book",
    }[conflict.basis]
    return (
        f'not imported: {conflict.source}: "{conflict.book.title}" already has a '
        f"different {kind} ({reason})\n"
        f"  to replace it, delete {conflict.existing} and import again"
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
