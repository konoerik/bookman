# Context
<!-- Updated by /wrap at session end. Edit manually if needed. Keep it under 8 lines. -->

**Current focus:** Post-1.0: running the rest of the user's library (mostly Humble Bundle) through bookman, one bundle at a time into a scratch library, logging shapes in `docs/FIELD-NOTES.md` and fixing only what a pattern justifies (spec → ADR → code → FEATURES row). Working method from the first bundle: symlink batches of ~10 titles into the scratchpad, `bookman --library <scratch> import <batch>`, stop and fix on a major gap before the next batch, re-run the whole set fresh at the end.
**Last session (2026-09-20):** First real bundle (37 No Starch/O'Reilly titles) → four fixes and ADR-26/27/28, then release plumbing, then **v1.0.0 released** with the wheel on the GitHub Release; `v0.1.0` tag deleted so 1.0.0 is the first release.
**Blocking:** Nothing. Shapes waiting for a second sighting before a "proper fix": OQ4 (PDF-first import order splits a print/ebook-ISBN pair), FN-7 (garbage PDF `/Author` overwrites a good EPUB author on equal evidence), FN-8 (MOBI adoption), FN-10 (EPUB `dc:creator` names only the first author).
**Next action:** Ask where the next bundle is, survey it (`find` by extension, publisher mix, stem patterns), then import it in batches and add a new `## Bundle:` section to FIELD-NOTES; new shapes get the next `FN-n`.
<!-- wrapped: 2026-09-20 -->
