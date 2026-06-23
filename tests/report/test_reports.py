import json
from pptx_a11y.models import FileResult, Finding, Change, Severity
from pptx_a11y.report import json_report, html_report


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
