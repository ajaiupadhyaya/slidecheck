import os
import sys
import stat

import pytest

from pptx_a11y.settings import load_settings, save_api_key, get_describer
from pptx_a11y.alt_text_ai import NullDescriber, ClaudeDescriber


def test_save_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "settings.json")
    save_api_key("sk-test", p)
    assert load_settings(p)["api_key"] == "sk-test"


def test_missing_settings_returns_empty(tmp_path):
    assert load_settings(str(tmp_path / "none.json")) == {}


def test_get_describer_picks_implementation(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(get_describer({}), NullDescriber)
    assert isinstance(get_describer({"api_key": "sk-x"}), ClaudeDescriber)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits not meaningful on Windows")
def test_saved_settings_file_is_owner_only(tmp_path):
    p = str(tmp_path / "settings.json")
    save_api_key("sk-secret", p)
    mode = stat.S_IMODE(os.stat(p).st_mode)
    assert mode == 0o600


def test_get_describer_uses_env_key_when_settings_empty(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
    d = get_describer({})
    assert isinstance(d, ClaudeDescriber)
    assert d._api_key == "sk-from-env"


def test_settings_key_takes_precedence_over_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
    d = get_describer({"api_key": "sk-from-settings"})
    assert isinstance(d, ClaudeDescriber)
    assert d._api_key == "sk-from-settings"


def test_no_key_anywhere_is_null_describer(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(get_describer({}), NullDescriber)
