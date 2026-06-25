"""Tests for pptx_a11y.web.analyze_service — TDD RED phase first."""
from __future__ import annotations

import io

import pytest
from pptx import Presentation

from pptx_a11y.alt_text_ai import NullDescriber
from pptx_a11y.web.analyze_service import analyze_upload
from tests.fixtures.build import deck_with_issues, clean_deck


def _bytes(tmp_path, builder, name="src.pptx"):
    p = builder(str(tmp_path / name))
    with open(p, "rb") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Happy path: valid deck
# ---------------------------------------------------------------------------

def test_analyze_upload_returns_analysis_dict(tmp_path):
    data = _bytes(tmp_path, deck_with_issues)
    result = analyze_upload("lecture.pptx", data, NullDescriber())
    assert result["filename"] == "lecture.pptx"
    assert result["error"] is None
    assert result["analysis"] is not None


def test_analyze_upload_analysis_has_required_keys(tmp_path):
    data = _bytes(tmp_path, deck_with_issues)
    result = analyze_upload("lecture.pptx", data, NullDescriber())
    analysis = result["analysis"]
    assert "findings" in analysis
    assert "score" in analysis
    assert "coverage" in analysis


def test_analyze_upload_findings_is_nonempty_for_deck_with_issues(tmp_path):
    data = _bytes(tmp_path, deck_with_issues)
    result = analyze_upload("lecture.pptx", data, NullDescriber())
    assert len(result["analysis"]["findings"]) > 0


def test_analyze_upload_alt_text_finding_has_thumbnail(tmp_path):
    """The alt_text finding for the picture in deck_with_issues must carry a
    base64 PNG thumbnail."""
    data = _bytes(tmp_path, deck_with_issues)
    result = analyze_upload("lecture.pptx", data, NullDescriber())
    findings = result["analysis"]["findings"]
    alt_text_findings = [f for f in findings if f.get("fix_action") == "set_alt_text"]
    assert alt_text_findings, "expected at least one set_alt_text finding"
    pic_finding = alt_text_findings[0]
    assert "thumbnail" in pic_finding, "thumbnail key must be present on picture finding"
    assert pic_finding["thumbnail"].startswith("data:image/png;base64,"), \
        f"thumbnail must be a PNG data URI, got: {pic_finding['thumbnail'][:50]}"


def test_analyze_upload_thumbnail_is_valid_image(tmp_path):
    """The thumbnail must decode to a valid PIL image no larger than 160x160."""
    import base64
    from PIL import Image

    data = _bytes(tmp_path, deck_with_issues)
    result = analyze_upload("lecture.pptx", data, NullDescriber())
    findings = result["analysis"]["findings"]
    pic_finding = next(f for f in findings if f.get("fix_action") == "set_alt_text")
    b64_data = pic_finding["thumbnail"].split(",", 1)[1]
    raw = base64.b64decode(b64_data)
    img = Image.open(io.BytesIO(raw))
    assert img.width <= 160
    assert img.height <= 160


def test_analyze_upload_clean_deck_returns_no_error(tmp_path):
    data = _bytes(tmp_path, clean_deck)
    result = analyze_upload("clean.pptx", data, NullDescriber())
    assert result["error"] is None
    assert result["analysis"] is not None


# ---------------------------------------------------------------------------
# Error path: corrupt bytes
# ---------------------------------------------------------------------------

def test_analyze_upload_corrupt_bytes_returns_error(tmp_path):
    result = analyze_upload("broken.pptx", b"this is not a pptx", NullDescriber())
    assert result["filename"] == "broken.pptx"
    assert result["error"] is not None
    assert result["analysis"] is None


def test_analyze_upload_corrupt_bytes_error_hides_temp_path(tmp_path):
    """The error message must not leak the server's temporary directory path."""
    import tempfile

    result = analyze_upload("my lecture.pptx", b"not a pptx", NullDescriber())
    err = result["error"]
    assert err, "error must be non-empty"
    assert tempfile.gettempdir() not in err, "temp dir must not appear in error"


def test_analyze_upload_leaves_no_files_in_cwd(tmp_path, monkeypatch):
    """Nothing may persist after analyze_upload returns."""
    import os

    monkeypatch.chdir(tmp_path)
    data = _bytes(tmp_path, clean_deck, "keep.pptx")
    analyze_upload("keep.pptx", data, NullDescriber())
    leftover = [n for n in os.listdir(tmp_path) if n.endswith((".pptx", ".html"))]
    assert leftover == ["keep.pptx"]  # only the fixture


def test_analyze_upload_findings_have_expected_shape(tmp_path):
    """Each finding dict must have all standard keys from finding_to_dict."""
    data = _bytes(tmp_path, deck_with_issues)
    result = analyze_upload("lecture.pptx", data, NullDescriber())
    for f in result["analysis"]["findings"]:
        assert "check_id" in f
        assert "severity" in f
        assert "slide_index" in f
        assert "fix_action" in f
        assert "target" in f
