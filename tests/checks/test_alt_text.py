from pptx_a11y.checks.alt_text import check
from tests.fixtures.build import clean_deck, deck_with_issues
from pptx import Presentation


def test_flags_picture_without_alt_text(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path / "x.pptx")))
    findings = check(prs)
    assert any(f.check_id == "alt_text" and f.slide_index == 0 for f in findings)
    assert findings[0].severity.value == "error"


def test_clean_deck_has_no_alt_text_findings(tmp_path):
    prs = Presentation(clean_deck(str(tmp_path / "ok.pptx")))
    assert check(prs) == []


def test_chart_without_alt_text_gets_manual_hint(tmp_path):
    from pptx.util import Inches
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    data = CategoryChartData()
    data.categories = ["a", "b"]
    data.add_series("s", (1, 2))
    s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(1), Inches(4), Inches(3), data)
    findings = check(prs)
    chart_findings = [f for f in findings if f.check_id == "alt_text"]
    assert len(chart_findings) == 1
    assert "Chart" in chart_findings[0].message
    assert "manually" in chart_findings[0].suggestion.lower()
