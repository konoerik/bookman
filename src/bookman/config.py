"""Persisted user configuration: where the managed library lives.

Set once (`bookman init`, or `save_config` from another frontend), then
every consumer resolves the library root through `resolve_library`, so
the CLI and TUI agree on the same library without each keeping its own
settings file.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from bookman.errors import ConfigError, LibraryNotConfiguredError

ENV_LIBRARY = "BOOKMAN_LIBRARY"
ENV_CONFIG = "BOOKMAN_CONFIG"


@dataclass(frozen=True)
class Config:
    """Persisted settings. `library` is the managed library's root directory."""

    library: Path


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
            have the expected shape (`{"library": "<path>"}`).
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
    return Config(library=Path(data["library"]))


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
    payload = {"library": str(config.library.expanduser().resolve())}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def resolve_library(explicit: Path | None = None) -> Path:
    """Decide which library root to use.

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
    if explicit is not None:
        return explicit
    env = os.environ.get(ENV_LIBRARY)
    if env:
        return Path(env).expanduser()
    config = load_config()
    if config is None:
        raise LibraryNotConfiguredError(
            f"no library configured: run `bookman init <dir>` or set ${ENV_LIBRARY}"
        )
    return config.library
