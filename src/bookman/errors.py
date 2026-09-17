"""Every exception bookman raises on purpose, under one base class.

A frontend can catch `BookmanError` to mean "bookman refused or failed
in a way it anticipated" and let anything else (OSError, a bug)
propagate. The subclasses that also inherit `ValueError` do so for
compatibility with code that already catches `ValueError` around the
same calls; the bookman type is the one to catch going forward.

Format-specific parse errors (`BadEpubError`, `BadPdfError`) live with
their parsers and subclass `ParseError`; the Open Library client's
`OpenLibraryError` subclasses `MetadataSourceError`.
"""

from __future__ import annotations


class BookmanError(Exception):
    """Base class for every exception bookman raises deliberately."""


class ParseError(BookmanError, ValueError):
    """A file could not be read as the format its suffix claims."""


class UnsupportedFormatError(BookmanError, ValueError):
    """A file's suffix has no registered format parser."""


class MetadataSourceError(BookmanError):
    """A metadata source could not answer: network failure, non-2xx
    response, or a response it could not parse. `identify` treats it as
    "no record"; it never escapes `Library`."""


class CatalogError(BookmanError, ValueError):
    """A book's metadata.json is unreadable, inconsistent, or unsafe
    (invalid JSON, a missing field, an unknown enum value or schema
    version, a filename that escapes the book's folder), or a Book was
    asked to be saved somewhere it cannot go."""


class ConfigError(BookmanError, ValueError):
    """The user config file exists but is not valid."""


class LibraryNotConfiguredError(BookmanError):
    """No library root can be resolved from any source."""


__all__ = [
    "BookmanError",
    "CatalogError",
    "ConfigError",
    "LibraryNotConfiguredError",
    "MetadataSourceError",
    "ParseError",
    "UnsupportedFormatError",
]
