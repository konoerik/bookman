# Conventions

> Reference style — pattern-match against these before writing or editing code.
> Modify to reflect actual project choices.

## Public function

```python
from __future__ import annotations

__all__ = ["parse_records", "RecordError"]


class RecordError(ValueError):
    """Raised when a record cannot be parsed."""


def parse_records(data: list[dict], *, strict: bool = False) -> list[Record]:
    """Parse a list of raw dicts into Record objects.

    Args:
        data: Raw records from the source.
        strict: If True, raise RecordError on the first invalid entry.
                If False, skip invalid entries silently.

    Returns:
        List of validated Record objects.

    Raises:
        RecordError: If strict is True and any entry is invalid.
    """
    results = []
    for entry in data:
        try:
            results.append(Record.from_dict(entry))
        except (KeyError, TypeError) as exc:
            if strict:
                raise RecordError(f"Invalid record: {entry!r}") from exc
    return results
```

## Stub (pre-implementation)

> Write this first for new public functions and pause for review — see `## Behavior Rules` in `.claude/claudify.md`.

```python
def validate_records(data: list[dict], *, strict: bool = False) -> list[Record]:
    """Validate a list of raw dicts against the Record schema.

    Args:
        data: Raw records from the source.
        strict: If True, raise RecordError on the first invalid entry.
                If False, skip invalid entries silently.

    Returns:
        List of validated Record objects.

    Raises:
        RecordError: If strict is True and any entry is invalid.
    """
    raise NotImplementedError


# Test scenarios (names only, no bodies yet):
# test_validate_records_all_valid
# test_validate_records_strict_raises_on_first_invalid
# test_validate_records_lenient_skips_invalid
# test_validate_records_empty_input_returns_empty_list
```

## Class

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Record:
    id: int
    name: str

    @classmethod
    def from_dict(cls, data: dict) -> "Record":
        return cls(id=int(data["id"]), name=str(data["name"]))
```

## Test

```python
import pytest
from mylib import parse_records, RecordError


def test_parse_records_valid():
    data = [{"id": "1", "name": "Alice"}]
    records = parse_records(data)
    assert len(records) == 1
    assert records[0].name == "Alice"


def test_parse_records_strict_raises():
    with pytest.raises(RecordError):
        parse_records([{"bad": "data"}], strict=True)


def test_parse_records_lenient_skips():
    records = parse_records([{"bad": "data"}], strict=False)
    assert records == []
```
