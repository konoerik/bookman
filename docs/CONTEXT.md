# Context
<!-- Updated by /wrap at session end. Edit manually if needed. Keep it under 8 lines. -->

**Current focus:** Nothing in progress — the three silent-merge gaps from FEATURES Part I (C17/F15, B10, B6) are closed and the work is uncommitted on `main` (276 tests, ruff/mypy clean; `ruff format --check` fails on 4 pre-existing files, not from this work).
**Last session:** Closed C17/F15 (title fuzz requires matching number tokens), B10 (`_find_book` ISBN join runs `match_basis`), and B6 via ADR-14 (`ParsedMetadata.isbns_scraped`; a PDF-scraped ISBN needs title agreement, an EPUB `dc:identifier` keeps the either-agrees guard); CHANGELOG `[Unreleased]` and FEATURES rows updated.
**Blocking:** Nothing. Residual noted on FEATURES B6: a scraped ISBN unknown to OL (B7) has no provenance on `Book`, so grouping can't apply the stricter rule — needs I12. Still worth a glance: the first CI run's Windows leg.
**Next action:** Commit this work, then choose between the remaining Part I items (A12 junk-title stop-list, A10, D9; F14 needs a decision first) and the first Part II slice (I5 + K1 + K2 + L2/L10, which the TUI needs first).
<!-- wrapped: 2026-09-16 -->
