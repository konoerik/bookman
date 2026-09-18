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

### Phase 2: Curation — the manual half of ADR-4
Stable book identity (FEATURES I5), then mark-reviewed / edit / re-identify
(K1–K3). The review flag exists; the way to act on it doesn't, and nothing in
Phase 3 works without it.

### Phase 3: TUI frontend (separate project)
Consumes bookman as a library: browse, filter/search, inspect multi-format
books, surface `Book.needs_review` books for manual correction and set `Book.reviewed`.

### Phase 4 (unscheduled): MOBI support
Add a MOBI parser behind the existing `FormatParser` protocol. **Deprioritized
2026-09-18:** MOBI is a legacy Amazon format — Amazon stopped accepting it for
Send to Kindle in 2022 and current Kindles use AZW3/KFX — and it is the most
expensive parser to write under ADR-3's dependency policy. Until then MOBI files
are skipped and reported (FEATURES H6), which is a fine answer. `FormatKind.MOBI`
stays in the enum so this needs no breaking change (ADR-2).

## Out of Scope
- Any document format that isn't an ebook: DOCX, TXT, RTF, CBZ/CBR, AZW.
  The format scope is EPUB and PDF, plus MOBI if Phase 4 ever happens, and
  nothing else (ADR-2). Adding a
  parser is deliberately easy (`FormatParser` is a suffix registry), which
  is exactly why the boundary is written down — bookman manages a *book*
  library, not a document pile. See FEATURES H13.
- Format conversion (EPUB↔MOBI↔PDF, etc.)
- Device transfer/sync
- News/RSS aggregation
- Author/Series-based directory nesting (library is flat by title — see ADR-1)

## Ideas (not yet scheduled)
- Humble Bundle candidate-title hints: given a bundle page URL, scrape the list of
  titles included in that bundle and use it as a non-authoritative hint set to bias
  fuzzy title matching during import of that batch. Deferred — needs its own
  scraping/parsing concern and Humble Bundle's page structure isn't a stable contract.
- Sibling-format attach within one bundle: a file whose siblings in the same source
  folder are already identified joins their book by source-path adjacency and
  filename stem, rather than by its own metadata. Aimed at MOBI as "the third format
  of a book we already matched" (so it needs no MOBI parser — see Phase 4), but it
  generalizes to any recognized-but-unparseable format. Notes: needs provenance
  (FEATURES I11, also wanted by F14/L6); it is a *grouping* rule, so it needs a new
  GROUP branch in `docs/IDENTIFICATION.md` and probably its own evidence basis;
  guard against merging a stray same-folder file of a different book (PR4); and any
  format-priority import ordering must stay an optimization, never something
  correctness depends on, or it breaks F16's order-independence invariant. Batch-level
  (`import_directory`), not a generic directory scan.
