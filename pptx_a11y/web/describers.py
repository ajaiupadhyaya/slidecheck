"""Describer wrappers used only by the web front end."""


class CappedDescriber:
    """Delegate to ``inner`` for the first ``max_images`` image descriptions,
    then return None so further images are flagged rather than auto-described.

    This keeps a single web request bounded in wall-clock time on serverless
    hosts. ``suggest_text`` (slide titles) is always delegated because it is
    cheap and not the timeout risk.
    """

    def __init__(self, inner, max_images: int):
        self._inner = inner
        self._max = max_images
        self._used = 0

    def describe(self, image_bytes: bytes, media_type: str, context: str) -> str | None:
        if self._used >= self._max:
            return None
        self._used += 1
        return self._inner.describe(image_bytes, media_type, context)

    def suggest_text(self, prompt: str) -> str | None:
        return self._inner.suggest_text(prompt)
