from pptx import Presentation
from pptx_a11y.checks.font_size import check
from tests.fixtures.build import deck_with_issues


def test_flags_small_font(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path / "x.pptx")))
    findings = check(prs)
    assert any(f.check_id == "font_size" and f.slide_index == 1 for f in findings)
