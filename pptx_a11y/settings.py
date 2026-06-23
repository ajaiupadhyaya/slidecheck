import json
import os

from pptx_a11y.alt_text_ai import ClaudeDescriber, NullDescriber


def _default_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    return os.path.join(base, "SlideCheck", "settings.json")


def load_settings(path: str | None = None) -> dict:
    path = path or _default_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def save_api_key(key: str, path: str | None = None) -> None:
    path = path or _default_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = load_settings(path)
    data["api_key"] = key
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def get_describer(settings: dict):
    key = (settings.get("api_key") or "").strip()
    return ClaudeDescriber(key) if key else NullDescriber()
