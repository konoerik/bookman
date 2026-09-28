"""Persisted user configuration: where the managed library lives, and
whether imports look books up online.

Set once (`bookman init`, or `save_config` from another frontend), then
every consumer opens the library through `configured_library` (or
resolves just the root through `resolve_library`), so the CLI and TUI
agree on the same library and the same metadata source without each
keeping its own settings file.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from bookman.errors import ConfigError, LibraryNotConfiguredError, LibraryNotFoundError
from bookman.identify.source import NullSource
from bookman.library import Library, is_library

ENV_LIBRARY = "BOOKMAN_LIBRARY"
ENV_CONFIG = "BOOKMAN_CONFIG"


@dataclass(frozen=True)
class Config:
    """Persisted settings.

    Attributes:
        library: The managed library's root directory.
        offline: Imports and re-identification never go online: no
            Open Library lookup and no cover download, so every book is
            cataloged from what its file says (FEATURES L9). A new field
            defaults when absent, so to change one setting, save
            `dataclasses.replace(load_config(), <field>=...)` rather
            than a fresh `Config`, which would reset the others.
    """

    library: Path
    offline: bool = False


def config_path() -> Path:
    """Return where bookman's config file lives on this platform.

    `$BOOKMAN_CONFIG`, if set, names the file directly and overrides the
    platform default. Otherwise: `~/Library/Application Support/bookman/`
    on macOS, `%APPDATA%\\bookman\\` on Windows, and
    `$XDG_CONFIG_HOME/bookman/` (default `~/.config/bookman/`) elsewhere,
    each holding a `config.json`.

    Returns:
        Absolute path to the config file. The file may not exist yet.
    """
    override = os.environ.get(ENV_CONFIG)
    if override:
        return Path(override).expanduser()

    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "bookman" / "config.json"


def load_config(path: Path | None = None) -> Config | None:
    """Read the config file.

    Args:
        path: File to read. Defaults to `config_path()`.

    Returns:
        The stored Config, or None if the file doesn't exist (bookman
        has never been set up).

    Raises:
        ValueError: If the file exists but isn't valid JSON or doesn't
            have the expected shape (`{"library": "<path>"}`, plus an
            optional `"offline": true|false`).
    """
    path = path or config_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path}: not valid JSON ({exc.msg})") from exc
    if not isinstance(data, dict) or not isinstance(data.get("library"), str):
        raise ConfigError(f'{path}: expected {{"library": "<path>"}}')
    offline = data.get("offline", False)
    if not isinstance(offline, bool):
        raise ConfigError(f'{path}: expected "offline" to be true or false, got {offline!r}')
    return Config(library=Path(data["library"]), offline=offline)


def save_config(config: Config, path: Path | None = None) -> None:
    """Write the config file, creating parent directories as needed.

    The library path is stored absolute (`~` expanded, symlinks resolved)
    so it means the same thing regardless of the working directory it's
    later read from. The write is atomic (temp file + rename).

    Args:
        config: Settings to persist.
        path: File to write. Defaults to `config_path()`.
    """
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "library": str(config.library.expanduser().resolve()),
        "offline": config.offline,
    }
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


class LibraryOrigin(str, Enum):
    """Where the library root in use was named."""

    EXPLICIT = "explicit"
    """Passed by the caller: a `--library` flag, a folder the user picked."""

    ENVIRONMENT = "environment"
    """The `$BOOKMAN_LIBRARY` environment variable."""

    CONFIG = "config"
    """The saved config file."""


@dataclass(frozen=True)
class LibraryLocation:
    """The library root in use, and where it was named.

    Attributes:
        path: The library root. Not guaranteed to exist.
        origin: Which of the three places named it.
        config_file: The config file that named it, when `origin` is
            CONFIG; otherwise None.
    """

    path: Path
    origin: LibraryOrigin
    config_file: Path | None = None

    def describe(self) -> str:
        """Where the root was named, as a phrase for a person:
        "passed explicitly", "set by $BOOKMAN_LIBRARY" or "saved in
        <config file>"."""
        if self.origin is LibraryOrigin.ENVIRONMENT:
            return f"set by ${ENV_LIBRARY}"
        if self.origin is LibraryOrigin.CONFIG:
            return f"saved in {self.config_file}"
        return "passed explicitly"


def locate_library(explicit: Path | None = None) -> LibraryLocation:
    """Decide which library root to use, and say where it was named.

    Precedence: `explicit` (e.g. a `--library` flag), then the
    `$BOOKMAN_LIBRARY` environment variable, then the config file. A
    frontend showing "which library, and why" reads it from here rather
    than repeating the precedence.

    Args:
        explicit: A caller-supplied root that should win over everything
            else; None to fall through to the environment and config.

    Returns:
        The root and its origin. The root is not guaranteed to exist.

    Raises:
        LibraryNotConfiguredError: If none of the three names a library.
        ConfigError: If it falls through to a config file that exists
            but is malformed (see `load_config`).
    """
    if explicit is not None:
        return LibraryLocation(explicit, LibraryOrigin.EXPLICIT)
    env = os.environ.get(ENV_LIBRARY)
    if env:
        return LibraryLocation(Path(env).expanduser(), LibraryOrigin.ENVIRONMENT)
    path = config_path()
    config = load_config(path)
    if config is None:
        raise LibraryNotConfiguredError(
            f"no library configured: run `bookman init <dir>` or set ${ENV_LIBRARY}"
        )
    return LibraryLocation(config.library, LibraryOrigin.CONFIG, path)


def resolve_library(explicit: Path | None = None) -> Path:
    """Decide which library root to use: `locate_library(explicit).path`.

    Precedence: `explicit` (e.g. a `--library` flag), then the
    `$BOOKMAN_LIBRARY` environment variable, then the config file.

    Args:
        explicit: A caller-supplied root that should win over everything
            else; None to fall through to the environment and config.

    Returns:
        The library root. Not guaranteed to exist.

    Raises:
        LibraryNotConfiguredError: If none of the three sources names a
            library.
        ValueError: If the config file exists but is malformed (see
            `load_config`).
    """
    return locate_library(explicit).path


def configured_library(explicit: Path | None = None, *, create: bool = False) -> Library:
    """Open the library the user configured, with the metadata source
    their settings choose.

    This is the one way a frontend should build its `Library`, so the
    CLI and the TUI use the same root and the same source. The root is
    chosen as `locate_library` does. The source comes from the config
    file, even when the root came from `explicit` or
    `$BOOKMAN_LIBRARY`: `NullSource()` when `offline` is set, else
    Open Library.

    Unless `create` is set, only an existing library is opened (see
    `is_library`), so a saved library on a drive that is not connected
    is reported instead of silently replaced by a new, empty one on the
    internal disk. An existing empty folder counts: it becomes the
    library.

    Args:
        explicit: A caller-supplied root that should win over the
            environment and the config file (e.g. a `--library` flag),
            or None.
        create: Create the library if the root is missing, and adopt
            an existing folder that is not a library yet. For a folder
            the user has just chosen for a new library.

    Returns:
        The opened `Library`, its root marked as a library.

    Raises:
        LibraryNotConfiguredError: If nothing names a library.
        LibraryNotFoundError: If `create` is not set and the root is
            missing or holds other files but no library; or, either
            way, if the root is a file.
        ConfigError: If the config file exists but is malformed.
    """
    location = locate_library(explicit)
    root = location.path
    where = location.describe()
    if root.exists() and not root.is_dir():
        raise LibraryNotFoundError(
            root, f"library path is not a directory: {root} ({where}); choose a folder instead"
        )
    if not create and not root.exists():
        raise LibraryNotFoundError(
            root,
            f"library not found: {root} ({where}) does not exist; if it is on a drive, "
            "connect it and try again, otherwise run `bookman init <dir>` to choose "
            "or create a library",
        )
    if not create and not is_library(root) and not _is_empty(root):
        raise LibraryNotFoundError(
            root,
            f"not a bookman library: {root} ({where}) holds other files; a library "
            "is a folder of its own, so run `bookman init <new dir>` and import "
            "these files into it",
        )
    config = load_config()
    offline = config is not None and config.offline
    # None keeps Library's own default (Open Library) the only one.
    return Library(root, source=NullSource() if offline else None)


def _is_empty(folder: Path) -> bool:
    """No entries but hidden ones (a Finder `.DS_Store`, an old index)."""
    return all(entry.name.startswith(".") for entry in folder.iterdir())
