from pptx_a11y.gui import handle_drop
from tests.fixtures.build import deck_with_issues


class _StubDescriber:
    def describe(self, image_bytes, media_type, context):
        return "img"


def test_handle_drop_processes_and_opens_reports(tmp_path):
    a = deck_with_issues(str(tmp_path / "a.pptx"))
    opened = []
    results = handle_drop([a], _StubDescriber(), opener=opened.append)
    assert len(results) == 1
    assert results[0].output_path.endswith("_accessible.pptx")
    assert opened and opened[0].endswith("a_a11y_report.html")


def test_handle_drop_skips_non_pptx(tmp_path):
    txt = tmp_path / "note.txt"
    txt.write_text("hi")
    results = handle_drop([str(txt)], _StubDescriber(), opener=lambda *_: None)
    assert results == []
