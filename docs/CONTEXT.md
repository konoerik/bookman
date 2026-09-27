# Context
<!-- Updated by /wrap at session end. Edit manually if needed. Keep it under 8 lines. -->

**Current focus:** Shipping the Calibre-run fixes (ADR-29..37) as 1.1.0 — new public API `ReadIssue`/`BookFormat.read_issue`, metadata.json schema v5, `bookman[crypto]` extra.
**Last session (2026-09-26):** Finished the Calibre run: 39 batches re-run via hard links, FN-11..18/20/21 fixed spec-first (ADR-29..37) — 0 failed imports, splits 23 → 12, review queue 76 → 46; `tools/calibre-oracle/` stays local (gitignored).
**Blocking:** Two spec decisions: OQ3 editions (8 of 12 remaining splits are one-side-only edition markers) and IDENT-4 divergence (code groups on the filename stem; spec says naming only).
**Next action:** `/release` 1.1.0, then decide OQ3 with the FIELD-NOTES data.
<!-- wrapped: 2026-09-26 -->
