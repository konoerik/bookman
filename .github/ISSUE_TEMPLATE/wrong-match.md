---
name: Wrong match, missed grouping, or missing cover
about: A file that was identified as the wrong book, not grouped with its sibling, or left without a cover
labels: identification
---

<!-- Fixes are made for patterns, not single files, so the shape of the
     file is what matters. Please fill in what you can; the commands
     under "What bookman saw" print exactly what is needed. If the shape
     is already in docs/FIELD-NOTES.md, just say which FN-n. -->

**What happened**

<!-- e.g. "the PDF landed in its own folder next to the EPUB's",
     "identified as the 2nd edition, file is the 3rd", "no cover" -->

**Where the files came from**

<!-- publisher and bundle, e.g. "No Starch via Humble Bundle, 2025" -->

**What bookman saw**

```
# EPUB:
uv run python -c "from bookman.formats.epub import parse_epub; print(parse_epub('book.epub'))"
# PDF:
uv run python -c "from bookman.formats.pdf import parse_pdf; print(parse_pdf('book.pdf'))"
```

<!-- paste the output; if a PDF's ISBN was missed, also say which page
     of the PDF the copyright notice is on -->

**What Open Library returns**

<!-- https://openlibrary.org/isbn/<ISBN>.json for each ISBN above:
     "no record", or the record's title/author and whether it has covers -->

**The `metadata.json` bookman wrote** (optional)

**bookman version**: `bookman --version`
