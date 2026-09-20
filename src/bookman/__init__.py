"""bookman: local ebook library management.

Identifies, catalogs, and organizes EPUB/PDF/MOBI files by title,
independent of any frontend (a companion TUI consumes this as a library).
"""

from __future__ import annotations

import logging

from bookman.config import (
    Config,
    config_path,
    load_config,
    resolve_library,
    save_config,
)
from bookman.errors import (
    BookmanError,
    CatalogError,
    ConfigError,
    FormatConflictError,
    LibraryNotConfiguredError,
    MetadataSourceError,
    ParseError,
    UnsupportedFormatError,
)
from bookman.formats import supported_suffixes
from bookman.formats.epub import BadEpubError
from bookman.formats.pdf import BadPdfError
from bookman.identify.openlibrary import OpenLibraryError, OpenLibrarySource
from bookman.identify.source import Candidate, MetadataSource, NullSource
from bookman.library import ImportBatchResult, ImportEvent, Library
from bookman.models import Book, BookFormat, FormatKind, MatchBasis

# Library convention: emit under the "bookman" logger and let the
# application decide whether anything is shown.
logging.getLogger("bookman").addHandler(logging.NullHandler())

__all__ = [
    "BadEpubError",
    "BadPdfError",
    "Book",
    "BookFormat",
    "BookmanError",
    "Candidate",
    "CatalogError",
    "Config",
    "ConfigError",
    "FormatConflictError",
    "FormatKind",
    "ImportBatchResult",
    "ImportEvent",
    "Library",
    "LibraryNotConfiguredError",
    "MatchBasis",
    "MetadataSource",
    "MetadataSourceError",
    "NullSource",
    "OpenLibraryError",
    "OpenLibrarySource",
    "ParseError",
    "UnsupportedFormatError",
    "config_path",
    "load_config",
    "resolve_library",
    "save_config",
    "supported_suffixes",
]
