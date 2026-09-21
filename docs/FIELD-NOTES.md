# Field notes

What real bundles do that the test suite didn't predict. One entry per
peculiarity, dated, with the bundle it was seen in and how many files
showed it. The point is to gather *shapes* — a fix for a shape seen once
is a guess, a fix for a shape seen in three bundles is a rule. When a
shape is fixed, say so and point at the ADR / FEATURES row; keep the
entry, since the next bundle may show a variant.

Conventions: the bundle is named by source and date; counts are "N of M
files of that publisher/format" so a rate survives later re-reading.
Entries are numbered `FN-n` so ADRs and FEATURES rows can cite them.

---

## Bundle: No Starch + O'Reilly, 2026-09-20

37 titles, 92 files. Every title has EPUB + PDF; 18 (all No Starch)
also have MOBI. Every format of a title shares one filename stem
except one (FN-6). Imported via `bookman import` in four alphabetical
batches, then the whole set again after fixes. Publisher split: 18
No Starch, 19 O'Reilly.

Headline: 0 failures in any run; 74 of 74 parseable files imported.
Before fixes 7 of 18 No Starch PDFs failed to group with their EPUB;
after FN-1 and FN-3 that was 4; after FN-4 the final run shelved 37
books, every one an EPUB + PDF pair. 16 of 37 had a cover (FN-5).

### FN-1 · PDF ISBN sits past page 5 · fixed

Every No Starch PDF runs cover, blank, half-title, blank, title page,
copyright — the ISBN is on page index 5. O'Reilly puts it at 3, 5 or 7
(often with a second hit on page 1, the marketing blurb). 23 of 37 PDFs
had their first ISBN at index ≥ 5, outside the five-page scan window.
Combined with FN-2 that orphaned five No Starch PDFs.

Fixed 2026-09-20: window widened to 10 pages. FEATURES B8.

### FN-2 · No Starch PDFs often have no `/Title` or `/Author` · observed

4 of 18 No Starch PDFs (*How Computers Really Work*, *Rust 3rd ed.*,
*Secret Life of Programs*, *Write Great Code Vol. 2*) carry an empty
info dictionary — `/Creator: Adobe InDesign`, nothing else. A fifth
(*Think Like a Programmer*) has `/Title: untitled` (FN-3). Such a file
has *only* its scraped ISBNs to identify or group by, which is why FN-1
hurt so much. Every O'Reilly PDF had both fields.

No fix as such — this is what the ISBN scrape is for. The rate matters:
for No Starch, expect ~1 in 4 PDFs to be metadata-blind.

### FN-3 · `/Title` is the literal placeholder "untitled" · fixed

*Think Like a Programmer* (No Starch, 2012) — the PDF's `/Title` is
"untitled". It was shelved as a book called `untitled`; the spec (IDENT-4)
already said a placeholder falls back to the filename stem, and the code
had kept it "for the user to correct".

Fixed 2026-09-20: a placeholder title is dropped in `identify` like a
stand-in author. FEATURES A12.

### FN-4 · Copyright page lists several ISBNs: print, ebook, prior editions · fixed (narrowly)

No Starch copyright pages carry `ISBN-13: … (print)` and `… (ebook)`,
and for a new edition also the previous editions' pair ("previously
published as"). So a PDF scrapes 2–4 ISBNs, in that order. The EPUB's
`dc:identifier` is the ebook one — the *second* on the page.

Consequences seen (4 of 18 No Starch pairs, all with a real fix pending
FN-1): identification accepted the first ISBN Open Library knew (the
print one, or worse a prior edition's — *Rust 3rd ed.* was identified
as the 2nd edition, *Write Great Code Vol. 2, 2nd ed.* as a record
titled just "Write Great Code"); grouping then compared only that one
ISBN against the EPUB's, missed, and fell to the title rule, where
"Effective C" vs "Effective C, 2nd Edition" and "Total Typescript" vs
"Total TypeScript … with Taylor Bell" split on the edition-marker and
author rules.

Fixed 2026-09-20, narrowly (ADR-26, ADR-27): GROUP-1 checks the book's
ISBN against every ISBN the file carries, and on an ISBN join a follow-up
only upgrades the book's identification when its record came through the
ISBN it joined on. Known gap: if the PDF is imported *first*, the book
stores the print ISBN and the EPUB's ebook ISBN won't hit it — the
proper fix is remembering every ISBN a book's files claimed (spec OQ4).
Watch for: bundles where the EPUB asserts the *print* ISBN, or where
the same-edition pair is split across the print/ebook numbers in the
other direction.

Side effect worth knowing: *Effective C* is shelved as "Effective C"
although the PDF's `/Title` says "Effective C, 2nd Edition" — the
EPUB's own `dc:title` omits the marker, the EPUB came first, and the
file's title wins (ADR-10). The PDF's print-ISBN record was declined
under ADR-27 so it could not respell it either. Publisher EPUB titles
dropping the edition marker may be a pattern; one instance so far.

### FN-5 · Open Library gaps · observed; cover side fixed

- **No record at all** for recent No Starch ebook ISBNs (`97817185…`):
  9 of 18 No Starch titles came back "no online match". Title search
  found some (*Algorithmic Thinking 2nd ed.*), not others (*The Art of
  ARM Assembly*: 0 results; *The Art of Randomness*: only *The Art of
  Random Walks*, correctly refused).
- **Record but no cover** for several O'Reilly editions (*Building Green
  Software*, *Building Medallion Architectures*, *Building Multi-Tenant
  SaaS Architectures*): `covers: None` on the edition record.
- **Record title without the edition/volume marker**: OL's record for
  9781718500389 is "Write Great Code" (file: "…, Volume 2: …, 2nd
  Edition"). ADR-10 keeps the file's title, so this only bites when the
  file has none (FN-2).

Net effect before the cover fallback: 21 of 37 books had no cover
although every EPUB embeds one (27 declare it the EPUB 3 way,
`properties="cover-image"`; all 37 also carry the EPUB 2 `<meta
name="cover">` and an item with `id="cover"`; 19 PNG, 18 JPEG).

Fixed 2026-09-20 (ADR-28): the EPUB's embedded cover is used when
identification supplies none. Final run: 37 of 37 with a cover. The
record gaps themselves remain — 10 books still say "no online match".

### FN-6 · Sibling formats with different stems · observed, worked

`learningsystemsthinking_V2.epub` beside `learningsystemsthinking.pdf`
(O'Reilly, a re-issued EPUB). Grouped correctly on ISBN — noted because
it is the one counter-example to "formats only differ by extension" in
this bundle, so any stem-based rule (e.g. adopting a MOBI by stem) would
have to tolerate it.

### FN-7 · Garbage `/Author` in an O'Reilly PDF · observed

*Software Architecture Metrics*: the PDF's `/Author` is the ten-author
list concatenated with itself ("… and Eoin Christian Ciceri, … and Eoin
Woods"). The EPUB's `dc:creator` is clean. Because the pair identified
equally (ISBN) and GROUP-4 lets an equal follow-up update the *author*
(only the title keeps its first spelling — ADR-10 §4), the PDF's garbage
replaced the EPUB's good author. One instance; not fixed. If it recurs,
the question is whether author should follow the title's
first-spelling-stands rule.

### FN-8 · MOBI beside identical-stem EPUB/PDF · observed, parked

18 of 18 MOBIs sit beside an EPUB and PDF with the same stem. All
skipped (H6). Stem adoption was considered and set aside 2026-09-20:
the stem alone is not enough evidence (FN-6 shows stems drift), and
what "enough" is needs more bundles.

### FN-9 · Author list formats differ between formats · observed, worked

EPUB `dc:creator` lists are "A, B, and C" (Oxford comma, "and"); OL
records are "A, B, C". *Total TypeScript*: EPUB "Matt Pocock", PDF
"Matt Pocock with Taylor Bell". `authors_agree` handled all of these
(one shared surname suffices). Noted for the pattern: "with X" is a
contributor marker that a stricter author rule would need to know.

### FN-10 · EPUB `dc:creator` names only the first author · observed

*The Rust Programming Language, 3rd Edition*: the cover says "Steve
Klabnik, Carol Nichols, and Chris Krycho"; the EPUB's `dc:creator` is
"Steve Klabnik" alone, so that is the cataloged author (ADR-22: the
file's author stands). Open Library, where it has the record, tends to
list all three. One instance; no fix — a frontend can offer
`record_author` when there is one. Worth counting across bundles: if
single-creator EPUBs for multi-author books are common, `record_author`
becomes more than provenance.
