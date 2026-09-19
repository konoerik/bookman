# Context
<!-- Updated by /wrap at session end. Edit manually if needed. Keep it under 8 lines. -->

**Current focus:** Closing out v1.0 (FEATURES *v1.0 scope*). Green at 473 tests, ruff/mypy clean. No unblocked code work left; remaining decision: volumes related-or-not (I6). (ISBN-as-identity discussed 2026-09-19 and settled as no — see PLAN.)
**Last session (2026-09-19):** Decided OQ3 as ADR-23 (spec_version 4): a different edition is a different book. Found the accident was worse than recorded — bracketed/colon editions were *merging* with the first edition — and fixed it by lifting an ordinal edition marker out of the title before MATCH-0's stripping rules, appended as `edition N` so the volume-number rule keeps them apart. Spec rows 22–27, C7 ✅. Day before: ADR-22 (file's author wins on any match; `Book.record_author`; stand-in authors dropped; schema 4).
**Blocking:** Nothing with observed harm. Volumes (I6) is a decision; the CLI's purpose is a backlog question; CI's Windows leg still unlooked-at.
**Next action:** Either volumes (I6) as a decision, or call v1.0 and run `/prep`.
<!-- wrapped: 2026-09-19 -->
