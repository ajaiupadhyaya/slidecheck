from pptx_a11y.web.describers import CappedDescriber


class _Counting:
    def __init__(self):
        self.describe_calls = 0
        self.suggest_calls = 0

    def describe(self, image_bytes, media_type, context):
        self.describe_calls += 1
        return f"alt-{self.describe_calls}"

    def suggest_text(self, prompt):
        self.suggest_calls += 1
        return "a title"


def test_caps_image_descriptions():
    inner = _Counting()
    capped = CappedDescriber(inner, max_images=2)
    assert capped.describe(b"x", "image/png", "c") == "alt-1"
    assert capped.describe(b"x", "image/png", "c") == "alt-2"
    assert capped.describe(b"x", "image/png", "c") is None  # over the cap
    assert inner.describe_calls == 2


def test_suggest_text_always_delegates():
    inner = _Counting()
    capped = CappedDescriber(inner, max_images=0)
    assert capped.suggest_text("p") == "a title"
    assert inner.suggest_calls == 1
