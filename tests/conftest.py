import pytest
from helpers import FakeSource

from bookman.library import Library


@pytest.fixture
def source():
    """A scriptable metadata source that starts out knowing nothing."""
    return FakeSource()


@pytest.fixture
def library(tmp_path, source):
    """A fresh Library under tmp_path wired to the `source` fixture, so a
    test never touches the network and can script lookups by mutating
    `source`."""
    return Library(tmp_path / "Library", source=source)
