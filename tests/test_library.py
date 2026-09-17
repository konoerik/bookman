import pytest
from helpers import VALID_ISBN13
from helpers import make_epub as _make_epub
from helpers import make_pdf as _make_pdf

from bookman.errors import UnsupportedFormatError
from bookman.identify.source import Candidate
from bookman.library import Library, _sanitize_dirname
from bookman.models import Book, BookFormat, FormatKind, MatchBasis
from bookman.storage.catalog import save_metadata

_LONG_PREFIX = (
    "A Word Word Word Word Word Word Word Word Word Word Word Word Word Word Word Wor"
    "d Word Word Word Word Word Word Word Word Word Word Word Word Word Word Word Wor"
)


def test_import_file_creates_new_book_folder_with_sanitized_title(tmp_path, library, source):
    source = _make_epub(
        tmp_path / "source.epub", title="Deep Work: Rules for Success", author="Cal Newport"
    )

    book = library.import_file(source)

    assert book.title == "Deep Work: Rules for Success"
    directory = book.formats[0].path.parent
    assert directory.name == "Deep Work - Rules for Success"
    assert directory.parent == library.root


@pytest.mark.parametrize(
    ("title", "dirname"),
    [
        ("Software Architecture : the Hard Parts", "Software Architecture - the Hard Parts"),
        ('What If?: "Serious" Answers', "What If - Serious Answers"),
        ("Trailing Colon:", "Trailing Colon"),
        ("A/B Testing <Guide>", "AB Testing Guide"),
        ("...", "Untitled"),
    ],
)
def test_sanitize_dirname(title, dirname):
    assert _sanitize_dirname(title) == dirname


def test_import_file_names_format_files_after_their_folder(tmp_path, library):
    epub = _make_epub(tmp_path / "a.epub", title="Deep Work: Rules", author="Cal Newport")
    pdf = _make_pdf(tmp_path / "b.pdf", title="Deep Work: Rules", author="Cal Newport")

    library.import_file(epub)
    book = library.import_file(pdf)

    directory = book.formats[0].path.parent
    assert {fmt.path.name for fmt in book.formats} == {
        f"{directory.name}.epub",
        f"{directory.name}.pdf",
    }
    assert sorted(p.name for p in directory.iterdir()) == [
        "Deep Work - Rules.epub",
        "Deep Work - Rules.pdf",
        "metadata.json",
    ]


def test_import_file_replaces_legacy_book_named_format_file(tmp_path, library):
    directory = library.root / "Deep Work"
    directory.mkdir()
    legacy = directory / "book.epub"
    legacy.write_bytes(b"old")
    save_metadata(
        Book(
            title="Deep Work",
            author="Cal Newport",
            isbn=None,
            formats=[BookFormat(kind=FormatKind.EPUB, path=legacy)],
        ),
        directory,
    )

    epub = _make_epub(tmp_path / "new.epub", title="Deep Work", author="Cal Newport")
    book = library.import_file(epub)

    assert [fmt.path for fmt in book.formats] == [directory / "Deep Work.epub"]
    assert not legacy.exists()


def test_import_file_keeps_first_title_when_second_format_is_identified_equally(
    tmp_path, library, source
):
    result = Candidate(title="Deep Work", author="Cal Newport", cover_url=None)
    source.record = result

    epub = _make_epub(
        tmp_path / "a.epub", title="Deep Work: Rules", identifiers=[f"urn:isbn:{VALID_ISBN13}"]
    )
    library.import_file(epub)
    pdf = _make_pdf(tmp_path / "b.pdf", title="DEEP WORK", text=f"ISBN {VALID_ISBN13}")
    book = library.import_file(pdf)

    assert book.identified == MatchBasis.ISBN
    assert book.title == "Deep Work: Rules"


def test_import_file_adds_second_format_to_existing_book_by_isbn_match(tmp_path, library, source):
    source.record = None

    epub = _make_epub(
        tmp_path / "book.epub", title="Deep Work", identifiers=[f"urn:isbn:{VALID_ISBN13}"]
    )
    library.import_file(epub)

    pdf = _make_pdf(tmp_path / "book.pdf", title="Deep Work", text=f"ISBN {VALID_ISBN13}")
    book = library.import_file(pdf)

    kinds = {fmt.kind for fmt in book.formats}
    assert kinds == {FormatKind.EPUB, FormatKind.PDF}
    assert len({fmt.path.parent for fmt in book.formats}) == 1
    assert book.grouped == MatchBasis.ISBN
    assert book.identified is None
    assert book.needs_review


def test_import_file_upgrades_identification_on_follow_up_format(tmp_path, library, source):
    source.record = None

    epub = _make_epub(
        tmp_path / "book.epub",
        title="Deep Work: Guessed Subtitle",
        identifiers=[f"urn:isbn:{VALID_ISBN13}"],
    )
    first = library.import_file(epub)
    assert first.identified is None

    result = Candidate(title="Deep Work", author="Cal Newport", cover_url=None)
    source.record = result
    pdf = _make_pdf(tmp_path / "book.pdf", title="Deep Work", text=f"ISBN {VALID_ISBN13}")

    book = library.import_file(pdf)

    assert book.title == "Deep Work"
    assert book.author == "Cal Newport"
    assert book.identified == MatchBasis.ISBN
    assert book.grouped == MatchBasis.ISBN
    assert not book.needs_review


def test_import_file_does_not_downgrade_identification_on_lookup_failure(tmp_path, library, source):
    result = Candidate(title="Deep Work", author="Cal Newport", cover_url=None)
    source.record = result

    epub = _make_epub(
        tmp_path / "book.epub", title="Deep Work", identifiers=[f"urn:isbn:{VALID_ISBN13}"]
    )
    first = library.import_file(epub)
    assert first.identified == MatchBasis.ISBN

    source.record = None
    pdf = _make_pdf(tmp_path / "book.pdf", title="Deep Work", text=f"ISBN {VALID_ISBN13}")
    second = library.import_file(pdf)

    assert second.identified == MatchBasis.ISBN
    assert second.title == "Deep Work"
    assert not second.needs_review


def test_import_file_does_not_replace_strong_identification_with_weaker(tmp_path, library, source):
    result = Candidate(title="Deep Work", author="Cal Newport", cover_url=None)
    source.record = result
    epub = _make_epub(
        tmp_path / "book.epub", title="Deep Work", identifiers=[f"urn:isbn:{VALID_ISBN13}"]
    )
    library.import_file(epub)

    # A second, ISBN-less format identified only by title search must not
    # overwrite the ISBN-verified title with the search hit's spelling.
    weaker = Candidate(title="Deep Work (Summary)", author="Cal Newport", cover_url=None)
    source.results = [weaker]
    pdf = _make_pdf(tmp_path / "book.pdf", title="Deep Work", author="Cal Newport")
    book = library.import_file(pdf)

    assert book.title == "Deep Work"
    assert book.identified == MatchBasis.ISBN
    assert book.grouped == MatchBasis.TITLE_AUTHOR


def test_import_file_groups_second_format_by_title_and_author(tmp_path, library):

    epub = _make_epub(tmp_path / "book.epub", title="Sapiens", author="Yuval Noah Harari")
    library.import_file(epub)

    pdf = _make_pdf(tmp_path / "book.pdf", title="Sapiens", author="Harari, Yuval Noah")
    book = library.import_file(pdf)

    kinds = {fmt.kind for fmt in book.formats}
    assert kinds == {FormatKind.EPUB, FormatKind.PDF}
    assert len({fmt.path.parent for fmt in book.formats}) == 1
    assert book.grouped == MatchBasis.TITLE_AUTHOR


def test_import_file_groups_deep_work_with_its_subtitled_edition(tmp_path, library):

    library.import_file(_make_epub(tmp_path / "a.epub", title="Deep Work", author="Cal Newport"))
    book = library.import_file(
        _make_pdf(
            tmp_path / "b.pdf", title="Deep Work: Rules for Focused Success", author="Cal Newport"
        )
    )

    assert {fmt.kind for fmt in book.formats} == {FormatKind.EPUB, FormatKind.PDF}
    assert book.grouped == MatchBasis.TITLE_AUTHOR
    assert len(library.scan()) == 1


def test_import_file_does_not_group_book_of_job_with_book_of_joel(tmp_path, library):

    library.import_file(_make_epub(tmp_path / "a.epub", title="The Book of Job"))
    library.import_file(_make_epub(tmp_path / "b.epub", title="The Book of Joel"))

    assert sorted(book.title for book in library.scan()) == ["The Book of Job", "The Book of Joel"]


def test_import_file_keeps_volumes_of_a_set_as_separate_books(tmp_path, library):
    library.import_file(
        _make_epub(tmp_path / "a.epub", title="The Lord of the Rings Volume 1", author="Tolkien")
    )
    library.import_file(
        _make_epub(tmp_path / "b.epub", title="The Lord of the Rings Volume 2", author="Tolkien")
    )

    books = library.scan()
    assert sorted(book.title for book in books) == [
        "The Lord of the Rings Volume 1",
        "The Lord of the Rings Volume 2",
    ]
    assert all(len(book.formats) == 1 for book in books)


def test_import_file_does_not_group_by_isbn_when_title_and_author_both_disagree(
    tmp_path, library, source
):
    # A false-positive ISBN scraped from two unrelated PDFs, unknown to the
    # source, so identification keeps it on both. Sharing it must not be
    # enough to put them in one folder.
    source.record = None
    library.import_file(
        _make_pdf(
            tmp_path / "a.pdf", title="Deep Work", author="Cal Newport", text=f"ISBN {VALID_ISBN13}"
        )
    )
    book = library.import_file(
        _make_pdf(
            tmp_path / "b.pdf",
            title="Sapiens",
            author="Yuval Noah Harari",
            text=f"ISBN {VALID_ISBN13}",
        )
    )

    assert book.grouped is None
    books = library.scan()
    assert sorted(b.title for b in books) == ["Deep Work", "Sapiens"]
    assert all(len(b.formats) == 1 for b in books)


def test_import_file_rejects_pdf_isbn_of_another_book_by_the_same_author(tmp_path, library, source):
    # B6: the "Also by Cal Newport" page cites a different book's ISBN.
    source.record = Candidate(
        title="So Good They Can't Ignore You", author="Cal Newport", cover_url="sg.jpg"
    )
    source.results = [Candidate(title="Deep Work", author="Cal Newport", cover_url="dw.jpg")]
    source.cover = b"jpeg"

    book = library.import_file(
        _make_pdf(
            tmp_path / "a.pdf", title="Deep Work", author="Cal Newport", text=f"ISBN {VALID_ISBN13}"
        )
    )

    assert book.identified == MatchBasis.TITLE_AUTHOR
    assert book.isbn is None
    assert ("fetch_cover", "dw.jpg") in source.calls
    assert ("fetch_cover", "sg.jpg") not in source.calls


def test_import_file_does_not_group_same_title_different_author(tmp_path, library):

    library.import_file(_make_epub(tmp_path / "a.epub", title="Dune", author="Frank Herbert"))
    library.import_file(_make_pdf(tmp_path / "b.pdf", title="Dune", author="Kevin J. Anderson"))

    books = library.scan()
    assert len(books) == 2
    assert all(len(book.formats) == 1 for book in books)


def test_import_file_groups_by_title_only_when_author_missing_and_flags_it(tmp_path, library):

    library.import_file(
        _make_epub(tmp_path / "a.epub", title="Sapiens", author="Yuval Noah Harari")
    )
    book = library.import_file(_make_pdf(tmp_path / "b.pdf", title="Sapiens"))

    assert {fmt.kind for fmt in book.formats} == {FormatKind.EPUB, FormatKind.PDF}
    assert book.grouped == MatchBasis.TITLE_ONLY
    assert book.author == "Yuval Noah Harari"
    assert book.needs_review


def test_import_file_records_weakest_grouping_basis(tmp_path, library, source):
    source.record = None
    isbn_id = [f"urn:isbn:{VALID_ISBN13}"]

    library.import_file(_make_epub(tmp_path / "a.epub", title="Sapiens", identifiers=isbn_id))
    weak = library.import_file(_make_pdf(tmp_path / "b.pdf", title="Sapiens"))
    assert weak.grouped == MatchBasis.TITLE_ONLY

    # A later strong join must not erase the record of the weak one.
    (tmp_path / "b.pdf").unlink()
    strong = library.import_file(
        _make_pdf(tmp_path / "c.pdf", title="Sapiens", text=f"ISBN {VALID_ISBN13}")
    )
    assert strong.grouped == MatchBasis.TITLE_ONLY
    assert strong.needs_review


def test_import_file_identifies_isbn_less_book_by_title_search(tmp_path, library, source):
    hit = Candidate(
        title="Alice's Adventures in Wonderland",
        author="Lewis Carroll",
        cover_url="https://covers.openlibrary.org/b/id/1-L.jpg",
    )
    source.results = [hit]
    source.cover = b"cover bytes"
    epub = _make_epub(
        tmp_path / "alice.epub", title="Alice's Adventures in Wonderland", author="Carroll, Lewis"
    )

    book = library.import_file(epub)

    assert book.identified == MatchBasis.TITLE_AUTHOR
    assert book.author == "Lewis Carroll"
    assert book.isbn is None
    assert book.cover_path is not None
    assert book.cover_path.read_bytes() == b"cover bytes"
    assert not book.needs_review


def test_import_file_flags_title_only_identification(tmp_path, library, source):
    hit = Candidate(title="Lazarillo de Tormes", author="Anonymous", cover_url=None)
    source.results = [hit]

    book = library.import_file(_make_epub(tmp_path / "l.epub", title="Lazarillo de Tormes"))

    assert book.identified == MatchBasis.TITLE_ONLY
    assert book.needs_review


def test_import_file_sets_identified_on_agreeing_isbn_lookup(tmp_path, library, source):
    result = Candidate(
        title="Original Title", author="Resolved Author", cover_url="https://example.com/c.jpg"
    )
    source.record = result
    source.cover = b"cover bytes"

    epub = _make_epub(
        tmp_path / "book.epub",
        title="Original Title",
        identifiers=[f"urn:isbn:{VALID_ISBN13}"],
    )

    book = library.import_file(epub)

    assert book.identified == MatchBasis.ISBN
    assert not book.needs_review
    assert book.author == "Resolved Author"
    assert book.cover_path is not None
    assert book.cover_path.read_bytes() == b"cover bytes"


def test_import_file_rejects_isbn_lookup_that_contradicts_the_file(tmp_path, library, source):
    result = Candidate(title="Guide to Tax Law", author="Jane Doe", cover_url="x.jpg")
    source.record = result
    pdf = _make_pdf(
        tmp_path / "book.pdf",
        title="Deep Work",
        author="Cal Newport",
        text=f"reference number {VALID_ISBN13}",
    )

    book = library.import_file(pdf)

    assert book.title == "Deep Work"
    assert book.author == "Cal Newport"
    assert book.isbn is None
    assert book.identified is None
    assert book.cover_path is None
    assert book.needs_review


def test_import_file_needs_review_without_any_online_match(tmp_path, library):
    epub = _make_epub(tmp_path / "book.epub", title="No ISBN Book")

    book = library.import_file(epub)

    assert book.identified is None
    assert book.grouped is None
    assert book.needs_review


def test_import_file_falls_back_to_parsed_metadata_on_lookup_failure(tmp_path, library, source):
    source.fail = True

    epub = _make_epub(
        tmp_path / "book.epub",
        title="Parsed Title",
        author="Parsed Author",
        identifiers=[f"urn:isbn:{VALID_ISBN13}"],
    )

    book = library.import_file(epub)

    assert book.identified is None
    assert book.needs_review
    assert book.title == "Parsed Title"
    assert book.author == "Parsed Author"
    assert book.isbn == VALID_ISBN13
    assert book.cover_path is None


def test_import_file_falls_back_when_cover_fetch_fails(tmp_path, library, source):
    result = Candidate(
        title="Original Title", author="Resolved Author", cover_url="https://example.com/c.jpg"
    )
    source.record = result

    source.cover = None  # every fetch fails

    epub = _make_epub(
        tmp_path / "book.epub", title="Original Title", identifiers=[f"urn:isbn:{VALID_ISBN13}"]
    )

    book = library.import_file(epub)

    assert book.identified == MatchBasis.ISBN
    assert book.author == "Resolved Author"
    assert book.cover_path is None


def _mark_reviewed(library, book, **corrections):
    from bookman.storage.catalog import save_metadata

    for key, value in corrections.items():
        setattr(book, key, value)
    book.reviewed = True
    save_metadata(book, book.formats[0].path.parent)


def test_import_file_does_not_overwrite_reviewed_book_metadata(tmp_path, library, source):
    source.record = None
    isbn_id = [f"urn:isbn:{VALID_ISBN13}"]
    first = library.import_file(_make_epub(tmp_path / "a.epub", title="Wrong", identifiers=isbn_id))
    _mark_reviewed(library, first, title="Corrected Title", author="Corrected Author")

    # The record's title agrees (so the PDF's scraped ISBN is accepted) but
    # its spelling and author differ from the reviewed values.
    result = Candidate(
        title="Corrected Title: Online Subtitle", author="Online Author", cover_url="c.jpg"
    )
    source.record = result
    book = library.import_file(
        _make_pdf(tmp_path / "b.pdf", title="Corrected Title", text=f"ISBN {VALID_ISBN13}")
    )

    assert book.title == "Corrected Title"
    assert book.author == "Corrected Author"
    assert book.identified is None
    assert book.cover_path is None
    assert book.reviewed is True
    assert book.grouped == MatchBasis.ISBN
    assert {fmt.kind for fmt in book.formats} == {FormatKind.EPUB, FormatKind.PDF}
    assert not book.needs_review


def test_import_file_clears_reviewed_on_title_only_join(tmp_path, library):
    first = library.import_file(_make_epub(tmp_path / "a.epub", title="Sapiens", author="Harari"))
    _mark_reviewed(library, first)

    book = library.import_file(_make_pdf(tmp_path / "b.pdf", title="Sapiens"))

    assert book.reviewed is False
    assert book.grouped == MatchBasis.TITLE_ONLY
    assert book.author == "Harari"
    assert book.needs_review


def test_import_file_deduplicates_folder_name_on_collision(tmp_path, library):
    title1 = _LONG_PREFIX + " Volume One With Extra Detail And More Words Appended At The End"
    title2 = _LONG_PREFIX + " Volume Two Totally Different Continuation Text Goes Right Here"

    book1 = library.import_file(_make_epub(tmp_path / "one.epub", title=title1))
    book2 = library.import_file(_make_epub(tmp_path / "two.epub", title=title2))

    dir1 = book1.formats[0].path.parent
    dir2 = book2.formats[0].path.parent
    assert dir1 != dir2
    assert dir1.parent == library.root
    assert dir2.parent == library.root


def test_import_file_leaves_original_file_in_place(tmp_path, library, source):
    source = _make_epub(tmp_path / "source.epub", title="Some Book")

    library.import_file(source)

    assert source.exists()


def test_import_file_raises_unsupported_format_error_for_unknown_suffix(tmp_path, library):
    mobi = tmp_path / "book.mobi"
    mobi.write_bytes(b"fake mobi bytes")

    with pytest.raises(UnsupportedFormatError):
        library.import_file(mobi)


def test_import_file_raises_file_not_found_for_missing_source(tmp_path, library):
    with pytest.raises(FileNotFoundError):
        library.import_file(tmp_path / "missing.epub")


def test_scan_returns_all_cataloged_books(tmp_path, library):
    library.import_file(_make_epub(tmp_path / "a.epub", title="Book A"))
    library.import_file(_make_epub(tmp_path / "b.epub", title="Book B"))

    titles = {book.title for book in library.scan()}
    assert titles == {"Book A", "Book B"}


def test_import_scan_and_search_all_return_books_that_know_their_directory(tmp_path, library):

    imported = library.import_file(_make_epub(tmp_path / "a.epub", title="Book A"))

    expected = library.root / "Book A"
    assert imported.directory == expected
    assert [book.directory for book in library.scan()] == [expected]
    assert [book.directory for book in library.search("book")] == [expected]


def test_second_format_joins_the_book_at_its_directory(tmp_path, library):
    first = library.import_file(_make_epub(tmp_path / "a.epub", title="Sapiens", author="Harari"))

    second = library.import_file(_make_pdf(tmp_path / "b.pdf", title="Sapiens", author="Harari"))

    assert second.directory == first.directory
    assert {fmt.path.parent for fmt in second.formats} == {first.directory}


def test_scan_skips_folders_without_metadata_json(tmp_path, library):
    library.import_file(_make_epub(tmp_path / "a.epub", title="Book A"))
    (library.root / "Not A Book").mkdir()

    books = library.scan()

    assert len(books) == 1
    assert books[0].title == "Book A"


def test_search_matches_by_title_or_author(tmp_path, library):
    library.import_file(_make_epub(tmp_path / "a.epub", title="Deep Work", author="Cal Newport"))
    library.import_file(
        _make_epub(tmp_path / "b.epub", title="Sapiens", author="Yuval Noah Harari")
    )

    assert {book.title for book in library.search("deep")} == {"Deep Work"}
    assert {book.title for book in library.search("harari")} == {"Sapiens"}


def test_search_builds_index_if_missing(tmp_path, library):
    library.import_file(_make_epub(tmp_path / "a.epub", title="Deep Work"))
    (library.root / ".bookman-index.sqlite3").unlink()

    results = library.search("deep")

    assert {book.title for book in results} == {"Deep Work"}


def test_search_works_after_the_library_folder_is_moved(tmp_path, library):
    library.import_file(_make_epub(tmp_path / "a.epub", title="Deep Work"))

    moved_root = tmp_path / "Moved"
    (tmp_path / "Library").rename(moved_root)
    moved = Library(moved_root)

    [book] = moved.search("deep")
    assert book.directory == moved_root / "Deep Work"
    assert book.formats[0].path.exists()


def test_import_directory_imports_every_supported_file_at_top_level(tmp_path, library):
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    _make_epub(source_dir / "a.epub", title="Book A")
    _make_pdf(source_dir / "b.pdf", title="Book B")
    (source_dir / "c.txt").write_text("not a book")

    result = library.import_directory(source_dir)

    assert {book.title for _, book in result.imported} == {"Book A", "Book B"}
    assert result.failed == []
    assert {book.title for book in library.scan()} == {"Book A", "Book B"}


def test_import_directory_ignores_subdirectories_unless_recursive(tmp_path, library):
    source_dir = tmp_path / "Source"
    nested_dir = source_dir / "Nested"
    nested_dir.mkdir(parents=True)
    _make_epub(source_dir / "a.epub", title="Book A")
    _make_epub(nested_dir / "b.epub", title="Book B")

    non_recursive = library.import_directory(source_dir)
    assert {book.title for _, book in non_recursive.imported} == {"Book A"}

    recursive = library.import_directory(source_dir, recursive=True)
    assert {book.title for _, book in recursive.imported} == {"Book A", "Book B"}


def test_import_directory_records_failures_without_aborting_the_batch(tmp_path, library):
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    _make_epub(source_dir / "good.epub", title="Good Book")
    bad = source_dir / "bad.epub"
    bad.write_bytes(b"not a real zip file")

    result = library.import_directory(source_dir)

    assert {book.title for _, book in result.imported} == {"Good Book"}
    assert len(result.failed) == 1
    failed_path, exc = result.failed[0]
    assert failed_path == bad
    assert isinstance(exc, Exception)


def test_import_directory_raises_file_not_found_for_missing_directory(tmp_path, library):
    with pytest.raises(FileNotFoundError):
        library.import_directory(tmp_path / "missing")


def test_import_directory_raises_not_a_directory_for_a_file(tmp_path, library):
    source = _make_epub(tmp_path / "book.epub", title="A Book")
    with pytest.raises(NotADirectoryError):
        library.import_directory(source)


def test_scan_and_search_skip_folders_with_corrupt_metadata_json(tmp_path, library):
    library.import_file(_make_epub(tmp_path / "a.epub", title="Deep Work"))

    broken = library.root / "Broken Book"
    broken.mkdir()
    (broken / "metadata.json").write_text("{not valid json")

    scanned = library.scan()
    assert {book.title for book in scanned} == {"Deep Work"}

    results = library.search("deep")
    assert {book.title for book in results} == {"Deep Work"}


def test_import_directory_pairs_each_imported_book_with_its_source_file(tmp_path, library):
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    epub = _make_epub(source_dir / "a.epub", title="Book A")
    pdf = _make_pdf(source_dir / "b.pdf", title="Book B")

    result = library.import_directory(source_dir)

    assert [(path, book.title) for path, book in result.imported] == [
        (epub, "Book A"),
        (pdf, "Book B"),
    ]


def test_import_directory_reports_unsupported_files_as_skipped(tmp_path, library):
    """A .mobi in a bundle is not an error (the batch still succeeds),
    but the caller must be able to tell the user it wasn't imported."""
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    _make_epub(source_dir / "a.epub", title="Book A")
    mobi = source_dir / "a.mobi"
    mobi.write_bytes(b"BOOKMOBI")
    (source_dir / ".DS_Store").write_bytes(b"junk")

    result = library.import_directory(source_dir)

    assert result.skipped == [mobi]
    assert result.failed == []
