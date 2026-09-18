---
name: matching
description: >-
  Load bookman's book-identification spec before touching how books are
  identified, matched, or grouped. Use when the work involves match_basis,
  title normalization, author agreement, ISBN acceptance or provenance,
  Open Library candidate selection, grouping a file into an existing book
  folder, the identified/grouped/reviewed fields, the review queue, or any
  FEATURES Part I scenario (A*, B*, C*, D*, E*, F*). Also use when adding a
  metadata source, or when a bug report sounds like "the wrong book matched",
  "these two merged", "it didn't find the cover", or "it should have grouped
  these".
---

# Book matching

`docs/IDENTIFICATION.md` is the specification for the Identify and Group
stages and the match rule they share. **Read it before proposing or
reviewing a change to any of them.**

It is written from the ADRs, never from `src/`. So it states what bookman
*should* do, which may differ from what it does. That is the point — a spec
transcribed from the code could only ever agree with the code.

`docs/FEATURES.md` Part I is the **conformance report** against it: every
scenario row names the step it exercises in its `Step` column, and the ❌/⚠️
rows are the register of where the code hasn't caught up. Expect the two to
disagree; that disagreement is the work list, not a defect.

## Working with it

**Changing behavior.** Change the spec first, with an ADR (`/log`)
recording why, then the code, then the FEATURES row. A behavior change
that leaves the spec untouched is a bug in one of the two.

**Reviewing a change.** Walk the steps the change touches and, for each,
find the implementing code and the pinning test. A step with neither is a
gap. Code with no corresponding step is either undocumented intent or a
defect — say which.

**Citing it.** Use the stable step IDs — `MATCH-0..3`, `IDENT-1..6`,
`GROUP-1..4` — in commit messages, ADRs, FEATURES rows and review
comments, so a rule can be traced both ways.

**Finding a divergence.** Do not quietly reconcile the spec to the code.
Report it: name the step, quote the intended outcome, state what the code
does instead, and let the user decide which one is wrong. If they decide
the spec was wrong, the fix is an ADR plus a spec edit — not a silent
rewrite.

## Two things the spec deliberately leaves open

`open_questions` at the end of the YAML block records these — OQ2
(scraped-ISBN provenance isn't persisted), OQ3 (is an edition a different
book). Don't invent behavior for them; if the work needs an answer, that
is a decision to make and log, not to infer. `decided_questions` above it
keeps the ones that have been answered (OQ1, same-kind files: refused)
with the reasoning, so the question isn't reopened by accident.

MATCH-0 also carries an `unspecified:` list — title shapes this spec
knowingly doesn't handle. They are gaps by choice, not oversights.
