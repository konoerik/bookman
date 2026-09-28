# Plan

## Active
<!-- Current sprint items. Keep this short — 5-10 items max.
     If it grows beyond that, move lower-priority items to Backlog. -->

v1.1.0 is released. Post-1.1 work, in this order:

TUI requests (inbox triage 2026-09-27) come first, then the items after them.

- **`Book.added` + `ReadIssue.summary`**: an `added` timestamp set once
  when a book is created, None for older books (FEATURES I11, J5).
  Share the metadata.json v6 bump with the content hash below. A short,
  sentence-cased `summary` beside `advice`, which stays the full next
  step and stays lowercase for the CLI.
- **Already-in-library check** (spec + ADR first: changes GROUP-4/F13
  re-import). A content hash per format in metadata.json and the index,
  `Library.find_file(path)` plus a batch form (offline, cheap enough for
  an import preview of a few hundred files), checked before the parse
  and lookup, and a new "already in library" outcome
  (`ImportBatchResult.unchanged`). Covers most of the Backlog cache item.
- **Persist the lookup outcome** (spec first: IDENT outcome recording,
  E9). Identified / no match / lookup failed / not attempted (offline)
  on `Book`, so a frontend can warn and retry exactly the failed ones.
  A filter for it belongs in the query layer.
- **Replace a wrong cover** (curation ADR; FEATURES K4):
  `reidentify(book, replace_cover=True)` that leaves human-set fields
  alone, and `set_cover(book, path | None)` for a local image or
  removal. Today the only route (un-review, reidentify, re-review) can
  overwrite an author the user just corrected.

- **Decide OQ3 editions against the Calibre data** — 8 of the 12
  remaining splits have an edition marker on one side only (C7's accepted
  cost under ADR-23). Use the FIELD-NOTES Calibre table to decide whether
  a one-sided marker should keep blocking a join. Spec + ADR if it
  changes, then FEATURES C7.
- **Resolve the IDENT-4 stem-grouping divergence** — the code groups on
  the filename stem; the spec says the stem is for naming only. Decide
  which one is wrong (FN-6: stems drift; FN-8: stem adoption set aside),
  then fix the spec or the code to match.
- **Manual grouping overrides** — for files the user knows belong
  together (or apart) when identification can't prove it. At import:
  force-group a file into a named existing book, and force-add a file as a
  new book that skips grouping (K12). After import: merge two books (K6)
  and split a format out (K7). Grouping behavior, so the spec comes first:
  an IDENTIFICATION.md step and ADR for a user-asserted group basis
  (`grouped=manual`?), and a decision on whether it sets `reviewed` and
  survives `reidentify`. Same-kind collisions are refused, as F14 does.
  API only, no CLI (ADR-24).
- **Query commands** — a query layer on the sqlite index with a fallback
  that walks the `metadata.json` files when the index is missing,
  unreadable or stale (`index.is_current`), so both paths return the same
  answer. Candidates from Part J: get by id (J3), filters for needs-review,
  format, basis and cover (J4), field-scoped `author:`/`isbn:` (J6), and
  counts (J7). Index columns grow to carry the filter fields (schema
  bump). API only, no CLI.

## Backlog
<!-- Accepted but not yet active. Load this section only when planning or prioritizing. -->
- Open Library signals worth using (surveyed 2026-09-18 against the *Why We Can't Wait* work, 29 editions): (a) `search.json?q=isbn:X&fields=editions,editions.cover_i,editions.format,editions.publisher` returns the work **plus the one edition carrying X** in the same single request — the owned edition's cover instead of the work's default, and `format`/`publisher` for free; parsing change only. (b) Work `key` + work-level `isbn[]` (every edition's ISBN): an EPUB with ISBN X and a PDF with ISBN Y are provably the same work — stronger than today's `title_author` join, and a stable identity beyond one ISBN; needs a `work_id` on `Book` and a new GROUP evidence kind (spec + ADR). (c) `language` on candidates vs EPUB `dc:language` as a MATCH veto (spec + ADR). (d) `format` in IDENT-5 ranking: `audio cd` below anything for an EPUB/PDF file (spec + ADR). (e) `author_key` is author *identity* — the real fix for D6 — but only on the OL side; needs a name→key step. (f) `edition_count`/`readinglog_count` as an explicit tie-break among equal-basis candidates ("Summary of Deep Work" vs *Deep Work*) — spec says relevance doesn't decide, so ADR. Not usable: no role field anywhere (narrator vs author is indistinguishable; `by_statement`/`contributions` are free text); `physical_format` is free-text and missing on 20/29 editions; `contributor`/`person` are noise. Edition-true authors exist only via `/isbn/…json` → `/works/…json` → `/authors/…json`.
- Source registry for N8, once a second source exists: enumerate the known sources with display name, description and whether each needs the network; per-source settings (enabled, order, credentials/options, N4) read and written through the shared config, so the TUI renders a Settings screen generically. The TUI asked for this shape on 2026-09-26; deferred because with only Open Library there is nothing to design against. Builds on `configured_library` (ADR-38). Also: record which source supplied each book's record (`Book` field + a name on `MetadataSource`). Deferred from ADR-38 because `identified is not None` means "Open Library" until a second source exists, so older books can be backfilled then.
- Author sort key (TUI request 2026-09-27): a public `author_sort_key(author)` giving the primary author as "Surname, Given", stable across "Last, First" and "First Last", with a small particle list (le, de, van, von…) so "Le Guin" sorts under L. The TUI sorts by the stored string until then. Needs a decision on how far name parsing goes; an editable override (Calibre's "author sort") is later still.
- Delete a book (FEATURES K9): once it exists, `ReadIssue.advice` should name it instead of "delete this book's folder".
- Cache at the `MetadataSource` seam (ADR-13): `import_file` runs `identify` (network) *before* `_find_book` (catalog), by design — GROUP-4 needs the follow-up format's own identification to decide upgrade/no-downgrade (F7/F8). So the PDF of an already-shelved EPUB does the full Open Library round-trip again. Fix is a memoizing wrapper source, not a reorder: per import batch at minimum, or persisted in the library so a re-imported ISBN never hits the network. No spec change. (Raised 2026-09-18.)
- Matching follow-ups (from the live Gutenberg smoke run after ADR-9): author agreement is surname-only, so "Frank Herbert" vs "Brian Herbert" count as the same author (pinned in `test_match.py` as a known limitation); a title whose subtitle follows a period ("A CHRISTMAS CAROL IN PROSE. Being a Ghost Story...") isn't split, since ". " also appears inside titles ("Mr. Darcy..."); Open Library title search is sent the raw file title, so a long Gutenberg-style title only surfaces the cover-less Gutenberg-derived records — acceptable, but a second search on the normalized short title could find a cover.
- MOBI parser (`formats/mobi.py`): one module exposing a `FormatParser` plus a `register(".mobi", FormatKind.MOBI, parse_mobi)` in `formats/__init__.py` (R7 made this a drop-in). Two sample files still skipped — and staying skipped: deprioritized below v1.0 on 2026-09-18 (legacy Amazon format, most expensive parser under ADR-3; see ADR-2 Amendment and FEATURES L11).
- Feature map follow-ups (docs/FEATURES.md, 2026-09-15): remaining Part I gaps from its "Gap summary" — none; F14 closed 2026-09-18 (ADR-21), A10 and D9 the same day. (C17, B6, B10 closed 2026-09-16; A12 junk titles and L2/L10 exports closed 2026-09-17.) Part II first slice: I5 stable id (R2), K1 set reviewed, K2 edit fields.
- Release hygiene leftovers: import copies the file before loading metadata (orphan on failed save). (README, CHANGELOG, CI, LICENSE done 2026-09-16; single-writer assumption documented 2026-09-19, M6.)
- Known accepted risk: EPUB parsing uses stdlib `xml.etree.ElementTree` with no entity-expansion guard (billion-laughs). Fixing needs a new dependency (`defusedxml`), which conflicts with the pypdf-only dependency policy (ADR-3) — deliberately not fixed for now.
- `_sanitize_dirname` doesn't reject Windows-reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9) — irrelevant on macOS today, worth a note if Windows ever becomes a target.
- A lock file to *enforce* the single-writer assumption (documented 2026-09-19, M6) — post-1.0, if two frontends against one library ever becomes a real use.

## Done
<!-- Completed items land here temporarily.
     The stop hook archives these to .claude/archive/YYYY-MM.md and clears this section. -->
- **Library marker, open-without-create, root origin** (2026-09-27, TUI SETUP-5/START-5): `.bookman-library.json` + `is_library`, `configured_library(create=False)` raising `LibraryNotFoundError`, `locate_library`/`LibraryLocation`/`LibraryOrigin` (ADR-39). CLI list/search/import refuse a missing or non-library root. 593 tests.
- **Frontend guide `docs/API.md`** (2026-09-27): open → settings → import with progress → catalog → `Book` fields → curate → errors → plug in a source, citing `cli.py`; `test_public_api` fails if an `__all__` name is missing from it. README points to it.
- **Config-driven source selection** (2026-09-27, TUI request): `Config.offline` + public `configured_library(explicit=None)` (ADR-38); CLI import/config/init use it. Source registry and per-book source provenance deferred to Backlog under N8. 573 tests.
- **v1.1.0 released** (2026-09-26): https://github.com/konoerik/bookman/releases/tag/v1.1.0 — ADR-29..37 from the Calibre run; minor for `ReadIssue`/`BookFormat.read_issue` and metadata.json schema v5; `bookman[crypto]` extra. Wheel smoke-tested locally with the extra (read a real AES PDF); Release and CI workflows green.
- **Calibre-library run, second half** (2026-09-26): all 39 batches run fresh three times via hard links (`tools/calibre-oracle/linked.py`, local only, gitignored). FN-11..18 plus new FN-20/21 fixed spec-first as ADR-29..37: unreadable PDFs import with `ReadIssue` (schema v5) and the `bookman[crypto]` extra (PyCryptodome); fuzz within a word; volume markers; layout-filename titles; EPUB front-matter ISBN scan; full-form title agreement; atomic copy + cleanup; folder rename on title upgrade; tag-free search with title-only retry. 456/19 → 477/0 imported/failed, 23 → 12 splits, 76 → 46 needs review, 0 wrong merges. spec_version 6, 557 tests.
- **v1.0.0 released** (2026-09-20): https://github.com/konoerik/bookman/releases/tag/v1.0.0 — wheel + sdist, installed from the Release URL into a clean venv. `v0.1.0` tag deleted (never had a Release) so 1.0.0 is the first; tag moved once onto the housekeeping commit `3c22a50` (CHANGELOG folds 0.1.0 into 1.0.0; asset glob `*.whl`/`*.tar.gz` only); stray `default.gitignore` asset removed by hand. Tag moves are classified destructive in auto mode — the user runs them.
- Release plumbing (2026-09-20): `.github/workflows/release.yml` on `v*` tags — checks, `uv build`, tag-matches-version guard, clean-venv smoke test, GitHub Release with sdist + wheel; version 1.0.0, classifier Production/Stable, CHANGELOG `[1.0.0]`; `CONTRIBUTING.md` (uv-only, spec-first rule, bug reports as shapes); issue template for wrong match / missed grouping / missing cover; README install via Release wheel; Makefile `check`/`build`. Wheel built and smoke-tested locally.
- First real bundle (2026-09-20): 37 No Starch/O'Reilly titles, 92 files, imported in four batches then whole. Four fixes — PDF ISBN scan 5 → 10 pages (B8), placeholder title → stem (A12), any-ISBN join + same-ISBN upgrade gate (ADR-26/27, F17/F18), EPUB embedded cover fallback (ADR-28, E15). Went from 7 split pairs and 16 covers to 0 and 37. `docs/FIELD-NOTES.md` started (FN-1..10). 485 tests.
- Import progress (2026-09-20, ADR-25): `Library.iter_import` yields an `ImportEvent` before and after each file; `import_directory` collects them via `ImportBatchResult.record`; stopping the iteration cancels. CLI prints `[i/n] name ... imported: …` per file. FEATURES L3/L4 ✅. 467 tests. Surfaced that `__init__.py` is a namespace, not a guide — `docs/API.md` added to Active.
- Ruff format enforced (2026-09-20): five drifted files reformatted; `ruff format --check` added to CI and the CLAUDE.md workflow, which had only run `ruff check`.
- Volumes (2026-09-20): "separate and unmerged" is the v1.0 answer (C17/F15); relating them is I6, post-1.0. One sentence on the I6 row, no ADR — no behavior changed.
- Windows CI fix (2026-09-20): the config test fixture faked the home dir with HOME only; Windows reads USERPROFILE. Pushed as `21aefe5`; the full matrix went green, including the ~200 tests that had never run on Windows.
- ISBN-as-identity (2026-09-19): discussed and settled as no — not every book has one, one book can have several, it can be wrong, unreadable as a folder name. ADR-1 + ADR-17 already give the identifier. No code.
- OQ3 / C7 (2026-09-19, ADR-23): a different edition is a different book. The accident was worse than recorded — bracketed/colon editions were merging; an ordinal edition marker is now lifted out before MATCH-0's stripping rules and compared like a volume number. Spec rows 22–27, spec_version 4.
- IDENT-6 author rule (2026-09-18, ADR-22): the file's author stands on any accepted match; `Book.record_author` keeps the record's (schema 4); stand-in authors ("Unknown", "N/A") dropped, "Anonymous"/"Various" kept. FEATURES D13/D14.
- M6 documented (2026-09-19): single-writer assumption in the README and the `Library` docstring; no lock file for v1.0. The last open v1.0 scope row — **v1.0 is complete as scoped.**
- Index self-heals on scan (2026-09-19, ADR-12 amendment): `Library.scan()` refreshes the search index from what it read, closing the hole ADR-24 opened (a hand-edited `metadata.json` reached `list` but not `search`). M1 ✅. `bookman list` is the reindex command.
- CLI trimmed to import + inspect (2026-09-19, ADR-24): `review`/`edit`/`reidentify` removed before they ever shipped; the N7 parity rule dropped — a new `Library` operation does not get a subcommand. Curation is the TUI's, or a hand edit of `metadata.json`. 473 → 458 tests.
- ADR-22 and ADR-23 (2026-09-18/19): file's author wins on any match with `Book.record_author` kept (schema 4); a different edition is a different book, marker lifted out before MATCH-0 strips it (spec_version 4). ISBN-as-identity discussed and settled as no.
- F14 / OQ1 (2026-09-18, ADR-21): a same-kind file is **refused**, never overwritten; `FormatConflictError` carries book, existing file, join basis and the incoming identification; `ImportBatchResult.conflicts`. The OQ1 blocker (needs I11) was wrong — the folder's copy is what a byte comparison needs. spec_version 2. K11 (replace) and K12 (import as separate book) recorded as the deferred resolutions. 446 tests.
- CLI commands for K1–K3 (2026-09-18, ADR-20): `review [--undo]`, `edit --title/--author/--no-author/--isbn/--no-isbn`, `reidentify`; BOOK resolves as folder name → id → exact title, shared titles refused. N7 back to ✅. 437 tests. Immediately questioned whether hand-editing via CLI is worth keeping — see Backlog.
- A10 (2026-09-18): `resolve.identify` walks every ISBN in turn (IDENT-1) — a rejected one is dropped, the first unknown one kept, the first accepted one wins. The one open spec divergence, closed; seen live with a three-ISBN EPUB.
- ISBN lookup migrated (2026-09-18): Open Library's `/api/books` returns 404 on every bibkey (their docs' own example included, any User-Agent), so `lookup_by_isbn` now goes through `search.json?isbn=` — one request, same doc shape as title search. Requests carry a `bookman/<version>` User-Agent. Cost noted: author names on an ISBN hit are now work-level.
- ADR-19 (2026-09-18): an asserted ISBN is rejected when the titles disagree and the author does not vouch (disagrees or is absent). Found live: a junk OL record with no author was accepted for "Deep Work" with `needs_review=False`. Spec MATCH-1 amended, decision-table row 21, FEATURES B11. The narrower rule was chosen over the symmetric one so row 9 (generic titles, disagreeing authors) doesn't move.
- D9 (2026-09-18): generational suffixes (Jr/Sr/II/III/IV, with or without a comma) dropped before the surname is taken; "King, Martin Luther, Jr." no longer reads as three people. Seen live: *Why We Can't Wait* identified `title_author` with cover.
- The five ❓ rows pinned (2026-09-18): A4/A8 stem fallback with no source call, F5 ISBN join beats a title/author join (asserted ISBN; a scraped one would lose per ADR-14 — recorded on the row), F13 re-import idempotent, F16 order independence. The code was right in all five. 402 → 421 tests.
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
