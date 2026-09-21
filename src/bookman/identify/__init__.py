"""Identification: turn a parsed file into the best-supported description of
its book, and decide whether two descriptions are the same book.

The intended behavior is specified in `docs/IDENTIFICATION.md` -- a flowchart
plus a normative YAML block with stable step IDs (MATCH-0..3, IDENT-1..6,
GROUP-1..4). Functions implementing a step carry a `Spec:` line naming it, so
a rule can be traced from the spec to the code and back without reading the
logic. `tests/test_spec_conformance.py` checks that every step has both.

The spec is the source of truth: change it (with an ADR) before changing
behavior here. Where this package and the spec disagree, the disagreement is
recorded in `docs/FEATURES.md` Part I, not silently reconciled.
"""

from __future__ import annotations

SPEC_VERSION = 5
"""The `spec_version` of `docs/IDENTIFICATION.md` that this package implements.

Bumped only when the *intended* behavior changes -- a step added, removed or
altered -- never when the code changes to conform to a step it already
claimed. Deliberately not re-exported from `bookman`: it is internal
bookkeeping, not part of the public API.
"""

__all__ = ["SPEC_VERSION"]
