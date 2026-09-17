# Roadmap
<!-- Load only when explicitly discussing goals or priorities.
     This is a high-level document — avoid granular tasks here, those belong in PLAN.md. -->

## Goal
A lean, scriptable alternative to Calibre for the one workflow that actually matters:
drop a batch of purchased ebook files (EPUB/PDF/sometimes MOBI, often from bundle
sites) into an inbox, have them identified, grouped by title across formats, and
organized into a managed library directory with metadata and cover art — with a
companion TUI to browse, filter/search, and inspect a book's available formats.
No conversion, no device sync, no news/RSS.

## Phases

### Phase 1: Core library, EPUB + PDF
Data model, EPUB/PDF parsers, ISBN extraction/validation, Open Library lookup,
metadata.json catalog, sqlite3 search index, flat-directory import flow with
confidence flagging. Out of scope for this phase: MOBI, any TUI/CLI.

### Phase 2: MOBI support
Add a MOBI parser behind the existing `FormatParser` protocol once the core
import/identify/organize flow is proven on EPUB+PDF.

### Phase 3: TUI frontend (separate project)
Consumes bookman as a library: browse, filter/search, inspect multi-format
books, surface `Book.needs_review` books for manual correction and set `Book.reviewed`.

## Out of Scope
- Format conversion (EPUB↔MOBI↔PDF, etc.)
- Device transfer/sync
- News/RSS aggregation
- Author/Series-based directory nesting (library is flat by title — see ADR-1)

## Ideas (not yet scheduled)
- Humble Bundle candidate-title hints: given a bundle page URL, scrape the list of
  titles included in that bundle and use it as a non-authoritative hint set to bias
  fuzzy title matching during import of that batch. Deferred — needs its own
  scraping/parsing concern and Humble Bundle's page structure isn't a stable contract.
