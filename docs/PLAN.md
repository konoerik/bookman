# Plan

## Active
<!-- Current sprint items. Keep this short — 5-10 items max.
     If it grows beyond that, move lower-priority items to Backlog. -->

Remaining v1.0 work (FEATURES *v1.0 scope*), in harm order:

1. **A10** — IDENT-1 says try each ISBN until one is accepted;
   `resolve.identify` tries only `isbns[0]`. The one open divergence
   between the spec and the code.
2. **D9** — "Martin Luther King Jr." yields surname `{'jr'}`.
3. **F14** — blocked on OQ1.
4. The five ❓ rows that pin the core promise: **A4, A8** (filename-stem
   fallback), **F5** (ISBN beats a title match), **F13** (re-import is
   idempotent), **F16** (order independence). Cheap tests, and F16
   matters more if format-priority import ordering is ever tried.
5. **CLI commands for K1–K3** — N7 dropped to 🔶 when the operations
   landed without them.

Decisions needed (they block behavior, not the list above):
- **OQ3 / C7** — is a different edition a different book?
- **OQ1 / F14** — two files of the same format kind for one book.
- Volumes: C17 keeps them apart. Should they also be *related* (I6
  series/volume), or is "separate and unmerged" the v1.0 answer?

## Backlog
<!-- Accepted but not yet active. Load this section only when planning or prioritizing. -->
- Matching follow-ups (from the live Gutenberg smoke run after ADR-9): author agreement is surname-only, so "Frank Herbert" vs "Brian Herbert" count as the same author (pinned in `test_match.py` as a known limitation); a title whose subtitle follows a period ("A CHRISTMAS CAROL IN PROSE. Being a Ghost Story...") isn't split, since ". " also appears inside titles ("Mr. Darcy..."); Open Library title search is sent the raw file title, so a long Gutenberg-style title only surfaces the cover-less Gutenberg-derived records — acceptable, but a second search on the normalized short title could find a cover.
- TUI/CLI needs a way to *set* `Book.reviewed` (and correct title/author) — the library has the field and honors it on import, but nothing writes it yet besides `save_metadata` directly.
- MOBI parser (`formats/mobi.py`): one module exposing a `FormatParser` plus a `register(".mobi", FormatKind.MOBI, parse_mobi)` in `formats/__init__.py` (R7 made this a drop-in). Two sample files still skipped — and staying skipped: deprioritized below v1.0 on 2026-09-18 (legacy Amazon format, most expensive parser under ADR-3; see ADR-2 Amendment and FEATURES L11).
- Feature map follow-ups (docs/FEATURES.md, 2026-09-15): remaining Part I gaps from its "Gap summary" — F14 same-kind format silently overwritten (needs a decision: reject / version / report — really I11 + L6), A10 only first ISBN tried, D9 "Jr." surnames. (C17, B6, B10 closed 2026-09-16; A12 junk titles and L2/L10 exports closed 2026-09-17.) Part II first slice: I5 stable id (R2), K1 set reviewed, K2 edit fields.
- Release hygiene leftovers: import copies the file before loading metadata (orphan on failed save); document single-writer assumption / lock file. (README, CHANGELOG, CI, LICENSE done 2026-09-16.)
- Known accepted risk: EPUB parsing uses stdlib `xml.etree.ElementTree` with no entity-expansion guard (billion-laughs). Fixing needs a new dependency (`defusedxml`), which conflicts with the pypdf-only dependency policy (ADR-3) — deliberately not fixed for now.
- `_sanitize_dirname` doesn't reject Windows-reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9) — irrelevant on macOS today, worth a note if Windows ever becomes a target.
- `Library` is not safe for concurrent `import_file` calls from multiple processes/threads against the same root (only the same-title new-folder race was closed; concurrent writes to an already-matched folder can still interleave) — should be documented explicitly as a single-writer assumption if not addressed.

## Done
<!-- Completed items land here temporarily.
     The stop hook archives these to .claude/archive/YYYY-MM.md and clears this section. -->
- Settled the identification-spec review by keeping both documents and inverting their relationship (ADR-16): `docs/IDENTIFICATION.md` is the source of truth, derived from the ADRs alone; `docs/FEATURES.md` Part I is the conformance report against it, with a `Step` column on all 86 Part I rows. Bound to the code by `bookman.identify.SPEC_VERSION`, a `Spec:` line on every implementing function, step IDs in the log lines, and `tests/test_spec_conformance.py` — which enforces the step trace and executes the spec's new 20-row decision table against `match_basis`.
- Drew the v1.0 line in FEATURES, wrote the format boundary down (H13, ROADMAP *Out of Scope*), and moved C7 (are editions different books) out of the spec's normative text into `open_questions` as OQ3, since FEATURES marked it unconfirmed.
- Deprioritized MOBI below v1.0 (ADR-2 Amendment): a legacy Amazon format, the most expensive parser under ADR-3, and unparsed files already degrade gracefully (H6). ROADMAP Phase 2 became curation and MOBI became Phase 4; the PyPI description that claimed MOBI support was corrected.
- Ran the first conformance audit: all 14 steps claimed by code and pinned by a ✅ row, and **no unregistered divergence** — A10, D6 and the B6 residual all already had rows. Confirmed two assumptions (GROUP-2's tie-break is deterministic; IDENT-5 prefers a stronger basis over a cover).
- I5 stable book identity (ADR-17): `Book.id`, a uuid4 hex minted at construction and stored in metadata.json schema v3, surviving the folder rename K2 performs. A pre-v3 book gets a deterministic folder-derived id rather than a fresh one per read, so identity is stable before the first save. `Book.directory` stays, demoted to where-it-lives and display name.
- K1–K3 curation (ADR-18): `Library.mark_reviewed`, `Library.edit`, `Library.reidentify`. Settled K2's open question — an edit **sets `reviewed`**, because `_apply_identification` would otherwise silently overwrite the correction on the next format import. A title edit renames inner files → metadata → folder, so an interruption leaves a loadable book under a stale name (verified in-session). `reidentify` always runs; on a reviewed book it fills only a missing cover and empty fields, the E12 route.
- Initialized git repo and applied claudify python-lib blueprint
- Brainstormed architecture: flat title-named managed library, EPUB+PDF-first format scope, pypdf-only dependency policy, auto-lookup-with-review identify workflow (ADR-1..4)
- Scaffolded project with `uv init --lib`; added `pypdf` runtime dep, pytest/ruff/mypy dev deps
- Wrote `models.py` (Book, BookFormat, FormatKind, MatchConfidence) and `formats/__init__.py` (ParsedMetadata, FormatParser protocol)
- Wrote stubs for `formats/epub.py:parse_epub` and `identify/isbn.py` (is_valid_isbn, normalize_isbn, extract_isbns); reviewed and approved
- Implemented + tested `identify/isbn.py` (12 tests) and `formats/epub.py:parse_epub` (8 tests) — all passing, ruff/mypy clean, 94% coverage
- Implemented + tested `formats/pdf.py:parse_pdf` (8 tests) and `storage/catalog.py` (8 tests) — 36 tests total, ruff/mypy clean, 96% coverage
- Wrote stubs for `identify/openlibrary.py` (lookup_by_isbn, fetch_cover) and `storage/index.py` (rebuild_index, search); reviewed and approved
- Implemented + tested `identify/openlibrary.py` (6 tests, no real network calls) and `storage/index.py` (7 tests) — 49 tests total, ruff/mypy clean, 96% coverage
- Wrote stub for `library.py` (Library class: __init__, import_file, scan, search); reviewed and approved
- Implemented + tested `library.py` (16 tests, including two added beyond the reviewed list to cover documented Open Library failure fallback) — 65 tests total, ruff/mypy clean, 96% coverage. `Library` now exported from `bookman/__init__.py` as the package's main entry point.
- Revamped the CLI for first-time users (full help on missing args, examples epilog, dashed-rule headers, clear errors for missing/unsupported files, `list`/`search` no longer silently create a typo'd library dir) and added the public `bookman.config` module + `bookman init`/`bookman config` so the library location is set once and shared by CLI and future TUI (ADR-8). 129 tests, ruff/mypy clean.
- Ran a fresh-context critique agent over the whole codebase; fixed the 6 blocking bugs it found: title not updated on verified merge, ISBN-matched books wrongly downgraded on transient lookup failure, corrupt metadata.json crashing scan/search/import for the whole library, path traversal via a crafted metadata.json (validated on load, matching the existing save-side check), a TOCTOU race on new-folder creation (now atomic via mkdir(exist_ok=False) + retry), and non-atomic metadata.json writes (now via temp file + os.replace). 70 tests total, ruff/mypy clean, 97% coverage. Design-level findings (matching threshold, confidence semantics, dead Protocol, exception export mismatch, XML-bomb risk) recorded in Backlog for a separate discussion, not acted on.
- File's title wins over Open Library's on an accepted match; format files named `<folder name>.<ext>` instead of `book.<ext>`; colon sanitizes to " -"; equal-strength follow-up formats keep the first title (ADR-10). Found by the first real-bundle run.
- Investigated the missing cover on "Algorithmic Thinking, 2nd Edition" (2026-09-15): an Open Library data gap, not a code path. The Books API has no record for the file's ebook ISBN, the 2nd-edition search doc has no `cover_i`, and the covers endpoint 404s for the ebook ISBN, the paperback ISBN, and the edition OLID. The only cover OL holds is the 1st edition's, which `match_basis` correctly treats as a different book, so it is deliberately not used. No code change; a covers-by-ISBN fallback was considered and skipped for lack of a case where it would hit. Adding other metadata sources besides Open Library (e.g. Google Books) is the future fix for this scenario, alongside a user-supplied cover via the pending set-metadata/`reviewed` work.
- Feature map (docs/FEATURES.md: Part I retrieval-accuracy scenario matrix with test pointers and verified gaps; Part II organization/operations capabilities) and code-health assessment (docs/HEALTH.md).
- Pre-Part-II refactor R1–R7, one commit each (2026-09-15): `import_file` split into `_apply_identification`/`_place_format`/`_persist` with an ADR-9 discrepancy fixed (reviewed metadata survives a title-only join); `Book.directory` identity (ADR-11); `storage.store.Catalog` persistence boundary with a name-keyed, per-write-updated index (ADR-12); `MetadataSource` Protocol injected into `Library` with `OpenLibrarySource`/`NullSource`, `FakeSource` in tests replacing 51 monkeypatch strings (ADR-13, v0.3.0); `bookman.errors` hierarchy under `BookmanError`; logging at every swallow point; `FormatParser` as a real suffix registry with public `supported_suffixes`. 214 → 263 tests, ruff/mypy clean.
- Closed the three silent-merge gaps from FEATURES Part I (2026-09-16): C17/F15 multi-volume merge (title fuzz requires matching number tokens, digits or roman numerals), B10 (`_find_book` ISBN join runs `match_basis(same_isbn=True)`), B6 (ADR-14: `ParsedMetadata.isbns_scraped`, a PDF-scraped ISBN needs title agreement). 263 → 276 tests, ruff/mypy clean.
- Prepared for GitHub (2026-09-16): README, MIT LICENSE, CHANGELOG, CI workflow (ruff/mypy/pytest on 3.10–3.14 + macOS/Windows), packaging metadata; git history reset to a single initial commit and the version renumbered to 0.1.0 for the first public release (ADR text still cites the pre-reset 0.1→0.3 bumps as history). docs/HEALTH.md deleted — it was transient scaffolding for the refactor.
