"""The suffix registry: what a Library will import and how a new format
plugs in."""

from pathlib import Path

import pytest

from bookman import supported_suffixes
from bookman.errors import UnsupportedFormatError
from bookman.formats import FormatParser, ParsedMetadata, is_supported, parser_for, register
from bookman.formats.base import _REGISTRY
from bookman.formats.epub import parse_epub
from bookman.formats.pdf import parse_pdf
from bookman.models import FormatKind


def test_built_in_parsers_are_registered_on_import():
    assert supported_suffixes() == (".epub", ".pdf")
    assert parser_for(Path("x.epub")) == (FormatKind.EPUB, parse_epub)
    assert parser_for(Path("x.pdf")) == (FormatKind.PDF, parse_pdf)


def test_suffix_lookup_is_case_insensitive():
    assert is_supported(Path("BOOK.EPUB"))
    assert parser_for(Path("BOOK.Pdf"))[0] == FormatKind.PDF


def test_unregistered_suffix_is_unsupported():
    assert not is_supported(Path("book.mobi"))
    with pytest.raises(UnsupportedFormatError, match=r"\.mobi"):
        parser_for(Path("book.mobi"))


def test_a_new_format_is_one_register_call(monkeypatch):
    monkeypatch.setattr("bookman.formats.base._REGISTRY", dict(_REGISTRY))

    def parse_mobi(path: Path) -> ParsedMetadata:
        return ParsedMetadata(title="from mobi", author=None)

    parser: FormatParser = parse_mobi  # a plain function satisfies the Protocol
    register(".MOBI", FormatKind.MOBI, parser)

    assert ".mobi" in supported_suffixes()
    kind, found = parser_for(Path("book.mobi"))
    assert kind == FormatKind.MOBI
    assert found(Path("book.mobi")).title == "from mobi"
