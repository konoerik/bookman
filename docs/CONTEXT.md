# Context
<!-- Updated by /wrap at session end. Edit manually if needed. Keep it under 8 lines. -->

**Current focus:** Releasing v1.0. Scope is complete (every FEATURES *v1.0 scope* row ✅); 461 tests, ruff/mypy clean. Four commits pushed 2026-09-20 (`ed0044f`..`21aefe5`) — CI is running the full matrix on them, Windows result not yet seen.
**Last session (2026-09-18 → 20):** ADR-25 (batch import streams `ImportEvent`s via `Library.iter_import`; CLI shows per-file progress) recorded after the first real bundle import sat silent for minutes; volumes closed on the I6 row; CI green on `21aefe5`. Earlier: ADR-22 (file's author wins, `record_author` kept), ADR-23 (editions are different books), ADR-24 (CLI trimmed to import + inspect), ADR-12 amendment (`scan()` refreshes the index), M6 documented, ISBN-as-identity settled as no, and the Windows CI failure fixed (`USERPROFILE` in the config test fixture — verified by reasoning only, no Windows here).
**Blocking:** The Windows CI result. The fixed log was from a 263-test run; ~200 newer tests (folder rename, `os.replace` on the sqlite index) have never run on Windows and may fail a second round. The user has no `gh`; they paste logs from the Actions tab.
**Next action:** Check the Actions run for `21aefe5`. Green → `/prep`, then `/release`. Red → fix the Windows leg from the pasted log.
<!-- wrapped: 2026-09-20 -->
