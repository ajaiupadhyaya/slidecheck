from pptx_a11y.alt_text_ai import NullDescriber, ClaudeDescriber


def test_null_describer_returns_none():
    assert NullDescriber().describe(b"x", "image/png", "ctx") is None


def test_claude_describer_returns_text(monkeypatch):
    class _FakeMessages:
        def create(self, **kwargs):
            class R:
                content = [type("B", (), {"text": "A red square."})()]
            return R()

    class _FakeClient:
        def __init__(self, **kwargs):
            self.messages = _FakeMessages()

    import pptx_a11y.alt_text_ai as mod
    monkeypatch.setattr(mod, "Anthropic", _FakeClient)
    d = ClaudeDescriber(api_key="test")
    assert d.describe(b"\x89PNG", "image/png", "slide 1") == "A red square."


def test_claude_describer_handles_api_error(monkeypatch):
    class _Boom:
        def __init__(self, **kwargs):
            raise RuntimeError("no network")

    import pptx_a11y.alt_text_ai as mod
    monkeypatch.setattr(mod, "Anthropic", _Boom)
    d = ClaudeDescriber(api_key="test")
    assert d.describe(b"x", "image/png", "ctx") is None


def test_null_describer_suggest_text_returns_none():
    assert NullDescriber().suggest_text("x") is None


def test_claude_describer_suggest_text_returns_text(monkeypatch):
    class _FakeMessages:
        def create(self, **kwargs):
            class R:
                content = [type("B", (), {"text": "A Good Title"})()]
            return R()

    class _FakeClient:
        def __init__(self, **kwargs):
            self.messages = _FakeMessages()

    import pptx_a11y.alt_text_ai as mod
    monkeypatch.setattr(mod, "Anthropic", _FakeClient)
    assert ClaudeDescriber("k").suggest_text("p") == "A Good Title"
