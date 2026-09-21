# Context
<!-- Updated by /wrap at session end. Edit manually if needed. Keep it under 8 lines. -->

**Current focus:** v1.0.0 is released (2026-09-20; GitHub Release carries the wheel, verified installable from its URL). The tag was moved once, minutes after the first run, onto the housekeeping commit — CHANGELOG folds 0.1.0 into 1.0.0 (the `v0.1.0` tag was deleted; it never had a Release), release workflow uploads only `*.whl`/`*.tar.gz` — so the first release is clean.
**Last session (2026-09-20):** Real bundle → four fixes + ADR-26/27/28 + FIELD-NOTES (`1727b62`); release plumbing (`f000373`); CI green; tagged and released. Stray `default.gitignore` asset on the 1.0.0 Release — user deletes it in the Release UI.
**Blocking:** Nothing. Parked with data pending: OQ4 (PDF-first order), FN-7, FN-8 (MOBI), FN-10.
**Next action:** The TUI can `uv add "bookman @ https://github.com/konoerik/bookman/releases/download/v1.0.0/bookman-1.0.0-py3-none-any.whl"`. Next bookman work: more Humble Bundle imports into FIELD-NOTES, then `docs/API.md` (frontend guide + `__all__`-coverage test); any API change from either is a 1.x minor bump.
<!-- wrapped: 2026-09-20 -->
