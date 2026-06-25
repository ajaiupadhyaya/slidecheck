import io
import os

from pptx import Presentation

from pptx_a11y.alt_text_ai import NullDescriber
from pptx_a11y.web.service import process_uploads
from tests.fixtures.build import clean_deck, deck_with_issues


def _bytes(tmp_path, builder, name="src.pptx"):
    p = builder(str(tmp_path / name))
    with open(p, "rb") as fh:
        return fh.read()


def test_single_upload_returns_report_and_valid_fixed_file(tmp_path):
    data = _bytes(tmp_path, deck_with_issues)
    res = process_uploads([("lecture.pptx", data)], NullDescriber())
    assert len(res.files) == 1
    out = res.files[0]
    assert out.error is None
    assert out.report_html and "<" in out.report_html
    assert out.fixed_filename.endswith("_accessible.pptx")
    assert out.fixed_bytes
    Presentation(io.BytesIO(out.fixed_bytes))  # valid pptx, no exception
    assert out.summary["error"] >= 1  # planted missing-title / alt-text errors


def test_batch_upload_returns_one_output_per_file(tmp_path):
    a = _bytes(tmp_path, clean_deck, "a.pptx")
    b = _bytes(tmp_path, deck_with_issues, "b.pptx")
    res = process_uploads([("a.pptx", a), ("b.pptx", b)], NullDescriber())
    assert [o.filename for o in res.files] == ["a.pptx", "b.pptx"]
    assert all(o.error is None for o in res.files)


def test_corrupt_upload_surfaces_error(tmp_path):
    res = process_uploads([("broken.pptx", b"definitely not a pptx")], NullDescriber())
    assert len(res.files) == 1
    assert res.files[0].error
    assert res.files[0].fixed_bytes is None


def test_corrupt_upload_error_hides_temp_path(tmp_path):
    import tempfile

    res = process_uploads([("broken deck.pptx", b"definitely not a pptx")], NullDescriber())
    err = res.files[0].error
    assert err
    assert tempfile.gettempdir() not in err      # no server temp path in the error
    assert "broken deck.pptx" in err              # the user's filename instead


def test_processing_leaves_no_files_in_cwd(tmp_path, monkeypatch):
    data = _bytes(tmp_path, clean_deck, "kept.pptx")
    monkeypatch.chdir(tmp_path)
    process_uploads([("d.pptx", data)], NullDescriber())
    leftover = sorted(n for n in os.listdir(tmp_path) if n.endswith((".pptx", ".html", ".json")))
    assert leftover == ["kept.pptx"]  # only the fixture, no engine artifacts


def test_generic_engine_exception_becomes_file_error(tmp_path, monkeypatch):
    import pptx_a11y.web.service as svc

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(svc, "process_file", boom)
    res = process_uploads([("x.pptx", _bytes(tmp_path, clean_deck))], NullDescriber())
    assert len(res.files) == 1
    assert res.files[0].error == "boom"
    assert res.files[0].fixed_bytes is None


def test_same_named_batch_uploads_do_not_collide(tmp_path):
    clean = _bytes(tmp_path, clean_deck, "clean.pptx")
    issues = _bytes(tmp_path, deck_with_issues, "issues.pptx")
    res = process_uploads([("slides.pptx", clean), ("slides.pptx", issues)], NullDescriber())
    assert len(res.files) == 2
    assert all(o.error is None for o in res.files)
    # distinct content preserved, not overwritten: one clean, one with errors
    assert res.files[0].summary["error"] == 0
    assert res.files[1].summary["error"] >= 1


def test_report_uses_original_filename_not_temp_path(tmp_path):
    import tempfile

    data = _bytes(tmp_path, deck_with_issues)
    res = process_uploads([("My Lecture.pptx", data)], NullDescriber())
    html = res.files[0].report_html
    assert "My Lecture.pptx" in html              # the user's filename appears
    assert tempfile.gettempdir() not in html      # no server temp path leaks
    assert res.files[0].fixed_filename == "My Lecture_accessible.pptx"
