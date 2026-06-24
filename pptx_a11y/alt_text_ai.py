import base64
from typing import Protocol

from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"
_PROMPT = (
    "Write concise alternative text (one sentence, under 125 characters) describing "
    "this image for a screen-reader user. Describe content and purpose; do not start "
    "with 'image of'. Context: {context}"
)


class Describer(Protocol):
    def describe(self, image_bytes: bytes, media_type: str, context: str) -> str | None: ...
    def suggest_text(self, prompt: str) -> str | None: ...


class NullDescriber:
    def describe(self, image_bytes: bytes, media_type: str, context: str) -> str | None:
        return None

    def suggest_text(self, prompt: str) -> str | None:
        return None


class ClaudeDescriber:
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                self._client = Anthropic(api_key=self._api_key)
            except Exception:  # noqa: BLE001 - degrade to flag-only on any client error
                return None
        return self._client

    def describe(self, image_bytes: bytes, media_type: str, context: str) -> str | None:
        try:
            client = self._get_client()
            if client is None:
                return None
            b64 = base64.standard_b64encode(image_bytes).decode("ascii")
            resp = client.messages.create(
                model=MODEL,
                max_tokens=120,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                            {"type": "text", "text": _PROMPT.format(context=context)},
                        ],
                    }
                ],
            )
            text = resp.content[0].text.strip()
            return text or None
        except Exception:  # noqa: BLE001 - any failure degrades to flag-only
            return None

    def suggest_text(self, prompt: str) -> str | None:
        try:
            client = self._get_client()
            if client is None:
                return None
            resp = client.messages.create(
                model=MODEL,
                max_tokens=40,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            return text or None
        except Exception:  # noqa: BLE001 - any failure degrades to no suggestion
            return None
