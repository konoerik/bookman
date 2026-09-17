import json
from pathlib import Path

import pytest

from bookman import config
from bookman.config import (
    Config,
    LibraryNotConfiguredError,
    config_path,
    load_config,
    resolve_library,
    save_config,
)


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch, tmp_path):
    """No test here should see the developer's real config or env."""
    monkeypatch.delenv(config.ENV_CONFIG, raising=False)
    monkeypatch.delenv(config.ENV_LIBRARY, raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


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
