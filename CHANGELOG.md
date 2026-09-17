# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
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
