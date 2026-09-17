# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
