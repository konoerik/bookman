# Context
<!-- Updated by /wrap at session end. Edit manually if needed. Keep it under 8 lines. -->

**Current focus:** Releasing v1.0. Committed `1727b62` (first real bundle: ADR-26/27/28, FIELD-NOTES). Uncommitted, awaiting the user's review: release workflow, version 1.0.0 + Production/Stable, CHANGELOG `[1.0.0] - 2026-09-20`, CONTRIBUTING.md, issue template, README install-from-Release, Makefile `check`/`build`. Three commits ahead of `origin/main`, nothing pushed — the user reviews before any push.
**Last session (2026-09-20):** Real bundle (37 No Starch/O'Reilly titles) imported in batches → four fixes (PDF ISBN scan 5→10 pages; placeholder title → stem; any-ISBN join + same-ISBN upgrade gate; EPUB embedded cover fallback); final run 37 books / 37 pairs / 37 covers / 0 failures. Then release plumbing: `release.yml` (tag-triggered, checks + `uv build` + clean-venv smoke + GitHub Release with wheel), wheel built and verified locally by importing a real pair from a clean venv.
**Blocking:** Nothing. Parked with data pending: OQ4 (PDF-first order), FN-7, FN-8 (MOBI), FN-10.
**Next action:** User reviews the uncommitted release plumbing → commit → push → `git tag v1.0.0 && git push origin v1.0.0` → confirm the Release has the wheel. Then more Humble Bundle imports into FIELD-NOTES; `docs/API.md` after that; `/prep`/`/release` checklists as gates.
<!-- wrapped: 2026-09-20 -->
