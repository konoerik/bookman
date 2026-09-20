from pathlib import Path

import pytest
from helpers import VALID_ISBN13, FakeSource
from helpers import make_epub as _make_epub
from helpers import make_pdf as _make_pdf

from bookman import cli, config
from bookman.identify.source import Candidate
from bookman.library import Library
from bookman.models import Book, BookFormat, FormatKind, MatchBasis


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """The CLI builds its own Library, so swap the default source at the
    composition root: every Library made here gets a FakeSource that
    knows nothing. A test that wants a hit re-patches with a scripted one."""
    monkeypatch.setattr("bookman.library.OpenLibrarySource", FakeSource)


@pytest.fixture(autouse=True)
def config_file(monkeypatch, tmp_path):
    """Point the CLI at a throwaway config file so tests never read or
    write the developer's real one, and start with no library configured."""
    path = tmp_path / "config" / "config.json"
    monkeypatch.setenv(config.ENV_CONFIG, str(path))
    monkeypatch.delenv(config.ENV_LIBRARY, raising=False)
    return path


def test_import_single_file_reports_success(tmp_path, capsys):
    library_root = tmp_path / "Library"
    source = _make_epub(tmp_path / "book.epub", title="Deep Work", author="Cal Newport")

    code = cli.main(["--library", str(library_root), "import", str(source)])

    assert code == 0
    out = capsys.readouterr().out
    assert "imported: Deep Work" in out
    assert {book.title for book in Library(library_root).scan()} == {"Deep Work"}


def test_import_single_file_reports_failure(tmp_path, capsys):
    library_root = tmp_path / "Library"
    bad = tmp_path / "bad.epub"
    bad.write_bytes(b"not a real zip file")

    code = cli.main(["import", str(bad), "--library", str(library_root)])

    assert code == 1
    err = capsys.readouterr().err
    assert "failed:" in err
    assert str(bad) in err
    assert "not a valid EPUB" in err


def test_import_directory_reports_batch_summary(tmp_path, capsys):
    library_root = tmp_path / "Library"
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    _make_epub(source_dir / "a.epub", title="Book A")
    _make_epub(source_dir / "b.epub", title="Book B")

    code = cli.main(["-l", str(library_root), "import", str(source_dir)])

    assert code == 0
    out = capsys.readouterr().out
    assert "imported: Book A" in out
    assert "imported: Book B" in out
    assert "2 imported, 0 failed" in out


def test_import_directory_with_a_bad_file_returns_nonzero(tmp_path, capsys):
    library_root = tmp_path / "Library"
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    _make_epub(source_dir / "good.epub", title="Good Book")
    (source_dir / "bad.epub").write_bytes(b"not a real zip file")

    code = cli.main(["-l", str(library_root), "import", str(source_dir)])

    assert code == 1
    captured = capsys.readouterr()
    assert "imported: Good Book" in captured.out
    assert "1 imported, 1 failed" in captured.out
    assert "failed:" in captured.err


def test_import_directory_prints_each_file_as_it_finishes(tmp_path, capsys, monkeypatch):
    """A long batch must not go quiet until the end: the line for a file
    is on screen before the next file is attempted, and the file being
    waited on is named while its lookup runs."""
    library_root = tmp_path / "Library"
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    _make_epub(source_dir / "a.epub", title="Book A")
    _make_epub(source_dir / "b.epub", title="Book B")
    seen_before_second: list[str] = []
    original = Library.import_file

    def spy(self, path):
        if path.name == "b.epub":
            seen_before_second.append(capsys.readouterr().out)
        return original(self, path)

    monkeypatch.setattr(Library, "import_file", spy)

    cli.main(["-l", str(library_root), "import", str(source_dir)])

    [out] = seen_before_second
    assert "[1/2] a.epub ... imported: Book A (epub)" in out
    assert out.endswith("[2/2] b.epub ...")
    assert "Book B" not in out


def test_import_directory_ends_the_progress_line_before_a_failure(tmp_path, capsys):
    """The failure goes to stderr; the half-written stdout line must be
    terminated so the next file's line doesn't join it."""
    library_root = tmp_path / "Library"
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    (source_dir / "bad.epub").write_bytes(b"not a real zip file")
    _make_epub(source_dir / "good.epub", title="Good Book")

    cli.main(["-l", str(library_root), "import", str(source_dir)])

    out, err = capsys.readouterr()
    assert "[1/2] bad.epub ...\n[2/2] good.epub ... imported: Good Book (epub)\n" in out
    assert "failed:" in err


def test_import_directory_recursive_flag_is_forwarded(tmp_path, capsys):
    library_root = tmp_path / "Library"
    source_dir = tmp_path / "Source"
    nested = source_dir / "Nested"
    nested.mkdir(parents=True)
    _make_epub(nested / "b.epub", title="Nested Book")

    code = cli.main(["-l", str(library_root), "import", str(source_dir), "--recursive"])

    assert code == 0
    assert "imported: Nested Book" in capsys.readouterr().out


def test_list_reports_no_books_found_for_empty_library(tmp_path, capsys):
    library_root = tmp_path / "Library"
    library_root.mkdir()

    code = cli.main(["-l", str(library_root), "list"])

    assert code == 0
    assert "no books found" in capsys.readouterr().out


def test_list_on_missing_library_is_an_error_and_does_not_create_it(tmp_path, capsys):
    library_root = tmp_path / "typo"

    code = cli.main(["-l", str(library_root), "list"])

    assert code == 1
    err = capsys.readouterr().err
    assert "library not found" in err
    assert str(library_root) in err
    assert not library_root.exists()


def test_search_on_missing_library_is_an_error_and_does_not_create_it(tmp_path, capsys):
    library_root = tmp_path / "typo"

    code = cli.main(["-l", str(library_root), "search", "anything"])

    assert code == 1
    assert "library not found" in capsys.readouterr().err
    assert not library_root.exists()


def test_library_path_that_is_a_file_is_an_error(tmp_path, capsys):
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x")

    code = cli.main(["-l", str(not_a_dir), "list"])

    assert code == 1
    assert "not a directory" in capsys.readouterr().err


def test_no_command_prints_help_and_succeeds(capsys):
    code = cli.main([])

    assert code == 0
    out = capsys.readouterr().out
    assert "usage: bookman" in out
    assert "examples:" in out


def test_missing_positional_prints_subcommand_help(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["import"])

    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "ebook file or directory to import" in err
    assert "required: path" in err


def test_import_missing_path_says_so(tmp_path, capsys):
    missing = tmp_path / "missing.epub"

    code = cli.main(["-l", str(tmp_path / "Library"), "import", str(missing)])

    assert code == 1
    err = capsys.readouterr().err
    assert "no such file or directory" in err
    assert str(missing) in err


def test_import_unsupported_extension_lists_supported_formats(tmp_path, capsys):
    source = tmp_path / "notes.txt"
    source.write_text("x")

    code = cli.main(["-l", str(tmp_path / "Library"), "import", str(source)])

    assert code == 1
    err = capsys.readouterr().err
    assert "unsupported format '.txt'" in err
    assert ".epub" in err and ".pdf" in err


def test_import_empty_directory_hints_at_recursive(tmp_path, capsys):
    source_dir = tmp_path / "Source"
    source_dir.mkdir()

    code = cli.main(["-l", str(tmp_path / "Library"), "import", str(source_dir)])

    assert code == 0
    out = capsys.readouterr().out
    assert "0 imported, 0 failed" in out
    assert "try --recursive" in out


def test_describe_strips_duplicated_path_prefix_from_parser_errors(tmp_path):
    path = tmp_path / "bad.epub"

    assert cli._describe(ValueError(f"{path}: not a valid EPUB"), path) == "not a valid EPUB"
    assert cli._describe(FileNotFoundError(path), path) == "no such file or directory"


def test_list_prints_books_sorted_by_title(tmp_path, capsys):
    library_root = tmp_path / "Library"
    _make_epub(tmp_path / "b.epub", title="Sapiens", author="Yuval Noah Harari")
    _make_epub(tmp_path / "a.epub", title="Deep Work", author="Cal Newport")
    library = Library(library_root)
    library.import_file(tmp_path / "b.epub")
    library.import_file(tmp_path / "a.epub")

    code = cli.main(["-l", str(library_root), "list"])

    out = capsys.readouterr().out
    assert code == 0
    assert out.index("Deep Work") < out.index("Sapiens")


def test_list_needs_review_filters_to_books_needing_review(tmp_path, capsys):
    library_root = tmp_path / "Library"
    hit = Candidate(title="Matched Book", author="Some Author", cover_url=None)
    library = Library(library_root, source=FakeSource(results=[hit]))
    library.import_file(_make_epub(tmp_path / "a.epub", title="Unmatched Book"))
    library.import_file(_make_epub(tmp_path / "b.epub", title="Matched Book", author="Some Author"))

    code = cli.main(["-l", str(library_root), "list", "--needs-review"])

    out = capsys.readouterr().out
    assert code == 0
    assert "Unmatched Book" in out
    assert "Matched Book" not in out
    assert "1 books needing review" in out


def test_search_reports_no_matches(tmp_path, capsys):
    library_root = tmp_path / "Library"
    library = Library(library_root)
    library.import_file(_make_epub(tmp_path / "a.epub", title="Deep Work"))

    code = cli.main(["-l", str(library_root), "search", "nonexistent"])

    assert code == 0
    assert "no matches" in capsys.readouterr().out


def test_search_prints_matching_books(tmp_path, capsys):
    library_root = tmp_path / "Library"
    library = Library(library_root)
    library.import_file(_make_epub(tmp_path / "a.epub", title="Deep Work", author="Cal Newport"))
    library.import_file(_make_epub(tmp_path / "b.epub", title="Sapiens"))

    code = cli.main(["-l", str(library_root), "search", "newport"])

    out = capsys.readouterr().out
    assert code == 0
    assert "Deep Work" in out
    assert "Sapiens" not in out


def test_commands_refuse_to_run_with_no_library_configured(capsys):
    code = cli.main(["list"])

    assert code == 1
    err = capsys.readouterr().err
    assert "no library configured" in err
    assert "bookman init" in err


def test_init_creates_library_and_saves_it_as_default(tmp_path, config_file, capsys):
    library_root = tmp_path / "Books"

    code = cli.main(["init", str(library_root)])

    assert code == 0
    assert library_root.is_dir()
    assert config.load_config(config_file) == config.Config(library=library_root.resolve())
    out = capsys.readouterr().out
    assert "Library set up" in out
    assert str(config_file) in out


def test_init_rejects_a_file_path(tmp_path, config_file, capsys):
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x")

    code = cli.main(["init", str(not_a_dir)])

    assert code == 1
    assert "not a directory" in capsys.readouterr().err
    assert not config_file.exists()


def test_commands_use_the_initialized_library_without_a_flag(tmp_path, capsys):
    library_root = tmp_path / "Books"
    source = _make_epub(tmp_path / "book.epub", title="Deep Work")
    assert cli.main(["init", str(library_root)]) == 0

    assert cli.main(["import", str(source)]) == 0
    code = cli.main(["list"])

    assert code == 0
    assert "Deep Work" in capsys.readouterr().out
    assert {book.title for book in Library(library_root).scan()} == {"Deep Work"}


def test_library_env_var_overrides_saved_config(tmp_path, monkeypatch, capsys):
    saved = tmp_path / "Saved"
    from_env = tmp_path / "FromEnv"
    assert cli.main(["init", str(saved)]) == 0
    library = Library(from_env)
    library.import_file(_make_epub(tmp_path / "a.epub", title="Env Book"))
    monkeypatch.setenv(config.ENV_LIBRARY, str(from_env))

    code = cli.main(["list"])

    assert code == 0
    out = capsys.readouterr().out
    assert "Env Book" in out


def test_library_flag_overrides_saved_config(tmp_path, capsys):
    saved = tmp_path / "Saved"
    explicit = tmp_path / "Explicit"
    assert cli.main(["init", str(saved)]) == 0
    Library(explicit).import_file(_make_epub(tmp_path / "a.epub", title="Flag Book"))

    code = cli.main(["list", "-l", str(explicit)])

    assert code == 0
    assert "Flag Book" in capsys.readouterr().out


def test_malformed_config_file_is_reported_not_raised(config_file, capsys):
    config_file.parent.mkdir(parents=True)
    config_file.write_text("{oops")

    code = cli.main(["list"])

    assert code == 1
    err = capsys.readouterr().err
    assert "bad config file" in err
    assert str(config_file) in err


def test_config_command_shows_state_before_and_after_init(tmp_path, config_file, capsys):
    assert cli.main(["config"]) == 0
    before = capsys.readouterr().out
    assert "(not created yet)" in before
    assert "Active library:   (none)" in before

    assert cli.main(["init", str(tmp_path / "Books")]) == 0
    capsys.readouterr()

    assert cli.main(["config"]) == 0
    after = capsys.readouterr().out
    assert str(config_file) in after
    assert f"Active library:   {(tmp_path / 'Books').resolve()}" in after


def test_config_command_shows_override_sources(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(config.ENV_LIBRARY, str(tmp_path / "FromEnv"))

    assert cli.main(["config", "-l", str(tmp_path / "Explicit")]) == 0

    out = capsys.readouterr().out
    assert f"$BOOKMAN_LIBRARY: {tmp_path / 'FromEnv'}" in out
    assert f"--library:        {tmp_path / 'Explicit'}" in out
    assert f"Active library:   {(tmp_path / 'Explicit').resolve()}" in out


def test_format_book_marks_needs_review_with_reason():
    book = Book(
        title="Some Book",
        author="Some Author",
        isbn=None,
        formats=[BookFormat(kind=FormatKind.EPUB, path=Path("book.epub"))],
    )

    line = cli._format_book(book)

    assert "Some Book" in line
    assert "Some Author" in line
    assert "epub" in line
    assert "[NEEDS REVIEW: no online match]" in line


def test_format_book_reason_reflects_the_weak_link():
    title_only = Book(title="X", author=None, isbn=None, identified=MatchBasis.TITLE_ONLY)
    weak_group = Book(
        title="X", author=None, isbn=None, identified=MatchBasis.ISBN, grouped=MatchBasis.TITLE_ONLY
    )

    assert "[NEEDS REVIEW: matched by title only]" in cli._format_book(title_only)
    assert "[NEEDS REVIEW: grouped by title only]" in cli._format_book(weak_group)


def test_format_book_omits_marker_for_identified_or_reviewed():
    identified = Book(title="Some Book", author=None, isbn=None, identified=MatchBasis.ISBN)
    reviewed = Book(title="Some Book", author=None, isbn=None, reviewed=True)

    assert "unknown author" in cli._format_book(identified)
    assert "NEEDS REVIEW" not in cli._format_book(identified)
    assert "NEEDS REVIEW" not in cli._format_book(reviewed)


def test_import_directory_names_the_format_of_each_file(tmp_path, capsys):
    """Two formats of one book print two lines; without the format kind
    the second reads like a double import."""
    library_root = tmp_path / "Library"
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    _make_epub(source_dir / "a.epub", title="Deep Work", author="Cal Newport")
    _make_pdf(source_dir / "b.pdf", title="Deep Work", author="Cal Newport")

    code = cli.main(["-l", str(library_root), "import", str(source_dir)])

    assert code == 0
    lines = capsys.readouterr().out.splitlines()
    assert "[1/2] a.epub ... imported: Deep Work (epub)" in lines
    assert "[2/2] b.pdf ... imported: Deep Work (pdf, grouped with epub)" in lines


def test_import_directory_reports_skipped_unsupported_files(tmp_path, capsys):
    library_root = tmp_path / "Library"
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    _make_epub(source_dir / "a.epub", title="Book A")
    mobi = source_dir / "a.mobi"
    mobi.write_bytes(b"BOOKMOBI")

    code = cli.main(["-l", str(library_root), "import", str(source_dir)])

    assert code == 0
    out = capsys.readouterr().out
    assert "[2/2] a.mobi ... skipped (unsupported format .mobi)" in out
    assert "1 imported, 0 failed, 1 skipped" in out


def test_import_directory_summary_omits_skipped_when_none(tmp_path, capsys):
    library_root = tmp_path / "Library"
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    _make_epub(source_dir / "a.epub", title="Book A")

    cli.main(["-l", str(library_root), "import", str(source_dir)])

    out = capsys.readouterr().out
    assert "1 imported, 0 failed" in out
    assert "skipped" not in out


def test_help_lists_only_the_import_and_inspect_commands(capsys):
    """ADR-24: the CLI is import + inspect. Curation is the TUI's job, or
    a hand edit of metadata.json."""
    with pytest.raises(SystemExit):
        cli.main(["--help"])

    out = capsys.readouterr().out
    for name in ("init", "import", "list", "search", "config"):
        assert name in out
    for name in ("bookman review", "bookman edit", "bookman reidentify", "  review ", "  edit "):
        assert name not in out


# --- F14: a refused same-kind import is reported, not hidden (ADR-21) ----


def test_import_reports_a_refused_same_kind_file(tmp_path, capsys):
    library_root = tmp_path / "Library"
    Library(library_root).import_file(
        _make_epub(tmp_path / "shelved.epub", title="Deep Work", author="Cal Newport")
    )
    second = _make_epub(
        tmp_path / "second.epub",
        title="Deep Work",
        author="Cal Newport",
        identifiers=[f"urn:isbn:{VALID_ISBN13}"],
    )

    code = cli.main(["-l", str(library_root), "import", str(second)])

    err = capsys.readouterr().err
    assert code == 1
    assert f'not imported: {second}: "Deep Work" already has a different epub' in err
    assert "same title and author" in err
    assert f"delete {library_root / 'Deep Work' / 'Deep Work.epub'} and import again" in err
    assert "failed" not in err


def test_import_directory_counts_conflicts_apart_from_failures(tmp_path, capsys):
    library_root = tmp_path / "Library"
    Library(library_root).import_file(_make_epub(tmp_path / "shelved.epub", title="Dune"))
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _make_epub(bundle / "dune.epub", title="Dune", author="Ada Lovelace")
    _make_epub(bundle / "sapiens.epub", title="Sapiens")

    code = cli.main(["-l", str(library_root), "import", str(bundle)])

    out, err = capsys.readouterr()
    assert code == 1
    assert "imported: Sapiens" in out
    assert "1 imported, 0 failed, 1 not imported (already have that format)" in out
    assert "same title only -- check it is really the same book" in err
