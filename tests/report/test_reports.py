import json
from pptx_a11y.models import FileResult, Finding, Change, Severity
from pptx_a11y.report import json_report, html_report, summary_counts


def _result():
    return FileResult(
        source_path="deck.pptx",
        output_path="deck_accessible.pptx",
        findings=[
            Finding(check_id="alt_text", severity=Severity.ERROR, slide_index=0,
                    message="missing alt", shape_ref="slide0:shape5", auto_fixed=True),
            Finding(check_id="contrast", severity=Severity.WARNING, slide_index=1,
                    message="low contrast", suggestion="use #333333"),
        ],
        changes=[
            Change(fixer_id="alt_text", slide_index=0, description="Added alt text",
                   machine_generated=True),
        ],
    )


def test_json_report_roundtrips():
    data = json.loads(json_report.render(_result()))
    assert data["source_path"] == "deck.pptx"
    assert data["summary"]["error"] == 1
    assert len(data["findings"]) == 2
    assert data["changes"][0]["machine_generated"] is True


def test_html_report_contains_key_content():
    html = html_report.render(_result())
    assert "<html" in html.lower()
    assert "deck.pptx" in html
    assert "review this" in html.lower()       # machine-generated marker
    assert "low contrast" in html
    assert "use #333333" in html


def test_html_escapes_user_text():
    r = _result()
    r.findings[0].message = "bad <script>alert(1)</script>"
    html = html_report.render(r)
    assert "<script>alert(1)</script>" not in html


def test_summary_counts_manual_attention():
    # one ERROR (auto_fixed) + one WARNING (not fixed) -> 1 needs manual fix
    s = summary_counts(_result())
    assert s["manual"] == 1


def test_html_shows_needs_manual_fix_pill():
    html = html_report.render(_result())
    assert "need manual fix" in html.lower()


def test_html_report_has_admin_summary_with_score_and_508():
    html = html_report.render(_result())
    low = html.lower()
    assert "summary for administration" in low
    assert "section 508" in low
    assert "grade" in low  # the letter grade is surfaced for an administrator


def test_html_report_verdict_flags_508_failure():
    r = FileResult(
        source_path="deck.pptx",
        findings=[
            Finding(check_id="alt_text", severity=Severity.ERROR, slide_index=0,
                    message="missing alt", sc_refs=["1.1.1"], section508=True),
        ],
    )
    html = html_report.render(r).lower()
    assert "must be fixed" in html  # plain-English administrator verdict


def test_admin_summary_excludes_autofixed_warnings():
    # A warning that was auto-fixed must NOT be reported as something to review,
    # and must not block the "passed all checks" verdict.
    r = FileResult(
        source_path="deck.pptx",
        findings=[
            Finding(check_id="metadata", severity=Severity.WARNING, slide_index=0,
                    message="no language", sc_refs=["3.1.1"], section508=True, auto_fixed=True),
        ],
    )
    html = html_report.render(r).lower()
    # the admin verdict + open-warning tally exclude the already-fixed warning
    assert "passed all automated accessibility checks" in html
    assert "open warnings: 0" in html


def test_admin_summary_counts_open_508_warning_as_floor_issue():
    # Missing document language (3.1.1) is a Section 508 floor item even though
    # it is WARNING severity — when open it must read as a 508 issue, not "meets
    # the floor".
    r = FileResult(
        source_path="deck.pptx",
        findings=[
            Finding(check_id="metadata", severity=Severity.WARNING, slide_index=0,
                    message="no language", sc_refs=["3.1.1"], section508=True),
        ],
    )
    html = html_report.render(r).lower()
    assert "must be fixed" in html


def test_html_report_has_aria_landmarks():
    html = html_report.render(_result())
    low = html.lower()
    assert "<main" in low
    assert "<nav" in low
    assert "aria-labelledby" in low
    assert "<section" in low
