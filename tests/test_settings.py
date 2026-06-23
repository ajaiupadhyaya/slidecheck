from pptx_a11y.settings import load_settings, save_api_key, get_describer
from pptx_a11y.alt_text_ai import NullDescriber, ClaudeDescriber


def test_save_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "settings.json")
    save_api_key("sk-test", p)
    assert load_settings(p)["api_key"] == "sk-test"


def test_missing_settings_returns_empty(tmp_path):
    assert load_settings(str(tmp_path / "none.json")) == {}


def test_get_describer_picks_implementation():
    assert isinstance(get_describer({}), NullDescriber)
    assert isinstance(get_describer({"api_key": "sk-x"}), ClaudeDescriber)
