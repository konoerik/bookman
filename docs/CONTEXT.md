# Context
<!-- Updated by /wrap at session end. Edit manually if needed. Keep it under 8 lines. -->

**Current focus:** Closing out v1.0 (FEATURES *v1.0 scope*). Green at 446 tests, ruff/mypy clean. No unblocked code work left — everything remaining is a decision: author-on-corroborated-match (IDENT-6), OQ3/C7 (editions), volumes related-or-not (I6).
**Last session:** Shipped the CLI commands for K1–K3 (`review`/`edit`/`reidentify`, N7 → ✅, ADR-20) and closed F14/OQ1 as ADR-21 — a same-kind file is refused with the evidence (book, existing file, join basis), never overwritten; `FormatConflictError` + `ImportBatchResult.conflicts`; spec_version 2. OQ1's "needs I11" blocker was wrong: the folder's own copy is what a byte comparison needs. K11 (replace a format) and K12 (import as separate book) recorded as the deferred resolutions.
**Blocking:** Three decisions — **file's author stands on a corroborated match** (OL work-level authors put an audiobook narrator on the book; seen live), **OQ3/C7**, **volumes** (I6). Backlog carries "decide what the CLI is for" — the user doubts they'd ever hand-edit via CLI. Carried over: CI's Windows leg still unlooked-at.
**Next action:** Decide **author-on-corroborated-match** (IDENT-6): spec change + ADR, then the one branch in `_accepted`. It's the only remaining decision with observed harm.
<!-- wrapped: 2026-09-18 -->
