# Context
<!-- Updated by /wrap at session end. Edit manually if needed. Keep it under 8 lines. -->

**Current focus:** Closing FEATURES gaps. L2/L10 (public-surface exports) and A12 (junk titles) are done and uncommitted on `main` — 320 tests, ruff/mypy clean; `ruff format --check` still fails on the same 4 pre-existing files, none of them newly touched.
**Last session:** Exported `ImportBatchResult` from `bookman` (L2; L10 turned out to be already done — all nine error types were exported, FEATURES was stale) with a new `tests/test_public_api.py` pinning `__all__`; closed A12 in two tiers and recorded it as **ADR-15** (placeholder title → `normalize_title` returns ""; generic title survives but is barred from TITLE_ONLY, so Alan Watts' "The Book" still identifies via TITLE_AUTHOR). CHANGELOG `[Unreleased]`, FEATURES A12/L2/L10/N2 + gap summary, and PLAN Backlog updated.
**Blocking:** Nothing. Residual noted on FEATURES B6: a scraped ISBN unknown to OL (B7) has no provenance on `Book`, so grouping can't apply the stricter rule — needs I12. Still worth a glance: the first CI run's Windows leg.
**Next action:** Commit this work (nothing is committed yet), then pick up the remaining Part I items (F14 needs a decision first — it is really I11 + L6; then A10, D9) or the Part II slice the TUI needs: I5 stable id → K1 set reviewed → K2 edit fields.
<!-- wrapped: 2026-09-16 -->
