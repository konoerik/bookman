# Contributing

bookman is a small library with one job: identify purchased ebook files,
group the formats of one book, and file them under a title-named folder.
Contributions that sharpen that job are welcome; format conversion, device
sync and anything else Calibre does are out of scope by design (see
`docs/ROADMAP.md`).

## Setup

Everything goes through [uv](https://docs.astral.sh/uv/) and the local
`.venv` — never the system Python, never bare `pip`.

```bash
uv sync                      # editable install with dev extras
uv run pytest                # tests
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run mypy src/             # types (strict)
```

CI runs exactly those four on Linux (3.10–3.14), macOS and Windows.
Dependencies change only via `uv add` / `uv remove`; adding a *runtime*
dependency needs a discussion first — the footprint is one package
(`pypdf`) and meant to stay that way.

## How changes to identification, matching and grouping work

`docs/IDENTIFICATION.md` is the specification for how a file becomes a
book. It is written from decisions, not from the code, so it says what
bookman *should* do. The order for any change to that behavior is:

1. **Spec first.** Amend the step in `docs/IDENTIFICATION.md` and record
   why in an ADR in `docs/ARCHITECTURE.md`.
2. **Then the code**, with a test that pins the step.
3. **Then the conformance row** in `docs/FEATURES.md` Part I.

A behavior change that leaves the spec untouched is a bug in one of the
two. Step IDs (`MATCH-0..3`, `IDENT-1..6`, `GROUP-1..4`) are stable —
cite them in commits and tests.

## Bug reports: bring the shape, not just the symptom

Most bugs here are "this file should have matched / grouped / got a
cover". What makes such a report actionable is the *shape* of the file:
what its metadata says, what the copyright page says, what Open Library
returns for its ISBN. `docs/FIELD-NOTES.md` is the register of shapes
seen in real bundles — check whether yours is already there, and if not,
the issue template asks for what an entry needs. Fixes are made for
patterns, not single files, so one more example of a known shape is
valuable too.

For a quick look at what bookman extracted from a file:

```bash
uv run python -c "from bookman.formats.epub import parse_epub; print(parse_epub('book.epub'))"
uv run python -c "from bookman.formats.pdf import parse_pdf; print(parse_pdf('book.pdf'))"
```

## Releases

`CHANGELOG.md` follows Keep a Changelog; the public API is
`bookman.__all__` and follows semantic versioning. A release is a tag:
`git tag v<version> && git push origin v<version>` runs the checks,
builds the wheel and publishes a GitHub Release with it (see
`.github/workflows/release.yml`).
