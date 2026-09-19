# Context
<!-- Updated by /wrap at session end. Edit manually if needed. Keep it under 8 lines. -->

**Current focus:** **v1.0 is complete as scoped** (every FEATURES *v1.0 scope* row ✅). Green at 461 tests, ruff/mypy clean. What stands between here and a release: the Windows CI leg (known to fail — not yet looked at), `/prep`, `/release`.
**Last session (2026-09-19):** ADR-23 (editions are different books; marker lifted out before MATCH-0 strips it). ADR-24: CLI trimmed to import + inspect — `review`/`edit`/`reidentify` removed before they shipped, N7 parity rule dropped; curation is the TUI's or a hand edit of `metadata.json`. ADR-12 amendment: `scan()` refreshes the index, so `bookman list` is the reindex and a hand edit reaches `search`. M6 documented (README + `Library` docstring). ISBN-as-identity settled as no.
**Blocking:** Nothing. Volumes (I6) is post-1.0 unless the user wants to relate them; CI's Windows leg has errors the user has seen and I have not.
**Next action:** Look at the Windows CI failure (`gh run list` / `gh run view --log-failed`), then `/prep`.
<!-- wrapped: 2026-09-19 -->
