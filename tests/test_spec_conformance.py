"""Check the code against `docs/IDENTIFICATION.md`.

Two things are enforced here:

1. Every step ID the spec defines is claimed by code in `src/` and pinned
   by at least one test-backed row of `docs/FEATURES.md` Part I. A step
   with neither is a gap; this is what stops the spec quietly drifting
   out of the code. The FEATURES `Step` column is the step-to-test index,
   so it stays load-bearing rather than decorative.
2. Every row of the spec's decision table is what `match_basis` actually
   returns, so the table is executable spec rather than prose.

A failure here is not automatically a code bug. The spec is the source of
truth (ADR-2 workflow: spec first, then code, then the `docs/FEATURES.md`
row), so a mismatch means one of the two is wrong -- decide which before
changing either.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from bookman.identify import SPEC_VERSION
from bookman.identify.match import match_basis
from bookman.models import MatchBasis

_ROOT = Path(__file__).resolve().parent.parent
_SPEC = _ROOT / "docs" / "IDENTIFICATION.md"
_STEP = re.compile(r"\b(?:MATCH|IDENT|GROUP)-\d\b")


def _spec_text() -> str:
    return _SPEC.read_text(encoding="utf-8")


def _sources(folder: str) -> str:
    """Every .py file under `folder`, concatenated. This test file is
    excluded so it can't satisfy the trace requirement by itself."""
    return "\n".join(
        f.read_text(encoding="utf-8")
        for f in sorted((_ROOT / folder).rglob("*.py"))
        if f.resolve() != Path(__file__).resolve()
    )


def _expand(cell: str) -> set[str]:
    """The steps a FEATURES Step cell cites: "IDENT-1..3" is three steps,
    "MATCH-0,3" is two, "GROUP-4 (OQ1)" is one."""
    steps: set[str] = set()
    for token in re.findall(r"(?:MATCH|IDENT|GROUP)-\d(?:\.\.\d)?(?:,\d)*", cell):
        family, first = token.split("-")[0], int(token[token.index("-") + 1])
        if ".." in token:
            steps |= {f"{family}-{n}" for n in range(first, int(token[-1]) + 1)}
        else:
            steps |= {f"{family}-{first}"}
            steps |= {f"{family}-{n}" for n in re.findall(r",(\d)", token)}
    return steps


def _pinned_steps() -> set[str]:
    """Steps cited by a FEATURES Part I row that a test actually pins."""
    pinned: set[str] = set()
    features = (_ROOT / "docs" / "FEATURES.md").read_text(encoding="utf-8")
    for line in features.splitlines():
        if not re.match(r"^\| [A-F]\d+ \|", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        step_cell, status = cells[1], cells[4]
        if "\u2705" in status:  # tested
            pinned |= _expand(step_cell)
    return pinned


def test_spec_version_matches_the_document() -> None:
    declared = re.search(r"^spec_version: (\d+)$", _spec_text(), re.M)
    assert declared is not None, "the spec's YAML block must declare spec_version"
    assert int(declared.group(1)) == SPEC_VERSION


def _defined_steps() -> list[str]:
    steps = sorted(set(_STEP.findall(_spec_text())))
    assert steps, "no step IDs found in the spec"
    return steps


@pytest.mark.parametrize("step", _defined_steps())
def test_every_step_is_implemented(step: str) -> None:
    """Each spec step names the code that carries it out. Read the module
    docstring before 'fixing' a failure by sprinkling the ID around -- the
    point is that the annotation is true."""
    assert step in _sources("src"), f"{step} is specified but nothing in src/ claims it"


@pytest.mark.parametrize("step", _defined_steps())
def test_every_step_is_pinned_by_a_feature_row(step: str) -> None:
    """Each spec step is exercised by at least one FEATURES Part I row
    that a test pins. A failure means the step is specified and coded but
    nothing holds it in place -- add the row, or the test the row wants."""
    assert step in _pinned_steps(), (
        f"{step} has no tested (\u2705) row in docs/FEATURES.md Part I citing it"
    )


# --- the decision table -------------------------------------------------

_BASES = {
    "ISBN": MatchBasis.ISBN,
    "TITLE_AUTHOR": MatchBasis.TITLE_AUTHOR,
    "TITLE_ONLY": MatchBasis.TITLE_ONLY,
    "none": None,
}


def _cell(text: str) -> str | None:
    text = text.strip()
    return None if text in {"", "—"} else text


def _decision_table() -> list[tuple[str, ...]]:
    rows = []
    for line in _spec_text().splitlines():
        if not re.match(r"^\| \d+ \|", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert len(cells) == 9, f"decision-table row {cells[0]} has {len(cells)} cells, want 9"
        rows.append(tuple(cells))
    assert rows, "no decision-table rows found in the spec"
    return rows


@pytest.mark.parametrize("row", _decision_table(), ids=lambda r: f"row{r[0]}-{r[1]}")
def test_decision_table_row(row: tuple[str, ...]) -> None:
    """MATCH-1, MATCH-2 and MATCH-3, exactly as the spec's table states
    them. MATCH-0 runs underneath every row via `normalize_title`."""
    _, step, f_title, f_author, c_title, c_author, isbn, basis, why = row
    shared_isbn = _cell(isbn)
    assert shared_isbn in {None, "asserted", "scraped"}, shared_isbn
    assert basis in _BASES, f"unknown basis {basis!r}"

    got = match_basis(
        _cell(f_title),
        _cell(f_author),
        _cell(c_title),
        _cell(c_author),
        same_isbn=shared_isbn is not None,
        isbn_scraped=shared_isbn == "scraped",
    )
    assert got == _BASES[basis], (
        f"{step} row: {why}\n"
        f"  file={_cell(f_title)!r} by {_cell(f_author)!r}\n"
        f"  cand={_cell(c_title)!r} by {_cell(c_author)!r}, isbn={shared_isbn}\n"
        f"  spec says {basis}, match_basis returned {got}"
    )
