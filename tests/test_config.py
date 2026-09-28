import json
from pathlib import Path

import pytest

from bookman import config
from bookman.config import (
    Config,
    LibraryLocation,
    LibraryNotConfiguredError,
    LibraryOrigin,
    config_path,
    configured_library,
    load_config,
    locate_library,
    resolve_library,
    save_config,
)
from bookman.errors import LibraryNotFoundError
from bookman.identify.source import NullSource
from bookman.library import MARKER_NAME, Library


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch, tmp_path):
    """No test here should see the developer's real config or env."""
    monkeypatch.delenv(config.ENV_CONFIG, raising=False)
    monkeypatch.delenv(config.ENV_LIBRARY, raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    # `Path.home()` and `expanduser` read HOME on POSIX but USERPROFILE on
    # Windows (HOME is ignored there since Python 3.8), so fake both.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))


def test_config_path_on_macos(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.platform", "darwin")

    assert config_path() == tmp_path / "home/Library/Application Support/bookman/config.json"


def test_config_path_on_linux_defaults_to_dot_config(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.platform", "linux")

    assert config_path() == tmp_path / "home/.config/bookman/config.json"


def test_config_path_on_linux_honors_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert config_path() == tmp_path / "xdg/bookman/config.json"


def test_config_path_on_windows_uses_appdata(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))

    assert config_path() == tmp_path / "AppData/bookman/config.json"


def test_config_path_env_override_wins_on_every_platform(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setenv(config.ENV_CONFIG, str(tmp_path / "custom.json"))

    assert config_path() == tmp_path / "custom.json"


def test_load_config_returns_none_when_file_is_missing(tmp_path):
    assert load_config(tmp_path / "nope.json") is None


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "deep" / "config.json"
    library = tmp_path / "Books"

    save_config(Config(library=library), path)

    assert load_config(path) == Config(library=library.resolve())
    assert not path.with_name("config.json.tmp").exists()


def test_save_config_stores_an_absolute_expanded_path(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    (tmp_path / "home").mkdir()

    save_config(Config(library=Path("~/Books")), path)

    stored = json.loads(path.read_text())["library"]
    assert Path(stored).is_absolute()
    assert stored == str((tmp_path / "home" / "Books").resolve())


def test_load_config_rejects_invalid_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json")

    with pytest.raises(ValueError, match="not valid JSON"):
        load_config(path)


@pytest.mark.parametrize("payload", ["[]", "{}", '{"library": 3}', '{"root": "/x"}'])
def test_load_config_rejects_wrong_shape(tmp_path, payload):
    path = tmp_path / "config.json"
    path.write_text(payload)

    with pytest.raises(ValueError, match="expected"):
        load_config(path)


def test_offline_round_trips(tmp_path):
    path = tmp_path / "config.json"

    save_config(Config(library=tmp_path / "Books", offline=True), path)

    assert load_config(path) == Config(library=(tmp_path / "Books").resolve(), offline=True)
    assert json.loads(path.read_text())["offline"] is True


def test_a_config_without_offline_loads_as_online(tmp_path):
    """A config written before the setting existed keeps working."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"library": str(tmp_path / "Books")}))

    assert load_config(path) == Config(library=tmp_path / "Books", offline=False)


@pytest.mark.parametrize("value", ['"yes"', "1", "null"])
def test_load_config_rejects_a_non_boolean_offline(tmp_path, value):
    path = tmp_path / "config.json"
    path.write_text(f'{{"library": "/x", "offline": {value}}}')

    with pytest.raises(ValueError, match='"offline" to be true or false'):
        load_config(path)


class _DefaultSource(NullSource):
    """Stands in for Library's default source, so no test goes online."""


@pytest.fixture
def default_source(monkeypatch):
    monkeypatch.setattr("bookman.library.OpenLibrarySource", _DefaultSource)


def test_configured_library_opens_the_saved_library_online(monkeypatch, tmp_path, default_source):
    monkeypatch.setenv(config.ENV_CONFIG, str(tmp_path / "config.json"))
    save_config(Config(library=tmp_path / "Books"))
    (tmp_path / "Books").mkdir()

    library = configured_library()

    assert library.root == (tmp_path / "Books").resolve()
    assert type(library._source) is _DefaultSource


def test_configured_library_is_offline_when_the_config_says_so(
    monkeypatch, tmp_path, default_source
):
    monkeypatch.setenv(config.ENV_CONFIG, str(tmp_path / "config.json"))
    save_config(Config(library=tmp_path / "Books", offline=True))
    (tmp_path / "Books").mkdir()

    assert type(configured_library()._source) is NullSource


def test_configured_library_takes_the_source_from_the_config_even_with_an_explicit_root(
    monkeypatch, tmp_path, default_source
):
    monkeypatch.setenv(config.ENV_CONFIG, str(tmp_path / "config.json"))
    save_config(Config(library=tmp_path / "Books", offline=True))

    library = configured_library(tmp_path / "Other", create=True)

    assert library.root == tmp_path / "Other"
    assert type(library._source) is NullSource


def test_configured_library_with_no_config_file_is_online(monkeypatch, tmp_path, default_source):
    monkeypatch.setenv(config.ENV_CONFIG, str(tmp_path / "config.json"))
    monkeypatch.setenv(config.ENV_LIBRARY, str(tmp_path / "FromEnv"))
    (tmp_path / "FromEnv").mkdir()

    library = configured_library()

    assert library.root == tmp_path / "FromEnv"
    assert type(library._source) is _DefaultSource


def test_configured_library_raises_when_nothing_is_configured(monkeypatch, tmp_path):
    monkeypatch.setenv(config.ENV_CONFIG, str(tmp_path / "config.json"))

    with pytest.raises(LibraryNotConfiguredError):
        configured_library()


def test_resolve_library_prefers_explicit_over_env_and_file(monkeypatch, tmp_path):
    monkeypatch.setenv(config.ENV_CONFIG, str(tmp_path / "config.json"))
    save_config(Config(library=tmp_path / "from-file"))
    monkeypatch.setenv(config.ENV_LIBRARY, str(tmp_path / "from-env"))

    assert resolve_library(tmp_path / "explicit") == tmp_path / "explicit"


def test_resolve_library_prefers_env_over_file(monkeypatch, tmp_path):
    monkeypatch.setenv(config.ENV_CONFIG, str(tmp_path / "config.json"))
    save_config(Config(library=tmp_path / "from-file"))
    monkeypatch.setenv(config.ENV_LIBRARY, "~/from-env")

    assert resolve_library() == tmp_path / "home" / "from-env"


def test_resolve_library_falls_back_to_file(monkeypatch, tmp_path):
    monkeypatch.setenv(config.ENV_CONFIG, str(tmp_path / "config.json"))
    save_config(Config(library=tmp_path / "from-file"))

    assert resolve_library() == (tmp_path / "from-file").resolve()


def test_resolve_library_raises_when_nothing_is_configured(monkeypatch, tmp_path):
    monkeypatch.setenv(config.ENV_CONFIG, str(tmp_path / "config.json"))

    with pytest.raises(LibraryNotConfiguredError, match="bookman init"):
        resolve_library()


def test_resolve_library_propagates_malformed_file(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{}")
    monkeypatch.setenv(config.ENV_CONFIG, str(path))

    with pytest.raises(ValueError):
        resolve_library()


def test_locate_library_says_the_root_was_passed_explicitly(monkeypatch, tmp_path):
    monkeypatch.setenv(config.ENV_LIBRARY, str(tmp_path / "from-env"))

    location = locate_library(tmp_path / "explicit")

    assert location == LibraryLocation(tmp_path / "explicit", LibraryOrigin.EXPLICIT)
    assert location.describe() == "passed explicitly"


def test_locate_library_says_the_root_came_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv(config.ENV_LIBRARY, str(tmp_path / "from-env"))

    location = locate_library()

    assert location == LibraryLocation(tmp_path / "from-env", LibraryOrigin.ENVIRONMENT)
    assert location.describe() == "set by $BOOKMAN_LIBRARY"


def test_locate_library_names_the_config_file_the_root_came_from(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    monkeypatch.setenv(config.ENV_CONFIG, str(path))
    save_config(Config(library=tmp_path / "Books"))

    location = locate_library()

    assert location == LibraryLocation((tmp_path / "Books").resolve(), LibraryOrigin.CONFIG, path)
    assert location.describe() == f"saved in {path}"


@pytest.fixture
def saved_root(monkeypatch, tmp_path, default_source):
    """A config file naming tmp_path/Books, which does not exist yet."""
    monkeypatch.setenv(config.ENV_CONFIG, str(tmp_path / "config.json"))
    save_config(Config(library=tmp_path / "Books"))
    return (tmp_path / "Books").resolve()


def test_configured_library_does_not_create_a_missing_saved_library(saved_root, tmp_path):
    """A library on an unplugged drive is reported, not replaced by an
    empty one on the internal disk."""
    with pytest.raises(LibraryNotFoundError, match="connect it") as info:
        configured_library()

    assert info.value.path == saved_root
    assert f"saved in {tmp_path / 'config.json'}" in str(info.value)
    assert not saved_root.exists()


def test_configured_library_refuses_a_folder_of_other_files(saved_root):
    saved_root.mkdir()
    (saved_root / "Deep Work.epub").write_bytes(b"x")

    with pytest.raises(LibraryNotFoundError, match="not a bookman library"):
        configured_library()

    assert not (saved_root / MARKER_NAME).exists()


def test_configured_library_adopts_an_empty_folder(saved_root):
    saved_root.mkdir()
    (saved_root / ".DS_Store").write_bytes(b"x")

    configured_library()

    assert (saved_root / MARKER_NAME).is_file()


def test_configured_library_opens_a_library_from_before_the_marker(saved_root, tmp_path):
    Library(saved_root)
    (saved_root / MARKER_NAME).unlink()
    (saved_root / "Deep Work").mkdir()
    (saved_root / "Deep Work" / "metadata.json").write_text("{}")

    configured_library()

    assert (saved_root / MARKER_NAME).is_file()


def test_configured_library_with_create_makes_a_missing_library(saved_root):
    library = configured_library(create=True)

    assert library.root == saved_root
    assert (saved_root / MARKER_NAME).is_file()


def test_configured_library_refuses_a_file_even_with_create(saved_root):
    saved_root.write_text("x")

    with pytest.raises(LibraryNotFoundError, match="not a directory"):
        configured_library(create=True)
