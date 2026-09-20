# CLAUDE.md

## Project Overview
A local ebook library manager: given a folder of purchased ebook files (typically
EPUB/PDF/MOBI bundles from sites like Humble Bundle), identify each book, fetch
metadata/cover art, and organize files into a flat, title-named library directory —
grouping multiple format files under one logical book. Built as a standalone library
so a separate TUI project can consume it as a frontend. Explicitly out of scope:
format conversion, device sync, news/RSS (the parts of Calibre this project exists
to avoid).

## Tech Stack
- **Language:** Python 3.10+
- **Package manager:** uv (see Operating Rules)
- **Testing:** pytest
- **Distribution:** PyPI (public library, consumed by a separate TUI project)

## Key Conventions
- Public API lives in `src/bookman/__init__.py`
- Keep public surface minimal — prefer explicit `__all__`
- Semantic versioning: bump patch for fixes, minor for new public API, major for breaking changes
- Type hints required on all public functions; Google-style docstrings (Args/Returns/Raises)

## Development Workflow
```bash
# Install the environment (editable, with dev extras)
uv sync

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov

# Lint, format-check and type-check
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
```

## Operating Rules

### Environment
- Always `uv` with the local `.venv` — never the system Python
- Every command goes through the venv: `uv run pytest`, `uv run mypy ...`
- Dependencies change only via `uv add` / `uv remove` — `pyproject.toml` is the single source of truth; never bare `pip install`

### Debugging
Work this sequence — do not improvise tooling:
1. **Reproduce** — write the failing test first; it becomes the regression test
2. **Read the full traceback** — before forming a hypothesis
3. **Isolate** — narrow with the existing suite and `git diff`/`git log`; bisect if the regression point is unknown
4. **Instrument** — stdlib only: `logging`, `breakpoint()`; remove instrumentation once fixed
5. **Never add a dependency to debug** — existing tools only
6. **Verify** — run `uv run pytest` yourself and confirm a zero exit code; a fix isn't done until the real command passes, not your read of the output

## Behavior Rules
- Never add a runtime dependency without discussion — keep the dependency footprint small
- When making an architectural decision (API shape, dependency policy, compatibility boundary), record it with `/log`
- `docs/IDENTIFICATION.md` is the source of truth for identification, matching and
  grouping. Change the spec **first** (with an ADR), then the code, then the
  `docs/FEATURES.md` Part I row. Code that changes behavior without a spec change is
  a bug in one of the two. The `matching` skill loads the spec on cue
<!-- Add project-specific rules here. Workflow rules (context loading, commits, plan hygiene) live in .claude/claudify.md. -->
