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

## Bundle: Calibre library export, 2026-09-20 · full run 2026-09-26, fixes in

Not a bundle but the rest of the library as Calibre had filed it:
340 books / 603 files (268 EPUB, 211 PDF, 123 MOBI, 1 AZW3) across 276
authors and ~10 publisher families — Adams Media 34, Mercury Learning
25, MIT Press 24, No Starch 19, O'Reilly 40, Packt 20, Parallax 22,
Penguin 11, no publisher in the `.opf` 93. Filenames are Calibre's
`<title cut at ~42 chars> - <author>.ext` (so `_` for `:`, and two
volumes of one series share a stem). Every file was symlinked into 39
publisher-grouped batches of ≤10 titles and imported with `bookman
import`; Calibre's `metadata.opf` served as an oracle (title, author,
the 84 ISBNs it had; its book folder = the grouping) through a scratch
compare script keyed by content fingerprint (see `tools/calibre-oracle/`).

Batches 1–25 completed (Adams, Mercury, MIT Press, No Starch, the
no-publisher set, O'Reilly). Batches 26–39 ran into a full disk; 34
imports failed on `ENOSPC` and their counts are not usable. **0 failures
in the matching code; 0 silent wrong merges** — the two wrong merges
below were both caught by the same-kind refusal (ADR-21). A fresh full
run needs ~9 GB free (bookman copies), so the re-run after fixes waits
on that.

**Full runs, 2026-09-26.** All 39 batches, fresh, through
`tools/calibre-oracle/linked.py` (placed files hard-linked, so no disk
cost), compared against Calibre by `compare.py`:

| | before fixes | ADR-29..34, with `bookman[crypto]` | + ADR-35..37 |
|---|---|---|---|
| files imported / failed | 456 / 19 | 477 / 0 | 477 / 0 |
| books missing | 20 | 1 (Calibre's own duplicate *Quick Start Guide*) | 1 |
| books split in two | 23 | 12 | 12 |
| wrong merges | 0 (1 Calibre-side) | 0 (1 Calibre-side) | 0 (1 Calibre-side) |
| title / author differs from Calibre | 15 / 9 | 9 / 5 | 9 / 5 |
| needs review | 76 | 70 | 46 |

The third run (ADR-35..37) changed nothing but the review queue: all 20
remaining "(Humble)" Adams books are now identified by search (FN-13),
as are four others the tag-free query or the title-only retry reached
(*Flowers in the Dark*, *A Handful of Quiet*, *Programming the
TI-83 Plus/TI-84 Plus*, *Introduction to Computer Organization*).
*Statistics 101*'s folder now matches its upgraded title (FN-17), and
no `.partial` file was left anywhere.

The 12 splits left: **8 are an edition marker present on one side only**
(OQ3's accepted cost) — the five FN-21 Packt pairs bar Modern C++, plus
*Think Python, 2E*, *Twisted …, 2nd Edition*, and two new ones below;
*Modern C++* ("C Plus Plus" vs "C++"); *Write Great Code* (FN-19);
*A Mind for Numbers* (FN-20, named after its filename by design); and
*Angular and Machine Learning*, whose EPUB `dc:creator` is literally
"Pocket Primer", so the author vetoes. Two splits are **new**: *Flask
Web Development* / *…, 2e* and *Head First Java* / *…, 3E*. Both EPUBs
are ISBN-identified as that edition; the PDFs' "2e"/"3E" is an
ordinal-less marker (MATCH-0 `unspecified`), and they had joined only
because the old whole-title fuzz swallowed the extra token, which
ADR-30 no longer does. Under ADR-23 a marked title does not agree with
an unmarked one anyway, so these join OQ3's group rather than being a
regression of a rule. Two author differences are now Calibre's: *Data
Structures and Program Design Using Java* is by the Malhotras, and
`book_insert.indd` is Manning's *Algorithms and Data Structures for
Massive Datasets* — bookman now has both right. Logs:
`tools/calibre-oracle/run-{full,fixed,tier3}.log` and
`compare-{full,fixed,tier3}.txt` (local only; the tooling is not
committed).

Oracle disagreements that are Calibre's, not ours: *Black Hat GraphQL*
and *Black Hat Python* are the same three files in Calibre (bookman
shelved the bytes once, as *Black Hat Python*); six byte-identical
files sit under different Calibre entries; a MOBI filed by Calibre as
its own book (id 195) beside its EPUB (192); two copies of Calibre's
own *Quick Start Guide*. Of Calibre's seven "Unknown" books, *Tkinter
GUI Application Development Hotshot* came out with a real title; the
rest were not checked before the disk filled.

### FN-11 · PDF `/Title` is the layout tool's filename · fixed (ADR-32)

`css.indb`, `Book 1.indb`, `data.indb`, `alg.indb`, `access.indb`,
`exc.indb`, `program.indb`, `9781683924708_A&MLPP_PRESS.indb` (8 of 25
Mercury PDFs, InDesign), `CC_03.book`, `hack2e_03.book` (2 No Starch,
FrameMaker), `book_insert.indd` (1, unknown publisher; Calibre had the
same junk title). Beside them `/Author` is the operator's login —
`radha` ×4, `Sys` ×2, `yps17`, `user` — which is FN-7's shape on a
second and third publisher. Each became an orphan book named after the
stamp. Spec MATCH-0 already counts "a converter's filename stamp" as a
placeholder; the code's pattern only knows `App - file.ext`. Every one
of these PDFs scrapes its ISBN and its EPUB asserts the same number, so
with the title treated as absent MATCH-1 joins them ("what says nothing
cannot contradict") and the login-name author never gets a say.
**Fix:** a bare filename with a document extension is a placeholder.
The full run added a fourth publisher: Springer's `482387_1_En_Print.indd`
and `486223_1_En_Print.indd`, with a job number as `/Author`. The
author beside such a title is dropped along with it (IDENT-6), or the
join would let "radha" replace the EPUB's author (GROUP-4).

### FN-12 · AES-encrypted PDFs cannot be opened at all · fixed (ADR-29)

18 of 18 Pearson / Addison-Wesley (InformIT) PDFs — *Domain-Driven
Design Distilled*, *Modern Software Engineering*, *Software
Architecture in Practice*, … — are AES-encrypted with an empty user
password (any reader opens them). pypdf needs the `cryptography`
backend for AES and raises its `DependencyError`, which is neither
`PdfReadError` nor `BadPdfError`, so the import **fails** with an
undocumented exception and the book is not in the library. Options:
`pypdf[crypto]` as a runtime dependency, as an optional `bookman[crypto]`
extra, and/or catch the error and import the file with stem-only
metadata regardless (a bought book must land in the library).
**Decided:** both — the filename fallback always (spec PR6, with the
reason kept on the format as `read_issue`), and `bookman[crypto]` as an
optional extra pulling PyCryptodome, not `cryptography`.

### FN-13 · Vendor tag in `dc:title` and honorific in `dc:creator` · fixed (ADR-37)

22 of 34 Adams Media EPUBs have "(Humble)" literally in `dc:title`
("Accounting 101 (Humble)"), and their eISBNs (978-1-5072-17xxx) are not
on Open Library, so identification falls to search — where the tag
makes the title query return nothing. Five of them also carry
`dc:creator` "CPA  Michele Cagan" (double space, credential first),
which on its own also empties the search. Verified against the live
API: the same query with the trailing bracket group stripped, or with no
author at all, finds the record. **Fix:** search with the trailing
bracket group removed, and retry title-only when title+author returns
nothing (IDENT-5 still vets every candidate's author through MATCH-2).
The stored title stays as the file wrote it (ADR-10).

### FN-14 · Fuzz bridges a whole substituted word · fixed (ADR-30)

*Microsoft® Excel® 2019 Programming by Example* (own ISBN, identified)
was grouped into *Microsoft Access 2019 Programming by Example* on
TITLE_AUTHOR: the difflib ratio of the normalized forms is 0.920, over
the 0.9 line, because on a 44-character title one different word is
under 10 %. Refused only because the book already had an EPUB (ADR-21),
with the message "same title and author" — a PDF would have merged
silently. One sighting, but PR4's class. **Fix:** fuzz within a word
(plural, typo, spelling), never across one — same word count, each pair
identical or nearly so; a trailing ", The" (the one legitimate extra
word the fuzz was carrying) becomes a MATCH-0 rule.

### FN-15 · Volume marker in the subtitle or brackets · fixed (ADR-31)

*Stoicism Today: Selected Writings (Volume 1)* and *… (Volume Two)
(Volume 2)* both normalize to "stoicism today": the subtitle and bracket
rules drop the marker before C17's number rule can see it. Refused as a
second EPUB of Volume 1 — again saved by ADR-21. Same class as the
edition marker ADR-23 lifts out first. **Fix:** lift a volume marker
("Volume 1", "Vol. 2", "Part II", "Book 3") the same way. "Book 3" was
left out: "book" is a generic-title word, and it has not been seen.

### FN-16 · A colon that is not a subtitle · fixed (ADR-34)

*Python 3: Pocket Primer* EPUB vs `PYTHON 3 Pocket Primer` PDF, and
*Python An Introduction to Programming* EPUB vs the record's *Python: An
Introduction to Programming* — 2 of 25 Mercury pairs, split because the
subtitle rule leaves "python 3" / "python" on one side. **Fix:** titles
agree when either the subtitle-stripped forms or the full forms agree.

### FN-17 · Import-time upgrade renames the title, not the folder · fixed (ADR-36)

*Statistics 101 (Humble)*: EPUB first (no match), then the PDF's print
ISBN hit Open Library and upgraded the book to "Statistics 101"
(GROUP-4, F7) — but the folder and files stayed "Statistics 101
(Humble)". `curate` renames on a title change; import does not; F7's
test never asserts the folder; ADR-1 says the folder is the identity.
**Fix:** an upgrade that changes the title renames like `curate`.

### FN-18 · A failed copy leaves a half-imported folder · fixed (ADR-35)

The `ENOSPC` run left `TinyML/TinyML.epub` truncated at 12 MB with no
`metadata.json`. `scan` ignores it; the user sees it on disk. **Fix:**
remove the partial file and the folder it claimed when the copy fails.
Writing the test found worse: re-importing a file already in the library
copied straight over it, so a failed copy destroyed the good one. The
copy now goes to a `.partial` name and is renamed into place.

### FN-19 · Same-edition ISBN pair split across print/ebook · observed, parked

FN-4's "watch for", on its own books: *Write Great Code* Vol. 1 and 2
EPUBs assert the ebook ISBN (…372, …396); the PDFs scrape only the
print number (…365, …389) and the 1st edition's. No number in common →
no GROUP-1 join; the record for the print number is titled just "Write
Great Code" → an orphan, and Vol. 2's PDF was then refused as its second
PDF. OQ4 (remember every ISBN a file claimed) would not help — neither
side has the other's number. What would: Open Library's record lists
every ISBN of the edition, so a join through the record's ISBN set. A
larger design; parked.

### FN-20 · `/Encrypt` is a null object · fixed (ADR-29)

*A Mind for Numbers* (Penguin) PDF: the trailer's `/Encrypt` entry is
`null`. pypdf's encryption setup, which runs inside `PdfReader()`,
calls `.get` on it and raises `AttributeError` — not a `PdfReadError`
— so the import failed like FN-12's, and no crypto backend helps.
Found by the first hard-linked run (2026-09-26); the earlier run had
lost the Penguin batches to the full disk. Now `UNSUPPORTED_ENCRYPTION`:
imported on its filename. An Adobe-DRM PDF (non-Standard security
handler, pypdf's `NotImplementedError`) takes the same path; none seen.

### FN-21 · Packt EPUBs carry their ISBN only on the title page · partly fixed (ADR-33)

Every Packt EPUB's `dc:identifier` is a bare `urn:uuid:`; the ebook
ISBN is printed on the title page (spine document 1) and in the
preface (3), and it is the number the PDF scrapes. Six Packt pairs
split on it: *Kotlin Design Patterns and Best Practices*, *Learn Java
17 Programming*, *Mastering Go*, *Hands-On Data Structures and
Algorithms with Python*, *Modern C++ Programming Cookbook*, *Build Your
Own Programming Language*. Back matter ("Other books you may enjoy")
lists other titles' ISBNs, and one book's Chapter 1 cites the previous
edition's. **Fix:** scan the first four spine documents when the OPF
has no ISBN, as scraped. Checked against Open Library before shipping,
it joins only 1 of the 6: the other five records disagree with the
EPUB's title — Kotlin, Mastering Go and Learn Java across an edition
marker present on one side only, Hands-On likewise (and its OPF declares
a wrong ISBN, `9789991167596`, so it is never scanned), Modern C++ as
"C Plus Plus" — and a scraped ISBN needs the titles to agree (MATCH-1).
What would close them is an edition-rule decision (OQ3), not a parse fix.

### Also seen, nothing to do

- `dc:title` "US. History 101" (publisher typo); search finds nothing.
- `/Author` "V. Scott Gordon/ John Clevenger" (slash-separated), "Charles
  P. Schultz and Robert…" — grouped fine (FN-9 variants).
- Indian co-edition ISBNs (978-93-…) scraped beside the US one on Mercury
  PDFs; harmless, the US number joins.
- MIT Press Essential Knowledge: 24 EPUB-only, no incidents.
- Manning PDF-only titles: no cover (no record cover, no EPUB to fall
  back to — ADR-28's known limit).
