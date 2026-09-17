# Real book fixtures

Small, real EPUB files from [Project Gutenberg](https://www.gutenberg.org/),
used by `tests/test_real_books.py` for integration coverage that synthetic
fixtures can't provide (real EPUB structure quirks, real non-ASCII text).
All are public domain; each file carries Project Gutenberg's own license
header unmodified. Downloaded as the "EPUB (no images)" format for size.

| File | Title | Author | Language | Gutenberg ID |
|---|---|---|---|---|
| `alice_11_en.epub` | Alice's Adventures in Wonderland | Lewis Carroll | English | [11](https://www.gutenberg.org/ebooks/11) |
| `christmas_carol_46_en.epub` | A Christmas Carol in Prose | Charles Dickens | English | [46](https://www.gutenberg.org/ebooks/46) |
| `loukis_laras_29062_el.epub` | Λουκής Λάρας | Demetrios Vikelas | Greek | [29062](https://www.gutenberg.org/ebooks/29062) |
| `lazarillo_320_es.epub` | Vida De Lazarillo De Tormes... | Anonymous | Spanish | [320](https://www.gutenberg.org/ebooks/320) |

None of these carry a machine-readable ISBN (pre-ISBN classics / Gutenberg
doesn't assign one), so importing them always yields `NEEDS_REVIEW`
confidence -- itself a realistic scenario worth covering, since most
public-domain reprints have no ISBN.

No real PDF fixture is included: Project Gutenberg doesn't distribute PDFs
for most texts, and other public-domain PDF sources are typically scanned
images without a real text layer (unsuitable for bookman's text-based ISBN
scan). PDF coverage stays on the synthetic fixtures in `tests/test_pdf.py`
and `tests/test_library.py`.
