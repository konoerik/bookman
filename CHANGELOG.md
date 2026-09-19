# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Curation: `Library.mark_reviewed`, `Library.edit` and
  `Library.reidentify` — the half of the review workflow that was
  missing. `edit` corrects a book's title, author or ISBN, renaming its
  folder and format files when the title changes, normalizing an ISBN to
  ISBN-13 and refusing an invalid one. Editing marks a book reviewed, so
  the correction is not overwritten the next time another format of that
  book is imported. `reidentify` looks a book up again; a reviewed book
  keeps everything a human set and gains only a cover it was missing,
  which is the way to get a cover for a book Open Library could not match
  on its own.
- CLI commands for the above: `bookman review BOOK [--undo]`,
  `bookman edit BOOK [--title T] [--author A | --no-author]
  [--isbn I | --no-isbn]` and `bookman reidentify BOOK`. BOOK is the
  title as `list` prints it, the book's folder name, or its id; a title
  shared by several books is refused with their folder names listed.
- A book now holds one file per format kind, and an import that would
  put a *different* file where one already is — a second EPUB edition, or
  two unrelated books that grouped by title — is refused instead of
  silently overwriting it. `Library.import_file` raises
  `FormatConflictError`, which carries the book, the file it already
  holds, how the file joined it (ISBN, title and author, or title only)
  and what the refused file resolved to, so a frontend can ask the user
  what they meant. `Library.import_directory` collects these in
  `ImportBatchResult.conflicts`, separate from `failed`. Re-importing the
  same file (same bytes, any name) stays idempotent. `bookman import`
  reports each refusal with the reason and how to replace the file.
- `Book.id` — a stable identity minted once per book and stored in
  `metadata.json`, which moves to schema version 3. Unlike `Book.directory`
  it survives a rename of the book's folder, so a frontend can hold a
  reference to a book, edit its title, and still be talking about the same
  book afterwards. Libraries written by earlier versions are migrated on
  read: a book with no stored id gets a deterministic one derived from its
  folder name, which becomes a stored id the next time it is saved. Schema
  versions 2 and 3 are both readable, and version 1 keeps its existing
  migration path.

- `Book.record_author` — what the Open Library record named as the
  author, kept beside the book's own `author` so a frontend can show
  "Open Library says …" and offer it as an alternative spelling.
  `metadata.json` moves to schema version 4 to carry it; versions 2 and 3
  are read as before and upgraded on the next save.

### Changed
- On an accepted Open Library match the file's own author now stands,
  the same way its title already did; the record's author is used only
  when the file names none. Open Library returns the *work's* author
  list — every edition's contributors, so an audiobook's narrator was
  landing on the book as a co-author. Files whose own author is a
  stand-in for a blank ("Unknown", "N/A") are treated as having none
  and get the record's author instead; "Anonymous" and "Various" are
  kept as written.
- A different edition is now a different book, whatever punctuation the
  title uses. An ordinal edition marker — "2nd Edition", "Second Edition",
  "2nd ed." — is recognized before the subtitle and bracket rules run,
  so "Algorithmic Thinking (2nd Edition)" and "Algorithmic Thinking: 2nd
  Edition" no longer group with the first edition (they did; the comma
  form never did). Two files carrying the same edition, however written,
  still group, and a shared ISBN still identifies an edition file
  against its edition record.

### Fixed
- A junk title no longer groups unrelated files. A *placeholder* —
  "Untitled", "Untitled Document 2", "No Title", or a converter's
  filename stamp ("Microsoft Word - chapter1.docx") — now normalizes to
  nothing and counts as no title at all: it matches nothing and is no
  longer searched for on Open Library. A merely *generic* title —
  "Book", "Final Draft", "New Document" — is still searched and can
  still be matched, but no longer on its own: it needs an agreeing
  author, so two unrelated files called "Book" stay two books while
  Alan Watts' "The Book" is identified as before. Neither kind vetoes a
  shared ISBN, exactly as a missing title never did.
- Volumes of a set ("... Volume 1" / "... Volume 2", "Part II" / "Part III")
  no longer merge into one book: the fuzzy title comparison now requires the
  numbers in both titles to match before consulting the similarity ratio.
- A shared ISBN no longer groups two files whose title *and* author both
  contradict each other (a false-positive ISBN scraped from PDF text);
  grouping now applies the same guard identification already did.
- An ISBN scraped from a PDF's page text is no longer accepted on the
  strength of a shared author alone (the "Also by this author" citation
  case); it now needs the record's title to agree with the file's. ISBNs
  from an EPUB's `dc:identifier` are unaffected.
- A file carrying several ISBNs — a print and an ebook ISBN, or a cited
  list — now has each tried in turn until one is accepted. Previously only
  the first was looked up, so if Open Library did not know it, or its
  record contradicted the file, the rest were never tried. A rejected ISBN
  is dropped; the first one Open Library does not know is kept as the
  file's own claim.
- ISBN lookup works again. Open Library's Books API (`/api/books`) stopped
  answering — 404 on every bibkey — which left every ISBN-based
  identification falling through to title search. The lookup now goes
  through the Search API (`/search.json?isbn=`), which answers in one
  request with the same document shape title search already uses.
  Requests also now carry a `bookman/<version>` User-Agent, as Open
  Library asks of API clients.
- An ISBN from a file's metadata is no longer accepted on the strength
  of a record whose title contradicts the file's and which names no
  author. Previously "title and author must both disagree" let a record
  with no author through, so a mis-keyed ISBN landing on some other
  book's record was identified with confidence. Now the title
  disagreement stands unless the author agrees; the ISBN is dropped and
  the file goes to title search instead (ADR-19).
- A generational suffix ("Martin Luther King Jr.", "King, Martin
  Luther, Jr.") is no longer taken as the surname when authors are
  compared, so such a file now agrees with Open Library's record
  instead of being vetoed on author.

### Added
- `ImportBatchResult` is exported from `bookman` itself, so a frontend
  reporting an import run no longer has to import it from
  `bookman.library`.
- `ParsedMetadata.isbns_scraped` records whether a parser found its ISBNs
  by scanning text (PDF) rather than in a metadata field (EPUB);
  `match_basis` takes a matching `isbn_scraped` keyword.

## [0.1.0] - 2026-09-16

### Added
- Initial release: EPUB and PDF parsing, ISBN extraction, Open Library
  lookup and title/author search behind a `MetadataSource` protocol, an
  evidence-based match rule for identification and grouping, a flat
  title-named library layout with `metadata.json` per book, a sqlite search
  index, persisted library config, and the `bookman init` / `import` /
  `list` / `search` / `config` CLI.

[Unreleased]: https://github.com/konoerik/bookman/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/konoerik/bookman/releases/tag/v0.1.0
