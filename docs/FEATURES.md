# Feature map

The library is two halves, tracked here as two parts:

- **Part I — Retrieval accuracy.** The conformance report against
  `docs/IDENTIFICATION.md`: the space of book files an import can
  encounter, the spec step each one exercises, and whether the code
  does what the spec says. Rows are scenarios; status says whether a
  test pins the behavior.
- **Part II — Organization and operations.** What a frontend (the TUI,
  the CLI, any embedder) needs from the library: the catalog schema and
  the operations over it. Rows are capabilities; status says whether the
  public API provides them.

Neither part is a plan. Add a row before fixing a new failure or adding
a capability; flip its status when it lands. Sequencing lives in
PLAN.md; the v1.0 boundary is below.

---

# v1.0 scope

bookman v1.0 delivers **one workflow**: point it at a folder of
purchased ebook files, have each identified, have the formats of one
book grouped into one folder, have volumes and editions kept apart, and
let a human fix whatever the automation got wrong. Everything that is
not that is post-1.0, however cheap it looks.

**In scope**

| Area | Rows | Why it's in |
|---|---|---|
| ~~Silent-merge and mislabel gaps~~ | ~~F14, A10, D9~~ | ✅ All closed 2026-09-18 — F14 by ADR-21 (refuse, never overwrite). Nothing on the import path loses data quietly any more |
| ~~The core promise, pinned~~ | ~~F13, F16, A4, A8, F5~~ | ✅ Done 2026-09-18 — all five pinned in `test_library`; the code was as believed |
| ~~Book identity~~ | ~~I5~~ | ✅ Done 2026-09-18 (ADR-17). Everything in K keys off it |
| ~~The manual fallback~~ | ~~K1, K2, K3~~ | ✅ Done 2026-09-18 (ADR-18), CLI commands the same day (ADR-20) |
| Single-writer assumption | M6 | Documentation only; the honest statement of a real limitation |
| ~~Open decisions~~ | ~~OQ3 (C7)~~ | ✅ OQ1 decided 2026-09-18 (ADR-21); OQ3 decided 2026-09-19 (ADR-23): a different edition is a different book |

**Out of scope for v1.0** — everything else in Parts I and II. The
notable ones, so they aren't mistaken for oversights: richer catalog
fields (I6–I12, I14), query and filtering beyond `scan`/`search`
(J3–J10), curation beyond fix-a-wrong-book (K4–K10), import ergonomics
(L3–L9), maintenance tooling (M1–M5, M7), a second metadata source
(N8), and **MOBI parsing (L11)** — see its row for why. Unparsed MOBI
files are already skipped and reported rather than failing a batch
(H6), which is an acceptable v1.0 answer. The bottom-tier Part I rows — C10, C12, H11, A15, A16, D11 — are
each *a cover we don't fetch*, never a wrong merge, and stay out.

*This line is a draft: move a row across it deliberately, not by
picking it up mid-task.*

---

# Part I — Retrieval accuracy

Pipeline stages, for orientation (see `Library.import_file` docstring):
**Parse** (formats/) → **Identify** (identify/resolve.py, match.py) →
**Group** (`Library._find_book`) → **Place** (folder/file naming,
metadata.json).

`docs/IDENTIFICATION.md` is the **source of truth** for what these rows
*should* do; this table is the conformance report against it. The
**Step** column names the spec step each scenario exercises
(MATCH-0..3, IDENT-1..6, GROUP-1..4), so a rule can be traced both
ways. Rows marked `— (parse)` sit at the Parse boundary, outside the
spec's scope.

This table tracks what is *pinned by a test*; the spec states what the
behavior *should be*. **When they disagree, the code is what needs
explaining** — and the ❌/⚠️ rows below are exactly that register of
disagreement. Change the spec first, with an ADR; then the code; then
the row.

## Conformance audit

Last walked **2026-09-18** against `docs/IDENTIFICATION.md` spec_version 1,
step by step, mapping each to its implementation and its pinning row.
`tests/test_spec_conformance.py` now enforces that mapping: all 14 steps are
claimed by code in `src/` and cited by a ✅ row here, and all 20 rows of the
spec's decision table pass against `match_basis`.

The audit found **no unregistered divergence** — every gap between spec and
code already had a row:

| Divergence | Step | Row | State |
|---|---|---|---|
| ~~Only the first ISBN is looked up; the spec says try each in turn~~ | IDENT-1 | A10 | ✅ closed 2026-09-18: `resolve.identify` loops over `parsed.isbns` |
| Authors "agree" on a shared *surname*; the spec says a shared *person* | MATCH-2 | D6 | ⚠️ accepted limitation |
| GROUP-1 can't apply the stricter scraped-ISBN rule IDENT-3 applies | GROUP-1 | B6 residual | ⚠️ accepted, blocked on I12 (spec OQ2) |

Two things confirmed *as specified*, which had been assumptions: GROUP-2's
tie-break really is deterministic (`Catalog.all()` returns folder-name
order), and IDENT-5's ranking really does prefer a stronger basis over a
weaker one with a cover.

## Status legend

| Mark | Meaning |
|---|---|
| ✅ tested | A unit test pins the behavior. |
| 🟢 live | Verified against real files / live Open Library (Gutenberg fixtures, the first Humble bundle), but not a regression test. |
| ⚠️ known | Deliberate or accepted limitation; documented in an ADR or PLAN Backlog. |
| ❌ gap | Wrong or undefined behavior, no test. Verified in-session where a value is shown. |
| ❓ unverified | Code path exists and is believed correct; nothing pins it. |
| 🚫 out of scope | Excluded by an ADR / ROADMAP; listed so it isn't re-proposed. |

The *Expected* column states the outcome in terms of the `Book` fields
(`identified`, `grouped`, `needs_review`) or the `match_basis` result.

## A. Embedded metadata completeness

What the file says about itself: title (T), author (A), ISBN (I).

| ID | Step | Scenario | Expected | Status | Pinned by |
|---|---|---|---|---|---|
| A1 | IDENT-1..3 | T + A + I, all correct | ISBN lookup accepted → `identified=isbn`, cover | ✅ | `test_resolve::accepts_isbn_hit_that_agrees_on_title`, `test_library::sets_identified_on_agreeing_isbn_lookup` |
| A2 | IDENT-4,5 | T + A, no I | Title/author search → `identified=title_author` | ✅ 🟢 | `test_resolve::searches_by_title_and_author_without_isbn`; live: Alice (Gutenberg) |
| A3 | IDENT-4,5; MATCH-3 | T only | Search; accept only an *identical* normalized title → `identified=title_only`, `needs_review` | ✅ 🟢 | `test_resolve::search_without_file_author_requires_identical_title`; live: Lazarillo |
| A4 | IDENT-4 | A only (no T, no I) | No lookup; title falls back to the filename stem; `identified=None` | ✅ | `test_resolve::does_nothing_without_title_or_isbn`, `test_library::falls_back_to_filename_stem_when_file_has_only_an_author` (no source call, stem names the folder) |
| A5 | IDENT-2,3; MATCH-1 | I only | ISBN lookup; record supplies title and author → `identified=isbn` | ✅ | `test_resolve::uses_record_title_only_when_file_has_none`, `test_match::same_isbn_with_missing_fields_is_isbn` |
| A6 | IDENT-3,6 | T + I, no A | ISBN lookup; record fills the missing author | ✅ | `test_resolve::accepts_isbn_hit_that_agrees_on_title` (file has `author=None`) |
| A7 | IDENT-6; MATCH-1 | A + I, no T | ISBN lookup; record supplies title | ✅ | same as A5 |
| A8 | IDENT-4 | Nothing (no T, A, I) | Folder named after filename stem, `needs_review` | ✅ | `test_library::with_no_metadata_at_all_is_shelved_under_its_stem_for_review` |
| A9 | MATCH-2 | Placeholder author ("Anonymous", "Unknown", "Various") | Treated as no author → A3 path | ✅ 🟢 | `test_match::author_surnames_ignores_placeholders`; live: Lazarillo keeps "Anonymous". Whether the string is *kept* on the book is D14 |
| A10 | IDENT-1 | Several ISBNs in one file (print + ebook, or a cited list) | Try each until one agrees; a rejected one is dropped, the first unknown one is kept | ✅ | `test_resolve::tries_the_next_isbn_when_the_first_is_unknown`, `..._when_the_first_is_rejected`, `stops_at_the_first_accepted_isbn`, `keeps_the_first_unknown_isbn_when_none_is_accepted`, `drops_a_rejected_isbn_but_keeps_an_unknown_one`, `keeps_no_isbn_when_every_one_is_rejected`, `moves_on_to_the_next_isbn_when_a_lookup_fails` |
| A11 | MATCH-0 | Title is whitespace/empty string | Treated as missing (A4/A8) | ❓ | `pdf._clean` strips; EPUB path unverified |
| A12 | MATCH-0,3 | Generic junk title ("Untitled", "Microsoft Word - final.docx", "Book") with no author | No match; `needs_review` | ✅ | Two tiers. **Placeholder** ("Untitled", "Untitled Document 2", "No Title", converter stamps like "Microsoft Word - x.docx"): `normalize_title` returns "", so it counts as no title — it cannot match at all and is not searched for. **Generic** ("Book", "Final Draft", "New Document"): survives normalization, so it is still searched, but `match_basis` refuses it on the TITLE_ONLY path — it only reaches TITLE_AUTHOR, where an agreeing author does the work. Neither tier vetoes an ISBN, the same as a missing title. Keeps a real title like Alan Watts' "The Book" identifiable. Tests: `test_match::normalize_title_of_a_placeholder_is_empty`, `a_generic_title_survives_normalization_but_is_flagged`, `normalize_title_keeps_a_real_title_containing_a_junk_word`, `match_basis_two_placeholder_titles_do_not_match`, `match_basis_two_generic_titles_do_not_match_without_an_author`, `match_basis_generic_title_still_matches_when_the_author_agrees`, `match_basis_junk_title_does_not_veto_an_isbn`; `test_library::keeps_placeholder_titled_files_as_separate_books`, `keeps_generic_titled_files_as_separate_books`, `groups_generic_titled_files_when_the_author_agrees`; `test_resolve::does_not_search_on_a_placeholder_title`, `searches_a_generic_title_and_lets_the_author_settle_it` |
| A13 | MATCH-2 | PDF `/Author` is a publisher or tool ("Manning Publications", "Adobe InDesign") | Author disagrees → no match, `needs_review`; author string stored as-is | ❓ | Safe direction (`match_basis` → None) but the bogus author is kept and shown; untested |
| A14 | — (parse) | Multiple `dc:creator` (co-authors) | All authors kept | ⚠️ | `epub._first_text` keeps only the first creator; matching still works via shared surname but the stored author is incomplete |
| A15 | — (parse) | `dc:creator` is an editor/translator, not the author (EPUB3 `role` refine) | Author role respected | ❌ | Roles are not read; an editor is stored as the author. Live: Bassett/Carroll retold edition matched only because both names appear |
| A16 | — (parse) | PDF with XMP metadata but empty/absent info dict | Title/author from XMP | ❌ | `parse_pdf` reads only the info dict |

## B. ISBN quality

| ID | Step | Scenario | Expected | Status | Pinned by |
|---|---|---|---|---|---|
| B1 | — (parse) | Valid ISBN-13 in `dc:identifier` | Extracted | ✅ | `test_epub::reads_title_author_and_isbn` |
| B2 | — (parse) | ISBN-10 | Normalized to ISBN-13 | ✅ | `test_isbn::normalize_isbn_converts_isbn10_to_isbn13` |
| B3 | — (parse) | Hyphens/spaces, `urn:isbn:` prefix | Extracted | ✅ | `test_isbn::is_valid_isbn_ignores_hyphens_and_spaces`; `urn:isbn:` verified in-session |
| B4 | — (parse) | Bad checksum / wrong length | Ignored | ✅ | `test_isbn::rejects_bad_checksum`, `rejects_wrong_length` |
| B5 | MATCH-1; IDENT-3 | False-positive ISBN from PDF text, record contradicts **title and author** | Rejected, ISBN dropped, fall through to search | ✅ | `test_resolve::rejects_isbn_hit_disagreeing_on_title_and_author_and_drops_isbn`, `test_library::rejects_isbn_lookup_that_contradicts_the_file` |
| B6 | MATCH-1 | False-positive ISBN whose record shares the **author** only ("Also by Cal Newport: … ISBN …" in Deep Work's front matter) | Rejected — it is a different book | ✅ | `test_match::scraped_isbn_with_only_author_agreeing_is_none`, `test_resolve::rejects_scraped_isbn_of_another_book_by_the_same_author`, `test_library::rejects_pdf_isbn_of_another_book_by_the_same_author` — a text-scraped ISBN (`ParsedMetadata.isbns_scraped`, set by the PDF parser) needs title agreement; an EPUB `dc:identifier` keeps the lenient either-agrees guard (ADR-14). Residual: a scraped ISBN *unknown* to OL is kept (B7) and can still seed a `grouped=isbn` join with the author's other book |
| B7 | IDENT-2 | Valid ISBN unknown to Open Library (new edition) | ISBN kept on the book; fall back to search | ✅ 🟢 | `test_resolve::keeps_isbn_when_open_library_has_no_record`, `falls_back_to_search_after_unknown_isbn`; live: Algorithmic Thinking 2nd ed. |
| B8 | — (parse) | ISBN appears after page 5 of a PDF | Not found | ⚠️ | `test_pdf::ignores_isbn_beyond_scan_page_limit` (pinned as the limit) |
| B9 | — (parse) | Scanned/image PDF (no extractable text) | No ISBN; title/author from info dict only | ❓ | Follows from `extract_text() or ""`; untested |
| B10 | GROUP-1 | Same false ISBN in two unrelated files, OL has no record for it | Not grouped | ✅ | `test_library::does_not_group_by_isbn_when_title_and_author_both_disagree` — `_find_book` applies `match_basis(same_isbn=True)` like identify does (same both-must-disagree guard, so B6 still applies to grouping) |
| B11 | MATCH-1; IDENT-3 | Asserted ISBN whose record contradicts the **title** and has **no author** to answer for it (live: `9780000000002` → "The three voices of poetry", no author, on a "Deep Work" file) | Rejected, ISBN dropped, fall through to search | ✅ 🟢 | `test_match::same_isbn_with_title_disagreeing_and_no_author_to_vouch_is_none`, spec row 21 (ADR-19). Before ADR-19 this was accepted with `needs_review=False` — a missing author could not "disagree" |

## C. Title shape

Comparisons are file-vs-OL-record (identify) and file-vs-existing-book
(group); the same `normalize_title` / `titles_agree` apply to both.

| ID | Step | Scenario | Expected | Status | Pinned by |
|---|---|---|---|---|---|
| C1 | MATCH-0 | Identical | Agree | ✅ | `test_match::titles_agree_on_normalized_equality` |
| C2 | MATCH-0 | Case / Unicode-form differences | Agree | ✅ | `test_match::normalize_title_folds_unicode_case` |
| C3 | MATCH-0 | Subtitle after `:` on one side ("Deep Work" vs "Deep Work: Rules…") | Agree | ✅ | `test_match::match_basis_deep_work_with_subtitle_is_title_author`, `test_library::groups_deep_work_with_its_subtitled_edition` |
| C4 | MATCH-0 | Subtitle after `;`, ` - `, en/em dash | Agree | ✅ | `test_match::normalize_title_strips_subtitle_after_semicolon`, `…after_spaced_dash` |
| C5 | MATCH-0 | Subtitle after a period ("A Christmas Carol. Being a Ghost Story…") | Agree | ⚠️ | PLAN Backlog: not split because ". " also appears inside titles ("Mr. Darcy…") |
| C6 | MATCH-0 | Edition in `(…)` / `[…]` | Stripped, agree | ✅ | `test_match::normalize_title_strips_edition_parenthetical` |
| C7 | MATCH-0 | Edition marker in any position — after a comma, a colon, bare, or in brackets ("Algorithmic Thinking, 2nd Edition", "(2nd Edition)", ": 2nd Edition", "Second Edition", "[2nd ed.]") vs "Algorithmic Thinking" | Disagree — a different edition is a different book; two markers must agree; the same marker in any spelling agrees | ✅ 🟢 | ADR-23, decided 2026-09-19. Spec rows 22–27; `test_match::normalize_title_lifts_an_edition_marker_out_of_any_position`, `…titles_agree_keeps_editions_apart_and_matches_the_same_one`. Before ADR-23 the answer depended on punctuation: bracketed and colon-separated markers were stripped and the editions merged. Live: the 2nd-edition file rejects the 1st-edition cover. Cost: an unmarked title never agrees with a marked one, so a companion PDF with a bare `/Title` groups only via a shared ISBN. Ordinal-less markers ("Revised Edition") are unspecified |
| C8 | MATCH-0 | Leading article ("The …" vs "…") | Agree | ✅ | `test_match::normalize_title_strips_leading_article_and_punctuation` |
| C9 | MATCH-2,3 | Near-miss different books ("Book of Job" / "Book of Joel") | Disagree | ✅ | `test_match::match_basis_book_of_job_vs_joel_is_none`, `test_library::does_not_group_book_of_job_with_book_of_joel` |
| C10 | MATCH-0 | Series prefix ("The Expanse 1: Leviathan Wakes" vs "Leviathan Wakes") | Agree | ❌ | Subtitle split keeps the *prefix* → None. Safe direction (no false merge) but no identification, no cover |
| C11 | MATCH-0 | Hyphenated words | Kept | ✅ | `test_match::normalize_title_keeps_hyphenated_words` |
| C12 | IDENT-5 | Very long Gutenberg-style title | Identify with a cover | ⚠️ | Backlog: raw title is sent to search, only cover-less records come back; a second search on the normalized title would help |
| C13 | MATCH-0 | Title is only punctuation | Never `title_only`-matches | ✅ | `test_match::normalize_title_of_only_punctuation_is_empty` |
| C14 | MATCH-0 | Non-Latin title (Greek fixture) | No false match; searchable case-insensitively | ✅ 🟢 | `test_real_books::search_matches_greek_title_case_insensitively` |
| C15 | MATCH-2 | Same title, different author ("Dune" Herbert / Anderson) | Separate books | ✅ | `test_match::same_title_different_authors_is_none`, `test_library::does_not_group_same_title_different_author` |
| C16 | MATCH-3 | Same title, author missing on one side | `title_only` group, `needs_review` | ✅ ⚠️ | `test_library::groups_by_title_only_when_author_missing_and_flags_it` — accepted false-merge risk, surfaced for review |
| C17 | MATCH-2 | **Multi-volume / numbered sequels, same author** ("The Lord of the Rings Volume 1" vs "Volume 2"; "Introduction to Algorithms" vs "…Algorithms 2") | Disagree — different books | ✅ | `test_match::titles_agree_treats_differing_volume_numbers_as_different_books`, `test_library::keeps_volumes_of_a_set_as_separate_books` — the fuzz is skipped when the number tokens (digits or roman numerals I–XXXIX) of the normalized titles differ |
| C18 | MATCH-2 | Title with trailing "Vol. 1"/"Part 2" vs OL record without it | Disagree (safe direction: unidentified, `needs_review`) | ✅ | Falls out of C17: `("… Volume 1", "…")` differs in number tokens. The `title_only`/identical path is unaffected |

## D. Author shape

| ID | Step | Scenario | Expected | Status | Pinned by |
|---|---|---|---|---|---|
| D1 | MATCH-2 | Same name, same order | Agree | ✅ | `test_match::authors_agree_on_shared_surname` |
| D2 | MATCH-2 | "Last, First" vs "First Last" | Agree | ✅ | `test_match::author_surnames_handles_last_first_order`, `…compound_surname` |
| D3 | MATCH-2 | Initials ("J.R.R. Tolkien" / "Tolkien, J. R. R.") | Agree | ✅ | `test_match::author_surnames_ignores_initials` |
| D4 | MATCH-2 | Several authors, any of `;` `&` `and` `,` | Split correctly | ✅ | `test_match::author_surnames_handles_multiple_authors`, `…reads_comma_list_of_full_names_as_several_people` |
| D5 | MATCH-2 | Accented vs unaccented | Agree | ✅ | `test_match::author_surnames_strips_accents` |
| D6 | MATCH-2 | Different people, same surname ("Frank Herbert" / "Brian Herbert") | Disagree | ⚠️ | Pinned as a known limitation in `test_match::match_basis_shared_surname_counts_as_agreement` |
| D7 | MATCH-2 | One side lists a subset of co-authors | Agree (share one surname) | ✅ | Falls out of D1; no dedicated test |
| D8 | MATCH-2 | Placeholder names | No evidence | ✅ | see A9 |
| D9 | MATCH-2 | Generational suffix, with or without a comma ("Martin Luther King Jr.", "King, Martin Luther, Jr.") | Surname "king" | ✅ | `test_match::author_surnames_ignores_generational_suffixes` — Jr/Sr/II/III/IV dropped from the end of a name, and a suffix set off by its own comma is not read as a person. Closed 2026-09-18 |
| D10 | MATCH-2 | Single-name author ("Homer", "Plato") | Surname is the name | ❓ | Works by construction; untested |
| D11 | MATCH-2 | Surname-first cultures / non-Latin scripts ("村上 春樹" vs OL "Haruki Murakami") | Agree | ❌ | Last token is taken as surname on both sides; script mismatch and name order both defeat it |
| D12 | MATCH-2 | Publisher/tool as author | See A13 | ❓ | |
| D13 | IDENT-6 | Record's author list is the *work's* — every edition's contributors, e.g. an audiobook narrator ("Martin Luther King Jr., J.D. Jackson") | File's own author stands on any accepted match; the record's is kept as `record_author` | ✅ 🟢 | ADR-22; `test_resolve::keeps_the_files_author_over_the_records_on_a_corroborated_match`, `…on_an_isbn_match_too`, `test_library::identifies_isbn_less_book_by_title_search`; live 2026-09-18 |
| D14 | IDENT-6 | File author is a stand-in for a blank ("Unknown", "N/A") | Treated as no author: filled from the record, never kept. "Anonymous"/"Various" are kept (they say something true) | ✅ | ADR-22; `test_resolve::treats_a_stand_in_author_as_none`, `…drops_a_stand_in_author_even_when_nothing_matches`, `…title_only_match_keeps_the_files_author` |

## E. Open Library behavior

| ID | Step | Scenario | Expected | Status | Pinned by |
|---|---|---|---|---|---|
| E1 | IDENT-3 | ISBN hit, agrees | Accepted | ✅ | A1 |
| E2 | IDENT-3 | ISBN hit, contradicts | Rejected, ISBN dropped | ✅ | B5 |
| E3 | IDENT-2 | ISBN unknown | Keep ISBN, search | ✅ | B7 |
| E4 | IDENT-5 | Search: no results | File-only, `identified=None`, `needs_review` | ✅ | `test_resolve::returns_file_metadata_when_nothing_agrees`, `test_library::needs_review_without_any_online_match` |
| E5 | IDENT-5 | Search: first result disagrees, a later one agrees | Later one accepted | ✅ | `test_resolve::skips_non_agreeing_search_docs_and_takes_first_agreeing` |
| E6 | IDENT-5 | Several agree, some with a cover | Prefer the one with a cover | ✅ | `test_resolve::prefers_agreeing_doc_with_a_cover` |
| E7 | IDENT-5 | A weaker match has a cover, a stronger one doesn't | Stronger basis wins | ✅ | `test_resolve::prefers_stronger_basis_over_cover` |
| E8 | IDENT-6 | Record missing title or author | Filled from the file | ✅ | `test_resolve::fills_missing_record_fields_from_the_file`. Since ADR-22 the file's author wins even when the record has one (D13) |
| E9 | IDENT-2 | Network error / timeout / 5xx | File-only, no exception | ✅ | `test_resolve::returns_file_metadata_on_network_error`, `test_library::falls_back_to_parsed_metadata_on_lookup_failure` |
| E10 | IDENT-2 | Malformed JSON | Treated as failure | ✅ | `openlibrary.py` wraps `JSONDecodeError`; `test_openlibrary` |
| E11 | IDENT-6 | Cover download fails | Book still cataloged, no cover | ✅ | `test_library::falls_back_when_cover_fetch_fails` |
| E12 | IDENT-6 | Record accepted but has no cover (data gap) | Identified, `cover_path=None` | 🟢 | Live: Algorithmic Thinking 2nd ed., A Christmas Carol. Only fix is another source or a user-supplied cover |
| E13 | IDENT-2 | HTTP 429 rate limiting during a large batch | Degrades to file-only, batch completes | ❓ | Caught as `URLError`/`OSError` → same as E9; not exercised at bundle scale |
| E14 | IDENT-6 | OL record's title differs in spelling from the file's | File's title kept | ✅ | ADR-10; `test_library::keeps_first_title_when_second_format_is_identified_equally` |

## F. Grouping against the existing library

| ID | Step | Scenario | Expected | Status | Pinned by |
|---|---|---|---|---|---|
| F1 | GROUP-3 | Empty library | New folder | ✅ | `test_library::creates_new_book_folder_with_sanitized_title` |
| F2 | GROUP-1 | Second format, same ISBN | `grouped=isbn` | ✅ | `test_library::adds_second_format_to_existing_book_by_isbn_match` |
| F3 | GROUP-2 | Second format, title + author agree, no ISBN | `grouped=title_author` | ✅ | `test_library::groups_second_format_by_title_and_author` |
| F4 | GROUP-2 | Second format, author missing on one side | `grouped=title_only`, `needs_review` | ✅ | C16 |
| F5 | GROUP-1 | ISBN match and a title/author match point at different folders | ISBN wins | ✅ | `test_library::isbn_join_beats_a_title_author_join_to_a_different_book` — asserted ISBN; the agreeing author is what carries it past the title mismatch (row 2), so for a *scraped* ISBN the title/author folder would win instead (ADR-14) |
| F6 | GROUP-2 | Two existing books both `title_only`-match | First in sorted folder order | ⚠️ | Arbitrary; only arises from junk titles (A12) |
| F7 | GROUP-4 | Follow-up format identified more strongly | Identification upgraded, cover fetched | ✅ | `test_library::upgrades_identification_on_follow_up_format` |
| F8 | GROUP-4 | Follow-up format identified more weakly or lookup fails | Nothing downgraded | ✅ | `test_library::does_not_downgrade_identification_on_lookup_failure`, `…does_not_replace_strong_identification_with_weaker` (ADR-5) |
| F9 | GROUP-4 | Follow-up identified equally | First title's spelling stands | ✅ | ADR-10; `test_library::keeps_first_title_when_second_format_is_identified_equally` |
| F10 | GROUP-4 | Weakest grouping basis remembered across joins | `grouped` never strengthens | ✅ | `test_library::records_weakest_grouping_basis` |
| F11 | GROUP-4 | Reviewed book, new format | Metadata untouched | ✅ | `test_library::does_not_overwrite_reviewed_book_metadata` |
| F12 | GROUP-4 | Reviewed book, `title_only` join | `reviewed` cleared | ✅ | `test_library::clears_reviewed_on_title_only_join` |
| F13 | GROUP-4 | Re-import of the same file (same format kind) | Idempotent: one format entry, file replaced | ✅ | `test_library::reimport_of_the_same_file_is_idempotent` (same `Book.id`, one entry, one book in the library), `the_same_file_under_another_name_is_a_reimport_not_a_conflict`; legacy rename in `replaces_legacy_book_named_format_file`. "Same file" is judged by bytes against the folder's copy (ADR-21), so a library copy that was modified on disk counts as a different file and hits F14 |
| F14 | GROUP-4 | Same format kind, different file, same book (two EPUB editions) | Refused; nothing changes; the conflict is reported with the join basis | ✅ | ADR-21. `import_file` raises `FormatConflictError` (book, existing file, basis, incoming title/author/isbn); `import_directory` collects them in `ImportBatchResult.conflicts`, apart from `failed`. `test_library::refuses_a_different_file_of_the_same_kind`, `a_refused_import_changes_nothing`, `conflict_reports_the_join_basis_for_a_doubtful_merge`, `a_recorded_file_missing_from_disk_is_not_a_conflict`, `import_directory_collects_conflicts_apart_from_failures`; CLI in `test_cli`. Resolving the conflict is K11/K12 |
| F15 | MATCH-2 | Multi-volume set (C17) | Separate books | ✅ | `test_library::keeps_volumes_of_a_set_as_separate_books` |
| F16 | GROUP-4 | Order independence: `{epub without ISBN, pdf with ISBN}` imported in either order | Same end state | ✅ | `test_library::import_order_does_not_change_the_end_state` — title, author, ISBN, `identified`, `grouped`, `needs_review` and format set all equal |

## G. Placement on disk

The **Place** stage — outside `docs/IDENTIFICATION.md`'s scope, so
these rows carry no Step.

| ID | Scenario | Expected | Status | Pinned by |
|---|---|---|---|---|
| G1 | Colon in title | `" -"` | ✅ | `test_library::sanitize_dirname` (parametrized), ADR-10 |
| G2 | `\ / * ? " < > \|` | Dropped | ✅ | same |
| G3 | Title over 150 chars | Truncated, no trailing ` .-` | ✅ | same |
| G4 | Sanitizes to empty | `Untitled` | ✅ | same |
| G5 | Folder name taken by an unrelated book | `(2)`, `(3)`… | ✅ | `test_library::deduplicates_folder_name_on_collision` |
| G6 | Pre-0.3 `book.epub` in folder | Renamed to `<folder>.epub` | ✅ | `test_library::replaces_legacy_book_named_format_file` |
| G7 | Windows reserved names (`CON`, `NUL`, …) | Rejected | ⚠️ | Backlog; irrelevant on macOS |
| G8 | Case-only difference on a case-insensitive FS ("Dune" / "dune") | `(2)` suffix via `mkdir` collision | ❓ | Works by mechanism (`FileExistsError`); untested |
| G9 | Unicode folder names (NFD on APFS vs NFC in metadata.json) | Round-trips through `scan` | ❓ | Untested |
| G10 | Source file left in place | Copy, not move | ✅ | `test_library::leaves_original_file_in_place` |

## H. File and bundle level

The **Parse** stage and the batch around it — outside
`docs/IDENTIFICATION.md`'s scope, so these rows carry no Step.

| ID | Scenario | Expected | Status | Pinned by |
|---|---|---|---|---|
| H1 | Well-formed EPUB 2/3 | Parsed | ✅ 🟢 | `test_epub::reads_title_author_and_isbn`; real bundle |
| H2 | EPUB: not a zip / no container.xml / no OPF | `BadEpubError`, batch continues | ✅ | `test_epub::not_a_zip…`, `missing_container_xml…`, `missing_opf…`; `test_library::import_directory_records_failures_without_aborting_the_batch` |
| H3 | EPUB3 `<dc:title>` split into main + subtitle elements (`title-type` refines) | Main title used | ❓ | First `dc:title` taken; whether that is the main title depends on the publisher's element order |
| H4 | Well-formed PDF with info dict | Parsed | ✅ 🟢 | `test_pdf::reads_title_and_author_from_info_dict`; real bundle |
| H5 | PDF: encrypted / not a PDF / no info dict | `BadPdfError` or `None` fields | ✅ | `test_pdf::encrypted_without_password…`, `not_a_pdf…`, `missing_info_dict…` |
| H6 | MOBI / AZW3 | Skipped and reported, not failed | ✅ 🟢 | `test_library::import_directory_reports_unsupported_files_as_skipped`; real bundle (2 files). This *is* the v1.0 behavior — the parser (L11) is deprioritized, and being told a file was skipped is a good enough answer for a legacy format |
| H7 | Uppercase extension (`.EPUB`) | Parsed | ✅ | `suffix.lower()`; covered implicitly |
| H8 | Hidden files (`.DS_Store`) | Ignored | ✅ | `test_library::import_directory_*` |
| H9 | Zero-byte file with a supported suffix | Recorded in `failed` | ❓ | Should raise `BadEpubError`/`BadPdfError`; untested |
| H10 | Bundle with per-book subfolders (Humble layout) | `recursive=True` walks them | ✅ | `test_library::import_directory_ignores_subdirectories_unless_recursive` |
| H11 | Empty metadata, informative filename (`deep_work_newport.epub`) | Something usable | ❌ | Title becomes the raw stem, no lookup succeeds, folder is `deep_work_newport`. No filename heuristics exist |
| H12 | Non-book PDFs in a bundle (receipts, "README.pdf", sample chapters) | Cataloged as `needs_review` — a human filters them | ❓ | Currently cataloged like any PDF. No size/page heuristics, and none planned: guessing "is this a book" is a classifier, and the review queue already exists for exactly this |
| H13 | Any other document format (DOCX, TXT, RTF, CBZ/CBR, AZW) | Not parsed; reported as skipped like any unregistered suffix | 🚫 | bookman manages **ebooks** — EPUB and PDF, with MOBI recognized but unparsed (ADR-2, L11) — not documents. See ROADMAP *Out of Scope*. `FormatParser`'s registry makes adding one easy, which is precisely why the boundary is written down |

## Gap summary (what to fix, roughly by damage)

Failures that **silently merge or mislabel** rank above ones that merely
leave a book unidentified, because the latter are already surfaced by
`needs_review`.

1. ~~**C17/F15 — multi-volume sets merge.**~~ Closed: number tokens
   must match before the fuzz applies.
2. ~~**B6 — false ISBN sharing the author is accepted.**~~ Closed
   (ADR-14): a scraped ISBN needs title agreement. Residual noted on
   the B6 row: the B7 keep-unknown-ISBN path has no provenance, so
   grouping can't apply the stricter rule.
3. ~~**B10 — scraped ISBN groups without a cross-check.**~~ Closed:
   `_find_book`'s ISBN branch runs `match_basis(..., same_isbn=True)`.
4. ~~**F14 — same-kind format silently overwritten.**~~ Closed
   2026-09-18 (ADR-21): refused with the evidence, never overwritten.
   The blocker was imaginary — the folder's own copy is what a byte
   comparison needs, not a stored hash.
5. ~~**A12 — junk titles `title_only`-match each other.**~~ Closed in
   two tiers: a placeholder title ("Untitled") normalizes to "" and so
   counts as no title, while a merely generic one ("Book") is barred
   from TITLE_ONLY but can still be corroborated by an author.
6. ~~**A10 — only the first ISBN is tried.**~~ Closed: `identify` walks
   every ISBN, dropping rejected ones and keeping the first unknown one.
7. ~~**D9 — "Jr."/"Sr."/"III" become the surname.**~~ Closed: suffixes are
   dropped before the surname is taken.
8. ~~**D13 — a corroborated match replaced the file's author with the
   work's contributor list**~~ (an audiobook narrator, seen live).
   Closed 2026-09-18 (ADR-22): the file's author stands, the record's
   is kept as `record_author`.
9. ~~**C7 — a bracketed or colon-separated edition merged with the
   first edition.**~~ Closed 2026-09-19 (ADR-23): the marker is lifted
   out before MATCH-0's stripping rules and compared like a volume
   number.
10. **C10, H11, A15, A16, D11** — books left unidentified for
   want of a heuristic (series prefix, filename, EPUB roles, XMP,
   name order). Each is a cover we don't fetch, not a wrong merge.

Unverified rows (❓) are cheap tests to add — the code is believed
right, and pinning them is what makes the next refactor safe. A4/A8,
F5, F13 and F16 were pinned 2026-09-18 (the code was right); G8 and H9
remain.

---

# Part II — Organization and operations

What a frontend needs from `bookman` to be a usable library manager, not
just an importer. "Frontend" means the companion TUI first, the bundled
CLI second, any embedder third. Rows are capabilities; the *Public API*
column is the contract a frontend would call.

## Status legend

| Mark | Meaning |
|---|---|
| ✅ exists | In the public API (`bookman.__all__`) and tested. |
| 🔶 partial | Exists internally, or exists with a gap a frontend would hit. |
| ❌ missing | Nothing provides it. |
| 🚫 out of scope | Excluded by ROADMAP / an ADR; listed so it isn't re-proposed. |
| 💬 decide | Needs a design call (an ADR) before code. |

Baseline today: `Library.import_file`, `import_directory`, `scan`,
`search`; `Book` with 9 fields; `metadata.json` v2; a sqlite index over
title/author/isbn/needs_review; `bookman.config` (ADR-8).

## I. Catalog schema — what a `Book` records

| ID | Field / concept | Why a frontend needs it | Status | Notes |
|---|---|---|---|---|
| I1 | Title, author, ISBN | Display, search, grouping | ✅ | `Book` |
| I2 | Formats (kind + path) | Open/inspect per-format files | ✅ | `Book.formats` |
| I3 | Cover image | Browse view | ✅ | `Book.cover_path`; only fetched, never user-supplied (see K4) |
| I4 | Evidence fields `identified` / `grouped` / `reviewed` / `needs_review` | Review queue, "why is this flagged" | ✅ | ADR-9 |
| I5 | **Stable book identity** | Select, edit, refer to a book across calls; TUI list keys | ✅ | `Book.id`, a uuid4 hex minted at construction and stored in metadata.json v3 (ADR-17). Survives the folder rename K2 will do; a pre-v3 book gets a deterministic folder-derived id until its next save. `Book.directory` remains, as where the book lives and its display name |
| I6 | Series / volume number | Sort volumes together, avoid C17-style merges | ❌ | Also the honest home for "Vol. 1" data instead of the title string |
| I7 | Edition | Distinguish 1st/2nd editions (C7) | ❌ | |
| I8 | Publisher, publication year, language, page count | Display, filter | ❌ | Open Library returns most of these; parsers see `dc:publisher`, `dc:language`, `dc:date` |
| I9 | Description / blurb, subjects | Detail view | ❌ | Available from OL work records |
| I10 | User fields: tags/shelves, rating, reading status, notes | Personal-library organization | ❌ 💬 | Where they live matters: in metadata.json (portable, per-book) vs. a separate user layer (survives re-identify). Needs an ADR |
| I11 | Provenance: added date, source path/bundle name, per-file hash/size | "Where did this come from", duplicate detection (F14), audit | ❌ | Hash also enables "already imported this exact file" |
| I12 | Metadata source per field (file / OL / user) | TUI can show "corrected by you" vs. "from Open Library" | 🔶 | `identified` covers file-vs-OL at book level; per-field and "user" provenance collapse into `reviewed` (ADR-9's deliberate choice — revisit if I10 lands). **Author** is the exception since ADR-22: `Book.record_author` keeps the source's author beside the file's, so a frontend can offer "use Open Library's spelling" |
| I13 | Schema versioning + migration | Old libraries keep working | ✅ | v1→v2, v2→v3 and v3→v4 (adds `record_author`) migration on read, upgraded on next save; `test_catalog` |
| I14 | Author as a structured list, not one string | Author browsing, multi-author display | ❌ | Also fixes A14 (only the first `dc:creator` is kept) |

## J. Read and query operations

| ID | Operation | Why | Status | Public API / notes |
|---|---|---|---|---|
| J1 | List all books | Main view | ✅ | `Library.scan()` — unordered, loads every metadata.json |
| J2 | Substring search over title/author | Quick find | ✅ | `Library.search(query)`; case-folds any script (ADR-7) |
| J3 | Get one book by id | Detail view, edits | ❌ | No longer blocked — I5 landed. Now a small `scan()` filter, or an index column if it needs to be cheap (ADR-17). Out of v1.0 scope until a K operation wants it |
| J4 | Filter: needs review / by format / by evidence basis / has cover | Review queue, "PDF-only books" | ❌ | Index already stores `needs_review`; frontend can filter `scan()` in memory today |
| J5 | Sort: title, author, added date | Any list view | 🔶 | Frontend can sort `scan()`; no added date to sort on (I11) |
| J6 | Field-scoped search (`author:`, `isbn:`) and ranking | Precision on large libraries | ❌ | Index is one `LIKE` over title OR author |
| J7 | Counts / summary (total, needs review, by format) | Status bar, `bookman config`-style overview | ❌ | Trivial over `scan()`; worth one call so every frontend agrees |
| J8 | Author / series browse (distinct values) | Navigation | ❌ | Blocked on I14 / I6 |
| J9 | Performance at scale (hundreds to low thousands of books) | TUI responsiveness | 🔶 | `scan()` reads every JSON file per call; `import_file` rebuilds the whole index per file. Fine for one bundle; measure before the TUI |
| J10 | Change detection / cache invalidation | TUI knows to refresh after an import | ❌ | No version stamp or mtime exposed; frontends re-`scan()` |

## K. Curation — human corrections

The half of ADR-4's "review flag, not blocking confirmation" that isn't
built yet: the review flag exists, the way to act on it doesn't.

| ID | Operation | Why | Status | Public API / notes |
|---|---|---|---|---|
| K1 | Mark reviewed / unreviewed | Clear the review queue | ✅ | `Library.mark_reviewed(book, reviewed=True)` (ADR-18); `bookman review BOOK [--undo]` |
| K2 | Edit title / author / ISBN | Fix a wrong or unidentified book | ✅ | `Library.edit(book, *, title=, author=, isbn=)` (ADR-18). Renames the folder and its format files, revalidates and normalizes the ISBN, and **sets `reviewed`** — decided: without it the edit is silently overwritten by the next format import. Author and ISBN can be cleared by passing None; omitted fields are untouched. `bookman edit BOOK --title/--author/--no-author/--isbn/--no-isbn` |
| K3 | Re-identify: retry the lookup for one book | After fixing a title, or when OL improves | ✅ | `Library.reidentify(book)` (ADR-18). Always runs; a reviewed book keeps its human-set fields and gains only a missing cover and empty fields — the E12 route. Never renames, since the book's own title always wins (ADR-10). `bookman reidentify BOOK` |
| K4 | Supply / replace / remove a cover (file or URL) | Only route to a cover for E12 cases | ❌ | Backlog; needs I3 to accept a user-supplied image |
| K5 | Choose among lookup candidates | "Which of these is it?" in the TUI, instead of auto-pick | ❌ 💬 | `identify` returns one answer; a `candidates(parsed) -> list[…]` API plus `apply(book, candidate)` would let a frontend disambiguate B6/C7/D6-style cases. Changes the ADR-4 stance from "auto with flag" to "auto with flag, override available" |
| K6 | Merge two books | Undo a false split (C10, D11) | ❌ | Formats move to one folder; conflicting same-kind formats must be refused or chosen, as F14 is on import |
| K7 | Split a format out into its own book | Undo a false merge (C16, C17, B10) | ❌ | Inverse of K6 |
| K8 | Remove a format from a book | Bad file | ❌ | |
| K9 | Delete a book | Housekeeping | ❌ | Folder removal + index; decide whether source files (never moved, G10) are touched — they shouldn't be |
| K10 | Undo / history of curation | Safety net for K2–K9 | ❌ 💬 | Probably out of scope for a personal tool; note the decision either way |
| K11 | Replace a book's file for one kind deliberately | Resolve an F14 refusal when the new file is the one wanted (a fixed re-download, a better edition) | ❌ | Deferred from ADR-21 by choice. Shape: `import_file(path, replace=True)` or `Library.replace_format(book, path)`. Until then: delete the file in the folder and import again, which the CLI hint says |
| K12 | Import a file as a new book, bypassing grouping | Resolve an F14 refusal when the merge was wrong (two unrelated "Dune"s) | ❌ | Deferred from ADR-21. The K7 split family. Since ADR-23 "different edition" *is* "different book", so one operation covers both |

## L. Import operations

| ID | Operation | Why | Status | Public API / notes |
|---|---|---|---|---|
| L1 | Import one file / a directory (optionally recursive) | Core | ✅ | `import_file`, `import_directory(recursive=)` |
| L2 | Batch result reporting: imported / failed / skipped | Tell the user what happened | ✅ | `ImportBatchResult`, exported from `bookman.__init__`; pinned by `test_public_api::batch_result_is_exported_from_the_package_root` |
| L3 | Progress callback / streaming results | TUI progress bar on a 40-book bundle with network per book | ❌ | `import_directory` returns only when done |
| L4 | Cancel an in-progress batch | TUI responsiveness | ❌ | Follows from L3's shape (generator or callback) |
| L5 | Dry run / preview: "here is what would happen" | Confidence before touching the library | ❌ | Needs identify + `_find_book` without the copy/save step |
| L6 | Duplicate / already-imported detection | Re-running a bundle import shouldn't re-copy or clobber | 🔶 | Never clobbers now (F14, ADR-21): the same bytes re-import idempotently, a changed file is refused and reported. Still re-copies identical bytes and still runs the lookup for each; a hash (I11) would make both skippable |
| L7 | Copy vs. move source files | Users who want the bundle folder gone | 🔶 💬 | Copy only (G10); a `move=` flag is cheap but changes the safety story |
| L8 | Adopt files dropped into the library folder by hand | Users who manage some folders manually | ❌ | `scan()` skips folders without metadata.json |
| L9 | Offline mode / no-network import | Airplane, rate limits, privacy | ❌ | Lookups run unconditionally; failures degrade gracefully (E9) but each costs a timeout |
| L10 | Exceptions a frontend can catch by name | Distinguish "bad file" from "disk full" | ✅ | All nine live under `BookmanError` and are exported from `bookman.__init__`; `test_errors` pins the hierarchy and that every exported error is a `BookmanError` |
| L11 | MOBI / AZW3 parsing | Bundles ship them | ❌ | **Deprioritized below v1.0** (2026-09-18). MOBI is Mobipocket, Amazon-only since 2005, and Amazon itself moved off it — Send to Kindle stopped accepting MOBI in 2022; current Kindles use AZW3/KFX. It is also the most expensive format work available: ADR-2 notes there is no clean pure-Python parsing story, and ADR-3's dependency policy rules out leaning on a library. Meanwhile H6 already degrades gracefully. Revisit if a real bundle ships MOBI-only titles |
| L12 | Bundle-level hints (Humble page title list) | Bias matching for a known batch | 🚫 | ROADMAP Ideas — deferred, not planned |

## M. Maintenance and integrity

| ID | Operation | Why | Status | Public API / notes |
|---|---|---|---|---|
| M1 | Rebuild the search index | Recover from corruption, after manual edits | 🔶 | `storage.index.rebuild_index` is internal; `Library.search` rebuilds only if the file is missing |
| M2 | Verify: metadata.json vs. disk (missing format files, orphan files, missing cover, unreadable JSON) | Trust the catalog | ❌ | `scan()` silently skips unreadable metadata.json — a frontend can't tell "empty" from "broken". Also the repair path for ADR-18's one failure window: a title edit interrupted partway through its inner file renames |
| M3 | Repair: re-link or drop missing formats, adopt orphans | Fix what M2 finds | ❌ | |
| M4 | Export catalog (JSON / CSV) | Backup, spreadsheets, other tools | ❌ | Cheap over `scan()` |
| M5 | Relocate the library | Move to a new disk/path | 🔶 | `save_config` repoints; paths in metadata.json are relative so folders can be moved, but nothing verifies afterwards (M2) |
| M6 | Single-writer assumption documented / enforced | Two TUI instances or TUI + CLI at once | 🔶 | Backlog: not concurrency-safe; at minimum document it, ideally a lock file |
| M7 | Library-level metadata (schema version, created, book count) | Detect an old library, show an overview | ❌ | Nothing at the root except the index file |

## N. Frontend contract

| ID | Concern | Why | Status | Notes |
|---|---|---|---|---|
| N1 | Library location resolution shared by all frontends | One config, no drift | ✅ | ADR-8 |
| N2 | Minimal, explicit public surface | Semver discipline | ✅ | `__all__` is the contract, pinned by `test_public_api` (every name resolves, sorted, no duplicates); everything a frontend uses is exported (L2, L10) |
| N3 | Type hints + docstrings on everything public | TUI author can rely on signatures | ✅ | Convention; mypy clean |
| N4 | Network configuration: timeouts, user-agent, endpoint override, disable | Tests, rate limits, mirrors | ❌ | Hard-coded in `identify.openlibrary` |
| N5 | Logging instead of silence | Frontend can show "lookup failed: timeout" | ❌ | Failures are swallowed into "no match"; no `logging` calls |
| N6 | Thread-safety statement | TUI will run imports off the UI thread | ❌ | Undocumented; relates to M6 |
| N7 | CLI parity with the public API | CLI stays a thin wrapper (ADR-6) | ✅ | `init`, `config`, `import`, `list`, `search`, and since 2026-09-18 `review [--undo]`, `edit --title/--author/--no-author/--isbn/--no-isbn` and `reidentify` for K1–K3. A book is named by its title as `list` prints it, its folder name, or its `Book.id` (ADR-20) |
| N8 | Second metadata source (Google Books, …) behind one interface | E12-class gaps; resilience to OL outages | ❌ 💬 | CONTEXT names it as the future fix; needs a provider abstraction ADR |

## Reading the two parts together

Several Part I gaps are cheaper to close as Part II features than as
matching heuristics:

- **C16** (ambiguous title-only merges) — a human choosing among
  candidates (K5) or splitting (K7) is more reliable than any
  threshold, once the evidence is *shown*. (C17 and C7 turned out to be
  clean rules — number tokens, and edition markers reduced to number
  tokens — and closed on the Part I side.)
- **E12** (no cover on Open Library) — only K4 or N8 fixes it.
- ~~**F14** (same-kind overwrite)~~ — closed without I11 (ADR-21); the *resolution* is K11/K12.
- **A14, D11** (multiple / non-Latin authors) — start with I14.

The first Part II slice that unblocks the TUI — **I5** (stable id),
**K1** (set reviewed), **K2** (edit fields), **K3** (re-identify) and
**L2/L10** (export what's already there) — is complete as of
2026-09-18, with CLI commands for K1–K3 (N7) landing the same day.
What it exposed: the first operation that rewrites a book's layout on
disk made M2/M3 (verify/repair) matter for the first time.
