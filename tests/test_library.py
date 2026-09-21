import pytest
from helpers import VALID_ISBN13
from helpers import make_epub as _make_epub
from helpers import make_pdf as _make_pdf

from bookman.errors import FormatConflictError, UnsupportedFormatError
from bookman.formats.epub import BadEpubError
from bookman.identify.source import Candidate
from bookman.library import ImportBatchResult, Library, _sanitize_dirname
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
    epub = _make_epub(tmp_path / "new.epub", title="Deep Work", author="Cal Newport")
    legacy = directory / "book.epub"
    legacy.write_bytes(epub.read_bytes())  # the same file, under the pre-0.3 name
    save_metadata(
        Book(
            title="Deep Work",
            author="Cal Newport",
            isbn=None,
            formats=[BookFormat(kind=FormatKind.EPUB, path=legacy)],
        ),
        directory,
    )

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


def test_import_file_keeps_placeholder_titled_files_as_separate_books(tmp_path, library, source):
    # FEATURES A12: two unrelated documents a converter left titled
    # "Untitled" are not one book, however identical those titles are.
    # IDENT-4: a placeholder names nothing, so each is shelved under its
    # own filename stem (A4/A8) rather than a folder called "Untitled".
    source.results = []

    library.import_file(_make_epub(tmp_path / "a.epub", title="Untitled", author=None))
    library.import_file(_make_epub(tmp_path / "b.epub", title="Untitled", author=None))

    books = library.scan()
    assert len(books) == 2
    assert all(len(book.formats) == 1 for book in books)
    assert sorted(book.formats[0].path.parent.name for book in books) == ["a", "b"]
    assert sorted(book.title for book in books) == ["a", "b"]


def test_import_file_keeps_generic_titled_files_as_separate_books(tmp_path, library, source):
    # The other half of A12: a template's "Book", with no author to
    # corroborate it, is not evidence that these are the same book.
    source.results = []

    library.import_file(_make_epub(tmp_path / "a.epub", title="Book", author=None))
    library.import_file(_make_epub(tmp_path / "b.epub", title="Book", author=None))

    assert len(library.scan()) == 2


def test_import_file_groups_generic_titled_files_when_the_author_agrees(tmp_path, library, source):
    # ... but "The Book" by Alan Watts is a real book, and its EPUB and
    # PDF still belong together.
    source.results = []

    library.import_file(_make_epub(tmp_path / "a.epub", title="The Book", author="Alan Watts"))
    book = library.import_file(_make_pdf(tmp_path / "a.pdf", title="The Book", author="Alan Watts"))

    assert len(library.scan()) == 1
    assert len(book.formats) == 2
    assert book.grouped == MatchBasis.TITLE_AUTHOR


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

    epub = _make_epub(tmp_path / "a.epub", title="Sapiens", identifiers=isbn_id)
    library.import_file(epub)
    weak = library.import_file(_make_pdf(tmp_path / "b.pdf", title="Sapiens"))
    assert weak.grouped == MatchBasis.TITLE_ONLY

    # A later strong join must not erase the record of the weak one. With
    # one file per kind (ADR-21) the strong join is a re-import of the
    # ISBN-bearing EPUB, which joins by ISBN (GROUP-1).
    strong = library.import_file(epub)
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
    assert book.author == "Carroll, Lewis"  # the file's own spelling (ADR-22)
    assert book.record_author == "Lewis Carroll"
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


# --- E15: the EPUB's own cover when identification supplies none (ADR-28) --

EMBEDDED = b"\xff\xd8\xff\xe0 embedded"


def test_import_file_uses_the_epubs_embedded_cover_when_there_is_no_record(
    tmp_path, library, source
):
    source.record = None
    source.results = []

    book = library.import_file(_make_epub(tmp_path / "book.epub", cover=EMBEDDED))

    assert book.identified is None
    assert book.cover_path is not None
    assert book.cover_path.read_bytes() == EMBEDDED


def test_import_file_uses_the_embedded_cover_when_the_record_has_none(tmp_path, library, source):
    source.record = Candidate(title="A Title", author="Someone", cover_url=None)
    epub = _make_epub(
        tmp_path / "book.epub", identifiers=[f"urn:isbn:{VALID_ISBN13}"], cover=EMBEDDED
    )

    book = library.import_file(epub)

    assert book.identified == MatchBasis.ISBN
    assert book.cover_path is not None and book.cover_path.read_bytes() == EMBEDDED


def test_import_file_uses_the_embedded_cover_when_the_download_fails(tmp_path, library, source):
    source.record = Candidate(title="A Title", author="Someone", cover_url="https://x/c.jpg")
    source.cover = None
    epub = _make_epub(
        tmp_path / "book.epub", identifiers=[f"urn:isbn:{VALID_ISBN13}"], cover=EMBEDDED
    )

    book = library.import_file(epub)

    assert book.cover_path is not None and book.cover_path.read_bytes() == EMBEDDED


def test_import_file_prefers_the_records_cover_to_the_embedded_one(tmp_path, library, source):
    source.record = Candidate(title="A Title", author="Someone", cover_url="https://x/c.jpg")
    source.cover = b"from the record"
    epub = _make_epub(
        tmp_path / "book.epub", identifiers=[f"urn:isbn:{VALID_ISBN13}"], cover=EMBEDDED
    )

    book = library.import_file(epub)

    assert book.cover_path is not None and book.cover_path.read_bytes() == b"from the record"


def test_import_file_follow_up_epub_fills_a_missing_cover_but_keeps_an_existing_one(
    tmp_path, library, source
):
    source.record = None
    source.results = []
    pdf = _make_pdf(
        tmp_path / "book.pdf", title="A Title", author="Someone", text=f"ISBN {VALID_ISBN13}"
    )
    first = library.import_file(pdf)
    assert first.cover_path is None

    epub = _make_epub(
        tmp_path / "book.epub",
        author="Someone",
        identifiers=[f"urn:isbn:{VALID_ISBN13}"],
        cover=EMBEDDED,
    )
    book = library.import_file(epub)
    assert book.grouped == MatchBasis.ISBN
    assert book.cover_path is not None and book.cover_path.read_bytes() == EMBEDDED

    # And the other way round: a book that has a cover keeps it.
    source.results = [Candidate(title="Other", author="Someone", cover_url="https://x/o.jpg")]
    source.cover = b"from the record"
    other_pdf = _make_pdf(tmp_path / "other.pdf", title="Other", author="Someone")
    with_cover = library.import_file(other_pdf)
    assert with_cover.cover_path is not None
    source.results = []
    other_epub = _make_epub(
        tmp_path / "other.epub", title="Other", author="Someone", cover=EMBEDDED
    )
    book = library.import_file(other_epub)
    assert book.id == with_cover.id
    assert book.cover_path is not None and book.cover_path.read_bytes() == b"from the record"


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


def test_scan_brings_search_in_step_with_a_hand_edited_metadata_json(tmp_path, library):
    """ADR-24's fallback for fixing a book without a frontend, closed by
    the ADR-12 amendment: the next scan refreshes the index, so search
    sees the edit without a repair command."""
    import json

    book = library.import_file(_make_epub(tmp_path / "a.epub", title="Deep Work", author="Unknown"))
    assert book.author is None
    metadata_path = book.directory / "metadata.json"
    data = json.loads(metadata_path.read_text())
    data["author"] = "Cal Newport"
    data["reviewed"] = True
    metadata_path.write_text(json.dumps(data))

    assert library.search("newport") == []  # the index still says what the import said

    [scanned] = library.scan()
    assert scanned.author == "Cal Newport"
    assert scanned.reviewed is True
    [found] = library.search("newport")
    assert found.author == "Cal Newport"


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


def test_iter_import_yields_before_and_after_each_attempted_file(tmp_path, library):
    """A frontend showing progress needs to know which file is being
    waited on, so a supported file announces itself before its lookup
    and reports after; a skipped file is never waited on, so it reports
    once."""
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    epub = _make_epub(source_dir / "a.epub", title="Book A")
    mobi = source_dir / "b.mobi"
    mobi.write_bytes(b"BOOKMOBI")
    (source_dir / ".DS_Store").write_bytes(b"junk")

    events = list(library.iter_import(source_dir))

    assert [(e.path, e.index, e.total) for e in events] == [
        (epub, 1, 2),
        (epub, 1, 2),
        (mobi, 2, 2),
    ]
    assert events[0].outcome is None
    assert isinstance(events[1].outcome, Book)
    assert events[1].outcome.title == "Book A"
    assert isinstance(events[2].outcome, UnsupportedFormatError)


def test_iter_import_reports_a_failure_as_the_outcome_and_continues(tmp_path, library):
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    bad = source_dir / "bad.epub"
    bad.write_bytes(b"not a real zip file")
    _make_epub(source_dir / "good.epub", title="Good Book")

    outcomes = [e.outcome for e in library.iter_import(source_dir) if e.outcome is not None]

    assert isinstance(outcomes[0], BadEpubError)
    assert isinstance(outcomes[1], Book)


def test_iter_import_checks_the_directory_on_the_call_not_the_first_pull(tmp_path, library):
    with pytest.raises(FileNotFoundError):
        library.iter_import(tmp_path / "missing")


def test_batch_result_record_reproduces_import_directory(tmp_path, library):
    """`record` is the one classification of an event, shared by
    `import_directory` and any frontend that streams the batch itself."""
    source_dir = tmp_path / "Source"
    source_dir.mkdir()
    _make_epub(source_dir / "a.epub", title="Book A")
    (source_dir / "b.mobi").write_bytes(b"BOOKMOBI")
    (source_dir / "c.epub").write_bytes(b"not a real zip file")

    result = ImportBatchResult()
    for event in library.iter_import(source_dir):
        result.record(event)

    assert [book.title for _, book in result.imported] == ["Book A"]
    assert result.skipped == [source_dir / "b.mobi"]
    assert [path for path, _ in result.failed] == [source_dir / "c.epub"]
    assert result.conflicts == []


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


# --- I5: stable book identity through imports (ADR-17) ------------------


def test_import_file_gives_each_new_book_its_own_id(tmp_path, library, source):
    source.record = None

    first = library.import_file(_make_epub(tmp_path / "a.epub", title="Dune"))
    second = library.import_file(_make_epub(tmp_path / "b.epub", title="Emma"))

    assert first.id and second.id
    assert first.id != second.id


def test_import_file_keeps_the_books_id_when_a_second_format_joins(tmp_path, library, source):
    """A joining format must not re-mint the identity of the book it
    joins, or every reference a frontend holds would go stale."""
    source.record = None

    epub = _make_epub(
        tmp_path / "book.epub", title="Deep Work", identifiers=[f"urn:isbn:{VALID_ISBN13}"]
    )
    original = library.import_file(epub).id

    pdf = _make_pdf(tmp_path / "book.pdf", title="Deep Work", text=f"ISBN {VALID_ISBN13}")
    joined = library.import_file(pdf)

    assert joined.grouped == MatchBasis.ISBN
    assert joined.id == original


def test_scan_reports_the_same_ids_across_calls(tmp_path, library, source):
    source.record = None
    library.import_file(_make_epub(tmp_path / "a.epub", title="Dune"))
    library.import_file(_make_epub(tmp_path / "b.epub", title="Emma"))

    first = {book.title: book.id for book in library.scan()}
    second = {book.title: book.id for book in library.scan()}

    assert first == second
    assert len(set(first.values())) == 2


# --- The core promise, pinned (FEATURES A4, A8, F5, F13, F16) ---


def test_import_file_falls_back_to_filename_stem_when_file_has_only_an_author(
    tmp_path, library, source
):
    # A4: nothing to search on, so no lookup; the stem names the book.
    epub = _make_epub(tmp_path / "sicp_notes.epub", title=None, author="Hal Abelson")

    book = library.import_file(epub)

    assert book.title == "sicp_notes"
    assert book.author == "Hal Abelson"
    assert book.identified is None
    assert book.needs_review
    assert book.directory is not None and book.directory.name == "sicp_notes"
    assert source.calls == []


def test_import_file_with_no_metadata_at_all_is_shelved_under_its_stem_for_review(
    tmp_path, library, source
):
    # A8: the degenerate file still lands somewhere findable.
    epub = _make_epub(tmp_path / "scan 0042.epub", title=None, author=None)

    book = library.import_file(epub)

    assert book.title == "scan 0042"
    assert book.author is None
    assert book.isbn is None
    assert book.identified is None
    assert book.grouped is None
    assert book.needs_review
    assert book.directory is not None and book.directory.name == "scan 0042"
    assert source.calls == []


def test_import_file_isbn_join_beats_a_title_author_join_to_a_different_book(
    tmp_path, library, source
):
    # F5: two shelved books -- one shares the file's (asserted) ISBN, the
    # other its title and author. GROUP-1 runs first, so the ISBN decides;
    # the author agreeing is what lets the ISBN survive the title mismatch.
    # The ISBN book is shelved as a PDF so the incoming EPUB can join it:
    # a book holds one file per kind (ADR-21).
    by_isbn = library.import_file(
        _make_pdf(
            tmp_path / "by_isbn.pdf",
            title="Deep Work",
            author="Cal Newport",
            text=f"ISBN {VALID_ISBN13}",
        )
    )
    assert by_isbn.isbn == VALID_ISBN13
    by_title = library.import_file(
        _make_epub(tmp_path / "by_title.epub", title="Digital Minimalism", author="Cal Newport")
    )
    assert by_isbn.directory != by_title.directory

    book = library.import_file(
        _make_epub(
            tmp_path / "new.epub",
            title="Digital Minimalism",
            author="Cal Newport",
            identifiers=[f"urn:isbn:{VALID_ISBN13}"],
        )
    )

    assert book.directory == by_isbn.directory
    assert book.grouped == MatchBasis.ISBN
    assert len(library.scan()) == 2
    (untouched,) = [b for b in library.scan() if b.directory == by_title.directory]
    assert [fmt.kind for fmt in untouched.formats] == [FormatKind.EPUB]


def test_import_file_reimport_of_the_same_file_is_idempotent(tmp_path, library):
    # F13: one format entry, the file replaced, nothing else disturbed.
    # (The library's copy is not tampered with here: a copy whose bytes
    # differ from the incoming file is, by ADR-21, a different file and
    # is refused -- see test_import_file_refuses_a_different_file_of_the_same_kind.)
    epub = _make_epub(tmp_path / "book.epub", title="Deep Work", author="Cal Newport")
    first = library.import_file(epub)
    stored = first.formats[0].path

    again = library.import_file(epub)

    assert again.id == first.id
    assert again.directory == first.directory
    assert [fmt.path for fmt in again.formats] == [stored]
    assert stored.read_bytes() == epub.read_bytes()
    assert sorted(p.name for p in first.directory.iterdir()) == ["Deep Work.epub", "metadata.json"]
    assert len(library.scan()) == 1


def test_import_order_does_not_change_the_end_state(tmp_path, source):
    # F16: {epub without ISBN, pdf with ISBN}, both ways round.
    source.record = Candidate(title="Deep Work", author="Cal Newport", cover_url=None)

    def shelve(order: str) -> Book:
        library = Library(tmp_path / order, source=source)
        epub = _make_epub(tmp_path / f"{order}.epub", title="Deep Work", author="Cal Newport")
        pdf = _make_pdf(
            tmp_path / f"{order}.pdf",
            title="Deep Work",
            author="Cal Newport",
            text=f"ISBN {VALID_ISBN13}",
        )
        for path in (epub, pdf) if order == "epub_first" else (pdf, epub):
            library.import_file(path)
        (book,) = library.scan()
        return book

    a, b = shelve("epub_first"), shelve("pdf_first")

    def state(book: Book) -> tuple:
        return (
            book.title,
            book.author,
            book.isbn,
            book.identified,
            book.grouped,
            book.needs_review,
            sorted(fmt.kind for fmt in book.formats),
        )

    assert state(a) == state(b)


# --- F17/F18: several ISBNs on one copyright page (ADR-26, ADR-27) ------

PRINT_ISBN, EBOOK_ISBN, PRIOR_EDITION_ISBN = "9781718504127", "9781718504134", "9781593278281"


def test_import_file_joins_on_any_isbn_the_file_carries(tmp_path, library, source):
    # F17 / FN-4: the EPUB asserts the ebook number; the PDF scrapes
    # print then ebook and is identified by the print one (the first the
    # source knows). The shared ebook number must still join them.
    source.records = {
        PRINT_ISBN: Candidate(title="Effective C", author="Robert C. Seacord", cover_url=None)
    }
    source.results = []

    epub = _make_epub(
        tmp_path / "book.epub",
        title="Effective C",
        author="Robert C. Seacord",
        identifiers=[f"urn:isbn:{EBOOK_ISBN}"],
    )
    library.import_file(epub)
    pdf = _make_pdf(
        tmp_path / "book.pdf",
        title="Effective C, 2nd Edition",
        author="Robert C. Seacord",
        text=f"ISBN {PRINT_ISBN} ISBN {EBOOK_ISBN}",
    )

    book = library.import_file(pdf)

    assert sorted(fmt.kind for fmt in book.formats) == [FormatKind.EPUB, FormatKind.PDF]
    assert book.grouped == MatchBasis.ISBN
    assert len(library.scan()) == 1


def test_import_file_on_an_isbn_join_declines_a_record_reached_through_another_isbn(
    tmp_path, library, source
):
    # F18 / FN-4: a title-less PDF cites the previous edition's ISBN and
    # the source knows only that one. It joins the EPUB's book on the
    # shared 3rd-edition number, but must not rename the book to the
    # 2nd-edition record or fetch its cover.
    source.records = {
        PRIOR_EDITION_ISBN: Candidate(
            title="The Rust Programming Language", author="Steve Klabnik", cover_url="2nd.jpg"
        )
    }
    source.results = []
    source.cover = b"png"

    epub = _make_epub(
        tmp_path / "book.epub",
        title="The Rust Programming Language, 3rd Edition",
        author="Steve Klabnik",
        identifiers=[f"urn:isbn:{EBOOK_ISBN}"],
    )
    first = library.import_file(epub)
    assert first.identified is None
    pdf = _make_pdf(
        tmp_path / "book.pdf",
        title=None,
        author=None,
        text=f"ISBN {EBOOK_ISBN} ISBN {PRIOR_EDITION_ISBN}",
    )

    book = library.import_file(pdf)

    assert sorted(fmt.kind for fmt in book.formats) == [FormatKind.EPUB, FormatKind.PDF]
    assert book.grouped == MatchBasis.ISBN
    assert book.title == "The Rust Programming Language, 3rd Edition"
    assert book.isbn == EBOOK_ISBN
    assert book.identified is None
    assert book.cover_path is None
    assert not source.called("fetch_cover")


def test_import_file_on_an_isbn_join_adopts_a_record_reached_through_the_joined_isbn(
    tmp_path, library, source
):
    # The other half of F18: the follow-up's record answers to the very
    # ISBN it joined on, so it is this book's and upgrades it (F7).
    source.record = None
    source.results = []
    source.cover = b"png"

    epub = _make_epub(
        tmp_path / "book.epub",
        title="Effective C",
        author="Robert C. Seacord",
        identifiers=[f"urn:isbn:{EBOOK_ISBN}"],
    )
    first = library.import_file(epub)
    assert first.identified is None
    source.records[EBOOK_ISBN] = Candidate(
        title="Effective C", author="Robert C. Seacord", cover_url="c.jpg"
    )
    pdf = _make_pdf(
        tmp_path / "book.pdf",
        title="Effective C",
        author="Robert C. Seacord",
        text=f"ISBN {PRINT_ISBN} ISBN {EBOOK_ISBN}",
    )

    book = library.import_file(pdf)

    assert book.grouped == MatchBasis.ISBN
    assert book.identified == MatchBasis.ISBN
    assert book.cover_path is not None


# --- F14: one file per format kind (spec GROUP-4, ADR-21) ----------------


def test_import_file_refuses_a_different_file_of_the_same_kind(tmp_path, library):
    first_src = _make_epub(tmp_path / "first.epub", title="Deep Work", author="Cal Newport")
    first = library.import_file(first_src)
    stored = first.formats[0].path
    # A different EPUB of the same book: the same metadata, different bytes.
    second_src = _make_epub(
        tmp_path / "second.epub",
        title="Deep Work",
        author="Cal Newport",
        identifiers=[f"urn:isbn:{VALID_ISBN13}"],
    )

    with pytest.raises(FormatConflictError) as exc:
        library.import_file(second_src)

    conflict = exc.value
    assert conflict.source == second_src
    assert conflict.book.id == first.id
    assert conflict.existing == stored
    assert conflict.basis == MatchBasis.TITLE_AUTHOR
    assert (conflict.title, conflict.author, conflict.isbn) == (
        "Deep Work",
        "Cal Newport",
        VALID_ISBN13,
    )
    assert "already has a different epub" in str(conflict)
    assert "title_author" in str(conflict)


def test_a_refused_import_changes_nothing(tmp_path, library):
    first = library.import_file(
        _make_epub(tmp_path / "first.epub", title="Deep Work", author="Cal Newport")
    )
    stored = first.formats[0].path
    before = stored.read_bytes()
    listing = sorted(p.name for p in first.directory.iterdir())
    metadata = (first.directory / "metadata.json").read_bytes()
    second = _make_epub(
        tmp_path / "second.epub",
        title="Deep Work",
        author="Cal Newport",
        identifiers=[f"urn:isbn:{VALID_ISBN13}"],
    )

    with pytest.raises(FormatConflictError):
        library.import_file(second)

    assert stored.read_bytes() == before
    assert sorted(p.name for p in first.directory.iterdir()) == listing
    assert (first.directory / "metadata.json").read_bytes() == metadata
    (saved,) = library.scan()
    assert saved.isbn is None  # the refused file's ISBN was not adopted
    assert saved.grouped is None


def test_conflict_reports_the_join_basis_for_a_doubtful_merge(tmp_path, library):
    # The in-session F14 case: two unrelated "Dune"s that GROUP-2 joins by
    # title alone. The basis tells the user the merge itself is doubtful.
    library.import_file(_make_epub(tmp_path / "a.epub", title="Dune", author=None))

    with pytest.raises(FormatConflictError) as exc:
        library.import_file(_make_epub(tmp_path / "b.epub", title="Dune", author="Ada Lovelace"))

    assert exc.value.basis == MatchBasis.TITLE_ONLY
    assert len(library.scan()) == 1


def test_a_different_kind_still_joins(tmp_path, library):
    library.import_file(_make_epub(tmp_path / "a.epub", title="Deep Work", author="Cal Newport"))

    book = library.import_file(
        _make_pdf(tmp_path / "a.pdf", title="Deep Work", author="Cal Newport")
    )

    assert sorted(fmt.kind for fmt in book.formats) == [FormatKind.EPUB, FormatKind.PDF]


def test_the_same_file_under_another_name_is_a_reimport_not_a_conflict(tmp_path, library):
    src = _make_epub(tmp_path / "a.epub", title="Deep Work", author="Cal Newport")
    first = library.import_file(src)
    copy = tmp_path / "elsewhere" / "deep-work-copy.epub"
    copy.parent.mkdir()
    copy.write_bytes(src.read_bytes())

    again = library.import_file(copy)

    assert again.id == first.id
    assert len(again.formats) == 1
    assert len(library.scan()) == 1


def test_a_recorded_file_missing_from_disk_is_not_a_conflict(tmp_path, library):
    first = library.import_file(
        _make_epub(tmp_path / "first.epub", title="Deep Work", author="Cal Newport")
    )
    first.formats[0].path.unlink()  # the user deleted it by hand to make room

    book = library.import_file(
        _make_epub(
            tmp_path / "second.epub",
            title="Deep Work",
            author="Cal Newport",
            identifiers=[f"urn:isbn:{VALID_ISBN13}"],
        )
    )

    assert book.id == first.id
    assert book.formats[0].path.exists()
    assert book.isbn == VALID_ISBN13


def test_import_directory_collects_conflicts_apart_from_failures(tmp_path, library):
    library.import_file(
        _make_epub(tmp_path / "shelved.epub", title="Deep Work", author="Cal Newport")
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _make_epub(
        bundle / "deep-work.epub",
        title="Deep Work",
        author="Cal Newport",
        identifiers=[f"urn:isbn:{VALID_ISBN13}"],
    )
    _make_epub(bundle / "other.epub", title="Sapiens", author="Yuval Noah Harari")
    (bundle / "bad.epub").write_bytes(b"not a zip")

    result = library.import_directory(bundle)

    assert [book.title for _, book in result.imported] == ["Sapiens"]
    assert [path.name for path, _ in result.failed] == ["bad.epub"]
    assert [c.source.name for c in result.conflicts] == ["deep-work.epub"]
    assert result.conflicts[0].book.title == "Deep Work"
