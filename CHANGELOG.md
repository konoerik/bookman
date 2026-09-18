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
- `Book.id` — a stable identity minted once per book and stored in
  `metadata.json`, which moves to schema version 3. Unlike `Book.directory`
  it survives a rename of the book's folder, so a frontend can hold a
  reference to a book, edit its title, and still be talking about the same
  book afterwards. Libraries written by earlier versions are migrated on
  read: a book with no stored id gets a deterministic one derived from its
  folder name, which becomes a stored id the next time it is saved. Schema
  versions 2 and 3 are both readable, and version 1 keeps its existing
  migration path.

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
