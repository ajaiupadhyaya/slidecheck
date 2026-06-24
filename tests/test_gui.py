from pptx_a11y.gui import drop_summary, handle_drop
from tests.fixtures.build import clean_deck, deck_with_issues


class _StubDescriber:
    def describe(self, image_bytes, media_type, context):
        return "img"

    def suggest_text(self, prompt):
        return "Stub Title"


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


def test_handle_drop_multiple_opens_batch_index(tmp_path):
    a = deck_with_issues(str(tmp_path / "a.pptx"))
    b = clean_deck(str(tmp_path / "b.pptx"))
    opened = []
    handle_drop([a, b], _StubDescriber(), opener=opened.append)
    assert opened and opened[0].endswith("index.html")
    assert (tmp_path / "index.html").exists()


def test_drop_summary_surfaces_errors(tmp_path):
    bad = tmp_path / "bad.pptx"
    bad.write_bytes(b"nope")
    results = handle_drop([str(bad)], _StubDescriber(), opener=lambda *_: None)
    summary = drop_summary([str(bad)], results)
    assert summary["ok"] == 0
    assert summary["errors"]  # the failed file is reported, not silently dropped


def test_drop_summary_no_pptx_found():
    summary = drop_summary(["/some/note.txt"], [])
    assert summary["pptx"] == 0
    assert "No PowerPoint" in summary["status"]
