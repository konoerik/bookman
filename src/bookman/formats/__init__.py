"""Per-format parsers, sharing a common contract and metadata shape.

Importing this package registers the built-in parsers (EPUB, PDF). A
new format is one module exposing a `FormatParser` plus one `register`
call here.
"""

from __future__ import annotations

from bookman.formats.base import (
    FormatParser,
    ParsedMetadata,
    is_supported,
    parser_for,
    register,
    supported_suffixes,
)
from bookman.formats.epub import parse_epub
from bookman.formats.pdf import parse_pdf
from bookman.models import FormatKind

register(".epub", FormatKind.EPUB, parse_epub)
register(".pdf", FormatKind.PDF, parse_pdf)

__all__ = [
    "FormatParser",
    "ParsedMetadata",
    "is_supported",
    "parser_for",
    "register",
    "supported_suffixes",
]
