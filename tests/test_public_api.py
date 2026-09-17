"""The package's public surface: what a frontend may import from `bookman`.

`bookman.__init__` is the contract (CLAUDE.md: "Public API lives in
`src/bookman/__init__.py`; keep the public surface minimal"). These tests
pin the names a frontend reaches for, so adding or dropping one is a
deliberate, semver-visible act rather than an accident.
"""

import bookman
from bookman import library


def test_every_exported_name_resolves():
    missing = [name for name in bookman.__all__ if not hasattr(bookman, name)]
    assert not missing


def test_all_is_sorted_and_free_of_duplicates():
    assert bookman.__all__ == sorted(bookman.__all__)
    assert len(bookman.__all__) == len(set(bookman.__all__))


def test_batch_result_is_exported_from_the_package_root():
    """A frontend reporting an import run shouldn't have to reach into
    `bookman.library` for the type `import_directory` hands back."""
    assert "ImportBatchResult" in bookman.__all__
    assert bookman.ImportBatchResult is library.ImportBatchResult
